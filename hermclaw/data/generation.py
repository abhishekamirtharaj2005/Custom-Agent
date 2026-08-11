"""Data generation pipeline: batch runner, trajectory compression, SWE benchmark.

Implements all features from Section 25 (Data Generation & Training):
- Batch runner (parallel prompt processing)
- Trajectory compression (for training data)
- SWE benchmark runner
- Toolset probability distributions
"""

from __future__ import annotations

import asyncio
import json
import random
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Batch runner (parallel prompt processing)
# ---------------------------------------------------------------------------


class BatchRunner:
    """Run multiple prompts in parallel for data generation.

    Used to process large sets of prompts for creating training data.
    """

    def __init__(self, concurrency: int = 5, timeout_per_prompt: float = 120.0) -> None:
        self._concurrency = concurrency
        self._timeout = timeout_per_prompt
        self._results: list[dict] = []
        self._errors: list[dict] = []

    async def run(self, prompts: list[str], process_fn: Any) -> list[dict]:
        """Process a batch of prompts with controlled concurrency."""
        sem = asyncio.Semaphore(self._concurrency)
        tasks = []

        async def _process(idx: int, prompt: str) -> dict:
            async with sem:
                start = time.time()
                try:
                    result = await asyncio.wait_for(
                        process_fn(prompt),
                        timeout=self._timeout,
                    )
                    elapsed = time.time() - start
                    return {
                        "index": idx,
                        "prompt": prompt[:200],
                        "result": result,
                        "duration_s": round(elapsed, 2),
                        "status": "success",
                    }
                except asyncio.TimeoutError:
                    return {"index": idx, "prompt": prompt[:200], "status": "timeout", "duration_s": self._timeout}
                except Exception as exc:
                    return {"index": idx, "prompt": prompt[:200], "status": "error", "error": str(exc)[:200]}

        for i, prompt in enumerate(prompts):
            tasks.append(asyncio.create_task(_process(i, prompt)))

        self._results = await asyncio.gather(*tasks)
        self._errors = [r for r in self._results if r["status"] != "success"]

        logger.info("batch.completed",
                    total=len(prompts),
                    success=len(prompts) - len(self._errors),
                    errors=len(self._errors))

        return self._results

    def summary(self) -> dict[str, Any]:
        total = len(self._results)
        success = sum(1 for r in self._results if r["status"] == "success")
        durations = [r.get("duration_s", 0) for r in self._results if r["status"] == "success"]
        return {
            "total": total,
            "success": success,
            "errors": total - success,
            "avg_duration_s": sum(durations) / len(durations) if durations else 0,
            "max_duration_s": max(durations) if durations else 0,
        }

    def save_results(self, output_path: str) -> None:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            for r in self._results:
                f.write(json.dumps(r) + "\n")
        logger.info("batch.saved", path=output_path, count=len(self._results))


# ---------------------------------------------------------------------------
# Trajectory compression (for training data)
# ---------------------------------------------------------------------------


class TrajectoryCompressor:
    """Compress agent trajectories for efficient training data.

    Trajectory: a sequence of (prompt, tool_call, result, response) turns.

    Compression strategies:
    1. Remove redundant tool calls (identical inputs/outputs)
    2. Merge consecutive edits to the same file
    3. Strip verbose tool outputs (keep summary)
    4. Remove failed retries (keep only the success)
    5. Compress system prompts (reference by hash)
    """

    def __init__(self, max_output_chars: int = 500) -> None:
        self._max_output = max_output_chars

    def compress(self, trajectory: list[dict]) -> list[dict]:
        """Compress a full trajectory."""
        compressed = trajectory[:]
        compressed = self._remove_redundant(compressed)
        compressed = self._merge_file_edits(compressed)
        compressed = self._truncate_outputs(compressed)
        compressed = self._remove_failed_retries(compressed)
        compressed = self._deduplicate_system_prompts(compressed)

        ratio = len(compressed) / len(trajectory) if trajectory else 1
        logger.info("trajectory.compressed",
                    original=len(trajectory),
                    compressed=len(compressed),
                    ratio=round(ratio, 2))
        return compressed

    def _remove_redundant(self, traj: list[dict]) -> list[dict]:
        """Remove tool calls with identical inputs that produced identical outputs."""
        seen: set[str] = set()
        result = []
        for step in traj:
            if step.get("type") == "tool_call":
                key = json.dumps({"tool": step.get("tool"), "args": step.get("args")}, sort_keys=True)
                if key in seen:
                    continue
                seen.add(key)
            result.append(step)
        return result

    def _merge_file_edits(self, traj: list[dict]) -> list[dict]:
        """Merge consecutive edits to the same file into one step."""
        result = []
        pending_edits: dict[str, list] = {}

        for step in traj:
            if step.get("tool") in ("file_write", "file_edit") and step.get("args", {}).get("path"):
                path = step["args"]["path"]
                pending_edits.setdefault(path, []).append(step)
            else:
                # Flush pending edits
                for path, edits in pending_edits.items():
                    if len(edits) > 1:
                        # Keep only the last edit (final state)
                        merged = edits[-1].copy()
                        merged["_merged_from"] = len(edits)
                        result.append(merged)
                    else:
                        result.append(edits[0])
                pending_edits.clear()
                result.append(step)

        # Flush remaining
        for edits in pending_edits.values():
            result.append(edits[-1])

        return result

    def _truncate_outputs(self, traj: list[dict]) -> list[dict]:
        """Truncate verbose tool outputs."""
        for step in traj:
            output = step.get("output", "")
            if isinstance(output, str) and len(output) > self._max_output:
                step["output"] = output[:self._max_output] + f"\n[truncated {len(output) - self._max_output} chars]"
        return traj

    def _remove_failed_retries(self, traj: list[dict]) -> list[dict]:
        """Remove failed tool calls that were retried successfully."""
        result = []
        i = 0
        while i < len(traj):
            step = traj[i]
            if step.get("status") == "error" and i + 1 < len(traj):
                next_step = traj[i + 1]
                if (next_step.get("tool") == step.get("tool") and
                    next_step.get("status") == "success"):
                    # Skip the failed attempt
                    i += 1
                    continue
            result.append(step)
            i += 1
        return result

    def _deduplicate_system_prompts(self, traj: list[dict]) -> list[dict]:
        """Replace repeated system prompts with hash references."""
        import hashlib
        prompt_hashes: dict[str, str] = {}

        for step in traj:
            if step.get("role") == "system":
                content = step.get("content", "")
                h = hashlib.md5(content.encode()).hexdigest()[:12]
                if h in prompt_hashes:
                    step["content"] = f"[system_prompt_ref:{h}]"
                else:
                    prompt_hashes[h] = content
        return traj


# ---------------------------------------------------------------------------
# SWE benchmark runner
# ---------------------------------------------------------------------------


class SWEBenchRunner:
    """Runner for SWE-bench style evaluations.

    SWE-bench tests AI ability to solve real-world software engineering tasks.
    """

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        self._output = output_dir or (Path.home() / ".hermclaw" / "swe_bench")
        self._output.mkdir(parents=True, exist_ok=True)

    async def run_instance(self, instance: dict[str, Any], agent_fn: Any) -> dict[str, Any]:
        """Run a single SWE-bench instance."""
        instance_id = instance.get("instance_id", uuid.uuid4().hex[:8])
        prompt = self._format_instance(instance)

        start = time.time()
        try:
            result = await agent_fn(prompt)
            elapsed = time.time() - start

            return {
                "instance_id": instance_id,
                "status": "completed",
                "duration_s": round(elapsed, 2),
                "result": result,
                "patch": self._extract_patch(result),
            }
        except Exception as exc:
            return {
                "instance_id": instance_id,
                "status": "error",
                "error": str(exc)[:500],
                "duration_s": round(time.time() - start, 2),
            }

    def _format_instance(self, instance: dict) -> str:
        """Format a SWE-bench instance as a prompt."""
        return (
            f"## Issue\n{instance.get('problem_statement', '')}\n\n"
            f"## Repository\n{instance.get('repo', '')}\n\n"
            f"## Base Commit\n{instance.get('base_commit', '')}\n\n"
            f"Please fix this issue and provide a git diff/patch."
        )

    def _extract_patch(self, result: Any) -> str:
        """Extract patch/diff from agent result."""
        if isinstance(result, str):
            import re
            diff_match = re.search(r"```diff\n(.*?)```", result, re.DOTALL)
            if diff_match:
                return diff_match.group(1)
            patch_match = re.search(r"```patch\n(.*?)```", result, re.DOTALL)
            if patch_match:
                return patch_match.group(1)
        return str(result)[:2000]

    async def run_batch(self, instances: list[dict], agent_fn: Any,
                        concurrency: int = 3) -> list[dict]:
        """Run multiple SWE-bench instances."""
        sem = asyncio.Semaphore(concurrency)
        results = []

        async def _run(inst: dict) -> dict:
            async with sem:
                return await self.run_instance(inst, agent_fn)

        tasks = [asyncio.create_task(_run(inst)) for inst in instances]
        results = await asyncio.gather(*tasks)

        # Save results
        output_path = self._output / f"results_{int(time.time())}.jsonl"
        with open(output_path, "w") as f:
            for r in results:
                f.write(json.dumps(r) + "\n")

        return list(results)

    def summary(self, results: list[dict]) -> dict[str, Any]:
        """Summarize benchmark results."""
        total = len(results)
        completed = sum(1 for r in results if r["status"] == "completed")
        durations = [r["duration_s"] for r in results if r.get("duration_s")]

        return {
            "total": total,
            "completed": completed,
            "errors": total - completed,
            "success_rate": completed / total if total else 0,
            "avg_duration_s": sum(durations) / len(durations) if durations else 0,
        }


# ---------------------------------------------------------------------------
# Toolset probability distributions
# ---------------------------------------------------------------------------


class ToolsetDistribution:
    """Define probability distributions for tool selection during data generation.

    Used to create realistic training data with varied tool usage patterns.
    """

    PRESETS = {
        "coding": {
            "file_read": 0.25, "file_write": 0.20, "file_edit": 0.15,
            "shell": 0.15, "grep_search": 0.10, "git": 0.05,
            "web_search": 0.05, "code_exec": 0.05,
        },
        "research": {
            "web_search": 0.30, "url_read": 0.25, "file_write": 0.15,
            "file_read": 0.10, "memory_search": 0.10, "pdf": 0.10,
        },
        "chat": {
            "web_search": 0.20, "memory_search": 0.20, "file_read": 0.15,
            "system_info": 0.10, "file_write": 0.10, "shell": 0.05,
            "image_gen": 0.05, "tts": 0.05, "scheduler": 0.05, "notify": 0.05,
        },
        "devops": {
            "shell": 0.30, "file_read": 0.15, "file_write": 0.15,
            "git": 0.15, "code_exec": 0.10, "web_search": 0.05,
            "system_info": 0.10,
        },
    }

    def __init__(self, preset: str = "coding") -> None:
        self._dist = self.PRESETS.get(preset, self.PRESETS["coding"]).copy()

    def sample(self, n: int = 1) -> list[str]:
        """Sample tools according to the distribution."""
        tools = list(self._dist.keys())
        weights = list(self._dist.values())
        return random.choices(tools, weights=weights, k=n)

    def adjust(self, tool: str, weight: float) -> None:
        """Adjust the probability of a specific tool."""
        self._dist[tool] = max(0, weight)
        # Re-normalize
        total = sum(self._dist.values())
        if total > 0:
            self._dist = {k: v / total for k, v in self._dist.items()}

    @property
    def distribution(self) -> dict[str, float]:
        return self._dist.copy()

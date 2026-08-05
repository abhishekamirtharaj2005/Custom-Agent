"""Parallel tool execution engine.

When the LLM requests multiple tool calls in a single response,
this module runs them concurrently instead of sequentially.
Also provides batch execution for pre-planned tool sequences.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ParallelResult:
    """Result of a parallel tool execution batch."""
    results: list[dict] = field(default_factory=list)
    total_time_s: float = 0.0
    sequential_time_s: float = 0.0  # Estimated if run sequentially
    speedup: float = 1.0


async def execute_parallel(
    dispatcher: Any,
    tool_calls: list[dict],
    max_concurrent: int = 5,
) -> ParallelResult:
    """Execute multiple tool calls concurrently.

    Args:
        dispatcher: ToolDispatcher instance
        tool_calls: List of {name, arguments, id} dicts
        max_concurrent: Maximum concurrent tool executions

    Returns:
        ParallelResult with ordered results matching input order
    """
    if not tool_calls:
        return ParallelResult()

    start = time.monotonic()
    semaphore = asyncio.Semaphore(max_concurrent)
    individual_times: list[float] = []

    async def _run_one(tc: dict, index: int) -> tuple[int, dict, float]:
        async with semaphore:
            t0 = time.monotonic()
            try:
                result = await dispatcher.dispatch(tc["name"], tc.get("arguments", {}))
                elapsed = time.monotonic() - t0
                return index, {
                    "tool_call_id": tc.get("id", ""),
                    "name": tc["name"],
                    "result": result,
                    "time_s": elapsed,
                }, elapsed
            except Exception as exc:
                elapsed = time.monotonic() - t0
                from hermclaw.tools.base import ToolResult
                return index, {
                    "tool_call_id": tc.get("id", ""),
                    "name": tc["name"],
                    "result": ToolResult(ok=False, output="", error=str(exc)),
                    "time_s": elapsed,
                }, elapsed

    tasks = [_run_one(tc, i) for i, tc in enumerate(tool_calls)]
    completed = await asyncio.gather(*tasks)

    # Sort by original order
    completed_sorted = sorted(completed, key=lambda x: x[0])
    results = [item[1] for item in completed_sorted]
    times = [item[2] for item in completed_sorted]

    total_time = time.monotonic() - start
    sequential_est = sum(times)

    return ParallelResult(
        results=results,
        total_time_s=round(total_time, 3),
        sequential_time_s=round(sequential_est, 3),
        speedup=round(sequential_est / max(total_time, 0.001), 2),
    )


@dataclass
class PipelineStage:
    """A single stage in a tool execution pipeline."""
    tool_name: str
    arguments: dict = field(default_factory=dict)
    condition: Optional[str] = None  # "success", "failure", or None (always)
    transform: Optional[str] = None  # jq-like expression to transform output


async def execute_pipeline(
    dispatcher: Any,
    stages: list[PipelineStage],
) -> list[dict]:
    """Execute a sequence of tool calls as a pipeline.

    Each stage's output can be referenced by the next stage.
    Stages with the same index run in parallel.
    """
    results = []
    prev_output = ""

    for i, stage in enumerate(stages):
        # Check condition
        if stage.condition == "success" and results and not results[-1].get("ok"):
            results.append({"stage": i, "skipped": True, "reason": "Previous stage failed"})
            continue
        if stage.condition == "failure" and results and results[-1].get("ok"):
            results.append({"stage": i, "skipped": True, "reason": "Previous stage succeeded"})
            continue

        # Inject previous output into arguments if referenced
        args = dict(stage.arguments)
        for key, val in args.items():
            if isinstance(val, str) and "{{prev}}" in val:
                args[key] = val.replace("{{prev}}", prev_output)

        try:
            result = await dispatcher.dispatch(stage.tool_name, args)
            results.append({
                "stage": i,
                "tool": stage.tool_name,
                "ok": result.ok,
                "output": result.output[:500],
                "error": result.error,
            })
            if result.ok:
                prev_output = result.output
        except Exception as exc:
            results.append({
                "stage": i,
                "tool": stage.tool_name,
                "ok": False,
                "error": str(exc),
            })

    return results

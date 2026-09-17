"""Multi-agent delegation system.

Allows the primary agent to spawn sub-agents for parallel task execution.
Sub-agents share the same tools and memory but run independently with
their own context windows.
"""

from __future__ import annotations

import asyncio
import dataclasses
import time
import uuid
from typing import Any, Optional

import structlog

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec

logger = structlog.get_logger(__name__)


@dataclasses.dataclass
class SubagentTask:
    id: str
    prompt: str
    status: str  # "running", "completed", "failed"
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: float = 0.0
    completed_at: float = 0.0


class SubagentRegistry:
    """Tracks running and completed sub-agent tasks."""

    def __init__(self) -> None:
        self._tasks: dict[str, SubagentTask] = {}
        self._running: dict[str, asyncio.Task] = {}

    def register(self, task: SubagentTask) -> None:
        self._tasks[task.id] = task

    def get(self, task_id: str) -> Optional[SubagentTask]:
        return self._tasks.get(task_id)

    def all_tasks(self) -> list[SubagentTask]:
        return list(self._tasks.values())

    def running_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status == "running")


# Global registry
_registry = SubagentRegistry()


class DelegateTool(ToolABC):
    """Delegate tasks to sub-agents for parallel execution."""

    def __init__(self, agent_factory=None) -> None:
        """agent_factory: async callable(prompt) -> str that runs a full
        agent turn and returns the result text."""
        self._agent_factory = agent_factory

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="delegate",
            description=(
                "Delegate tasks to parallel sub-agents or an autonomous multi-agent swarm. "
                "Actions: swarm (execute coordinated multi-specialist pipeline: researcher -> coder -> reviewer), "
                "roles (list available swarm personas), spawn (start a sub-agent), "
                "status (check task status), list (show all tasks), collect (retrieve result)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["swarm", "roles", "spawn", "status", "list", "collect"],
                        "description": "Delegation or swarm action.",
                    },
                    "prompt": {"type": "string", "description": "Task prompt for the sub-agent or swarm."},
                    "roles": {
                        "type": "string",
                        "description": "Comma-separated specialist roles for swarm (e.g. 'researcher,coder,reviewer'). Default: researcher,coder,reviewer.",
                    },
                    "task_id": {"type": "string", "description": "Task ID to check or collect (status/collect)."},
                },
                "required": ["action"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        action = args.get("action", "")

        if action == "roles":
            from hermclaw.brain.swarm import SwarmOrchestrator
            orch = SwarmOrchestrator()
            roles = orch.list_roles()
            lines = ["🤖 **Available Multi-Agent Swarm Personas**:"]
            for r in roles:
                lines.append(f"  • **{r['role'].upper()}** ({r['title']})")
                lines.append(f"    {r['description']}")
                lines.append(f"    Preferred Tools: {', '.join(r['preferred_tools'])}")
            return ToolResult(ok=True, output="\n".join(lines), metadata={"roles": roles})

        elif action == "swarm":
            prompt = args.get("prompt", "")
            if not prompt:
                return ToolResult(ok=False, output="", error="'prompt' required for swarm action.")

            roles_arg = args.get("roles", "")
            roles_list = [r.strip().lower() for r in roles_arg.split(",") if r.strip()] or [
                "researcher", "coder", "reviewer"
            ]

            from hermclaw.brain.swarm import SwarmOrchestrator
            orch = SwarmOrchestrator(agent_executor=self._agent_factory)
            result = await orch.execute_swarm_pipeline(task=prompt, roles=roles_list)

            lines = [
                f"🐝 **Multi-Agent Swarm Pipeline Completed** ({result['total_duration_seconds']}s)",
                f"Roles: {' ➔ '.join(result['roles_executed'])}",
                "",
            ]
            for step in result["steps"]:
                lines.append(f"### {step['title']} ({step['duration_seconds']}s)")
                lines.append(f"{step['output']}")
                lines.append("")

            lines.append("### 🏁 Final Synthesis")
            lines.append(result["final_synthesis"])
            return ToolResult(ok=True, output="\n".join(lines), metadata=result)

        elif action == "spawn":
            prompt = args.get("prompt", "")
            if not prompt:
                return ToolResult(ok=False, output="", error="'prompt' required for spawn.")

            task_id = uuid.uuid4().hex[:8]
            task = SubagentTask(
                id=task_id,
                prompt=prompt,
                status="running",
                started_at=time.time(),
            )
            _registry.register(task)

            if self._agent_factory:
                async def _run():
                    try:
                        result = await self._agent_factory(prompt)
                        task.result = result
                        task.status = "completed"
                    except Exception as exc:
                        task.error = str(exc)
                        task.status = "failed"
                    finally:
                        task.completed_at = time.time()

                asyncio.create_task(_run())
            else:
                task.status = "completed"
                task.result = f"[Sub-agent would process: {prompt}] (agent_factory not configured)"
                task.completed_at = time.time()

            return ToolResult(
                ok=True,
                output=f"Spawned sub-agent task {task_id}: {prompt[:80]}...\n"
                       f"Running tasks: {_registry.running_count()}",
            )

        elif action == "status":
            task_id = args.get("task_id", "")
            if not task_id:
                return ToolResult(ok=False, output="", error="'task_id' required for status.")
            task = _registry.get(task_id)
            if not task:
                return ToolResult(ok=False, output="", error=f"Task {task_id} not found.")
            elapsed = (task.completed_at or time.time()) - task.started_at
            return ToolResult(
                ok=True,
                output=f"Task {task.id}: {task.status} ({elapsed:.1f}s)\n"
                       f"Prompt: {task.prompt[:100]}\n"
                       f"Result: {(task.result or task.error or 'pending')[:200]}",
            )

        elif action == "list":
            tasks = _registry.all_tasks()
            if not tasks:
                return ToolResult(ok=True, output="No delegated tasks yet.")
            lines = ["Delegated Tasks:"]
            for t in tasks:
                elapsed = (t.completed_at or time.time()) - t.started_at
                lines.append(f"  [{t.id}] {t.status} ({elapsed:.1f}s) - {t.prompt[:60]}")
            return ToolResult(ok=True, output="\n".join(lines))

        elif action == "collect":
            task_id = args.get("task_id", "")
            if not task_id:
                return ToolResult(ok=False, output="", error="'task_id' required for collect.")
            task = _registry.get(task_id)
            if not task:
                return ToolResult(ok=False, output="", error=f"Task {task_id} not found.")
            if task.status == "running":
                return ToolResult(ok=True, output=f"Task {task_id} is still running. Check back later.")
            if task.status == "failed":
                return ToolResult(ok=False, output="", error=f"Task failed: {task.error}")
            return ToolResult(ok=True, output=task.result or "")

        else:
            return ToolResult(ok=False, output="", error=f"Unknown action: {action}")

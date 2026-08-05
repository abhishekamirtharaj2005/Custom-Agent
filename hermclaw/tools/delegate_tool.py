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
                "Delegate a task to a sub-agent for parallel execution. "
                "Actions: spawn (start a new sub-agent), status (check on a task), "
                "list (show all tasks), collect (get result of a completed task). "
                "Use this to break complex tasks into parallel sub-tasks."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["spawn", "status", "list", "collect"],
                        "description": "Delegation action.",
                    },
                    "prompt": {"type": "string", "description": "Task prompt for the sub-agent (spawn)."},
                    "task_id": {"type": "string", "description": "Task ID to check or collect (status/collect)."},
                },
                "required": ["action"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        action = args.get("action", "")

        if action == "spawn":
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

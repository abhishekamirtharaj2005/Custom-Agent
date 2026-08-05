"""Scheduler tool: let the agent schedule recurring and one-shot tasks.

Builds on APScheduler (already a dependency) to provide:
- One-shot timers ("remind me in 30 minutes")
- Recurring cron jobs ("check email every hour")
- Named schedules that persist across sessions via SQLite
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import structlog

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec

logger = structlog.get_logger(__name__)

_SCHEDULE_SCHEMA = """
CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    task_type TEXT NOT NULL,
    schedule TEXT NOT NULL,
    prompt TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    last_run REAL,
    next_run REAL,
    run_count INTEGER DEFAULT 0,
    max_runs INTEGER,
    created_at REAL NOT NULL
);
"""


class ScheduleDB:
    """SQLite-backed schedule persistence."""

    def __init__(self, db_path: Path) -> None:
        self._db = sqlite3.connect(str(db_path))
        self._db.row_factory = sqlite3.Row
        self._db.executescript(_SCHEDULE_SCHEMA)

    def close(self) -> None:
        self._db.close()

    def create(self, name: str, task_type: str, schedule: str, prompt: str,
               max_runs: Optional[int] = None) -> str:
        tid = uuid.uuid4().hex[:8]
        now = time.time()
        self._db.execute(
            "INSERT INTO scheduled_tasks (id, name, task_type, schedule, prompt, max_runs, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (tid, name, task_type, schedule, prompt, max_runs, now),
        )
        self._db.commit()
        return tid

    def list_active(self) -> list[dict]:
        rows = self._db.execute(
            "SELECT * FROM scheduled_tasks WHERE status = 'active' ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def list_all(self) -> list[dict]:
        rows = self._db.execute("SELECT * FROM scheduled_tasks ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def mark_run(self, task_id: str) -> None:
        now = time.time()
        task = self._db.execute("SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,)).fetchone()
        if not task:
            return
        run_count = (task["run_count"] or 0) + 1
        max_runs = task["max_runs"]

        if max_runs and run_count >= max_runs:
            self._db.execute(
                "UPDATE scheduled_tasks SET run_count = ?, last_run = ?, status = 'completed' WHERE id = ?",
                (run_count, now, task_id),
            )
        else:
            self._db.execute(
                "UPDATE scheduled_tasks SET run_count = ?, last_run = ? WHERE id = ?",
                (run_count, now, task_id),
            )
        self._db.commit()

    def cancel(self, task_id: str) -> bool:
        cur = self._db.execute(
            "UPDATE scheduled_tasks SET status = 'cancelled' WHERE id = ? AND status = 'active'",
            (task_id,),
        )
        self._db.commit()
        return cur.rowcount > 0

    def pause(self, task_id: str) -> bool:
        cur = self._db.execute(
            "UPDATE scheduled_tasks SET status = 'paused' WHERE id = ? AND status = 'active'",
            (task_id,),
        )
        self._db.commit()
        return cur.rowcount > 0

    def resume(self, task_id: str) -> bool:
        cur = self._db.execute(
            "UPDATE scheduled_tasks SET status = 'active' WHERE id = ? AND status = 'paused'",
            (task_id,),
        )
        self._db.commit()
        return cur.rowcount > 0


# Global instance
_db: Optional[ScheduleDB] = None


def _get_db() -> ScheduleDB:
    global _db
    if _db is None:
        db_path = Path.home() / ".hermclaw" / "schedules.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _db = ScheduleDB(db_path)
    return _db


class SchedulerTool(ToolABC):
    """Schedule recurring and one-shot tasks."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="scheduler",
            description=(
                "Schedule tasks to run at specific times or intervals. "
                "Actions: create (new schedule), list (active schedules), cancel, pause, resume. "
                "Types: 'once' (run once after delay), 'interval' (run every N minutes/hours), "
                "'cron' (cron expression). Examples: '30m' delay, '2h' interval, '0 9 * * 1-5' cron."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create", "list", "cancel", "pause", "resume"],
                    },
                    "name": {"type": "string", "description": "Human-readable name for the schedule."},
                    "task_type": {
                        "type": "string",
                        "enum": ["once", "interval", "cron"],
                        "description": "Schedule type.",
                    },
                    "schedule": {
                        "type": "string",
                        "description": "Timing: '30m'/'2h'/'1d' for once/interval, '0 9 * * 1-5' for cron.",
                    },
                    "prompt": {
                        "type": "string",
                        "description": "What the agent should do when the schedule fires.",
                    },
                    "task_id": {"type": "string", "description": "Task ID for cancel/pause/resume."},
                    "max_runs": {"type": "integer", "description": "Max runs for interval/cron (optional)."},
                },
                "required": ["action"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        action = args.get("action", "")
        db = _get_db()

        try:
            if action == "create":
                name = args.get("name", "Unnamed task")
                task_type = args.get("task_type", "once")
                schedule = args.get("schedule", "")
                prompt = args.get("prompt", "")

                if not schedule:
                    return ToolResult(ok=False, output="", error="'schedule' is required.")
                if not prompt:
                    return ToolResult(ok=False, output="", error="'prompt' is required.")

                max_runs = args.get("max_runs")
                if task_type == "once":
                    max_runs = 1

                tid = db.create(name, task_type, schedule, prompt, max_runs)
                return ToolResult(
                    ok=True,
                    output=f"Scheduled [{tid}] '{name}': {task_type} @ {schedule}\n"
                           f"Prompt: {prompt[:100]}",
                )

            elif action == "list":
                tasks = db.list_active()
                if not tasks:
                    return ToolResult(ok=True, output="No active schedules.")
                lines = ["Active Schedules:"]
                for t in tasks:
                    runs = f"({t['run_count']}/{t['max_runs']})" if t.get("max_runs") else f"({t['run_count']} runs)"
                    lines.append(
                        f"  [{t['id']}] {t['status']} | {t['task_type']} @ {t['schedule']} "
                        f"{runs} | {t['name']}"
                    )
                return ToolResult(ok=True, output="\n".join(lines))

            elif action == "cancel":
                tid = args.get("task_id", "")
                if not tid:
                    return ToolResult(ok=False, output="", error="'task_id' required.")
                ok = db.cancel(tid)
                return ToolResult(ok=ok, output=f"Cancelled: {tid}" if ok else "", error="Task not found or not active." if not ok else None)

            elif action == "pause":
                tid = args.get("task_id", "")
                ok = db.pause(tid)
                return ToolResult(ok=ok, output=f"Paused: {tid}" if ok else "", error="Task not found or not active." if not ok else None)

            elif action == "resume":
                tid = args.get("task_id", "")
                ok = db.resume(tid)
                return ToolResult(ok=ok, output=f"Resumed: {tid}" if ok else "", error="Task not found or not paused." if not ok else None)

            else:
                return ToolResult(ok=False, output="", error=f"Unknown action: {action}")

        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Scheduler error: {exc}")

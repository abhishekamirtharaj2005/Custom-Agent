"""Scheduler tool: let the agent schedule recurring and one-shot tasks.

Builds on background threads to provide:
- One-shot timers ("remind me in 30 minutes")
- Recurring interval tasks ("check email every hour")
- Named schedules that persist across sessions via SQLite

When a timer fires, it sends a desktop notification using ctypes MessageBox.
"""

from __future__ import annotations

import ctypes
import json
import re
import sqlite3
import threading
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

# ---- Duration parsing ----

_DUR_RE = re.compile(r"(\d+)\s*(s|sec|second|seconds|m|min|minute|minutes|h|hr|hour|hours|d|day|days)$", re.I)
_UNITS = {"s": 1, "sec": 1, "second": 1, "seconds": 1,
          "m": 60, "min": 60, "minute": 60, "minutes": 60,
          "h": 3600, "hr": 3600, "hour": 3600, "hours": 3600,
          "d": 86400, "day": 86400, "days": 86400}


def _parse_duration(s: str) -> Optional[float]:
    """Parse a duration string like '30m', '2h', '1 minute' into seconds."""
    s = s.strip()
    # Try direct number (assume seconds)
    try:
        return float(s)
    except ValueError:
        pass
    m = _DUR_RE.match(s)
    if m:
        return int(m.group(1)) * _UNITS[m.group(2).lower()]
    return None


# ---- Active timers (in-process) ----

_active_timers: dict[str, threading.Timer] = {}


def _fire_notification(task_id: str, name: str, prompt: str, db: ScheduleDB,
                       interval_secs: Optional[float] = None, max_runs: Optional[int] = None) -> None:
    """Called when a timer fires. Shows notification and optionally reschedules."""
    logger.info("scheduler.fired", task_id=task_id, name=name)
    db.mark_run(task_id)

    # Show Windows notification
    try:
        FLAGS = 0x40 | 0x1000  # MB_ICONINFORMATION | MB_SYSTEMMODAL
        title = "Hermclaw Reminder"
        ctypes.windll.user32.MessageBoxW(0, prompt, title, FLAGS)
    except Exception:
        logger.debug("scheduler.notify_failed", task_id=task_id)

    # If interval, reschedule (check max_runs)
    if interval_secs and interval_secs > 0:
        task = db.get(task_id)
        if task and task["status"] == "active":
            if max_runs and task["run_count"] >= max_runs:
                logger.info("scheduler.max_runs_reached", task_id=task_id)
                return
            _start_timer(task_id, name, prompt, interval_secs, db, interval_secs, max_runs)


def _start_timer(task_id: str, name: str, prompt: str, delay_secs: float,
                 db: "ScheduleDB", interval_secs: Optional[float] = None,
                 max_runs: Optional[int] = None) -> None:
    """Start a background timer that fires after delay_secs."""
    # Cancel existing timer for this task if any
    if task_id in _active_timers:
        _active_timers[task_id].cancel()

    timer = threading.Timer(delay_secs, _fire_notification,
                            args=(task_id, name, prompt, db, interval_secs, max_runs))
    timer.daemon = True
    timer.name = f"hermclaw-scheduler-{task_id}"
    timer.start()
    _active_timers[task_id] = timer

    # Update next_run in DB
    db.set_next_run(task_id, time.time() + delay_secs)
    logger.info("scheduler.timer_started", task_id=task_id, delay_secs=delay_secs)


class ScheduleDB:
    """SQLite-backed schedule persistence."""

    def __init__(self, db_path: Path) -> None:
        self._db = sqlite3.connect(str(db_path), check_same_thread=False)
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

    def get(self, task_id: str) -> Optional[dict]:
        row = self._db.execute("SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else None

    def list_active(self) -> list[dict]:
        rows = self._db.execute(
            "SELECT * FROM scheduled_tasks WHERE status = 'active' ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def list_all(self) -> list[dict]:
        rows = self._db.execute("SELECT * FROM scheduled_tasks ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def set_next_run(self, task_id: str, next_run: float) -> None:
        self._db.execute(
            "UPDATE scheduled_tasks SET next_run = ? WHERE id = ?",
            (next_run, task_id),
        )
        self._db.commit()

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
        # Also cancel the in-process timer
        if task_id in _active_timers:
            _active_timers[task_id].cancel()
            del _active_timers[task_id]
        return cur.rowcount > 0

    def pause(self, task_id: str) -> bool:
        cur = self._db.execute(
            "UPDATE scheduled_tasks SET status = 'paused' WHERE id = ? AND status = 'active'",
            (task_id,),
        )
        self._db.commit()
        if task_id in _active_timers:
            _active_timers[task_id].cancel()
            del _active_timers[task_id]
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
    """Schedule recurring and one-shot tasks with actual timers."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="scheduler",
            description=(
                "Schedule tasks to run at specific times or intervals. "
                "Actions: create (new schedule), list (active schedules), cancel, pause, resume. "
                "Types: 'once' (run once after delay), 'interval' (run every N minutes/hours). "
                "Examples: '30m' delay, '2h' interval, '1m' for 1 minute. "
                "When the timer fires, a desktop notification is shown."
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
                        "enum": ["once", "interval"],
                        "description": "Schedule type.",
                    },
                    "schedule": {
                        "type": "string",
                        "description": "Timing: '30s', '1m', '2h', '1d' for delay/interval.",
                    },
                    "prompt": {
                        "type": "string",
                        "description": "The reminder message to show when the timer fires.",
                    },
                    "task_id": {"type": "string", "description": "Task ID for cancel/pause/resume."},
                    "max_runs": {"type": "integer", "description": "Max runs for interval (optional)."},
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

                delay_secs = _parse_duration(schedule)
                if delay_secs is None:
                    return ToolResult(
                        ok=False, output="",
                        error=f"Cannot parse duration: '{schedule}'. Use formats like '30s', '5m', '2h', '1d'."
                    )

                max_runs = args.get("max_runs")
                if task_type == "once":
                    max_runs = 1

                tid = db.create(name, task_type, schedule, prompt, max_runs)

                # Start the actual timer!
                interval_secs = delay_secs if task_type == "interval" else None
                _start_timer(tid, name, prompt, delay_secs, db, interval_secs, max_runs)

                return ToolResult(
                    ok=True,
                    output=f"Timer [{tid}] '{name}' set for {schedule} ({delay_secs:.0f}s)\n"
                           f"Reminder: {prompt}\n"
                           f"A desktop notification will pop up when it fires.",
                )

            elif action == "list":
                tasks = db.list_active()
                if not tasks:
                    return ToolResult(ok=True, output="No active schedules.")
                lines = ["Active Schedules:"]
                for t in tasks:
                    runs = f"({t['run_count']}/{t['max_runs']})" if t.get("max_runs") else f"({t['run_count']} runs)"
                    remaining = ""
                    if t.get("next_run"):
                        secs_left = t["next_run"] - time.time()
                        if secs_left > 0:
                            remaining = f" | fires in {secs_left:.0f}s"
                        else:
                            remaining = " | overdue"
                    active = "[ON]" if t["id"] in _active_timers else "[PAUSED]"
                    lines.append(
                        f"  {active} [{t['id']}] {t['task_type']} @ {t['schedule']} "
                        f"{runs}{remaining} | {t['name']}"
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
                if ok:
                    task = db.get(tid)
                    if task:
                        delay = _parse_duration(task["schedule"])
                        if delay:
                            interval = delay if task["task_type"] == "interval" else None
                            _start_timer(tid, task["name"], task["prompt"], delay, db, interval, task.get("max_runs"))
                return ToolResult(ok=ok, output=f"Resumed: {tid}" if ok else "", error="Task not found or not paused." if not ok else None)

            else:
                return ToolResult(ok=False, output="", error=f"Unknown action: {action}")

        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Scheduler error: {exc}")

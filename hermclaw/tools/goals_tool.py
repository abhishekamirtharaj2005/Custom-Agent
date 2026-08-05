"""Goals system: autonomous long-running goal pursuit.

The agent can set goals, track progress, and work towards them
over multiple sessions. Goals persist in SQLite and are surfaced
in the system prompt so the agent stays aware of them.
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

_GOALS_SCHEMA = """
CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    priority TEXT DEFAULT 'medium',
    progress INTEGER DEFAULT 0,
    milestones TEXT DEFAULT '[]',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    completed_at REAL
);

CREATE TABLE IF NOT EXISTS goal_logs (
    id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL REFERENCES goals(id),
    entry TEXT NOT NULL,
    created_at REAL NOT NULL
);
"""


class GoalsDB:
    """SQLite-backed goals storage."""

    def __init__(self, db_path: Path) -> None:
        self._db = sqlite3.connect(str(db_path))
        self._db.row_factory = sqlite3.Row
        self._db.executescript(_GOALS_SCHEMA)

    def close(self) -> None:
        self._db.close()

    def create(self, title: str, description: str = "", priority: str = "medium") -> str:
        gid = uuid.uuid4().hex[:8]
        now = time.time()
        self._db.execute(
            "INSERT INTO goals (id, title, description, priority, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (gid, title, description, priority, now, now),
        )
        self._db.commit()
        return gid

    def update_progress(self, goal_id: str, progress: int, log_entry: str = "") -> bool:
        now = time.time()
        cur = self._db.execute(
            "UPDATE goals SET progress = ?, updated_at = ? WHERE id = ?",
            (min(100, max(0, progress)), now, goal_id),
        )
        if log_entry:
            self._db.execute(
                "INSERT INTO goal_logs (id, goal_id, entry, created_at) VALUES (?, ?, ?, ?)",
                (uuid.uuid4().hex[:8], goal_id, log_entry, now),
            )
        self._db.commit()
        return cur.rowcount > 0

    def complete(self, goal_id: str) -> bool:
        now = time.time()
        cur = self._db.execute(
            "UPDATE goals SET status = 'completed', progress = 100, completed_at = ?, updated_at = ? WHERE id = ?",
            (now, now, goal_id),
        )
        self._db.commit()
        return cur.rowcount > 0

    def list_active(self) -> list[dict]:
        rows = self._db.execute(
            "SELECT * FROM goals WHERE status = 'active' ORDER BY priority DESC, created_at"
        ).fetchall()
        return [dict(r) for r in rows]

    def list_all(self) -> list[dict]:
        rows = self._db.execute("SELECT * FROM goals ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def get(self, goal_id: str) -> Optional[dict]:
        row = self._db.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        logs = self._db.execute(
            "SELECT * FROM goal_logs WHERE goal_id = ? ORDER BY created_at DESC LIMIT 10",
            (goal_id,),
        ).fetchall()
        result["logs"] = [dict(l) for l in logs]
        return result

    def active_summary(self) -> str:
        """Compact summary for injection into system prompt."""
        goals = self.list_active()
        if not goals:
            return ""
        lines = ["Active Goals:"]
        for g in goals:
            lines.append(f"  [{g['id']}] ({g['progress']}%) {g['title']}")
        return "\n".join(lines)

    def abandon(self, goal_id: str) -> bool:
        cur = self._db.execute(
            "UPDATE goals SET status = 'abandoned', updated_at = ? WHERE id = ?",
            (time.time(), goal_id),
        )
        self._db.commit()
        return cur.rowcount > 0


# Global DB instance
_db: Optional[GoalsDB] = None


def _get_db() -> GoalsDB:
    global _db
    if _db is None:
        db_path = Path.home() / ".hermclaw" / "goals.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _db = GoalsDB(db_path)
    return _db


class GoalsTool(ToolABC):
    """Autonomous goals system."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="goals",
            description=(
                "Manage long-running goals. Actions: create (new goal), list (active goals), "
                "update (progress + log), complete (mark done), abandon, show (details + logs). "
                "Goals persist across sessions and are shown in your system prompt."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create", "list", "update", "complete", "abandon", "show"],
                    },
                    "title": {"type": "string", "description": "Goal title (create)."},
                    "description": {"type": "string", "description": "Goal details (create)."},
                    "goal_id": {"type": "string", "description": "Goal ID (update/complete/abandon/show)."},
                    "progress": {"type": "integer", "description": "Progress percentage 0-100 (update)."},
                    "log_entry": {"type": "string", "description": "Progress log note (update)."},
                    "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                },
                "required": ["action"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        action = args.get("action", "")
        db = _get_db()

        try:
            if action == "create":
                title = args.get("title", "")
                if not title:
                    return ToolResult(ok=False, output="", error="'title' required.")
                gid = db.create(title, args.get("description", ""), args.get("priority", "medium"))
                return ToolResult(ok=True, output=f"Created goal [{gid}]: {title}")

            elif action == "list":
                goals = db.list_all()
                if not goals:
                    return ToolResult(ok=True, output="No goals yet. Use create to set one.")
                lines = ["Goals:"]
                for g in goals:
                    status = "x" if g["status"] == "completed" else ("-" if g["status"] == "abandoned" else " ")
                    lines.append(f"  [{status}] [{g['id']}] ({g['progress']}%) [{g['priority']}] {g['title']}")
                return ToolResult(ok=True, output="\n".join(lines))

            elif action == "update":
                gid = args.get("goal_id", "")
                if not gid:
                    return ToolResult(ok=False, output="", error="'goal_id' required.")
                progress = args.get("progress", 0)
                log = args.get("log_entry", "")
                ok = db.update_progress(gid, progress, log)
                return ToolResult(ok=ok, output=f"Updated goal {gid} to {progress}%" if ok else "", error="Goal not found." if not ok else None)

            elif action == "complete":
                gid = args.get("goal_id", "")
                ok = db.complete(gid)
                return ToolResult(ok=ok, output=f"Goal {gid} completed!" if ok else "", error="Goal not found." if not ok else None)

            elif action == "abandon":
                gid = args.get("goal_id", "")
                ok = db.abandon(gid)
                return ToolResult(ok=ok, output=f"Goal {gid} abandoned." if ok else "", error="Goal not found." if not ok else None)

            elif action == "show":
                gid = args.get("goal_id", "")
                goal = db.get(gid)
                if not goal:
                    return ToolResult(ok=False, output="", error="Goal not found.")
                lines = [
                    f"Goal: {goal['title']} [{goal['id']}]",
                    f"Status: {goal['status']} | Progress: {goal['progress']}% | Priority: {goal['priority']}",
                    f"Description: {goal.get('description', '(none)')}",
                    "", "Recent log entries:",
                ]
                for log in goal.get("logs", []):
                    lines.append(f"  - {log['entry']}")
                return ToolResult(ok=True, output="\n".join(lines))

            else:
                return ToolResult(ok=False, output="", error=f"Unknown action: {action}")
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Goals error: {exc}")

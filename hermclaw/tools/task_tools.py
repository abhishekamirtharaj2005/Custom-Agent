"""Task management tools: Todo list and Kanban board.

Provides the agent with structured project/task tracking persisted
in SQLite alongside the existing memory store.
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

_KANBAN_SCHEMA = """
CREATE TABLE IF NOT EXISTS kb_boards (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS kb_columns (
    id TEXT PRIMARY KEY,
    board_id TEXT NOT NULL REFERENCES kb_boards(id),
    name TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS kb_tasks (
    id TEXT PRIMARY KEY,
    board_id TEXT NOT NULL REFERENCES kb_boards(id),
    column_id TEXT NOT NULL REFERENCES kb_columns(id),
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    priority TEXT DEFAULT 'medium',
    tags TEXT DEFAULT '[]',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS todos (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0,
    priority TEXT DEFAULT 'medium',
    created_at REAL NOT NULL,
    completed_at REAL
);
"""


class _KanbanDB:
    """Thin SQLite wrapper for Kanban + Todos."""

    def __init__(self, db_path: Path) -> None:
        self._db = sqlite3.connect(str(db_path))
        self._db.row_factory = sqlite3.Row
        self._db.executescript(_KANBAN_SCHEMA)

    def close(self) -> None:
        self._db.close()

    # --- Boards ---
    def create_board(self, name: str) -> str:
        bid = uuid.uuid4().hex[:8]
        self._db.execute(
            "INSERT INTO kb_boards (id, name, created_at) VALUES (?, ?, ?)",
            (bid, name, time.time()),
        )
        # Create default columns
        for i, col_name in enumerate(["Backlog", "In Progress", "Done"]):
            self._db.execute(
                "INSERT INTO kb_columns (id, board_id, name, position) VALUES (?, ?, ?, ?)",
                (uuid.uuid4().hex[:8], bid, col_name, i),
            )
        self._db.commit()
        return bid

    def list_boards(self) -> list[dict]:
        rows = self._db.execute("SELECT * FROM kb_boards ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def get_board(self, board_id: str) -> dict:
        board = self._db.execute("SELECT * FROM kb_boards WHERE id = ?", (board_id,)).fetchone()
        if not board:
            return {}
        columns = self._db.execute(
            "SELECT * FROM kb_columns WHERE board_id = ? ORDER BY position", (board_id,)
        ).fetchall()
        result = dict(board)
        result["columns"] = []
        for col in columns:
            c = dict(col)
            tasks = self._db.execute(
                "SELECT * FROM kb_tasks WHERE column_id = ? ORDER BY position", (col["id"],)
            ).fetchall()
            c["tasks"] = [dict(t) for t in tasks]
            result["columns"].append(c)
        return result

    # --- Tasks ---
    def add_task(self, board_id: str, title: str, description: str = "", priority: str = "medium", column_name: str = "Backlog") -> str:
        col = self._db.execute(
            "SELECT id FROM kb_columns WHERE board_id = ? AND name = ?", (board_id, column_name)
        ).fetchone()
        if not col:
            col = self._db.execute(
                "SELECT id FROM kb_columns WHERE board_id = ? ORDER BY position LIMIT 1", (board_id,)
            ).fetchone()
        if not col:
            return ""
        tid = uuid.uuid4().hex[:8]
        now = time.time()
        self._db.execute(
            "INSERT INTO kb_tasks (id, board_id, column_id, title, description, priority, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (tid, board_id, col["id"], title, description, priority, now, now),
        )
        self._db.commit()
        return tid

    def move_task(self, task_id: str, column_name: str) -> bool:
        task = self._db.execute("SELECT board_id FROM kb_tasks WHERE id = ?", (task_id,)).fetchone()
        if not task:
            return False
        col = self._db.execute(
            "SELECT id FROM kb_columns WHERE board_id = ? AND name = ?", (task["board_id"], column_name)
        ).fetchone()
        if not col:
            return False
        self._db.execute(
            "UPDATE kb_tasks SET column_id = ?, updated_at = ? WHERE id = ?",
            (col["id"], time.time(), task_id),
        )
        self._db.commit()
        return True

    # --- Todos ---
    def add_todo(self, text: str, priority: str = "medium") -> str:
        tid = uuid.uuid4().hex[:8]
        self._db.execute(
            "INSERT INTO todos (id, text, priority, created_at) VALUES (?, ?, ?, ?)",
            (tid, text, priority, time.time()),
        )
        self._db.commit()
        return tid

    def complete_todo(self, todo_id: str) -> bool:
        cur = self._db.execute(
            "UPDATE todos SET done = 1, completed_at = ? WHERE id = ?",
            (time.time(), todo_id),
        )
        self._db.commit()
        return cur.rowcount > 0

    def list_todos(self, show_done: bool = False) -> list[dict]:
        if show_done:
            rows = self._db.execute("SELECT * FROM todos ORDER BY created_at DESC").fetchall()
        else:
            rows = self._db.execute("SELECT * FROM todos WHERE done = 0 ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


# Global DB instance (created lazily)
_db: Optional[_KanbanDB] = None


def _get_db() -> _KanbanDB:
    global _db
    if _db is None:
        db_path = Path.home() / ".hermclaw" / "kanban.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _db = _KanbanDB(db_path)
    return _db


class KanbanTool(ToolABC):
    """Kanban board for project management."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="kanban",
            description=(
                "Project management with Kanban boards. Actions: create_board, list_boards, "
                "view_board, add_task, move_task. Each board has columns (Backlog, In Progress, "
                "Done by default). Use for tracking project tasks."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create_board", "list_boards", "view_board", "add_task", "move_task"],
                        "description": "Kanban action to perform.",
                    },
                    "board_name": {"type": "string", "description": "Name for a new board."},
                    "board_id": {"type": "string", "description": "ID of the board to operate on."},
                    "task_title": {"type": "string", "description": "Title of the task."},
                    "task_description": {"type": "string", "description": "Task description."},
                    "task_id": {"type": "string", "description": "Task ID for move operations."},
                    "column_name": {"type": "string", "description": "Column to add task to or move task to."},
                    "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                },
                "required": ["action"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        action = args.get("action", "")
        db = _get_db()

        try:
            if action == "create_board":
                name = args.get("board_name", "New Board")
                bid = db.create_board(name)
                return ToolResult(ok=True, output=f"Created board '{name}' (id: {bid})")

            elif action == "list_boards":
                boards = db.list_boards()
                if not boards:
                    return ToolResult(ok=True, output="No boards yet. Use create_board to make one.")
                lines = ["Kanban Boards:"]
                for b in boards:
                    lines.append(f"  [{b['id']}] {b['name']}")
                return ToolResult(ok=True, output="\n".join(lines))

            elif action == "view_board":
                board_id = args.get("board_id", "")
                if not board_id:
                    return ToolResult(ok=False, output="", error="board_id required.")
                board = db.get_board(board_id)
                if not board:
                    return ToolResult(ok=False, output="", error=f"Board {board_id} not found.")
                lines = [f"Board: {board['name']} [{board['id']}]", ""]
                for col in board.get("columns", []):
                    lines.append(f"--- {col['name']} ---")
                    for task in col.get("tasks", []):
                        prio = f"[{task['priority']}]" if task.get("priority") else ""
                        lines.append(f"  [{task['id']}] {prio} {task['title']}")
                        if task.get("description"):
                            lines.append(f"         {task['description'][:80]}")
                    if not col.get("tasks"):
                        lines.append("  (empty)")
                    lines.append("")
                return ToolResult(ok=True, output="\n".join(lines))

            elif action == "add_task":
                board_id = args.get("board_id", "")
                title = args.get("task_title", "")
                if not board_id or not title:
                    return ToolResult(ok=False, output="", error="board_id and task_title required.")
                tid = db.add_task(
                    board_id, title,
                    description=args.get("task_description", ""),
                    priority=args.get("priority", "medium"),
                    column_name=args.get("column_name", "Backlog"),
                )
                if not tid:
                    return ToolResult(ok=False, output="", error="Failed to add task (board not found?).")
                return ToolResult(ok=True, output=f"Added task '{title}' (id: {tid})")

            elif action == "move_task":
                task_id = args.get("task_id", "")
                column = args.get("column_name", "")
                if not task_id or not column:
                    return ToolResult(ok=False, output="", error="task_id and column_name required.")
                ok = db.move_task(task_id, column)
                if not ok:
                    return ToolResult(ok=False, output="", error="Task or column not found.")
                return ToolResult(ok=True, output=f"Moved task {task_id} to '{column}'")

            else:
                return ToolResult(ok=False, output="", error=f"Unknown action: {action}")

        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Kanban error: {exc}")


class TodoTool(ToolABC):
    """Simple todo list for quick task tracking."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="todo",
            description=(
                "Simple todo list. Actions: add, complete, list. Use for quick task "
                "tracking when a full Kanban board is overkill."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["add", "complete", "list"],
                        "description": "Todo action.",
                    },
                    "text": {"type": "string", "description": "Todo text (for add)."},
                    "todo_id": {"type": "string", "description": "Todo ID (for complete)."},
                    "show_done": {"type": "boolean", "description": "Include completed items (for list)."},
                    "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                },
                "required": ["action"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        action = args.get("action", "")
        db = _get_db()

        try:
            if action == "add":
                text = args.get("text", "")
                if not text:
                    return ToolResult(ok=False, output="", error="'text' is required for add.")
                tid = db.add_todo(text, priority=args.get("priority", "medium"))
                return ToolResult(ok=True, output=f"Added todo: [{tid}] {text}")

            elif action == "complete":
                todo_id = args.get("todo_id", "")
                if not todo_id:
                    return ToolResult(ok=False, output="", error="'todo_id' is required for complete.")
                ok = db.complete_todo(todo_id)
                return ToolResult(ok=ok, output=f"Completed: {todo_id}" if ok else "", error="Todo not found." if not ok else None)

            elif action == "list":
                todos = db.list_todos(show_done=args.get("show_done", False))
                if not todos:
                    return ToolResult(ok=True, output="No todos. Use add to create one.")
                lines = ["Todo List:"]
                for t in todos:
                    status = "[x]" if t["done"] else "[ ]"
                    lines.append(f"  {status} [{t['id']}] ({t['priority']}) {t['text']}")
                return ToolResult(ok=True, output="\n".join(lines))

            else:
                return ToolResult(ok=False, output="", error=f"Unknown action: {action}")

        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Todo error: {exc}")

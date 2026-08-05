"""Achievement / Gamification System.

Tracks milestones and unlocks achievements as the user interacts with
Hermclaw. Makes the AI experience fun and engaging.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec

_ACH_SCHEMA = """
CREATE TABLE IF NOT EXISTS achievements (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    icon TEXT DEFAULT '',
    unlocked INTEGER DEFAULT 0,
    unlocked_at REAL,
    progress INTEGER DEFAULT 0,
    target INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS stats (
    key TEXT PRIMARY KEY,
    value INTEGER DEFAULT 0
);
"""

# Built-in achievement definitions
BUILTIN_ACHIEVEMENTS = [
    # Getting started
    {"id": "first_chat", "name": "Hello World!", "description": "Send your first message.", "icon": "[CHAT]", "category": "beginner", "target": 1},
    {"id": "chats_10", "name": "Chatty", "description": "Have 10 conversations.", "icon": "[10x]", "category": "beginner", "target": 10},
    {"id": "chats_100", "name": "Motormouth", "description": "Have 100 conversations.", "icon": "[100]", "category": "beginner", "target": 100},

    # Tools
    {"id": "first_tool", "name": "Tool User", "description": "Use a tool for the first time.", "icon": "[WRN]", "category": "tools", "target": 1},
    {"id": "tools_50", "name": "Handyman", "description": "Use tools 50 times.", "icon": "[50T]", "category": "tools", "target": 50},
    {"id": "tools_500", "name": "Master Craftsman", "description": "Use tools 500 times.", "icon": "[500]", "category": "tools", "target": 500},
    {"id": "all_tools", "name": "Jack of All Trades", "description": "Use every available tool at least once.", "icon": "[ALL]", "category": "tools", "target": 20},

    # Files
    {"id": "first_file", "name": "File Explorer", "description": "Read your first file.", "icon": "[FIL]", "category": "files", "target": 1},
    {"id": "files_written", "name": "Prolific Writer", "description": "Write 10 files.", "icon": "[10F]", "category": "files", "target": 10},
    {"id": "code_exec", "name": "Code Runner", "description": "Execute code for the first time.", "icon": "[RUN]", "category": "files", "target": 1},

    # Web
    {"id": "first_search", "name": "Web Explorer", "description": "Perform your first web search.", "icon": "[WEB]", "category": "web", "target": 1},
    {"id": "browser_use", "name": "Browser Pilot", "description": "Use browser automation.", "icon": "[BRW]", "category": "web", "target": 1},

    # Memory
    {"id": "first_memory", "name": "Remember Me", "description": "Store your first memory.", "icon": "[MEM]", "category": "memory", "target": 1},
    {"id": "memories_50", "name": "Elephant", "description": "Store 50 memories.", "icon": "[ELP]", "category": "memory", "target": 50},
    {"id": "first_goal", "name": "Goal Setter", "description": "Create your first goal.", "icon": "[GOL]", "category": "goals", "target": 1},
    {"id": "goal_complete", "name": "Mission Accomplished", "description": "Complete a goal.", "icon": "[WIN]", "category": "goals", "target": 1},

    # Fun
    {"id": "pet_adopt", "name": "Pet Parent", "description": "Adopt a virtual pet.", "icon": "[PET]", "category": "fun", "target": 1},
    {"id": "pet_legendary", "name": "Legendary Tamer", "description": "Evolve your pet to legendary.", "icon": "[LEG]", "category": "fun", "target": 1},
    {"id": "night_owl", "name": "Night Owl", "description": "Chat after midnight.", "icon": "[OWL]", "category": "fun", "target": 1},
    {"id": "early_bird", "name": "Early Bird", "description": "Chat before 6 AM.", "icon": "[BRD]", "category": "fun", "target": 1},

    # Mastery
    {"id": "models_3", "name": "Model Hopper", "description": "Use 3 different models.", "icon": "[3M]", "category": "mastery", "target": 3},
    {"id": "learning_10", "name": "Quick Learner", "description": "Add 10 concepts to the learning graph.", "icon": "[LRN]", "category": "mastery", "target": 10},
    {"id": "skills_5", "name": "Skilled", "description": "Have 5 skills.", "icon": "[SKL]", "category": "mastery", "target": 5},
    {"id": "streak_7", "name": "Week Warrior", "description": "Use Hermclaw 7 days in a row.", "icon": "[7D]", "category": "mastery", "target": 7},
]


class AchievementSystem:
    """SQLite-backed achievement tracking."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        if db_path is None:
            db_path = Path.home() / ".hermclaw" / "achievements.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(db_path))
        self._db.row_factory = sqlite3.Row
        self._db.executescript(_ACH_SCHEMA)
        self._ensure_builtin()

    def close(self) -> None:
        self._db.close()

    def _ensure_builtin(self) -> None:
        for ach in BUILTIN_ACHIEVEMENTS:
            existing = self._db.execute("SELECT id FROM achievements WHERE id = ?", (ach["id"],)).fetchone()
            if not existing:
                self._db.execute(
                    "INSERT INTO achievements (id, name, description, category, icon, target) VALUES (?, ?, ?, ?, ?, ?)",
                    (ach["id"], ach["name"], ach["description"], ach["category"], ach["icon"], ach["target"]),
                )
        self._db.commit()

    def increment(self, stat_key: str, amount: int = 1) -> list[dict]:
        """Increment a stat and check for newly unlocked achievements."""
        self._db.execute(
            "INSERT INTO stats (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = value + ?",
            (stat_key, amount, amount),
        )
        self._db.commit()

        # Check for unlocks
        newly_unlocked = []
        stat_to_achievement = {
            "chats": ["first_chat", "chats_10", "chats_100"],
            "tool_calls": ["first_tool", "tools_50", "tools_500"],
            "unique_tools": ["all_tools"],
            "files_read": ["first_file"],
            "files_written": ["files_written"],
            "code_executions": ["code_exec"],
            "web_searches": ["first_search"],
            "browser_actions": ["browser_use"],
            "memories_stored": ["first_memory", "memories_50"],
            "goals_created": ["first_goal"],
            "goals_completed": ["goal_complete"],
            "pet_adopted": ["pet_adopt"],
            "concepts_learned": ["learning_10"],
            "models_used": ["models_3"],
        }

        ach_ids = stat_to_achievement.get(stat_key, [])
        current_val = self._get_stat(stat_key)

        for aid in ach_ids:
            ach = self._db.execute("SELECT * FROM achievements WHERE id = ?", (aid,)).fetchone()
            if ach and not ach["unlocked"] and current_val >= ach["target"]:
                self._db.execute(
                    "UPDATE achievements SET unlocked = 1, unlocked_at = ?, progress = ? WHERE id = ?",
                    (time.time(), ach["target"], aid),
                )
                newly_unlocked.append(dict(ach))
            elif ach and not ach["unlocked"]:
                self._db.execute(
                    "UPDATE achievements SET progress = ? WHERE id = ?",
                    (min(current_val, ach["target"]), aid),
                )

        self._db.commit()
        return newly_unlocked

    def _get_stat(self, key: str) -> int:
        row = self._db.execute("SELECT value FROM stats WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else 0

    def list_all(self) -> list[dict]:
        rows = self._db.execute("SELECT * FROM achievements ORDER BY category, unlocked DESC, name").fetchall()
        return [dict(r) for r in rows]

    def list_unlocked(self) -> list[dict]:
        rows = self._db.execute("SELECT * FROM achievements WHERE unlocked = 1 ORDER BY unlocked_at DESC").fetchall()
        return [dict(r) for r in rows]

    def summary(self) -> dict:
        total = self._db.execute("SELECT COUNT(*) as n FROM achievements").fetchone()["n"]
        unlocked = self._db.execute("SELECT COUNT(*) as n FROM achievements WHERE unlocked = 1").fetchone()["n"]
        categories = self._db.execute(
            "SELECT category, COUNT(*) as total, SUM(unlocked) as done FROM achievements GROUP BY category"
        ).fetchall()
        return {
            "total": total,
            "unlocked": unlocked,
            "progress": f"{unlocked}/{total} ({unlocked*100//max(1,total)}%)",
            "categories": {r["category"]: f"{r['done'] or 0}/{r['total']}" for r in categories},
        }

    def render(self) -> str:
        unlocked = self.list_unlocked()
        summary = self.summary()
        lines = [
            "=== Achievements ===",
            f"Progress: {summary['progress']}",
            "",
        ]
        if unlocked:
            lines.append("Unlocked:")
            for a in unlocked[:20]:
                lines.append(f"  {a['icon']} {a['name']} - {a['description']}")
        else:
            lines.append("No achievements unlocked yet. Keep chatting!")
        lines.append("")
        lines.append("Categories:")
        for cat, prog in summary["categories"].items():
            lines.append(f"  {cat}: {prog}")
        return "\n".join(lines)


class AchievementsTool(ToolABC):
    """Achievement/gamification tool."""

    def __init__(self) -> None:
        self._system = AchievementSystem()

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="achievements",
            description=(
                "View your achievements and gamification progress. "
                "Actions: list (all achievements), unlocked (only unlocked), "
                "summary (progress overview), show (full ASCII display)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "unlocked", "summary", "show"],
                    },
                },
                "required": ["action"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        action = args.get("action", "show")
        try:
            if action == "list":
                achs = self._system.list_all()
                lines = []
                for a in achs:
                    status = "[x]" if a["unlocked"] else f"[{a['progress']}/{a['target']}]"
                    lines.append(f"  {status} {a['icon']} {a['name']} - {a['description']}")
                return ToolResult(ok=True, output="\n".join(lines) if lines else "No achievements defined.")

            elif action == "unlocked":
                achs = self._system.list_unlocked()
                if not achs:
                    return ToolResult(ok=True, output="No achievements unlocked yet!")
                lines = [f"  {a['icon']} {a['name']} - {a['description']}" for a in achs]
                return ToolResult(ok=True, output="\n".join(lines))

            elif action == "summary":
                s = self._system.summary()
                return ToolResult(ok=True, output=json.dumps(s, indent=2))

            elif action == "show":
                return ToolResult(ok=True, output=self._system.render())

            else:
                return ToolResult(ok=False, output="", error=f"Unknown action: {action}")
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Achievement error: {exc}")

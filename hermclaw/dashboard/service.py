"""Dashboard Service: Data and execution bridge for the Hermclaw Web Dashboard.

Provides high-level access to:
- Overview stats (agent, model, profiles, system)
- Interactive agent chat execution & session management
- Skills registry & validation
- Self-learning reflection triggering & history
- Concept Learning Graph querying & modification
- Identity & Memory editors (MEMORY.md, USER.md, SOUL.md, Vector Memory)
- Kanban boards, tasks, and Todo items
- Long-term autonomous Goals & OKRs
- Virtual Pet companion (Clawbert) & Achievements
- Tools directory & execution playground
- System health, doctor diagnostics, and config management
"""

from __future__ import annotations

import asyncio
import dataclasses
import datetime
import json
import os
import platform
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

import httpx
import psutil
import structlog

from hermclaw.brain.profiles import ProfileManager
from hermclaw.brain.reflection import reflect as run_reflection
from hermclaw.config import (
    HermclawConfig,
    default_config_path,
    hermclaw_home,
    load_config,
    save_config_text,
)
from hermclaw.runtime import AgentRuntime, build_agent_runtime, gateway_token
from hermclaw.security.secrets import redact, resolve_env_ref
from hermclaw.skills.registry import SkillRegistry
from hermclaw.tools.achievements import BUILTIN_ACHIEVEMENTS
from hermclaw.tools.goals_tool import GoalsDB
from hermclaw.tools.task_tools import _KanbanDB
from hermclaw.tools.virtual_pet import MOOD_EMOTES, PET_ART, VirtualPet

logger = structlog.get_logger(__name__)


class DashboardService:
    """Unified service for the Hermclaw Web Dashboard."""

    def __init__(self, config_path: Optional[Path] = None, profile: str = "default") -> None:
        self.config_path = config_path or default_config_path()
        self.profile = profile
        self.pm = ProfileManager()
        self._runtime: Optional[AgentRuntime] = None
        self._runtime_lock = asyncio.Lock()
        self._started_at = time.time()

    # ------------------------------------------------------------------
    # Runtime & Agent Management
    # ------------------------------------------------------------------

    async def get_runtime(self) -> AgentRuntime:
        """Get or lazily initialize the shared AgentRuntime for the active profile."""
        async with self._runtime_lock:
            if self._runtime is None:
                config_result = load_config(self.config_path)
                if not config_result.valid or config_result.config is None:
                    raise RuntimeError(f"Config is invalid: {config_result.errors}")
                self._runtime = await build_agent_runtime(self.profile, config_result.config, self.pm)
            return self._runtime

    async def reload_runtime(self) -> None:
        """Reload the agent runtime (e.g. after config changes)."""
        async with self._runtime_lock:
            if self._runtime is not None:
                try:
                    await self._runtime.aclose()
                except Exception as exc:
                    logger.warning("runtime.close_error", error=str(exc))
                self._runtime = None
        await self.get_runtime()

    def get_config(self) -> dict[str, Any]:
        """Return the current redacted configuration dict."""
        res = load_config(self.config_path)
        if not res.config:
            return {}
        return redact(res.config.model_dump(by_alias=True))

    def get_raw_config_text(self) -> str:
        """Return the raw hermclaw.yaml text."""
        if self.config_path.exists():
            return self.config_path.read_text(encoding="utf-8")
        return ""

    def save_raw_config_text(self, raw_text: str) -> tuple[bool, list[str]]:
        """Validate and save raw YAML text to hermclaw.yaml."""
        from hermclaw.config import _validate_dict, _yaml

        try:
            parsed = dict(_yaml.load(raw_text) or {})
        except Exception as exc:
            return False, [f"YAML parse error: {exc}"]

        new_config, errors = _validate_dict(parsed)
        if new_config is None:
            return False, errors

        try:
            save_config_text(raw_text, self.config_path)
            return True, []
        except Exception as exc:
            return False, [str(exc)]

    # ------------------------------------------------------------------
    # Overview & Telemetry
    # ------------------------------------------------------------------

    async def get_overview(self) -> dict[str, Any]:
        """Aggregate stats for the Command Center dashboard view."""
        config_res = load_config(self.config_path)
        config = config_res.config

        model_name = config.brain.model.model_name if config else "unknown"
        provider = config.brain.model.provider if config else "unknown"

        # Check Ollama connection
        ollama_online, ollama_models = await self.check_ollama()

        # Session count
        session_count = 0
        try:
            runtime = await self.get_runtime()
            recent_sessions = await runtime.memory_store.a_get_recent_sessions(n=500)
            session_count = len(recent_sessions)
        except Exception:
            pass

        # Skills count
        skills_info = self.get_skills()
        auto_skills = [s for s in skills_info if s.get("auto_generated")]

        # Learning graph count
        graph_stats = self.get_learning_graph_stats()

        # Tasks & Goals
        kanban_data = self.get_kanban_summary()
        goals_data = self.get_goals_summary()

        # Virtual Pet
        pet_data = self.get_pet()

        # System resources
        system_stats = self.get_system_metrics()

        return {
            "profile": self.profile,
            "profiles_available": self.pm.list_profiles(),
            "model": {
                "name": model_name,
                "provider": provider,
                "ollama_online": ollama_online,
                "available_models": ollama_models,
            },
            "stats": {
                "total_sessions": session_count,
                "total_skills": len(skills_info),
                "auto_skills": len(auto_skills),
                "total_concepts": graph_stats.get("total_concepts", 0),
                "total_relationships": graph_stats.get("total_relationships", 0),
                "active_goals": goals_data.get("active", 0),
                "completed_goals": goals_data.get("completed", 0),
                "total_tasks": kanban_data.get("total_tasks", 0),
                "todo_count": kanban_data.get("todos_pending", 0),
                "pet_level": pet_data.get("level", 1),
                "pet_mood": pet_data.get("mood", "happy"),
                "pet_stage": pet_data.get("stage", "egg"),
            },
            "system": system_stats,
            "uptime_seconds": round(time.time() - self._started_at, 1),
        }

    async def check_ollama(self) -> tuple[bool, list[str]]:
        """Check if local Ollama daemon is reachable and list models."""
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                res = await client.get("http://localhost:11434/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
                    return True, models
        except Exception:
            pass
        return False, []

    def get_system_metrics(self) -> dict[str, Any]:
        """Live CPU, RAM, Disk, and host details."""
        cpu_percent = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(str(Path.home()))

        return {
            "cpu_percent": cpu_percent,
            "ram_percent": mem.percent,
            "ram_used_mb": round(mem.used / (1024 * 1024), 1),
            "ram_total_mb": round(mem.total / (1024 * 1024), 1),
            "disk_percent": disk.percent,
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": psutil.cpu_count(logical=True),
        }

    # ------------------------------------------------------------------
    # Chat & Session Management
    # ------------------------------------------------------------------

    async def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        """List recent chat sessions."""
        runtime = await self.get_runtime()
        sessions = await runtime.memory_store.a_get_recent_sessions(n=limit)
        results = []
        for s in sessions:
            results.append({
                "id": s.id,
                "title": s.title or f"Session {s.id[:8]}",
                "channel": getattr(s, "channel", "web-dashboard"),
                "started_at": str(s.started_at)[:19] if s.started_at else "",
                "total_tokens": getattr(s, "total_tokens", 0) or 0,
            })
        return results

    async def get_session_messages(self, session_id: str) -> list[dict[str, Any]]:
        """Get all messages for a specific session."""
        runtime = await self.get_runtime()
        messages = await runtime.memory_store.a_get_session_messages(session_id, include_compressed_away=True)
        results = []
        for m in messages:
            tool_calls = []
            if m.tool_calls:
                for tc in m.tool_calls:
                    tool_calls.append({
                        "name": tc.name if hasattr(tc, "name") else tc.get("name", ""),
                        "arguments": tc.arguments if hasattr(tc, "arguments") else tc.get("arguments", {}),
                    })
            results.append({
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": str(m.created_at)[:19] if m.created_at else "",
                "tool_calls": tool_calls,
                "tokens": getattr(m, "tokens", 0) or 0,
            })
        return results

    async def create_session(self, title: Optional[str] = None) -> str:
        """Create a new session and return its ID."""
        runtime = await self.get_runtime()
        config_res = load_config(self.config_path)
        model_name = config_res.config.brain.model.model_name if config_res.config else "default"
        sid = await runtime.memory_store.a_create_session(channel="web-dashboard", model=model_name)
        if title:
            paths = self.pm.ensure_profile(self.profile)
            conn = sqlite3.connect(str(paths.state_db))
            try:
                conn.execute("UPDATE sessions SET title = ? WHERE id = ?", (title, sid))
                conn.commit()
            finally:
                conn.close()
        return sid

    async def send_message(self, session_id: str, message: str) -> dict[str, Any]:
        """Run an agent turn on a session and capture response and tool calls."""
        runtime = await self.get_runtime()

        start_time = time.time()
        turn_result = await runtime.agent.run_turn(session_id, message)
        elapsed = round(time.time() - start_time, 2)

        # Extract tool calls performed in this turn
        tools_executed = []
        for step in getattr(turn_result, "steps", []):
            if hasattr(step, "tool_call"):
                tc = step.tool_call
                tools_executed.append({
                    "name": tc.name if hasattr(tc, "name") else getattr(tc, "tool_name", "tool"),
                    "arguments": tc.arguments if hasattr(tc, "arguments") else {},
                    "output": str(getattr(step, "tool_result", ""))[:1000],
                })

        return {
            "text": turn_result.text,
            "session_id": session_id,
            "elapsed_seconds": elapsed,
            "input_tokens": turn_result.usage.input_tokens if turn_result.usage else 0,
            "output_tokens": turn_result.usage.output_tokens if turn_result.usage else 0,
            "tools_executed": tools_executed,
        }

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session from state.db."""
        paths = self.pm.ensure_profile(self.profile)
        conn = sqlite3.connect(str(paths.state_db))
        try:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
            return True
        except Exception as exc:
            logger.error("session.delete_error", error=str(exc))
            return False
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Skills & Reflection
    # ------------------------------------------------------------------

    def get_skills(self) -> list[dict[str, Any]]:
        """List all skills available to this profile."""
        paths = self.pm.ensure_profile(self.profile)
        config_res = load_config(self.config_path)
        extra = config_res.config.skills.extra_directories if config_res.config else []
        registry = SkillRegistry(directory=paths.skills_dir, extra_directories=extra)
        registry.load()

        skills = []
        for name in registry.names():
            skill = registry.get(name)
            if not skill:
                continue
            skills.append({
                "name": skill.name,
                "description": skill.description,
                "auto_generated": getattr(skill, "auto_generated", False),
                "path": str(skill.path),
                "body": skill.body,
            })
        return skills

    def validate_skills(self) -> list[dict[str, Any]]:
        """Run validation against all skills for the profile."""
        paths = self.pm.ensure_profile(self.profile)
        config_res = load_config(self.config_path)
        extra = config_res.config.skills.extra_directories if config_res.config else []
        registry = SkillRegistry(directory=paths.skills_dir, extra_directories=extra)
        validations = registry.discover()
        return [
            {
                "name": v.skill_path.name,
                "path": str(v.skill_path),
                "passed": v.passed,
                "errors": v.errors,
            }
            for v in validations
        ]

    async def trigger_reflection(self) -> dict[str, Any]:
        """Trigger reflection across recent sessions to distill facts & auto-skills."""
        config_res = load_config(self.config_path)
        if not config_res.config:
            raise RuntimeError("Config not loaded.")

        runtime = await self.get_runtime()
        reflection_result = await run_reflection(
            self.profile,
            runtime.memory_store,
            runtime.identity_files,
            runtime.skill_growth_engine,
            runtime.agent.transport,
        )

        return {
            "sessions_reviewed": reflection_result.sessions_reviewed,
            "facts_saved": reflection_result.facts_saved,
            "user_facts_saved": reflection_result.user_facts_saved,
            "draft_skills_created": reflection_result.draft_skills_created,
            "timestamp": datetime.datetime.now().isoformat(),
        }

    # ------------------------------------------------------------------
    # Learning Graph
    # ------------------------------------------------------------------

    def _get_learning_graph_db(self) -> sqlite3.Connection:
        db_path = hermclaw_home() / "learning_graph.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def get_learning_graph_data(self) -> dict[str, Any]:
        """Return full nodes and edges for network graph visualization."""
        conn = self._get_learning_graph_db()
        try:
            concepts = conn.execute(
                "SELECT id, name, category, description, confidence, usage_count, created_at FROM concepts ORDER BY usage_count DESC"
            ).fetchall()

            relationships = conn.execute(
                """
                SELECT r.id, r.source_id, r.target_id, r.relation_type, r.strength,
                       c1.name as source_name, c2.name as target_name
                FROM relationships r
                JOIN concepts c1 ON r.source_id = c1.id
                JOIN concepts c2 ON r.target_id = c2.id
                """
            ).fetchall()

            nodes = [
                {
                    "id": c["id"],
                    "name": c["name"],
                    "category": c["category"] or "general",
                    "description": c["description"] or "",
                    "confidence": c["confidence"],
                    "usage_count": c["usage_count"],
                }
                for c in concepts
            ]

            edges = [
                {
                    "id": r["id"],
                    "source": r["source_id"],
                    "target": r["target_id"],
                    "source_name": r["source_name"],
                    "target_name": r["target_name"],
                    "relation_type": r["relation_type"],
                    "strength": r["strength"],
                }
                for r in relationships
            ]

            categories: dict[str, int] = {}
            for n in nodes:
                cat = n["category"]
                categories[cat] = categories.get(cat, 0) + 1

            return {
                "nodes": nodes,
                "edges": edges,
                "categories": categories,
                "total_concepts": len(nodes),
                "total_relationships": len(edges),
            }
        except sqlite3.OperationalError:
            return {"nodes": [], "edges": [], "categories": {}, "total_concepts": 0, "total_relationships": 0}
        finally:
            conn.close()

    def get_learning_graph_stats(self) -> dict[str, Any]:
        """Quick summary of learning graph."""
        data = self.get_learning_graph_data()
        return {
            "total_concepts": data["total_concepts"],
            "total_relationships": data["total_relationships"],
            "categories": data["categories"],
        }

    def add_learning_concept(self, name: str, category: str = "general", description: str = "", confidence: float = 0.5) -> str:
        """Add a concept to the learning graph."""
        from hermclaw.brain.learning_graph import LearningGraph
        graph = LearningGraph()
        try:
            return graph.add_concept(name, category, description, confidence)
        finally:
            graph.close()

    def add_learning_relationship(self, source_name: str, target_name: str, relation_type: str = "related_to", strength: float = 0.5) -> str:
        """Add a relation between two concepts."""
        from hermclaw.brain.learning_graph import LearningGraph
        graph = LearningGraph()
        try:
            return graph.add_relationship(source_name, target_name, relation_type, strength)
        finally:
            graph.close()

    # ------------------------------------------------------------------
    # Memory & Identity Vault
    # ------------------------------------------------------------------

    def get_identity_file(self, file_type: str) -> str:
        """Read MEMORY.md, USER.md, or SOUL.md."""
        paths = self.pm.ensure_profile(self.profile)
        mapping = {
            "memory": paths.memory_md,
            "user": paths.user_md,
            "soul": paths.soul_md,
        }
        target = mapping.get(file_type.lower())
        if not target or not target.exists():
            return ""
        return target.read_text(encoding="utf-8")

    def save_identity_file(self, file_type: str, content: str) -> bool:
        """Save MEMORY.md, USER.md, or SOUL.md with automatic timestamped backup."""
        paths = self.pm.ensure_profile(self.profile)
        mapping = {
            "memory": paths.memory_md,
            "user": paths.user_md,
            "soul": paths.soul_md,
        }
        target = mapping.get(file_type.lower())
        if not target:
            return False

        # Make backup
        if target.exists():
            backup_path = target.with_suffix(f".bak.{int(time.time())}")
            try:
                backup_path.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
            except Exception:
                pass

        target.write_text(content, encoding="utf-8")
        return True

    async def search_vector_memory(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search vector memory for semantic matches."""
        try:
            runtime = await self.get_runtime()
            if runtime.vector_memory is not None:
                results = await runtime.vector_memory.a_search(query, limit=limit)
                return [
                    {
                        "content": r.content if hasattr(r, "content") else str(r),
                        "score": getattr(r, "score", 0.0),
                        "metadata": getattr(r, "metadata", {}),
                    }
                    for r in results
                ]
        except Exception as exc:
            logger.debug("vector_memory.search_error", error=str(exc))
        return []

    # ------------------------------------------------------------------
    # Tasks (Kanban & Todos)
    # ------------------------------------------------------------------

    def _get_kanban_db(self) -> _KanbanDB:
        db_path = hermclaw_home() / "kanban.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return _KanbanDB(db_path)

    def get_kanban_summary(self) -> dict[str, int]:
        db = self._get_kanban_db()
        try:
            boards = db.list_boards()
            total_tasks = 0
            if boards:
                board_data = db.get_board(boards[0]["id"])
                if board_data:
                    for col in board_data.get("columns", []):
                        total_tasks += len(col.get("tasks", []))
            todos = db.list_todos(show_done=False)
            return {"total_tasks": total_tasks, "todos_pending": len(todos)}
        finally:
            db.close()

    def get_kanban_board(self, board_id: Optional[str] = None) -> dict[str, Any]:
        """Fetch Kanban board with columns and tasks."""
        db = self._get_kanban_db()
        try:
            boards = db.list_boards()
            if not boards:
                # Initialize default project board
                bid = db.create_board("Default Project")
                boards = db.list_boards()

            target_id = board_id or boards[0]["id"]
            board = db.get_board(target_id)
            return {
                "boards": boards,
                "current_board": board or {"columns": []},
            }
        finally:
            db.close()

    def add_kanban_task(self, board_id: str, column_name: str, title: str, description: str = "", priority: str = "medium") -> str:
        db = self._get_kanban_db()
        try:
            return db.add_task(board_id=board_id, title=title, description=description, priority=priority, column_name=column_name)
        finally:
            db.close()

    def move_kanban_task(self, task_id: str, column_name: str) -> bool:
        db = self._get_kanban_db()
        try:
            return db.move_task(task_id, column_name)
        finally:
            db.close()

    def delete_kanban_task(self, task_id: str) -> bool:
        db_path = hermclaw_home() / "kanban.db"
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("DELETE FROM kb_tasks WHERE id = ?", (task_id,))
            conn.commit()
            return True
        finally:
            conn.close()

    def get_todos(self, show_done: bool = True) -> list[dict[str, Any]]:
        db = self._get_kanban_db()
        try:
            return db.list_todos(show_done=show_done)
        finally:
            db.close()

    def add_todo(self, text: str, priority: str = "medium") -> str:
        db = self._get_kanban_db()
        try:
            return db.add_todo(text, priority)
        finally:
            db.close()

    def toggle_todo(self, todo_id: str, done: bool) -> bool:
        db_path = hermclaw_home() / "kanban.db"
        conn = sqlite3.connect(str(db_path))
        try:
            now = time.time() if done else None
            conn.execute("UPDATE todos SET done = ?, completed_at = ? WHERE id = ?", (1 if done else 0, now, todo_id))
            conn.commit()
            return True
        finally:
            conn.close()

    def delete_todo(self, todo_id: str) -> bool:
        db_path = hermclaw_home() / "kanban.db"
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
            conn.commit()
            return True
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Autonomous Goals (OKRs)
    # ------------------------------------------------------------------

    def _get_goals_db(self) -> GoalsDB:
        db_path = hermclaw_home() / "goals.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return GoalsDB(db_path)

    def get_goals_summary(self) -> dict[str, int]:
        db = self._get_goals_db()
        try:
            active = len(db.list_active())
            all_goals = db.list_all()
            completed = len([g for g in all_goals if g.get("status") == "completed"])
            return {"active": active, "completed": completed}
        finally:
            db.close()

    def list_goals(self, status: str = "all") -> list[dict[str, Any]]:
        db = self._get_goals_db()
        try:
            if status == "active":
                return db.list_active()
            all_goals = db.list_all()
            if status == "all":
                return all_goals
            return [g for g in all_goals if g.get("status") == status]
        finally:
            db.close()

    def create_goal(self, title: str, description: str = "", priority: str = "medium") -> str:
        db = self._get_goals_db()
        try:
            return db.create(title, description, priority)
        finally:
            db.close()

    def update_goal_progress(self, goal_id: str, progress: int, entry: str = "") -> bool:
        db = self._get_goals_db()
        try:
            ok = db.update_progress(goal_id, progress, entry)
            if progress >= 100:
                db.complete(goal_id)
            return ok
        finally:
            db.close()

    def delete_goal(self, goal_id: str) -> bool:
        db_path = hermclaw_home() / "goals.db"
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("DELETE FROM goal_logs WHERE goal_id = ?", (goal_id,))
            conn.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
            conn.commit()
            return True
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Virtual Pet (Clawbert) & Achievements
    # ------------------------------------------------------------------

    def get_pet(self) -> dict[str, Any]:
        pet = VirtualPet()
        try:
            status = pet.status()
            if "error" in status:
                pet.adopt("Clawbert", "hermit_crab")
                status = pet.status()
            stage = status.get("stage", "egg")
            mood = status.get("mood", "curious")
            art = PET_ART.get(stage, PET_ART["egg"])
            emote = MOOD_EMOTES.get(mood, "(^_^)")
            status["art"] = art
            status["emote"] = emote
            return status
        finally:
            pet.close()

    def pet_action(self, action: str) -> dict[str, Any]:
        """Perform feed, play, or rest action on Clawbert."""
        pet = VirtualPet()
        try:
            status = pet.status()
            if "error" in status:
                pet.adopt("Clawbert", "hermit_crab")

            if action == "feed":
                result = pet.feed()
            elif action == "play":
                result = pet.play()
            elif action == "rest":
                result = pet.rest()
            else:
                result = {"error": f"Unknown action {action}"}
            new_status = pet.status()
            stage = new_status.get("stage", "egg")
            new_status["art"] = PET_ART.get(stage, PET_ART["egg"])
            new_status["emote"] = MOOD_EMOTES.get(new_status.get("mood", "happy"), "(^_^)")
            new_status["action_result"] = result
            return new_status
        finally:
            pet.close()

    def get_achievements(self) -> list[dict[str, Any]]:
        """Fetch all achievements and unlock status."""
        db_path = hermclaw_home() / "achievements.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            # Check if table exists
            exists = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='achievements'"
            ).fetchone()
            if not exists:
                from hermclaw.tools.achievements import AchievementsTool
                tool = AchievementsTool()
                return tool.get_all()

            rows = conn.execute("SELECT * FROM achievements ORDER BY unlocked DESC, id ASC").fetchall()
            if not rows:
                from hermclaw.tools.achievements import AchievementsTool
                tool = AchievementsTool()
                return tool.get_all()

            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Tools Directory & Playground
    # ------------------------------------------------------------------

    async def get_tools_catalog(self) -> list[dict[str, Any]]:
        """List all 40+ tools registered in the runtime tool dispatcher."""
        runtime = await self.get_runtime()
        tools_list = []
        for tool in runtime.tool_dispatcher._tools.values():
            spec = tool.spec()
            tools_list.append({
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters,
                "read_only": getattr(spec, "read_only", False),
            })
        tools_list.sort(key=lambda t: t["name"])
        return tools_list

    async def execute_tool_playground(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool directly via the ToolDispatcher playground."""
        runtime = await self.get_runtime()
        tool = runtime.tool_dispatcher._tools.get(tool_name)
        if not tool:
            return {"ok": False, "output": "", "error": f"Tool '{tool_name}' not found."}

        start = time.time()
        try:
            res = await runtime.tool_dispatcher.dispatch(tool_name, arguments)
            return {
                "ok": res.ok,
                "output": res.output,
                "error": res.error,
                "elapsed_seconds": round(time.time() - start, 3),
            }
        except Exception as exc:
            return {
                "ok": False,
                "output": "",
                "error": str(exc),
                "elapsed_seconds": round(time.time() - start, 3),
            }

    # ------------------------------------------------------------------
    # Diagnostics & Doctor
    # ------------------------------------------------------------------

    async def run_diagnostics(self) -> dict[str, Any]:
        """Run full health check suite equivalent to `hermclaw doctor`."""
        checks: list[dict[str, Any]] = []

        # Config validity
        res = load_config(self.config_path)
        checks.append({
            "name": "Config Validity",
            "passed": res.valid,
            "detail": f"Loaded from {self.config_path}" if res.valid else "; ".join(res.errors),
        })

        # Profile state.db
        paths = self.pm.ensure_profile(self.profile)
        db_exists = paths.state_db.exists()
        checks.append({
            "name": f"Profile '{self.profile}' SQLite State DB",
            "passed": db_exists,
            "detail": str(paths.state_db) if db_exists else "Missing (auto-created on first use)",
        })

        # Identity files
        mem_ok = paths.memory_md.exists()
        user_ok = paths.user_md.exists()
        soul_ok = paths.soul_md.exists()
        checks.append({
            "name": "Identity Files (MEMORY.md, USER.md, SOUL.md)",
            "passed": mem_ok and user_ok and soul_ok,
            "detail": f"Memory: {'OK' if mem_ok else 'No'}, User: {'OK' if user_ok else 'No'}, Soul: {'OK' if soul_ok else 'No'}",
        })

        # Gateway auth token
        if res.config:
            token = gateway_token(res.config)
            checks.append({
                "name": "Gateway Auth Token",
                "passed": bool(token),
                "detail": "Configured" if token else "Not set (gateway running in open/local mode)",
            })

        # Ollama connection
        ollama_ok, models = await self.check_ollama()
        checks.append({
            "name": "Ollama Local Service (11434)",
            "passed": ollama_ok,
            "detail": f"Online with {len(models)} model(s): {', '.join(models[:4])}" if ollama_ok else "Offline or unreachable at http://localhost:11434",
        })

        # Skills validation
        skill_validations = self.validate_skills()
        all_skills_passed = all(v["passed"] for v in skill_validations) if skill_validations else True
        checks.append({
            "name": f"Skill Validations ({len(skill_validations)} skills)",
            "passed": all_skills_passed,
            "detail": "All skills passed schema check" if all_skills_passed else f"{sum(1 for v in skill_validations if not v['passed'])} skills have errors",
        })

        return {
            "all_passed": all(c["passed"] for c in checks),
            "checks": checks,
            "config_path": str(self.config_path),
            "timestamp": datetime.datetime.now().isoformat(),
        }

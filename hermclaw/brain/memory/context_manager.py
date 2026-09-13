"""External Context and Memory Manager for Hermclaw.

Upgrades the agent to support effectively unlimited context without increasing the
model's native context window.

Key Features:
1. Working Memory: Keeps only the current task, subtask, recent actions, and immediately
   relevant information in the active LLM context.
2. Long-Term Memory: Stores raw interactions, observations, and decisions externally in SQLite,
   using vector semantic retrieval and FTS5 to pull back only relevant data.
3. Persistent Task State: Tracks overall goal, phase, subtasks, completed tasks, decisions,
   errors, files modified, and next actions across restarts.
4. Automatic Context Compression & Continuation: Detects when context approaches model limits,
   flushes facts, checkpoints state, creates a clean continuation context, and automatically
   continues multi-step execution without user intervention.
5. Hierarchical Memory: Raw events -> Episode summaries -> Task summaries -> Phase summaries -> Global summary.
6. Context Budgeting: Strict token budgeting (System 10%, Task State 15%, Working Memory 20%,
   Retrieved Memory 25%, Files 20%, UI 10%) scaled to any model context window.
7. Memory Importance: Classifies data into temporary, useful, important, critical; only
   important/critical facts are promoted to permanent memory.
8. Checkpointing: Automatic state recovery after crashes, restarts, or context resets.
"""

from __future__ import annotations

import dataclasses
import json
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import structlog

from hermclaw.config import MemoryConfig, ModelConfig

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Task State
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class TaskState:
    session_id: str
    goal: str = ""
    phase: str = "initiation"
    current_subtask: str = ""
    completed_tasks: list[str] = dataclasses.field(default_factory=list)
    pending_tasks: list[str] = dataclasses.field(default_factory=list)
    important_decisions: list[str] = dataclasses.field(default_factory=list)
    errors: list[str] = dataclasses.field(default_factory=list)
    files_modified: list[str] = dataclasses.field(default_factory=list)
    next_action: str = ""
    status: str = "active"  # active, completed, blocked, paused
    updated_at: float = dataclasses.field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskState:
        fields = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in data.items() if k in fields}
        return cls(**filtered)

    def mark_completed(self, task_name: str) -> None:
        if task_name not in self.completed_tasks:
            self.completed_tasks.append(task_name)
        if task_name in self.pending_tasks:
            self.pending_tasks.remove(task_name)
        if self.current_subtask == task_name:
            self.current_subtask = self.pending_tasks[0] if self.pending_tasks else ""
        self.updated_at = time.time()

    def add_file_modified(self, path: str) -> None:
        if path and path not in self.files_modified:
            self.files_modified.append(path)
            self.updated_at = time.time()

    def add_decision(self, decision: str) -> None:
        if decision and decision not in self.important_decisions:
            self.important_decisions.append(decision)
            self.updated_at = time.time()

    def add_error(self, err: str) -> None:
        if err and err not in self.errors:
            self.errors.append(err[:200])
            self.updated_at = time.time()

    def render_prompt_block(self, max_tokens: int = 500) -> str:
        """Render a compact, high-signal task state block for prompt injection."""
        if not self.goal and not self.pending_tasks and not self.completed_tasks:
            return ""

        lines = ["[Current Task State]"]
        if self.goal:
            lines.append(f"Goal: {self.goal}")
        if self.phase:
            lines.append(f"Phase: {self.phase}")
        if self.current_subtask:
            lines.append(f"Active Subtask: {self.current_subtask}")
        if self.completed_tasks:
            lines.append(f"Completed: {', '.join(self.completed_tasks[-5:])}")
        if self.pending_tasks:
            lines.append(f"Pending: {', '.join(self.pending_tasks[:5])}")
        if self.files_modified:
            lines.append(f"Files Modified: {', '.join(self.files_modified[-6:])}")
        if self.errors:
            lines.append(f"Recent Issues: {'; '.join(self.errors[-2:])}")
        if self.next_action:
            lines.append(f"Next Action: {self.next_action}")

        text = "\n".join(lines)
        if len(text) > max_tokens * 4:
            text = text[: max_tokens * 4] + "..."
        return text


# ---------------------------------------------------------------------------
# Database Schema & Initialization
# ---------------------------------------------------------------------------

_CONTEXT_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS task_states (
    session_id TEXT PRIMARY KEY,
    goal TEXT,
    phase TEXT,
    current_subtask TEXT,
    data TEXT NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS checkpoints (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    milestone TEXT,
    task_state TEXT NOT NULL,
    working_memory TEXT NOT NULL,
    metadata TEXT,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_session ON checkpoints(session_id);

CREATE TABLE IF NOT EXISTS raw_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    role TEXT,
    content TEXT NOT NULL,
    metadata TEXT,
    importance TEXT DEFAULT 'useful',
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_raw_events_session ON raw_events(session_id);
CREATE INDEX IF NOT EXISTS idx_raw_events_importance ON raw_events(importance);

CREATE TABLE IF NOT EXISTS hierarchical_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    level INTEGER NOT NULL,
    scope TEXT NOT NULL,
    summary TEXT NOT NULL,
    metadata TEXT,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_summaries_session_level ON hierarchical_summaries(session_id, level);
"""

# ---------------------------------------------------------------------------
# Importance Classification
# ---------------------------------------------------------------------------

_CRITICAL_PATTERNS = [
    re.compile(r"\b(password|credential|api[_-]?key|secret|token|critical|fatal|cannot undo|never delete)\b", re.I),
    re.compile(r"\b(overall goal|main objective|must always|constraint:)\b", re.I),
]

_IMPORTANT_PATTERNS = [
    re.compile(r"\b(wrote file|created file|edited file|modified|patched|installed|configured|decided to)\b", re.I),
    re.compile(r"\b(error:|failed:|exception:|syntaxerror|notfounderror|traceback)\b", re.I),
    re.compile(r"\b(architecture|requirement|endpoint|schema|database|table|function)\b", re.I),
    re.compile(r"\b(completed subtask|milestone reached)\b", re.I),
]

_TEMPORARY_PATTERNS = [
    re.compile(r"\b(ping|pong|heartbeat|progress: \d+%|status check|listening on)\b", re.I),
    re.compile(r"^\s*(\[debug\]|debug:)\b", re.I),
]


def classify_memory_importance(event_type: str, content: str, metadata: Optional[dict[str, Any]] = None) -> str:
    """Classify an event into temporary, useful, important, or critical."""
    content_lower = content.lower()

    if any(p.search(content) for p in _CRITICAL_PATTERNS):
        return "critical"

    if event_type in ("file_write", "file_edit", "patch", "decision", "error", "checkpoint"):
        return "important"

    if any(p.search(content) for p in _IMPORTANT_PATTERNS):
        return "important"

    if any(p.search(content) for p in _TEMPORARY_PATTERNS):
        return "temporary"

    # Default tool reads and queries are useful
    return "useful"


# ---------------------------------------------------------------------------
# Context Budgeting
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class BudgetAllocation:
    system_tokens: int
    task_state_tokens: int
    recent_actions_tokens: int
    retrieved_memory_tokens: int
    relevant_files_tokens: int
    current_observation_tokens: int
    total_budget: int

    @classmethod
    def calculate(cls, context_window: int, max_context_percent: float = 0.75) -> BudgetAllocation:
        effective_budget = max(1024, int(context_window * max_context_percent))

        # Standard allocation ratios:
        # System: 10%, Task State: 15%, Recent Actions: 20%,
        # Retrieved Memory: 25%, Files/Data: 20%, Observation: 10%
        sys_t = int(effective_budget * 0.10)
        state_t = int(effective_budget * 0.15)
        actions_t = int(effective_budget * 0.20)
        memory_t = int(effective_budget * 0.25)
        files_t = int(effective_budget * 0.20)
        obs_t = int(effective_budget * 0.10)

        return cls(
            system_tokens=max(200, sys_t),
            task_state_tokens=max(200, state_t),
            recent_actions_tokens=max(300, actions_t),
            retrieved_memory_tokens=max(300, memory_t),
            relevant_files_tokens=max(200, files_t),
            current_observation_tokens=max(150, obs_t),
            total_budget=effective_budget,
        )


# ---------------------------------------------------------------------------
# UI / Vision State Compactizer
# ---------------------------------------------------------------------------


def compact_ui_observation(content: str | list | dict) -> str:
    """Convert large UI/screen observations into compact structured representations."""
    if isinstance(content, dict):
        # Already structured
        elements = content.get("elements", [])
        title = content.get("title", "Active Screen")
        return f"[UI State: Window='{title}', Elements={len(elements)} interactive controls]"

    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "image_url" or "image" in item:
                    text_parts.append("[Screenshot captured: Full resolution stored externally]")
                elif "text" in item:
                    text_parts.append(str(item["text"]))
            else:
                text_parts.append(str(item))
        return "\n".join(text_parts)

    content_str = str(content)
    # Check for large base64 or raw image strings
    if "data:image/" in content_str or ";base64," in content_str or len(content_str) > 10000 and "==" in content_str:
        return "[Screenshot data stored externally in session media cache]"

    return content_str[:2000]


def normalize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ensure message list alternates roles and starts with 'user' without consecutive same-role messages."""
    if not messages:
        return []
    normalized: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if normalized and normalized[-1]["role"] == role:
            prev_content = normalized[-1]["content"]
            if isinstance(prev_content, str) and isinstance(content, str):
                normalized[-1]["content"] = prev_content + "\n\n" + content
            elif isinstance(prev_content, list) and isinstance(content, list):
                normalized[-1]["content"] = prev_content + content
            elif isinstance(prev_content, list):
                normalized[-1]["content"] = prev_content + [{"type": "text", "text": str(content)}]
            else:
                normalized[-1]["content"] = [
                    {"type": "text", "text": str(prev_content)},
                    {"type": "text", "text": str(content)},
                ]
        else:
            normalized.append(dict(msg))

    if normalized and normalized[0]["role"] != "user":
        normalized.insert(0, {"role": "user", "content": "Proceed with active task."})

    return normalized


# ---------------------------------------------------------------------------
# Context & Memory Manager
# ---------------------------------------------------------------------------


class ContextManager:
    """External Context & Memory Manager for Hermclaw."""

    def __init__(
        self,
        db_path: Path,
        config: Optional[MemoryConfig] = None,
        vector_memory: Optional[Any] = None,
    ) -> None:
        self.db_path = db_path
        self.config = config or MemoryConfig()
        self.vector_memory = vector_memory
        self._db = sqlite3.connect(str(db_path))
        self._db.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self._db.executescript(_CONTEXT_DB_SCHEMA)
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    # -----------------------------------------------------------------------
    # Task State Management
    # -----------------------------------------------------------------------

    def get_task_state(self, session_id: str) -> TaskState:
        """Fetch or initialize TaskState for a session."""
        row = self._db.execute(
            "SELECT data FROM task_states WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row:
            try:
                d = json.loads(row["data"])
                return TaskState.from_dict(d)
            except Exception:
                pass
        return TaskState(session_id=session_id)

    def save_task_state(self, state: TaskState) -> None:
        """Persist TaskState to SQLite."""
        state.updated_at = time.time()
        self._db.execute(
            """
            INSERT INTO task_states (session_id, goal, phase, current_subtask, data, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                goal = excluded.goal,
                phase = excluded.phase,
                current_subtask = excluded.current_subtask,
                data = excluded.data,
                updated_at = excluded.updated_at
            """,
            (
                state.session_id,
                state.goal,
                state.phase,
                state.current_subtask,
                json.dumps(state.to_dict()),
                state.updated_at,
            ),
        )
        self._db.commit()

    def initialize_task_from_prompt(self, session_id: str, user_message: str) -> TaskState:
        """Extract goal and subtasks from an initial user prompt."""
        state = self.get_task_state(session_id)
        if not state.goal:
            state.goal = user_message.strip().split("\n")[0][:250]

        # Simple heuristic subtask decomposition if user prompt contains steps
        if not state.pending_tasks:
            subtasks = []
            for line in user_message.split("\n"):
                line_clean = line.strip()
                if re.match(r"^(\d+\.|\-|\*)\s+", line_clean):
                    clean_task = re.sub(r"^(\d+\.|\-|\*)\s+", "", line_clean)
                    if len(clean_task) > 5:
                        subtasks.append(clean_task[:150])
            if not subtasks and " and " in user_message:
                parts = user_message.split(" and ")
                if len(parts) >= 2:
                    subtasks = [p.strip()[:150] for p in parts if len(p.strip()) > 8]

            if subtasks:
                state.pending_tasks = subtasks
                state.current_subtask = subtasks[0]
            else:
                state.current_subtask = state.goal

        self.save_task_state(state)
        return state

    # -----------------------------------------------------------------------
    # Checkpoints
    # -----------------------------------------------------------------------

    def save_checkpoint(
        self,
        session_id: str,
        milestone: str,
        working_memory: list[dict[str, Any]],
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Create a durable checkpoint of TaskState and working memory."""
        state = self.get_task_state(session_id)
        cid = f"chk_{uuid.uuid4().hex[:12]}"
        self.save_task_state(state)

        self._db.execute(
            """
            INSERT INTO checkpoints (id, session_id, milestone, task_state, working_memory, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cid,
                session_id,
                milestone,
                json.dumps(state.to_dict()),
                json.dumps(working_memory),
                json.dumps(metadata or {}),
                time.time(),
            ),
        )
        self._db.commit()
        logger.info("context_manager.checkpoint_saved", checkpoint_id=cid, milestone=milestone)
        return cid

    def get_latest_checkpoint(self, session_id: str) -> Optional[dict[str, Any]]:
        """Retrieve the latest checkpoint for recovery."""
        row = self._db.execute(
            "SELECT * FROM checkpoints WHERE session_id = ? ORDER BY created_at DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "session_id": row["session_id"],
            "milestone": row["milestone"],
            "task_state": json.loads(row["task_state"]),
            "working_memory": json.loads(row["working_memory"]),
            "created_at": row["created_at"],
        }

    def restore_from_checkpoint(self, session_id: str) -> Optional[tuple[TaskState, list[dict[str, Any]]]]:
        """Restore TaskState and working memory from the latest checkpoint."""
        chk = self.get_latest_checkpoint(session_id)
        if not chk:
            return None
        state = TaskState.from_dict(chk["task_state"])
        self.save_task_state(state)
        return state, chk["working_memory"]

    # -----------------------------------------------------------------------
    # Event Logging & Hierarchical Memory
    # -----------------------------------------------------------------------

    async def record_event(
        self,
        session_id: str,
        event_type: str,
        content: str,
        role: str = "assistant",
        metadata: Optional[dict[str, Any]] = None,
    ) -> int:
        """Log a raw interaction event, classify importance, and promote if critical."""
        importance = classify_memory_importance(event_type, content, metadata)
        cur = self._db.execute(
            """
            INSERT INTO raw_events (session_id, event_type, role, content, metadata, importance, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                event_type,
                role,
                content,
                json.dumps(metadata or {}),
                importance,
                time.time(),
            ),
        )
        self._db.commit()
        event_id = cur.lastrowid

        # Update task state if files were modified or errors occurred
        state = self.get_task_state(session_id)
        if event_type in ("file_write", "file_edit", "patch") and metadata and metadata.get("path"):
            state.add_file_modified(metadata["path"])
            self.save_task_state(state)
        elif event_type == "error":
            state.add_error(content[:200])
            self.save_task_state(state)

        # Promote Important and Critical events to semantic vector memory
        if importance in ("important", "critical") and self.vector_memory:
            cat = "event_" + event_type
            summary = f"[{importance.upper()}] {event_type}: {content[:300]}"
            try:
                await self.vector_memory.store(
                    summary,
                    category=cat,
                    metadata={"session_id": session_id, "importance": importance, "event_id": event_id},
                )
            except Exception as exc:
                logger.debug("context_manager.vector_store_failed", error=str(exc))

        return event_id

    def add_hierarchical_summary(
        self,
        session_id: str,
        level: int,
        scope: str,
        summary: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Store hierarchical memory summaries (Level 2: Episode, 3: Task, 4: Phase, 5: Global)."""
        self._db.execute(
            """
            INSERT INTO hierarchical_summaries (session_id, level, scope, summary, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, level, scope, summary, json.dumps(metadata or {}), time.time()),
        )
        self._db.commit()
        logger.info("context_manager.hierarchical_summary_added", level=level, scope=scope)

    def create_episode_summary(self, session_id: str, summary: str, metadata: Optional[dict[str, Any]] = None) -> None:
        """Level 2: Episode summary (recent actions and subtask progress)."""
        self.add_hierarchical_summary(session_id, level=2, scope="episode", summary=summary, metadata=metadata)

    def create_task_summary(self, session_id: str, task_name: str, summary: str, metadata: Optional[dict[str, Any]] = None) -> None:
        """Level 3: Task summary for a completed subtask or task."""
        self.add_hierarchical_summary(session_id, level=3, scope=f"task:{task_name}", summary=summary, metadata=metadata)

    def create_phase_summary(self, session_id: str, phase_name: str, summary: str, metadata: Optional[dict[str, Any]] = None) -> None:
        """Level 4: Phase summary across a major milestone/phase."""
        self.add_hierarchical_summary(session_id, level=4, scope=f"phase:{phase_name}", summary=summary, metadata=metadata)

    def create_global_summary(self, session_id: str, summary: str, metadata: Optional[dict[str, Any]] = None) -> None:
        """Level 5: Global project / long-term persistent summary."""
        self.add_hierarchical_summary(session_id, level=5, scope="global", summary=summary, metadata=metadata)

    def get_latest_summaries(self, session_id: str, limit: int = 3) -> list[dict[str, Any]]:
        rows = self._db.execute(
            """
            SELECT * FROM hierarchical_summaries
            WHERE session_id = ?
            ORDER BY level DESC, created_at DESC LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    # -----------------------------------------------------------------------
    # Intelligent Dynamic Retrieval
    # -----------------------------------------------------------------------

    async def retrieve_relevant_memories(
        self,
        query: str,
        session_id: str,
        limit: int = 5,
        max_tokens: int = 800,
    ) -> list[str]:
        """Semantically retrieve relevant facts, decisions, and previous solutions."""
        retrieved: list[str] = []
        if self.vector_memory:
            try:
                results = await self.vector_memory.search(query, limit=limit)
                for r in results:
                    content = r.get("content", "").strip()
                    if content and content not in retrieved:
                        retrieved.append(content)
            except Exception as exc:
                logger.debug("context_manager.retrieval_failed", error=str(exc))

        # Also pull from recent hierarchical summaries
        summaries = self.get_latest_summaries(session_id, limit=2)
        for s in summaries:
            summary_txt = f"Summary ({s['scope']}): {s['summary']}"
            if summary_txt not in retrieved:
                retrieved.append(summary_txt)

        # Truncate to budget
        budget_chars = max_tokens * 4
        final_list = []
        cur_len = 0
        for item in retrieved:
            if cur_len + len(item) > budget_chars:
                break
            final_list.append(item)
            cur_len += len(item)

        return final_list

    # -----------------------------------------------------------------------
    # Budgeted Context Assembly
    # -----------------------------------------------------------------------

    async def build_budgeted_context(
        self,
        session_id: str,
        user_message: str,
        system_prompt: str,
        all_messages: list[dict[str, Any]],
        model_config: ModelConfig,
    ) -> list[dict[str, Any]]:
        """Construct a balanced, compact context respecting model token boundaries.

        Allocates tokens across:
        - System instructions
        - Task state & subtask progress
        - Relevant retrieved memories
        - Recent working memory (tail of conversation)
        """
        budget = BudgetAllocation.calculate(
            context_window=model_config.context_window,
            max_context_percent=getattr(self.config, "max_context_percent", 0.75),
        )

        # 1. Task state block
        task_state = self.get_task_state(session_id)
        task_state_block = task_state.render_prompt_block(max_tokens=budget.task_state_tokens)

        # 2. Semantic retrieval based on current task & user message
        retrieval_query = f"{user_message} {task_state.current_subtask} {task_state.next_action}".strip()
        memories = await self.retrieve_relevant_memories(
            query=retrieval_query,
            session_id=session_id,
            limit=getattr(self.config, "retrieval_count", 5),
            max_tokens=budget.retrieved_memory_tokens,
        )
        memory_block = ""
        if memories:
            memory_block = "[Retrieved Context & Relevant Memories]:\n" + "\n".join(f"- {m}" for m in memories)

        # 3. Context header injection (combined state + memory)
        context_header_parts = []
        if task_state_block:
            context_header_parts.append(task_state_block)
        if memory_block:
            context_header_parts.append(memory_block)

        injected_header = "\n\n".join(context_header_parts)

        # 4. Working memory: keep the N most recent exchanges
        keep_n = getattr(self.config, "recent_interactions_count", 4) * 2
        working_tail = all_messages[-keep_n:] if len(all_messages) > keep_n else all_messages

        assembled: list[dict[str, Any]] = []

        # If we have an injected header, place it in an initial system/user instruction block
        if injected_header:
            assembled.append({"role": "user", "content": f"[Active Context & Task Management]\n{injected_header}"})
            assembled.append({"role": "assistant", "content": "Acknowledged. Continuing with active task state."})

        # Append working tail with compact UI observations
        for m in working_tail:
            content = m.get("content", "")
            # Compact any huge observations
            compact_content = compact_ui_observation(content)
            assembled.append({"role": m.get("role", "user"), "content": compact_content})

        return normalize_messages(assembled)

    # -----------------------------------------------------------------------
    # Auto-Compression & Continuation Context Construction
    # -----------------------------------------------------------------------

    def should_compress_context(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        model_config: ModelConfig,
    ) -> bool:
        """Determine if active prompt size crosses the context budget threshold."""
        total_chars = len(system_prompt)
        for m in messages:
            c = m.get("content", "")
            total_chars += len(str(c))
        estimated_tokens = total_chars // 4

        max_allowed = int(model_config.context_window * getattr(self.config, "max_context_percent", 0.75))
        return estimated_tokens >= max_allowed

    async def compress_and_create_continuation(
        self,
        session_id: str,
        working_messages: list[dict[str, Any]],
        summarizer_func: Optional[Callable[[list[dict[str, Any]]], Any]] = None,
    ) -> Tuple[str, list[dict[str, Any]]]:
        """Summarize working memory, persist task state, and return a clean continuation context."""
        state = self.get_task_state(session_id)

        # 1. Generate Episode Summary
        if summarizer_func:
            try:
                summary = await summarizer_func(working_messages)
            except Exception as exc:
                summary = f"Execution progressed through {len(working_messages)} actions. Subtask: {state.current_subtask}."
        else:
            summary = f"Completed subtasks: {', '.join(state.completed_tasks[-3:])}. Files: {', '.join(state.files_modified[-3:])}."

        self.add_hierarchical_summary(session_id, level=2, scope=state.current_subtask or "episode", summary=summary)

        # 2. Checkpoint state
        self.save_checkpoint(session_id, milestone="auto_compression", working_memory=working_messages)

        # 3. Create continuation context
        continuation_messages: list[dict[str, Any]] = []

        header = (
            f"[Context Auto-Compressed]\n"
            f"Previous Episode Summary: {summary}\n\n"
            f"{state.render_prompt_block()}\n\n"
            f"Continue executing the next action automatically."
        )
        continuation_messages.append({"role": "user", "content": header})
        continuation_messages.append({"role": "assistant", "content": "Context refreshed. Proceeding with next action."})

        # Keep only the single most recent exchange for continuity
        if len(working_messages) >= 2:
            continuation_messages.extend(working_messages[-2:])

        logger.info("context_manager.continuation_created", session_id=session_id)
        return summary, normalize_messages(continuation_messages)

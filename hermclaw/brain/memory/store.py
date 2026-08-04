"""SQLite-backed persistent memory, one database file per profile.

Ported from Hermes Agent's ~/.hermes/state.db: same schema shape, same
WAL-mode rationale (a concurrent reader like `hermclaw status` never
blocks an in-progress agent turn's writes), same FTS5-backed
session_search episodic-recall tool. Uses the stdlib `sqlite3` module,
per the build spec, wrapped with a lock plus asyncio.to_thread helpers so
it's safe to call from the async agent loop without blocking the event
loop or racing concurrent callers.
"""

from __future__ import annotations

import asyncio
import dataclasses
import datetime
import json
import re
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any, Optional

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _sanitize_fts_query(query: str) -> str:
    """Turn free-text user input into a safe FTS5 MATCH expression: each
    word becomes a quoted phrase token, OR'd together, so punctuation in
    the input can never be interpreted as FTS5 query syntax."""
    tokens = re.findall(r"\w+", query)
    if not tokens:
        return '""'
    return " OR ".join(f'"{t}"' for t in tokens)


@dataclasses.dataclass
class MessageHit:
    message_id: int
    session_id: str
    role: str
    content: str
    created_at: str
    rank: float = 0.0


@dataclasses.dataclass
class SessionRow:
    id: str
    channel: Optional[str]
    model: Optional[str]
    started_at: Optional[str]
    ended_at: Optional[str]
    token_count: int
    cost_usd: float
    title: Optional[str]
    parent_session_id: Optional[str]


@dataclasses.dataclass
class MessageRow:
    id: int
    session_id: str
    role: str
    content: str
    tool_calls: Optional[list[dict[str, Any]]]
    reasoning_tokens: int
    created_at: str
    compressed_away: bool


def _row_to_session(row: sqlite3.Row) -> SessionRow:
    return SessionRow(
        id=row["id"], channel=row["channel"], model=row["model"],
        started_at=row["started_at"], ended_at=row["ended_at"],
        token_count=row["token_count"], cost_usd=row["cost_usd"],
        title=row["title"], parent_session_id=row["parent_session_id"],
    )


def _row_to_message(row: sqlite3.Row) -> MessageRow:
    raw_tc = row["tool_calls"]
    return MessageRow(
        id=row["id"], session_id=row["session_id"], role=row["role"], content=row["content"],
        tool_calls=json.loads(raw_tc) if raw_tc else None,
        reasoning_tokens=row["reasoning_tokens"], created_at=row["created_at"],
        compressed_away=bool(row["compressed_away"]),
    )


class MemoryStore:
    """One instance per (profile). Never holds state for more than one
    profile -- callers are responsible for constructing one MemoryStore
    per profile directory (see brain/profiles.py), which is what makes
    profile isolation testable rather than merely documented."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
            self._conn.commit()
        # sqlite3 creates new files at the process umask (typically 0o644)
        # -- this holds full conversation history, so tighten it to
        # owner-only regardless of umask. WAL mode also creates -wal/-shm
        # sidecar files that inherit the same exposure; lock those down
        # too whenever they exist.
        for suffix in ("", "-wal", "-shm"):
            sidecar = Path(str(self.db_path) + suffix)
            if sidecar.exists():
                try:
                    sidecar.chmod(0o600)
                except OSError:
                    pass

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def create_session(
        self,
        session_id: Optional[str] = None,
        channel: Optional[str] = None,
        model: Optional[str] = None,
        title: Optional[str] = None,
        parent_session_id: Optional[str] = None,
    ) -> str:
        sid = session_id or str(uuid.uuid4())
        with self._lock:
            self._conn.execute(
                "INSERT INTO sessions (id, channel, model, started_at, title, parent_session_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (sid, channel, model, _now_iso(), title, parent_session_id),
            )
            self._conn.commit()
        return sid

    def end_session(self, session_id: str) -> None:
        with self._lock:
            self._conn.execute("UPDATE sessions SET ended_at = ? WHERE id = ?", (_now_iso(), session_id))
            self._conn.commit()

    def update_session_usage(self, session_id: str, token_delta: int = 0, cost_usd_delta: float = 0.0) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE sessions SET token_count = token_count + ?, cost_usd = cost_usd + ? WHERE id = ?",
                (token_delta, cost_usd_delta, session_id),
            )
            self._conn.commit()

    def get_session(self, session_id: str) -> Optional[SessionRow]:
        with self._lock:
            row = self._conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return _row_to_session(row) if row else None

    def get_recent_sessions(self, n: int = 20) -> list[SessionRow]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?", (n,)
            ).fetchall()
        return [_row_to_session(r) for r in rows]

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_calls: Optional[list[dict[str, Any]]] = None,
        reasoning_tokens: int = 0,
    ) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO messages (session_id, role, content, tool_calls, reasoning_tokens) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, role, content, json.dumps(tool_calls) if tool_calls is not None else None,
                 reasoning_tokens),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def mark_messages_compressed_away(self, message_ids: list[int]) -> None:
        if not message_ids:
            return
        with self._lock:
            self._conn.executemany(
                "UPDATE messages SET compressed_away = 1 WHERE id = ?", [(mid,) for mid in message_ids]
            )
            self._conn.commit()

    def get_session_messages(self, session_id: str, include_compressed_away: bool = True) -> list[MessageRow]:
        query = "SELECT * FROM messages WHERE session_id = ?"
        params: list[Any] = [session_id]
        if not include_compressed_away:
            query += " AND compressed_away = 0"
        query += " ORDER BY id ASC"
        with self._lock:
            rows = self._conn.execute(query, params).fetchall()
        return [_row_to_message(r) for r in rows]

    def session_search(self, query: str, limit: int = 10) -> list[MessageHit]:
        """Hermes Agent's own episodic-recall mechanism, ported
        field-for-field: FTS5 full-text search, not a LIKE scan, so it
        stays fast as the messages table grows (see the perf acceptance
        test in tests/brain/test_memory_store.py)."""
        sql = (
            "SELECT m.id AS id, m.session_id AS session_id, m.role AS role, "
            "m.content AS content, m.created_at AS created_at, bm25(messages_fts) AS rank "
            "FROM messages_fts JOIN messages m ON m.id = messages_fts.rowid "
            "WHERE messages_fts MATCH ? ORDER BY rank LIMIT ?"
        )
        fts_query = _sanitize_fts_query(query)
        with self._lock:
            rows = self._conn.execute(sql, (fts_query, limit)).fetchall()
        return [
            MessageHit(
                message_id=r["id"], session_id=r["session_id"], role=r["role"],
                content=r["content"], created_at=r["created_at"], rank=r["rank"],
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Async wrappers (agent_loop.py and friends run inside an event loop;
    # sqlite3 is sync, so these hop to a worker thread rather than block it)
    # ------------------------------------------------------------------

    async def a_create_session(self, *args: Any, **kwargs: Any) -> str:
        return await asyncio.to_thread(self.create_session, *args, **kwargs)

    async def a_add_message(self, *args: Any, **kwargs: Any) -> int:
        return await asyncio.to_thread(self.add_message, *args, **kwargs)

    async def a_session_search(self, query: str, limit: int = 10) -> list[MessageHit]:
        return await asyncio.to_thread(self.session_search, query, limit)

    async def a_get_recent_sessions(self, n: int = 20) -> list[SessionRow]:
        return await asyncio.to_thread(self.get_recent_sessions, n)

    async def a_get_session_messages(self, session_id: str, include_compressed_away: bool = True) -> list[MessageRow]:
        return await asyncio.to_thread(self.get_session_messages, session_id, include_compressed_away)

    async def a_mark_messages_compressed_away(self, message_ids: list[int]) -> None:
        await asyncio.to_thread(self.mark_messages_compressed_away, message_ids)

    async def a_update_session_usage(self, session_id: str, token_delta: int = 0, cost_usd_delta: float = 0.0) -> None:
        await asyncio.to_thread(self.update_session_usage, session_id, token_delta, cost_usd_delta)

    async def a_end_session(self, session_id: str) -> None:
        await asyncio.to_thread(self.end_session, session_id)

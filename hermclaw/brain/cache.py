"""Response cache: LRU cache for repeated identical prompts.

Saves API costs and reduces latency for repeated queries.
Uses a hash of the messages + model to key the cache.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)

_CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS response_cache (
    cache_key TEXT PRIMARY KEY,
    model TEXT NOT NULL,
    response_text TEXT NOT NULL,
    tool_calls TEXT DEFAULT '[]',
    usage_json TEXT DEFAULT '{}',
    hit_count INTEGER DEFAULT 0,
    created_at REAL NOT NULL,
    last_hit_at REAL
);
"""


class ResponseCache:
    """SQLite-backed response cache with LRU eviction."""

    def __init__(self, db_path: Optional[Path] = None, max_entries: int = 1000, ttl_hours: float = 24) -> None:
        if db_path is None:
            db_path = Path.home() / ".hermclaw" / "cache.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(db_path))
        self._db.row_factory = sqlite3.Row
        self._db.executescript(_CACHE_SCHEMA)
        self._max_entries = max_entries
        self._ttl_seconds = ttl_hours * 3600
        self._hits = 0
        self._misses = 0

    def close(self) -> None:
        self._db.close()

    @staticmethod
    def _make_key(messages: list[dict], model: str) -> str:
        """Create a deterministic cache key from messages + model."""
        content = json.dumps(messages, sort_keys=True) + f"||{model}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def get(self, messages: list[dict], model: str) -> Optional[dict]:
        """Look up a cached response. Returns None on miss."""
        key = self._make_key(messages, model)
        row = self._db.execute(
            "SELECT * FROM response_cache WHERE cache_key = ?", (key,)
        ).fetchone()

        if not row:
            self._misses += 1
            return None

        # Check TTL
        if time.time() - row["created_at"] > self._ttl_seconds:
            self._db.execute("DELETE FROM response_cache WHERE cache_key = ?", (key,))
            self._db.commit()
            self._misses += 1
            return None

        # Update hit count
        self._db.execute(
            "UPDATE response_cache SET hit_count = hit_count + 1, last_hit_at = ? WHERE cache_key = ?",
            (time.time(), key),
        )
        self._db.commit()
        self._hits += 1

        return {
            "text": row["response_text"],
            "tool_calls": json.loads(row["tool_calls"]),
            "usage": json.loads(row["usage_json"]),
            "cached": True,
        }

    def put(self, messages: list[dict], model: str, response_text: str,
            tool_calls: Optional[list] = None, usage: Optional[dict] = None) -> None:
        """Store a response in the cache."""
        key = self._make_key(messages, model)

        # Don't cache tool-call responses (they have side effects)
        if tool_calls:
            return

        self._db.execute(
            "INSERT OR REPLACE INTO response_cache (cache_key, model, response_text, tool_calls, usage_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                key, model, response_text,
                json.dumps(tool_calls or []),
                json.dumps(usage or {}),
                time.time(),
            ),
        )
        self._db.commit()

        # Evict oldest if over limit
        count = self._db.execute("SELECT COUNT(*) as n FROM response_cache").fetchone()["n"]
        if count > self._max_entries:
            excess = count - self._max_entries
            self._db.execute(
                "DELETE FROM response_cache WHERE cache_key IN "
                "(SELECT cache_key FROM response_cache ORDER BY last_hit_at ASC, created_at ASC LIMIT ?)",
                (excess,),
            )
            self._db.commit()

    def clear(self) -> int:
        """Clear all cached responses. Returns count deleted."""
        cur = self._db.execute("DELETE FROM response_cache")
        self._db.commit()
        return cur.rowcount

    def stats(self) -> dict:
        """Cache statistics."""
        total = self._db.execute("SELECT COUNT(*) as n FROM response_cache").fetchone()["n"]
        return {
            "total_entries": total,
            "max_entries": self._max_entries,
            "ttl_hours": self._ttl_seconds / 3600,
            "session_hits": self._hits,
            "session_misses": self._misses,
            "hit_rate": f"{self._hits / max(1, self._hits + self._misses) * 100:.1f}%",
        }

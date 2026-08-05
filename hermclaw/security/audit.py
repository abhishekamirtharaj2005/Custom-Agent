"""Audit logging system.

Records every tool call, model request, and security-relevant event
in a persistent SQLite audit log. This provides:
- Complete traceability of all agent actions
- Security forensics capability
- Usage analytics
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)

_AUDIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    event_type TEXT NOT NULL,
    tool_name TEXT,
    session_id TEXT,
    profile TEXT,
    details TEXT DEFAULT '{}',
    risk_level TEXT DEFAULT 'low',
    outcome TEXT DEFAULT 'success'
);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_tool ON audit_log(tool_name);
"""


class AuditLogger:
    """Persistent audit logging for all agent actions."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        if db_path is None:
            db_path = Path.home() / ".hermclaw" / "audit.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(db_path))
        self._db.row_factory = sqlite3.Row
        self._db.executescript(_AUDIT_SCHEMA)

    def close(self) -> None:
        self._db.close()

    def log(
        self,
        event_type: str,
        tool_name: Optional[str] = None,
        session_id: Optional[str] = None,
        profile: Optional[str] = None,
        details: Optional[dict] = None,
        risk_level: str = "low",
        outcome: str = "success",
    ) -> None:
        """Record an audit event."""
        self._db.execute(
            "INSERT INTO audit_log (timestamp, event_type, tool_name, session_id, profile, details, risk_level, outcome) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                time.time(),
                event_type,
                tool_name,
                session_id,
                profile,
                json.dumps(details or {}),
                risk_level,
                outcome,
            ),
        )
        self._db.commit()

    def query(
        self,
        event_type: Optional[str] = None,
        tool_name: Optional[str] = None,
        risk_level: Optional[str] = None,
        limit: int = 50,
        since_hours: Optional[float] = None,
    ) -> list[dict]:
        """Query audit logs with filters."""
        conditions = []
        params = []

        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        if tool_name:
            conditions.append("tool_name = ?")
            params.append(tool_name)
        if risk_level:
            conditions.append("risk_level = ?")
            params.append(risk_level)
        if since_hours:
            conditions.append("timestamp > ?")
            params.append(time.time() - (since_hours * 3600))

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT * FROM audit_log {where} ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        rows = self._db.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def stats(self, hours: float = 24) -> dict:
        """Get audit statistics for the last N hours."""
        since = time.time() - (hours * 3600)

        total = self._db.execute(
            "SELECT COUNT(*) as n FROM audit_log WHERE timestamp > ?", (since,)
        ).fetchone()["n"]

        by_type = self._db.execute(
            "SELECT event_type, COUNT(*) as n FROM audit_log WHERE timestamp > ? GROUP BY event_type ORDER BY n DESC",
            (since,),
        ).fetchall()

        by_tool = self._db.execute(
            "SELECT tool_name, COUNT(*) as n FROM audit_log WHERE timestamp > ? AND tool_name IS NOT NULL GROUP BY tool_name ORDER BY n DESC",
            (since,),
        ).fetchall()

        by_risk = self._db.execute(
            "SELECT risk_level, COUNT(*) as n FROM audit_log WHERE timestamp > ? GROUP BY risk_level",
            (since,),
        ).fetchall()

        failures = self._db.execute(
            "SELECT COUNT(*) as n FROM audit_log WHERE timestamp > ? AND outcome != 'success'",
            (since,),
        ).fetchone()["n"]

        return {
            "period_hours": hours,
            "total_events": total,
            "failures": failures,
            "by_type": {r["event_type"]: r["n"] for r in by_type},
            "by_tool": {r["tool_name"]: r["n"] for r in by_tool},
            "by_risk": {r["risk_level"]: r["n"] for r in by_risk},
        }


class RateLimiter:
    """Simple in-memory rate limiter for tools.

    Tracks calls per tool per time window and rejects excess calls.
    """

    def __init__(self, default_rpm: int = 60) -> None:
        self._default_rpm = default_rpm
        self._limits: dict[str, int] = {}  # tool_name -> max calls per minute
        self._windows: dict[str, list[float]] = {}  # tool_name -> list of timestamps

    def set_limit(self, tool_name: str, max_per_minute: int) -> None:
        """Set a per-tool rate limit."""
        self._limits[tool_name] = max_per_minute

    def check(self, tool_name: str) -> tuple[bool, str]:
        """Check if a tool call is allowed. Returns (allowed, reason)."""
        limit = self._limits.get(tool_name, self._default_rpm)
        now = time.time()
        window_start = now - 60

        # Clean old entries
        timestamps = self._windows.get(tool_name, [])
        timestamps = [t for t in timestamps if t > window_start]
        self._windows[tool_name] = timestamps

        if len(timestamps) >= limit:
            return False, f"Rate limit exceeded for {tool_name}: {limit}/min"

        timestamps.append(now)
        return True, ""

    def stats(self) -> dict[str, dict]:
        """Current rate limiter state."""
        now = time.time()
        window_start = now - 60
        result = {}
        for tool, timestamps in self._windows.items():
            recent = [t for t in timestamps if t > window_start]
            limit = self._limits.get(tool, self._default_rpm)
            result[tool] = {
                "calls_last_minute": len(recent),
                "limit_per_minute": limit,
                "remaining": max(0, limit - len(recent)),
            }
        return result


# Global singleton
_audit_logger: Optional[AuditLogger] = None
_rate_limiter: Optional[RateLimiter] = None


def get_audit_logger() -> AuditLogger:
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(default_rpm=120)
        # Set stricter limits for dangerous tools
        _rate_limiter.set_limit("shell", 30)
        _rate_limiter.set_limit("browser", 20)
        _rate_limiter.set_limit("app_launcher", 10)
        _rate_limiter.set_limit("file_write", 60)
        _rate_limiter.set_limit("code_exec", 30)
    return _rate_limiter

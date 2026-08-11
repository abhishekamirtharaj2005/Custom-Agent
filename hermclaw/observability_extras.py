"""Observability extras: trace upload, analytics, context window visualizer,
user journey tracking, prompt size analyzer, billing display.

Implements all remaining Hermes ✅ features from Section 23.
"""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

import httpx
import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Trace upload (send diagnostics to remote endpoint)
# ---------------------------------------------------------------------------


class TraceUploader:
    """Upload traces/diagnostics to a remote observability endpoint."""

    def __init__(self, endpoint: str = "", api_key: str = "") -> None:
        self._endpoint = endpoint or os.environ.get("HERMCLAW_TRACE_ENDPOINT", "")
        self._key = api_key or os.environ.get("HERMCLAW_TRACE_KEY", "")

    async def upload(self, trace: dict[str, Any], trace_type: str = "session") -> bool:
        if not self._endpoint:
            logger.debug("trace.no_endpoint")
            return False

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    self._endpoint,
                    headers={
                        "Authorization": f"Bearer {self._key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "type": trace_type,
                        "timestamp": time.time(),
                        "data": trace,
                    },
                )
                resp.raise_for_status()
                logger.info("trace.uploaded", type=trace_type)
                return True
        except Exception as exc:
            logger.warning("trace.upload_failed", error=str(exc)[:100])
            return False


# ---------------------------------------------------------------------------
# Streaming diagnostics
# ---------------------------------------------------------------------------


class StreamingDiagnostics:
    """Real-time streaming diagnostics for token generation."""

    def __init__(self) -> None:
        self._sessions: dict[str, dict] = {}

    def start_stream(self, session_id: str) -> None:
        self._sessions[session_id] = {
            "started_at": time.time(),
            "tokens": 0,
            "chunks": 0,
            "first_token_time": None,
            "errors": 0,
        }

    def record_chunk(self, session_id: str, token_count: int = 1) -> None:
        session = self._sessions.get(session_id)
        if session:
            session["tokens"] += token_count
            session["chunks"] += 1
            if session["first_token_time"] is None:
                session["first_token_time"] = time.time()

    def record_error(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session:
            session["errors"] += 1

    def end_stream(self, session_id: str) -> dict[str, Any]:
        session = self._sessions.pop(session_id, None)
        if not session:
            return {}

        now = time.time()
        duration = now - session["started_at"]
        ttft = (session["first_token_time"] - session["started_at"]) if session["first_token_time"] else 0

        return {
            "duration_s": round(duration, 2),
            "total_tokens": session["tokens"],
            "total_chunks": session["chunks"],
            "tokens_per_second": round(session["tokens"] / duration, 1) if duration else 0,
            "time_to_first_token_s": round(ttft, 3),
            "errors": session["errors"],
        }


# ---------------------------------------------------------------------------
# Agent insights / analytics
# ---------------------------------------------------------------------------


class AgentInsights:
    """Analytics and insights about agent behavior."""

    def __init__(self) -> None:
        self._tool_usage: dict[str, int] = defaultdict(int)
        self._model_usage: dict[str, int] = defaultdict(int)
        self._session_durations: list[float] = []
        self._error_counts: dict[str, int] = defaultdict(int)
        self._daily_tokens: dict[str, int] = defaultdict(int)

    def record_tool_use(self, tool_name: str) -> None:
        self._tool_usage[tool_name] += 1

    def record_model_use(self, model_name: str) -> None:
        self._model_usage[model_name] += 1

    def record_session(self, duration_s: float) -> None:
        self._session_durations.append(duration_s)

    def record_error(self, error_type: str) -> None:
        self._error_counts[error_type] += 1

    def record_tokens(self, count: int) -> None:
        day = time.strftime("%Y-%m-%d")
        self._daily_tokens[day] += count

    def summary(self) -> dict[str, Any]:
        return {
            "tool_usage": dict(sorted(self._tool_usage.items(), key=lambda x: x[1], reverse=True)),
            "model_usage": dict(self._model_usage),
            "sessions": len(self._session_durations),
            "avg_session_s": sum(self._session_durations) / len(self._session_durations) if self._session_durations else 0,
            "top_errors": dict(sorted(self._error_counts.items(), key=lambda x: x[1], reverse=True)[:5]),
            "daily_tokens": dict(self._daily_tokens),
        }

    def top_tools(self, n: int = 10) -> list[tuple[str, int]]:
        return sorted(self._tool_usage.items(), key=lambda x: x[1], reverse=True)[:n]


# ---------------------------------------------------------------------------
# Context window breakdown visualizer
# ---------------------------------------------------------------------------


class ContextWindowVisualizer:
    """Visualize the context window usage breakdown."""

    def visualize(self, breakdown: dict[str, int], max_tokens: int = 128000) -> str:
        """Create an ASCII visualization of context window usage."""
        total_used = sum(breakdown.values())
        pct_used = (total_used / max_tokens * 100) if max_tokens else 0

        lines = [
            f"📊 Context Window Usage: {total_used:,} / {max_tokens:,} tokens ({pct_used:.1f}%)",
            "═" * 60,
        ]

        # Sort by size
        sorted_items = sorted(breakdown.items(), key=lambda x: x[1], reverse=True)

        for label, tokens in sorted_items:
            pct = tokens / max_tokens * 100 if max_tokens else 0
            bar_len = int(pct / 100 * 40)
            bar = "█" * bar_len + "░" * (40 - bar_len)
            lines.append(f"  {label:<20} {bar} {tokens:>6,} ({pct:.1f}%)")

        # Free space
        free = max_tokens - total_used
        free_pct = free / max_tokens * 100 if max_tokens else 0
        free_bar_len = int(free_pct / 100 * 40)
        free_bar = "▒" * free_bar_len + "░" * (40 - free_bar_len)
        lines.append(f"  {'Free':<20} {free_bar} {free:>6,} ({free_pct:.1f}%)")

        lines.append("═" * 60)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# User journey tracking
# ---------------------------------------------------------------------------


class UserJourneyTracker:
    """Track user interaction patterns and journeys."""

    def __init__(self) -> None:
        self._events: list[dict] = []
        self._sessions: dict[str, list[dict]] = {}

    def track_event(self, event_type: str, details: str = "", session_id: str = "") -> None:
        event = {
            "type": event_type,
            "details": details[:200],
            "timestamp": time.time(),
            "session": session_id,
        }
        self._events.append(event)
        if session_id:
            self._sessions.setdefault(session_id, []).append(event)

    def get_journey(self, session_id: str) -> list[dict]:
        return self._sessions.get(session_id, [])

    def common_patterns(self) -> dict[str, int]:
        """Find common event sequences."""
        patterns: dict[str, int] = defaultdict(int)
        for events in self._sessions.values():
            for i in range(len(events) - 1):
                pattern = f"{events[i]['type']} → {events[i+1]['type']}"
                patterns[pattern] += 1
        return dict(sorted(patterns.items(), key=lambda x: x[1], reverse=True)[:20])

    def funnel(self, steps: list[str]) -> dict[str, int]:
        """Calculate conversion funnel."""
        result = {}
        for step in steps:
            count = sum(1 for events in self._sessions.values()
                       if any(e["type"] == step for e in events))
            result[step] = count
        return result


# ---------------------------------------------------------------------------
# Diagnostics upload
# ---------------------------------------------------------------------------


class DiagnosticsUploader:
    """Upload diagnostic data for support/debugging."""

    def collect(self) -> dict[str, Any]:
        """Collect system diagnostic data."""
        import platform
        import sys

        return {
            "timestamp": time.time(),
            "python_version": sys.version,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "hermclaw_version": self._get_version(),
            "env_keys": self._check_env_keys(),
        }

    def _get_version(self) -> str:
        try:
            from hermclaw import __version__
            return __version__
        except Exception:
            return "unknown"

    def _check_env_keys(self) -> list[str]:
        keys = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"]
        return [k for k in keys if os.environ.get(k)]

    def save(self, output_path: Optional[str] = None) -> str:
        data = self.collect()
        if not output_path:
            output_path = str(Path.home() / ".hermclaw" / "diagnostics" / f"diag_{int(time.time())}.json")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(json.dumps(data, indent=2))
        return output_path


# ---------------------------------------------------------------------------
# Billing / usage display
# ---------------------------------------------------------------------------


class BillingDisplay:
    """Display billing and usage information."""

    # Approximate costs per 1M tokens (USD)
    MODEL_COSTS = {
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4-turbo": {"input": 10.00, "output": 30.00},
        "claude-3.5-sonnet": {"input": 3.00, "output": 15.00},
        "claude-3-opus": {"input": 15.00, "output": 75.00},
        "claude-3-haiku": {"input": 0.25, "output": 1.25},
        "gemini-pro": {"input": 0.50, "output": 1.50},
        "gemini-flash": {"input": 0.075, "output": 0.30},
        "deepseek-chat": {"input": 0.14, "output": 0.28},
    }

    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        costs = self.MODEL_COSTS.get(model, {"input": 1.0, "output": 3.0})
        return (input_tokens * costs["input"] + output_tokens * costs["output"]) / 1_000_000

    def format_usage(self, sessions: list[dict]) -> str:
        """Format usage data as a billing table."""
        lines = [
            "💳 Usage Summary",
            "═" * 60,
            f"  {'Model':<25} {'Input':>8} {'Output':>8} {'Cost':>8}",
            "─" * 60,
        ]

        total_cost = 0.0
        by_model: dict[str, dict] = defaultdict(lambda: {"input": 0, "output": 0})
        for s in sessions:
            model = s.get("model", "unknown")
            by_model[model]["input"] += s.get("input_tokens", 0)
            by_model[model]["output"] += s.get("output_tokens", 0)

        for model, usage in sorted(by_model.items()):
            cost = self.estimate_cost(model, usage["input"], usage["output"])
            total_cost += cost
            lines.append(
                f"  {model:<25} {usage['input']:>7,} {usage['output']:>7,} ${cost:>6.4f}"
            )

        lines.extend([
            "─" * 60,
            f"  {'TOTAL':<25} {'':>8} {'':>8} ${total_cost:>6.4f}",
            "═" * 60,
        ])
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prompt size analyzer
# ---------------------------------------------------------------------------


class PromptSizeAnalyzer:
    """Analyze prompt size and composition."""

    def analyze(self, messages: list[dict], model: str = "gpt-4o") -> dict[str, Any]:
        """Analyze the size of a prompt."""
        total_chars = 0
        by_role: dict[str, int] = defaultdict(int)
        by_type: dict[str, int] = defaultdict(int)

        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, str):
                chars = len(content)
            elif isinstance(content, list):
                chars = sum(len(str(p)) for p in content)
            else:
                chars = len(str(content))

            total_chars += chars
            by_role[role] += chars

            # Classify content type
            if msg.get("tool_calls"):
                by_type["tool_calls"] += chars
            elif role == "system":
                by_type["system_prompt"] += chars
            elif role == "tool":
                by_type["tool_results"] += chars
            else:
                by_type["conversation"] += chars

        # Rough token estimate (1 token ≈ 4 chars)
        est_tokens = total_chars // 4

        return {
            "total_chars": total_chars,
            "estimated_tokens": est_tokens,
            "by_role": dict(by_role),
            "by_type": dict(by_type),
            "message_count": len(messages),
            "largest_message": max(
                (len(str(m.get("content", ""))) for m in messages),
                default=0,
            ),
        }

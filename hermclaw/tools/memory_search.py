"""session_search tool: gives the agent searchable access to past sessions.

This is the agent's episodic recall mechanism -- backed by the same FTS5
full-text search that MemoryStore already exposes, now surfaced as a tool
the model can call within a conversation to look up what happened in
prior sessions.
"""

from __future__ import annotations

from typing import Any

from hermclaw.brain.memory.store import MemoryStore
from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec


class SessionSearchTool(ToolABC):
    """Searches past conversation messages using full-text search."""

    def __init__(self, memory_store: MemoryStore) -> None:
        self._memory_store = memory_store

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="session_search",
            description=(
                "Search your past conversation history across all previous sessions. "
                "Use this to recall what was discussed, what tasks were done, what "
                "the user asked for, or any other context from prior conversations. "
                "Returns matching messages with their session ID, role, and timestamp."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search terms to look for in past conversations.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 10).",
                    },
                },
                "required": ["query"],
            },
            requires_approval_gate=False,
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        query = args.get("query", "")
        limit = int(args.get("limit", 10))

        if not query.strip():
            return ToolResult(ok=False, output="", error="Query cannot be empty.")

        try:
            hits = await self._memory_store.a_session_search(query, limit=limit)
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Search failed: {exc}")

        if not hits:
            return ToolResult(ok=True, output="No matching messages found in past sessions.")

        lines = []
        for h in hits:
            content_preview = h.content[:500] if h.content else ""
            lines.append(
                f"[Session {h.session_id[:8]}] [{h.created_at}] {h.role}: {content_preview}"
            )

        return ToolResult(ok=True, output="\n---\n".join(lines))

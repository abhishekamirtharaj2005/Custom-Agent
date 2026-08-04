"""HermclawAgent: the ReAct-style tool-calling loop at Hermclaw's core.

One turn = one user message in, zero or more tool round-trips, one final
reply out. Scoped strictly to a single (profile, session) pair for the
whole call -- everything it touches (MemoryStore, IdentityFiles,
SkillRegistry, ToolDispatcher) is a per-profile instance handed in by the
caller, never looked up from a global.
"""

from __future__ import annotations

import dataclasses
import json
import logging
from typing import Any, Optional

import structlog

from hermclaw.brain.memory.store import MemoryStore, MessageRow
from hermclaw.brain.profiles import IdentityFiles
from hermclaw.brain.transports.base import AgentResponse, ProviderTransport, ToolCallRequest, TransportError, Usage
from hermclaw.config import ModelConfig
from hermclaw.skills.registry import SkillRegistry
from hermclaw.tools.base import ToolDispatcher, ToolResult

logger = structlog.get_logger(__name__)

DEFAULT_MAX_TOOL_ITERATIONS = 10


# ---------------------------------------------------------------------------
# Canonical (Anthropic-shaped) content-block helpers, shared with
# context compression, which needs to read the same message shape back
# out of a session to build its flush/summarize prompts.
# ---------------------------------------------------------------------------


def text_block(text: str) -> dict[str, Any]:
    return {"type": "text", "text": text}


def tool_use_block(tc: ToolCallRequest) -> dict[str, Any]:
    return {"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.arguments}


def tool_result_block(tool_use_id: str, result: ToolResult) -> dict[str, Any]:
    content = result.output if result.ok else (result.error or "Tool execution failed")
    return {"type": "tool_result", "tool_use_id": tool_use_id, "content": str(content), "is_error": not result.ok}


def assistant_content_from_response(response: AgentResponse) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    if response.text:
        blocks.append(text_block(response.text))
    for tc in response.tool_calls:
        blocks.append(tool_use_block(tc))
    return blocks


def rows_to_canonical_messages(rows: list[MessageRow]) -> list[dict[str, Any]]:
    """Reconstruct the canonical message list the transport expects from
    persisted MessageRow history. `role="tool"` rows (our own storage
    convention -- see MemoryStore) become role="user" tool_result blocks,
    matching Anthropic's convention that tool results travel back on the
    user turn."""
    messages: list[dict[str, Any]] = []
    for row in rows:
        if row.role == "tool":
            try:
                blocks = json.loads(row.content)
            except (json.JSONDecodeError, TypeError):
                blocks = [text_block(row.content)]
            messages.append({"role": "user", "content": blocks})
        elif row.role == "assistant" and row.tool_calls:
            blocks: list[dict[str, Any]] = []
            if row.content:
                blocks.append(text_block(row.content))
            for tc in row.tool_calls:
                blocks.append({"type": "tool_use", "id": tc["id"], "name": tc["name"], "input": tc["arguments"]})
            messages.append({"role": "assistant", "content": blocks})
        else:
            messages.append({"role": row.role, "content": row.content})
    return messages


def add_usage(a: Usage, b: Usage) -> Usage:
    return Usage(
        input_tokens=a.input_tokens + b.input_tokens,
        output_tokens=a.output_tokens + b.output_tokens,
        cache_read_input_tokens=a.cache_read_input_tokens + b.cache_read_input_tokens,
        cache_creation_input_tokens=a.cache_creation_input_tokens + b.cache_creation_input_tokens,
    )


def approx_token_count(messages: list[dict[str, Any]], system: str) -> int:
    """Cheap 4-chars-per-token estimate used only to decide when to hand
    off to the context compressor -- not billed anywhere, so it doesn't
    need provider-exact tokenization."""
    total_chars = len(system)
    for m in messages:
        content = m["content"]
        if isinstance(content, str):
            total_chars += len(content)
        else:
            for block in content:
                total_chars += len(json.dumps(block))
    return total_chars // 4


# ---------------------------------------------------------------------------


@dataclasses.dataclass
class ToolCallRecord:
    name: str
    arguments: dict[str, Any]
    result: ToolResult


@dataclasses.dataclass
class AgentTurnResult:
    session_id: str
    text: str
    tool_calls_made: list[ToolCallRecord]
    stop_reason: str
    usage: Usage
    compressed: bool = False


@dataclasses.dataclass
class FallbackEntry:
    transport: ProviderTransport
    model_config: ModelConfig


class HermclawAgent:
    def __init__(
        self,
        profile: str,
        memory_store: MemoryStore,
        identity_files: IdentityFiles,
        skill_registry: SkillRegistry,
        tool_dispatcher: ToolDispatcher,
        transport: ProviderTransport,
        model_config: ModelConfig,
        fallbacks: Optional[list[FallbackEntry]] = None,
        compressor: Optional[Any] = None,  # ContextCompressor; typed loosely to avoid a circular import
        max_tool_iterations: int = DEFAULT_MAX_TOOL_ITERATIONS,
    ) -> None:
        self.profile = profile
        self.memory_store = memory_store
        self.identity_files = identity_files
        self.skill_registry = skill_registry
        self.tool_dispatcher = tool_dispatcher
        self.transport = transport
        self.model_config = model_config
        self.fallbacks = fallbacks or []
        self.compressor = compressor
        self.max_tool_iterations = max_tool_iterations

    async def _send_with_fallback(
        self, messages: list[dict[str, Any]], tools: list[Any], system: str
    ) -> tuple[AgentResponse, ModelConfig]:
        candidates: list[tuple[ProviderTransport, ModelConfig]] = [(self.transport, self.model_config)]
        candidates.extend((f.transport, f.model_config) for f in self.fallbacks)

        last_exc: Optional[Exception] = None
        for i, (transport, model_cfg) in enumerate(candidates):
            try:
                response = await transport.send(messages, tools, system)
                if i > 0:
                    logger.warning(
                        "agent.failed_over", from_provider=candidates[0][0].name,
                        to_provider=transport.name, attempt=i,
                    )
                return response, model_cfg
            except TransportError as exc:
                last_exc = exc
                logger.warning("agent.transport_error", provider=transport.name, attempt=i, error=str(exc))
                continue
        raise TransportError(f"All configured transports failed for this turn. Last error: {last_exc}")

    async def _build_recent_summary(self, current_session_id: str) -> str:
        """Build a compact summary of recent past sessions to inject into
        the system prompt, giving the model cross-session awareness."""
        sessions = await self.memory_store.a_get_recent_sessions(n=5)
        # Exclude the current session from the summary
        past_sessions = [s for s in sessions if s.id != current_session_id]
        if not past_sessions:
            return ""

        parts = []
        for s in past_sessions:
            header = f"Session {s.id[:8]}"
            if s.title:
                header += f" — {s.title}"
            if s.started_at:
                header += f" ({s.started_at})"
            msgs = await self.memory_store.a_get_session_messages(s.id, include_compressed_away=False)
            previews = []
            for m in msgs[:6]:  # first few exchanges only
                if m.role in ("user", "assistant") and m.content:
                    content = m.content[:200].replace("\n", " ")
                    previews.append(f"  {m.role}: {content}")
            parts.append(header + "\n" + "\n".join(previews))

        return "\n\n".join(parts)

    async def run_turn(self, session_id: str, user_message: str) -> AgentTurnResult:
        await self.memory_store.a_add_message(session_id, "user", user_message)

        history_rows = await self.memory_store.a_get_session_messages(session_id, include_compressed_away=False)
        messages = rows_to_canonical_messages(history_rows)

        recent_summary = await self._build_recent_summary(session_id)
        system_prompt = self.identity_files.assemble_system_prompt(
            recent_summary=recent_summary,
            skills_compact=self.skill_registry.compact_listing()
        )
        tools = self.tool_dispatcher.specs()

        compressed = False
        if self.compressor is not None:
            token_estimate = approx_token_count(messages, system_prompt)
            if self.compressor.should_compress(self.model_config, token_estimate):
                comp_result = await self.compressor.compress(
                    transport=self.transport,
                    profile=self.profile,
                    session_id=session_id,
                    messages=messages,
                    message_rows=history_rows,
                    model_config=self.model_config,
                )
                session_id = comp_result.new_session_id
                messages = comp_result.new_messages
                compressed = True

        final_text = ""
        final_stop = "end_turn"
        total_usage = Usage()
        tool_records: list[ToolCallRecord] = []

        for _ in range(self.max_tool_iterations):
            response, _used_model_cfg = await self._send_with_fallback(messages, tools, system_prompt)
            total_usage = add_usage(total_usage, response.usage)

            if response.tool_calls:
                assistant_blocks = assistant_content_from_response(response)
                messages.append({"role": "assistant", "content": assistant_blocks})
                await self.memory_store.a_add_message(
                    session_id, "assistant", response.text,
                    tool_calls=[dataclasses.asdict(tc) for tc in response.tool_calls],
                )

                result_blocks = []
                for tc in response.tool_calls:
                    result = await self.tool_dispatcher.dispatch(tc.name, tc.arguments)
                    tool_records.append(ToolCallRecord(name=tc.name, arguments=tc.arguments, result=result))
                    result_blocks.append(tool_result_block(tc.id, result))

                messages.append({"role": "user", "content": result_blocks})
                await self.memory_store.a_add_message(session_id, "tool", json.dumps(result_blocks))
                continue

            final_text = response.text
            final_stop = response.stop_reason
            await self.memory_store.a_add_message(session_id, "assistant", response.text)
            break
        else:
            logger.warning("agent.max_tool_iterations_reached", session_id=session_id, limit=self.max_tool_iterations)
            final_stop = "max_tool_iterations"

        await self.memory_store.a_update_session_usage(session_id, token_delta=total_usage.total_tokens)

        return AgentTurnResult(
            session_id=session_id, text=final_text, tool_calls_made=tool_records,
            stop_reason=final_stop, usage=total_usage, compressed=compressed,
        )

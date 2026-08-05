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
        vector_memory: Optional[Any] = None,  # VectorMemory for persistent recall
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
        self.vector_memory = vector_memory
        self._turn_count = 0

    async def _send_with_fallback(
        self, messages: list[dict[str, Any]], tools: list[Any], system: str, stream: bool = False,
    ) -> tuple[AgentResponse, ModelConfig]:
        candidates: list[tuple[ProviderTransport, ModelConfig]] = [(self.transport, self.model_config)]
        candidates.extend((f.transport, f.model_config) for f in self.fallbacks)

        last_exc: Optional[Exception] = None
        for i, (transport, model_cfg) in enumerate(candidates):
            try:
                response = await transport.send(messages, tools, system, stream=stream)
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

    def _audit_tool_call(self, session_id: str, tool_name: str, result: ToolResult) -> None:
        """Log a tool call to the audit system (best-effort, non-blocking)."""
        try:
            from hermclaw.security.audit import get_audit_logger
            risk = "high" if tool_name in ("shell", "browser", "app_launcher", "code_exec") else "low"
            get_audit_logger().log(
                event_type="tool_call",
                tool_name=tool_name,
                session_id=session_id,
                profile=self.profile,
                details={"ok": result.ok, "output_len": len(result.output)},
                risk_level=risk,
                outcome="success" if result.ok else "failure",
            )
        except Exception:
            pass  # Audit is best-effort, never break the main loop

    async def _auto_recall(self, user_message: str) -> list[str]:
        """Search vector memory for context relevant to the user's message.
        Returns a list of relevant fact strings, or empty list."""
        if not self.vector_memory:
            return []
        try:
            results = await self.vector_memory.search(user_message, limit=5)
            if not results:
                return []
            facts = []
            for r in results:
                sim = r.get("similarity", 0)
                if sim < 0.3:  # skip low-relevance matches
                    continue
                content = r.get("content", "")
                # Clean up the stored format
                if content.startswith("User said: "):
                    content = content[11:]  # strip prefix
                facts.append(content)
            return facts
        except Exception as exc:
            logger.debug("agent.auto_recall_failed", error=str(exc))
            return []

    async def _auto_save(self, session_id: str, user_message: str, assistant_text: str) -> None:
        """Extract and persist important facts from the conversation.
        Runs best-effort after each turn — never blocks the response."""
        if not self.vector_memory or not assistant_text:
            return
        try:
            # Save user's key statements (preferences, personal info, requests)
            user_lower = user_message.lower().strip()

            # Don't save questions — only save statements
            is_question = user_lower.startswith(("do you", "can you", "what", "how", "why", "where",
                                                  "when", "who", "which", "is there", "are there",
                                                  "does", "did", "will", "would", "could", "should"))

            save_triggers = [
                "my name is", "i am ", "i'm ", "i like", "i prefer", "i want",
                "i need", "i live", "i work", "don't forget", "please remember",
                "call me", "my favorite", "i use", "i have", "my email",
                "my phone", "my address", "i study", "my age",
                "remember that", "remember this", "note that",
            ]
            should_save = not is_question and any(trigger in user_lower for trigger in save_triggers)

            if should_save:
                # Determine category
                if any(t in user_lower for t in ["my name", "call me", "i am", "i'm", "my age", "i live", "i work", "i study"]):
                    category = "user_info"
                elif any(t in user_lower for t in ["i like", "i prefer", "my favorite", "i use"]):
                    category = "user_preference"
                else:
                    category = "user_request"

                await self.vector_memory.store(
                    f"User said: {user_message}",
                    category=category,
                    metadata={"session_id": session_id, "type": "auto_saved"},
                )
                logger.info("agent.auto_saved_memory", category=category, preview=user_message[:80])

                # Also persist to USER.md for durable cross-session context
                try:
                    self.identity_files.append_user_facts([user_message.strip()])
                except Exception:
                    pass

            # Every 5 turns, save a conversation summary
            self._turn_count += 1
            if self._turn_count % 5 == 0 and assistant_text:
                summary = f"Conversation context (turn {self._turn_count}): User asked about '{user_message[:100]}'. Agent responded about '{assistant_text[:100]}'"
                await self.vector_memory.store(summary, category="conversation", metadata={"session_id": session_id})

        except Exception as exc:
            logger.debug("agent.auto_save_failed", error=str(exc))

    async def run_turn(self, session_id: str, user_message: str, stream: bool = False) -> AgentTurnResult:
        await self.memory_store.a_add_message(session_id, "user", user_message)

        history_rows = await self.memory_store.a_get_session_messages(session_id, include_compressed_away=False)
        messages = rows_to_canonical_messages(history_rows)

        recent_summary = await self._build_recent_summary(session_id)

        # Auto-recall: search persistent memory for relevant context
        recalled_facts = await self._auto_recall(user_message)

        system_prompt = self.identity_files.assemble_system_prompt(
            recent_summary=recent_summary,
            skills_compact=self.skill_registry.compact_listing()
        )

        # Inject recalled memories by appending them directly to the last
        # user message. This is the most reliable approach for ALL model
        # sizes — the model literally cannot ignore context that's part
        # of the message it's responding to.
        if recalled_facts and messages:
            facts_text = "\n".join(f"- {f}" for f in recalled_facts)
            augmented_content = (
                f"{user_message}\n\n"
                f"[Your memory recalls these relevant facts about the user. "
                f"USE them in your response:]\n{facts_text}"
            )
            # Replace the last message's content (which is the current user message)
            if messages[-1].get("role") == "user":
                messages[-1] = {"role": "user", "content": augmented_content}
            logger.info("agent.memory_recalled", facts_count=len(recalled_facts))

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
            # Only stream the final response (not intermediate tool-use rounds)
            use_stream = stream and len(tool_records) == 0
            response, _used_model_cfg = await self._send_with_fallback(messages, tools, system_prompt, stream=use_stream)
            total_usage = add_usage(total_usage, response.usage)

            if response.tool_calls:
                assistant_blocks = assistant_content_from_response(response)
                messages.append({"role": "assistant", "content": assistant_blocks})
                await self.memory_store.a_add_message(
                    session_id, "assistant", response.text,
                    tool_calls=[dataclasses.asdict(tc) for tc in response.tool_calls],
                )

                result_blocks = []

                # Parallel execution when multiple tool calls arrive
                if len(response.tool_calls) > 1:
                    try:
                        from hermclaw.brain.parallel_exec import execute_parallel
                        par_result = await execute_parallel(
                            self.tool_dispatcher,
                            [{"name": tc.name, "arguments": tc.arguments, "id": tc.id} for tc in response.tool_calls],
                            max_concurrent=5,
                        )
                        for tc, pr in zip(response.tool_calls, par_result.results):
                            result = pr["result"]
                            tool_records.append(ToolCallRecord(name=tc.name, arguments=tc.arguments, result=result))
                            result_blocks.append(tool_result_block(tc.id, result))
                            self._audit_tool_call(session_id, tc.name, result)
                        if par_result.speedup > 1.2:
                            logger.info("agent.parallel_speedup", speedup=par_result.speedup,
                                        parallel_s=par_result.total_time_s, sequential_s=par_result.sequential_time_s)
                    except ImportError:
                        # Fallback to sequential
                        for tc in response.tool_calls:
                            result = await self.tool_dispatcher.dispatch(tc.name, tc.arguments)
                            tool_records.append(ToolCallRecord(name=tc.name, arguments=tc.arguments, result=result))
                            result_blocks.append(tool_result_block(tc.id, result))
                            self._audit_tool_call(session_id, tc.name, result)
                else:
                    for tc in response.tool_calls:
                        result = await self.tool_dispatcher.dispatch(tc.name, tc.arguments)
                        tool_records.append(ToolCallRecord(name=tc.name, arguments=tc.arguments, result=result))
                        result_blocks.append(tool_result_block(tc.id, result))
                        self._audit_tool_call(session_id, tc.name, result)

                messages.append({"role": "user", "content": result_blocks})
                await self.memory_store.a_add_message(session_id, "tool", json.dumps(result_blocks))
                continue

            # Model produced a text response (possibly alongside tool calls on some providers)
            final_text = response.text
            final_stop = response.stop_reason
            await self.memory_store.a_add_message(session_id, "assistant", response.text)
            break
        else:
            logger.warning("agent.max_tool_iterations_reached", session_id=session_id, limit=self.max_tool_iterations)
            final_stop = "max_tool_iterations"
            # Synthesize a response from the tool results so the user isn't left with nothing
            if tool_records and not final_text:
                parts = []
                for tr in tool_records:
                    if tr.result.ok and tr.result.output:
                        parts.append(f"[{tr.name}]: {tr.result.output[:500]}")
                if parts:
                    final_text = "Here are the results from the tools I used:\n\n" + "\n\n".join(parts)
                else:
                    final_text = "I used several tools but couldn't produce a final answer. Please try rephrasing your question."

        await self.memory_store.a_update_session_usage(session_id, token_delta=total_usage.total_tokens)

        # Auto-save: persist important facts from this turn to long-term memory
        await self._auto_save(session_id, user_message, final_text)

        return AgentTurnResult(
            session_id=session_id, text=final_text, tool_calls_made=tool_records,
            stop_reason=final_stop, usage=total_usage, compressed=compressed,
        )

"""Context compression: keeps a long-running session from ever hard-failing
on a full context window.

Triggered when the live prompt crosses brain.memory.compression_threshold
(a fraction of the active model's context window). On trigger:

  1. A memory-flush turn gives the model one last chance to explicitly
     save anything worth keeping via a `save_memory` tool, before older
     turns become unreachable in the live prompt.
  2. The older portion of the conversation is summarized into a compact
     recap; the `keep_recent_exchanges` most recent turns stay verbatim.
  3. The full pre-compression messages are already in SQLite (agent_loop
     persists every turn as it happens) -- they're flagged
     compressed_away rather than deleted, so session_search still finds
     them.
  4. A continuation session row is created, linked to the original via
     parent_session_id, so lineage survives across compressions.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Optional

import structlog

from hermclaw.brain.memory.store import MemoryStore
from hermclaw.brain.profiles import IdentityFiles
from hermclaw.brain.transports.base import ProviderTransport
from hermclaw.config import ModelConfig
from hermclaw.tools.base import ToolSpec

logger = structlog.get_logger(__name__)

SAVE_MEMORY_TOOL = ToolSpec(
    name="save_memory",
    description=(
        "Save a durable fact you want to remember beyond this conversation, before it gets "
        "compressed away. Call once per distinct fact worth keeping; skip it if nothing here "
        "is worth persisting."
    ),
    parameters={
        "type": "object",
        "properties": {
            "fact": {"type": "string", "description": "The fact to remember, written plainly and self-contained."},
            "about_user": {
                "type": "boolean",
                "description": "True if this is a fact about the user specifically, rather than a general fact.",
                "default": False,
            },
        },
        "required": ["fact"],
    },
)

_FLUSH_PROMPT = (
    "[System: this conversation is about to be compressed to free up context space. "
    "If there is anything you want to remember beyond this point, call save_memory now -- "
    "once per fact. If there's nothing worth keeping, just say so briefly and don't call the tool.]"
)

_SUMMARIZE_PROMPT = (
    "[System: summarize the conversation above in one compact paragraph, preserving anything "
    "a continuation would need -- open questions, decisions made, work in progress. "
    "Reply with ONLY the summary text, no preamble.]"
)


@dataclasses.dataclass
class CompressionResult:
    new_session_id: str
    new_messages: list[dict[str, Any]]
    summary: str
    facts_saved: list[str]


class ContextCompressor:
    def __init__(
        self,
        memory_store: MemoryStore,
        identity_files: IdentityFiles,
        compression_threshold: float = 0.5,
        keep_recent_exchanges: int = 2,
    ) -> None:
        self.memory_store = memory_store
        self.identity_files = identity_files
        self.compression_threshold = compression_threshold
        self.keep_recent_exchanges = keep_recent_exchanges

    def should_compress(self, model_config: ModelConfig, token_estimate: int) -> bool:
        threshold_tokens = model_config.context_window * self.compression_threshold
        return token_estimate >= threshold_tokens

    async def _summarize(self, transport: ProviderTransport, older_messages: list[dict[str, Any]]) -> str:
        if not older_messages:
            return ""
        prompt = {"role": "user", "content": _SUMMARIZE_PROMPT}
        response = await transport.send(older_messages + [prompt], tools=[], system="")
        return response.text.strip()

    async def compress(
        self,
        transport: ProviderTransport,
        profile: str,
        session_id: str,
        messages: list[dict[str, Any]],
        message_rows: list[Any],
        model_config: ModelConfig,
    ) -> CompressionResult:
        # -- Step 1: memory-flush turn --
        flush_prompt = {"role": "user", "content": _FLUSH_PROMPT}
        flush_response = await transport.send(messages + [flush_prompt], tools=[SAVE_MEMORY_TOOL], system="")

        general_facts: list[str] = []
        user_facts: list[str] = []
        for tc in flush_response.tool_calls:
            if tc.name != "save_memory":
                continue
            fact = str(tc.arguments.get("fact", "")).strip()
            if not fact:
                continue
            (user_facts if tc.arguments.get("about_user") else general_facts).append(fact)

        if general_facts:
            self.identity_files.append_memory_facts(general_facts)
        if user_facts:
            self.identity_files.append_user_facts(user_facts)

        # -- Step 2: summarize the older portion, keep the tail verbatim --
        keep_n = self.keep_recent_exchanges * 2  # one exchange == one user + one assistant turn
        if len(messages) > keep_n:
            older, recent = messages[:-keep_n], messages[-keep_n:]
        else:
            older, recent = messages, []

        summary = await self._summarize(transport, older)

        # -- Step 3: flag the pre-compression messages compressed_away --
        # (they are already durably persisted; agent_loop writes every
        # turn as it happens). message_rows is passed in by the caller,
        # 1:1 aligned with `messages`, rather than re-fetched here, so
        # there's no window for a race to desync the two.
        older_row_count = max(0, len(message_rows) - keep_n)
        older_ids = [r.id for r in message_rows[:older_row_count]]
        await self.memory_store.a_mark_messages_compressed_away(older_ids)

        # -- Step 4: continuation session, linked for lineage --
        old_session = self.memory_store.get_session(session_id)
        new_session_id = await self.memory_store.a_create_session(
            channel=old_session.channel if old_session else None,
            model=old_session.model if old_session else None,
            parent_session_id=session_id,
        )

        new_messages: list[dict[str, Any]] = []
        if summary:
            summary_content = f"[System: summary of earlier conversation]\n{summary}"
            new_messages.append({"role": "user", "content": summary_content})
            await self.memory_store.a_add_message(new_session_id, "user", summary_content)
        for m in recent:
            new_messages.append(m)
            role = m["role"]
            content = m["content"]
            if isinstance(content, list):
                import json

                await self.memory_store.a_add_message(new_session_id, role, json.dumps(content))
            else:
                await self.memory_store.a_add_message(new_session_id, role, content)

        logger.info(
            "compressor.compressed", profile=profile, old_session=session_id, new_session=new_session_id,
            older_messages_flagged=len(older_ids), facts_saved=len(general_facts) + len(user_facts),
        )

        return CompressionResult(
            new_session_id=new_session_id, new_messages=new_messages, summary=summary,
            facts_saved=general_facts + user_facts,
        )

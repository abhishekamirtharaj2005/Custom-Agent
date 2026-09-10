"""Reflection: periodically distills recent sessions into durable memory.

Runs manually (`hermclaw reflect`) or automatically every
brain.reflection.trigger_every_n_turns. Reviews the last N sessions in
one model call, asking it to separate what it saw into three buckets:
general facts, user-specific facts, and repeated procedures (3+
occurrences) -- the last of which get expanded into draft skills by
skill_growth.py rather than written into MEMORY.md as prose.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any, Optional

import structlog

from hermclaw.brain.memory.store import MemoryStore
from hermclaw.brain.profiles import IdentityFiles
from hermclaw.brain.skill_growth import SkillGrowthEngine
from hermclaw.brain.transports.base import AgentResponse, ProviderTransport
from hermclaw.tools.base import ToolSpec

logger = structlog.get_logger(__name__)

MIN_OCCURRENCES_FOR_SKILL = 2

SUBMIT_REFLECTION_TOOL = ToolSpec(
    name="submit_reflection",
    description="Submit your distillation of the reviewed sessions. Call this exactly once.",
    parameters={
        "type": "object",
        "properties": {
            "facts": {
                "type": "array", "items": {"type": "string"},
                "description": "General durable facts worth remembering long-term (not about the user specifically).",
            },
            "user_facts": {
                "type": "array", "items": {"type": "string"},
                "description": "Facts specifically about the user (preferences, context, ongoing projects).",
            },
            "repeated_procedures": {
                "type": "array",
                "description": (
                    f"Any procedure that recurs {MIN_OCCURRENCES_FOR_SKILL}+ times across these sessions, even with "
                    f"different wording each time -- describe the underlying procedure once."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string", "description": "What the procedure does and when it's used."},
                        "occurrences": {"type": "integer"},
                        "steps": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["description", "occurrences", "steps"],
                },
            },
        },
        "required": ["facts", "user_facts", "repeated_procedures"],
    },
)

_REFLECTION_SYSTEM = (
    "You are Hermclaw's reflection process, distilling recent sessions into durable memory. "
    "Review the session transcripts you're given and call submit_reflection exactly once with: "
    "(1) general facts worth remembering long-term, (2) facts specifically about the user, and "
    f"(3) any procedure that appears {MIN_OCCURRENCES_FOR_SKILL} or more times across these sessions, "
    "regardless of small wording differences -- these become candidate skills, so describe the "
    "underlying procedure once with its steps, not each individual occurrence. If nothing qualifies "
    "for a bucket, submit an empty list for it -- don't invent facts or procedures that aren't there."
)


@dataclasses.dataclass
class ReflectionDistillation:
    facts: list[str] = dataclasses.field(default_factory=list)
    user_facts: list[str] = dataclasses.field(default_factory=list)
    repeated_procedures: list[dict[str, Any]] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class ReflectionResult:
    sessions_reviewed: int
    facts_saved: list[str]
    user_facts_saved: list[str]
    procedures_handed_to_skill_growth: list[dict[str, Any]]
    draft_skills_created: list[str]


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines)
    return text


def _parse_distillation(response: AgentResponse) -> ReflectionDistillation:
    for tc in response.tool_calls:
        if tc.name == "submit_reflection":
            args = tc.arguments
            return ReflectionDistillation(
                facts=[str(f) for f in args.get("facts", [])],
                user_facts=[str(f) for f in args.get("user_facts", [])],
                repeated_procedures=list(args.get("repeated_procedures", [])),
            )
    # Fallback: some models answer in plain JSON text instead of calling
    # the tool. Try to parse it; never let a malformed response crash
    # the whole reflection pass.
    try:
        data = json.loads(_strip_code_fences(response.text))
        return ReflectionDistillation(
            facts=[str(f) for f in data.get("facts", [])],
            user_facts=[str(f) for f in data.get("user_facts", [])],
            repeated_procedures=list(data.get("repeated_procedures", [])),
        )
    except (json.JSONDecodeError, AttributeError, TypeError):
        logger.warning("reflection.no_structured_output", text_preview=response.text[:200])
        return ReflectionDistillation()


def _build_transcript(sessions: list[Any], sessions_messages: list[list[Any]], max_chars: int = 8000) -> str:
    parts = []
    total = 0
    for session, rows in zip(sessions, sessions_messages):
        header = f"=== Session {session.id} ({session.started_at}) ==="
        parts.append(header)
        total += len(header)
        for row in rows:
            if row.role == "tool":
                continue  # raw tool-result JSON blobs add noise, not signal, to distillation
            content_preview = row.content[:500] if row.content else ""
            line = f"{row.role}: {content_preview}"
            total += len(line)
            if total > max_chars:
                parts.append("... [transcript truncated for context limits]")
                return "\n".join(parts)
            parts.append(line)
    return "\n".join(parts)


_REFLECTION_JSON_SYSTEM = (
    "You are analyzing conversation sessions to find patterns. "
    "Reply with ONLY a JSON object (no extra text) with these keys:\n"
    '- "facts": array of strings - general durable facts worth remembering\n'
    '- "user_facts": array of strings - facts about the user (preferences, context)\n'
    '- "repeated_procedures": array of objects, each with:\n'
    '    - "description": string - what the procedure does\n'
    '    - "occurrences": integer - how many times it appeared\n'
    '    - "steps": array of strings - the steps involved\n'
    "Include any procedure that appears 2+ times, even with different wording. "
    "If nothing qualifies, use empty arrays. Reply with ONLY the JSON."
)


async def reflect(
    profile: str,
    memory_store: MemoryStore,
    identity_files: IdentityFiles,
    skill_growth_engine: SkillGrowthEngine,
    transport: ProviderTransport,
    n_sessions: int = 20,
) -> ReflectionResult:
    sessions = await memory_store.a_get_recent_sessions(n_sessions)
    if not sessions:
        return ReflectionResult(0, [], [], [], [])

    ordered = list(reversed(sessions))  # oldest first, for a coherent narrative
    sessions_messages = [
        await memory_store.a_get_session_messages(s.id, include_compressed_away=True) for s in ordered
    ]
    transcript = _build_transcript(ordered, sessions_messages)

    # Attempt 1: Use the submit_reflection tool (works well with large models)
    message = {"role": "user", "content": transcript + "\n\nDistill the sessions above via submit_reflection."}
    response = await transport.send([message], tools=[SUBMIT_REFLECTION_TOOL], system=_REFLECTION_SYSTEM)
    distillation = _parse_distillation(response)

    # Attempt 2: If tool calling failed (common with small models like gemma4),
    # retry WITHOUT tools, asking for plain JSON output instead
    if not distillation.facts and not distillation.user_facts and not distillation.repeated_procedures:
        logger.info("reflection.tool_call_failed_retrying_json", text_preview=response.text[:200])
        json_message = {"role": "user", "content": transcript + "\n\nAnalyze the sessions above and return the JSON."}
        try:
            json_response = await transport.send([json_message], tools=[], system=_REFLECTION_JSON_SYSTEM)
            distillation = _parse_distillation(json_response)
            if distillation.facts or distillation.user_facts or distillation.repeated_procedures:
                logger.info("reflection.json_fallback_succeeded")
        except Exception as exc:
            logger.warning("reflection.json_fallback_failed", error=str(exc))

    if distillation.facts:
        identity_files.append_memory_facts(distillation.facts)
    if distillation.user_facts:
        identity_files.append_user_facts(distillation.user_facts)

    handed: list[dict[str, Any]] = []
    draft_paths: list[str] = []
    for proc in distillation.repeated_procedures:
        if int(proc.get("occurrences", 0)) >= MIN_OCCURRENCES_FOR_SKILL:
            handed.append(proc)
            path = skill_growth_engine.generate_draft_skill(proc, profile)
            if path:
                draft_paths.append(str(path))

    logger.info(
        "reflection.completed", profile=profile, sessions_reviewed=len(sessions),
        facts=len(distillation.facts), user_facts=len(distillation.user_facts),
        procedures_handed=len(handed), drafts_created=len(draft_paths),
    )

    return ReflectionResult(
        sessions_reviewed=len(sessions), facts_saved=distillation.facts, user_facts_saved=distillation.user_facts,
        procedures_handed_to_skill_growth=handed, draft_skills_created=draft_paths,
    )


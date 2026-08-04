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

MIN_OCCURRENCES_FOR_SKILL = 3

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


def _build_transcript(sessions: list[Any], sessions_messages: list[list[Any]]) -> str:
    parts = []
    for session, rows in zip(sessions, sessions_messages):
        parts.append(f"=== Session {session.id} ({session.started_at}) ===")
        for row in rows:
            if row.role == "tool":
                continue  # raw tool-result JSON blobs add noise, not signal, to distillation
            content_preview = row.content[:500] if row.content else ""
            parts.append(f"{row.role}: {content_preview}")
    return "\n".join(parts)


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

    message = {"role": "user", "content": transcript + "\n\nDistill the sessions above via submit_reflection."}
    response = await transport.send([message], tools=[SUBMIT_REFLECTION_TOOL], system=_REFLECTION_SYSTEM)
    distillation = _parse_distillation(response)

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

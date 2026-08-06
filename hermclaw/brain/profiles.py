"""Profile isolation and identity files.

Every subsystem that touches disk state (memory store, skills, workspace,
identity files) takes an explicit `profile: str` -- there is no ambient
"current profile" global anywhere in Hermclaw. That's what makes two
profiles running concurrently (e.g. two entries in agent.list bound to
different channels) actually safe rather than merely documented as safe.

Layout per profile, rooted at hermclaw_home()/profiles/<profile>/:
    SOUL.md      identity/personality -- human-edited only, never auto-written
    MEMORY.md    durable facts distilled by reflection
    USER.md      facts about the user, distilled by reflection
    state.db     SQLite memory (brain/memory/store.py)
    skills/      this profile's skill directory
    workspace/   this profile's default filesystem_scope for tool execution
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path
from typing import Optional

import structlog

from hermclaw.config import hermclaw_home

logger = structlog.get_logger(__name__)

_PROFILE_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")

_DEFAULT_SOUL_MD = """\
# SOUL.md

This file defines Hermclaw's identity and personality for this profile.
Edit it by hand -- Hermclaw never writes to this file automatically.

## Personality

(Describe how you want your agent to communicate: tone, verbosity, quirks.)

## Values

(Anything it should always or never do, beyond the security defaults
already enforced in tools/ and security/.)
"""

_DEFAULT_MEMORY_MD = """\
# MEMORY.md

Durable facts Hermclaw has learned across sessions for this profile.
Maintained automatically by the reflection loop (`hermclaw reflect`).
Manual edits are fine but may be reorganized on the next reflection pass.
"""

_DEFAULT_USER_MD = """\
# USER.md

Facts Hermclaw has learned about you across sessions for this profile.
Maintained automatically by the reflection loop, same as MEMORY.md.
"""

CORE_SYSTEM_INSTRUCTIONS = """\
You are Hermclaw, a personal AI agent on the user's Windows machine. \
You have FULL SYSTEM ACCESS through your tools.

## Rules
1. ALWAYS use your tools to fulfill requests. Never say "I can't".
2. For files: use list_dir, file_read, file_write, shell.
3. For commands: use shell (PowerShell). Use `dir` to list, `start` to open apps.
4. For web: use web_search, url_read.
5. For tasks: use goals, todo, kanban, scheduler.
6. For memory: use memory store/search. You recall facts automatically.
7. Keep responses concise and helpful.
"""


def _validate_profile_name(profile: str) -> None:
    if not profile or not _PROFILE_NAME_RE.match(profile):
        raise ValueError(
            f"Invalid profile name: {profile!r} -- must be non-empty and match [A-Za-z0-9_-]+ "
            f"(this restriction also prevents path traversal via profile names)"
        )


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _trim_to_limit(text: str, limit: int) -> str:
    """Keep the most recently appended lines (the tail) when a file grows
    past its soft char limit, since newer distilled facts are generally
    more relevant than older ones."""
    if len(text) <= limit:
        return text
    lines = text.splitlines()
    kept: list[str] = []
    total = 0
    for line in reversed(lines):
        total += len(line) + 1
        if total > limit and kept:
            break
        kept.append(line)
    kept.reverse()
    return "\n".join(kept) + "\n"


@dataclasses.dataclass(frozen=True)
class ProfilePaths:
    profile: str
    root: Path
    soul_md: Path
    memory_md: Path
    user_md: Path
    state_db: Path
    skills_dir: Path
    workspace_dir: Path


class ProfileManager:
    def __init__(self, home: Optional[Path] = None) -> None:
        self.home = Path(home) if home else hermclaw_home()

    def profile_root(self, profile: str) -> Path:
        _validate_profile_name(profile)
        return self.home / "profiles" / profile

    def paths(self, profile: str) -> ProfilePaths:
        root = self.profile_root(profile)
        return ProfilePaths(
            profile=profile,
            root=root,
            soul_md=root / "SOUL.md",
            memory_md=root / "MEMORY.md",
            user_md=root / "USER.md",
            state_db=root / "state.db",
            skills_dir=root / "skills",
            workspace_dir=root / "workspace",
        )

    def ensure_profile(self, profile: str) -> ProfilePaths:
        """Idempotent bootstrap: create the profile directory and any
        missing default files/folders. Safe to call on every access --
        a profile that doesn't exist yet is not an error, it's just new."""
        p = self.paths(profile)
        p.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        p.skills_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        p.workspace_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not p.soul_md.exists():
            p.soul_md.write_text(_DEFAULT_SOUL_MD, encoding="utf-8")
        if not p.memory_md.exists():
            p.memory_md.write_text(_DEFAULT_MEMORY_MD, encoding="utf-8")
        if not p.user_md.exists():
            p.user_md.write_text(_DEFAULT_USER_MD, encoding="utf-8")
        return p

    def list_profiles(self) -> list[str]:
        profiles_dir = self.home / "profiles"
        if not profiles_dir.exists():
            return []
        return sorted(d.name for d in profiles_dir.iterdir() if d.is_dir())


class IdentityFiles:
    """Reads/writes SOUL.md, MEMORY.md, USER.md for exactly one profile,
    and assembles them (plus the core instructions and skill listing)
    into a system prompt. Holds no state beyond its own ProfilePaths."""

    def __init__(self, paths: ProfilePaths, memory_char_limit: int = 2200, user_char_limit: int = 1375) -> None:
        self.paths = paths
        self.memory_char_limit = memory_char_limit
        self.user_char_limit = user_char_limit

    def read_soul(self) -> str:
        return _safe_read(self.paths.soul_md)

    def read_memory(self) -> str:
        return _safe_read(self.paths.memory_md)

    def read_user(self) -> str:
        return _safe_read(self.paths.user_md)

    def append_memory_facts(self, facts: list[str]) -> None:
        """Reflection-only. SOUL.md is deliberately not touched here or
        anywhere else Hermclaw writes automatically."""
        facts = [f.strip() for f in facts if f.strip()]
        if not facts:
            return
        current = self.read_memory().rstrip()
        combined = current + "\n" + "\n".join(f"- {f}" for f in facts) + "\n"
        if len(combined) > self.memory_char_limit:
            logger.warning(
                "profiles.memory_over_limit", profile=self.paths.profile,
                length=len(combined), limit=self.memory_char_limit,
            )
            combined = _trim_to_limit(combined, self.memory_char_limit)
        self.paths.memory_md.write_text(combined, encoding="utf-8")

    def append_user_facts(self, facts: list[str]) -> None:
        facts = [f.strip() for f in facts if f.strip()]
        if not facts:
            return
        current = self.read_user().rstrip()
        combined = current + "\n" + "\n".join(f"- {f}" for f in facts) + "\n"
        if len(combined) > self.user_char_limit:
            logger.warning(
                "profiles.user_over_limit", profile=self.paths.profile,
                length=len(combined), limit=self.user_char_limit,
            )
            combined = _trim_to_limit(combined, self.user_char_limit)
        self.paths.user_md.write_text(combined, encoding="utf-8")

    def assemble_system_prompt(
        self,
        recent_summary: Optional[str] = None,
        skills_compact: Optional[list[dict[str, str]]] = None,
    ) -> str:
        parts = [CORE_SYSTEM_INSTRUCTIONS]

        soul = self.read_soul().strip()
        if soul:
            parts.append("# Identity (SOUL.md)\n\n" + soul)

        memory = self.read_memory().strip()
        if memory:
            parts.append("# Durable Memory (MEMORY.md)\n\n" + memory)

        user = self.read_user().strip()
        if user:
            parts.append("# About the User (USER.md)\n\n" + user)

        if recent_summary and recent_summary.strip():
            parts.append("# Recent Session Summary\n\n" + recent_summary.strip())

        if skills_compact:
            skills_block = "\n".join(f"- **{s['name']}**: {s['description']}" for s in skills_compact)
            parts.append("# Available Skills\n\nAsk to see a skill's full instructions before using it.\n\n" + skills_block)

        return "\n\n".join(parts)

"""Skill registry: discovers, validates, and serves skills with the
agentskills.io spec's progressive-disclosure model.

Tier 1 (always loaded): name + description for every skill (~100 tokens
each) go into the system prompt at startup.
Tier 2 (loaded on demand): the full SKILL.md body loads only once a skill
is activated for a given turn.
Tier 3 (loaded on demand, by the skill's own instructions): references/
files are never eagerly read by the registry itself.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Optional

import structlog

from hermclaw.skills.loader import SkillMetadata, SkillValidationResult, discover_skill_dirs, parse_skill_md

logger = structlog.get_logger(__name__)


@dataclasses.dataclass
class SkillRegistry:
    directory: Path
    extra_directories: list[Path] = dataclasses.field(default_factory=list)
    _skills: dict[str, SkillMetadata] = dataclasses.field(default_factory=dict, init=False, repr=False)
    _load_errors: list[SkillValidationResult] = dataclasses.field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        self.directory = Path(self.directory).expanduser()
        self.extra_directories = [Path(d).expanduser() for d in self.extra_directories]

    def _search_roots(self) -> list[Path]:
        return [self.directory, *self.extra_directories]

    def discover(self) -> list[SkillValidationResult]:
        """Validate every skill directory under every search root. This is
        the function backing `hermclaw skills validate`."""
        results: list[SkillValidationResult] = []
        for root in self._search_roots():
            for skill_dir in discover_skill_dirs(root):
                results.append(parse_skill_md(skill_dir))
        return results

    def load(self) -> None:
        """(Re)build the in-memory registry from disk. Only skills that
        pass validation are made available to the agent; failures are kept
        for `hermclaw skills validate` / `hermclaw doctor` to report."""
        self._skills = {}
        self._load_errors = []
        for result in self.discover():
            if not result.passed or result.metadata is None:
                self._load_errors.append(result)
                logger.warning("skills.invalid_skill", path=str(result.skill_path), errors=result.errors)
                continue
            if result.metadata.name in self._skills:
                logger.warning(
                    "skills.duplicate_name",
                    name=result.metadata.name,
                    kept=str(self._skills[result.metadata.name].path),
                    ignored=str(result.metadata.path),
                )
                continue
            self._skills[result.metadata.name] = result.metadata

    def compact_listing(self) -> list[dict[str, str]]:
        """Tier 1: name+description for every loaded skill."""
        return [s.compact() for s in self._skills.values()]

    def activate(self, name: str) -> Optional[SkillMetadata]:
        """Tier 2: full SKILL.md body for one skill, only called once the
        agent has decided (from the compact listing) that it needs it."""
        return self._skills.get(name)

    def names(self) -> list[str]:
        return sorted(self._skills.keys())

    def get(self, name: str) -> Optional[SkillMetadata]:
        return self._skills.get(name)

    def auto_generated_skills(self) -> list[SkillMetadata]:
        return [s for s in self._skills.values() if s.auto_generated]

    def human_authored_skills(self) -> list[SkillMetadata]:
        return [s for s in self._skills.values() if not s.auto_generated]

    @property
    def load_errors(self) -> list[SkillValidationResult]:
        return list(self._load_errors)

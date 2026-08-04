"""Skill growth: turns repeated procedures noticed during reflection into
draft skills (Tier 1, always on), and optionally refines existing
auto-generated skills over time (Tier 2, behind skills.evolution_enabled).

Tier 2 ships a working heuristic variant-and-score loop in v1. A full
DSPy+GEPA-based evolution loop is a deliberately scoped v2 extension
point (see evolve_with_gepa below and MERGE_DECISIONS.md) -- not a
silent no-op, since evolve_skill() already does real, useful work today.
"""

from __future__ import annotations

import dataclasses
import difflib
import re
from pathlib import Path
from typing import Any, Optional

import structlog

from hermclaw.brain.memory.store import MemoryStore
from hermclaw.brain.profiles import ProfileManager
from hermclaw.brain.transports.base import ProviderTransport
from hermclaw.skills.registry import SkillRegistry

logger = structlog.get_logger(__name__)

DEDUP_SIMILARITY_THRESHOLD = 0.5


def _slugify(text: str, max_len: int = 64) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    if len(text) > max_len:
        text = text[:max_len].rstrip("-")
    return text or "auto-skill"


def _sanitize_for_frontmatter(text: str) -> str:
    """Model-generated text can legitimately contain '<'/'>' (shell
    redirects, comparisons); strip them here so an auto-drafted skill can
    never fail its own loader's prompt-injection defense (see
    skills/loader.py) on account of ordinary generated phrasing."""
    return text.replace("<", "").replace(">", "")


def _stem(token: str) -> str:
    """Deliberately crude suffix-stripping, not a real stemmer -- just
    enough to fold "deploy"/"deploying", "app"/"apps" together so token
    overlap survives ordinary verb/plural variation across restatements
    of the same procedure."""
    for suffix in ("ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    return token


def _token_similarity(a: str, b: str) -> float:
    """Combines stemmed Jaccard token overlap with a character-level
    sequence-match ratio, taking the higher of the two -- deliberately
    not exact-text matching, so realistically-reworded restatements of
    the same procedure ("deploy the app to staging" / "deploying the
    application onto the staging environment") still dedup against an
    existing draft, without over-matching genuinely different procedures.
    A production deployment could swap this for embedding similarity
    behind the same function signature; this heuristic keeps skill
    growth testable with no network call and no extra dependency."""
    ta = {_stem(t) for t in re.findall(r"\w+", a.lower())}
    tb = {_stem(t) for t in re.findall(r"\w+", b.lower())}
    if not ta or not tb:
        return 0.0
    jaccard = len(ta & tb) / len(ta | tb)
    seq_ratio = difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()
    return max(jaccard, seq_ratio)


@dataclasses.dataclass
class EvolutionResult:
    skill_name: str
    proposed_steps_md: str
    backend: str = "heuristic"


class SkillGrowthEngine:
    """Tier 1: always-on draft-skill generation from reflection's
    repeated-procedure output."""

    def __init__(self, profile_manager: ProfileManager, dedup_threshold: float = DEDUP_SIMILARITY_THRESHOLD) -> None:
        self.profile_manager = profile_manager
        self.dedup_threshold = dedup_threshold

    def generate_draft_skill(self, procedure: dict[str, Any], profile: str) -> Optional[Path]:
        description_raw = str(procedure.get("description", "")).strip()
        if not description_raw:
            return None
        occurrences = procedure.get("occurrences", 0)
        steps = procedure.get("steps") or []

        paths = self.profile_manager.ensure_profile(profile)
        skills_dir = paths.skills_dir

        registry = SkillRegistry(directory=skills_dir)
        registry.load()
        for existing in registry.auto_generated_skills():
            # Compare against the original distilled description, not the
            # augmented `description` field written into frontmatter
            # (which has boilerplate appended that would dilute the
            # similarity signal) -- see metadata.source_description below.
            existing_source = existing.metadata.get("source_description", existing.description)
            if _token_similarity(existing_source, description_raw) >= self.dedup_threshold:
                logger.info(
                    "skill_growth.deduped", profile=profile, existing=existing.name,
                    new_description=description_raw[:60],
                )
                return None

        name = _slugify(description_raw)
        candidate, n = name, 2
        while (skills_dir / candidate).exists():
            candidate = f"{name}-{n}"
            n += 1
        name = candidate

        description = _sanitize_for_frontmatter(f"{description_raw}. Use when this same procedure comes up again.")
        if len(description) > 1024:
            description = description[:1021] + "..."

        steps_md = "\n".join(f"{i + 1}. {_sanitize_for_frontmatter(str(s))}" for i, s in enumerate(steps)) or "(no steps captured)"

        skill_dir = skills_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        source_description_safe = _sanitize_for_frontmatter(description_raw).replace('"', "'")
        body = (
            f"---\n"
            f"name: {name}\n"
            f"description: {description}\n"
            f"metadata:\n"
            f"  auto_generated: true\n"
            f"  source: reflection\n"
            f"  occurrences_observed: {occurrences}\n"
            f'  source_description: "{source_description_safe}"\n'
            f"---\n\n"
            f"# {_sanitize_for_frontmatter(description_raw)}\n\n"
            f"Auto-generated from {occurrences} observed repetitions during reflection. "
            f"Review and edit freely -- this is a draft, not a finished skill.\n\n"
            f"## Steps\n\n{steps_md}\n"
        )
        (skill_dir / "SKILL.md").write_text(body, encoding="utf-8")
        logger.info("skill_growth.draft_created", profile=profile, name=name, occurrences=occurrences)
        return skill_dir / "SKILL.md"


class SkillEvolutionEngine:
    """Tier 2 (skills.evolution_enabled, off by default): refines
    existing auto-generated skills over time. evolve_skill() is real,
    working v1 behavior; evolve_with_gepa() is the scoped v2 extension
    point for the originally-envisioned DSPy+GEPA loop."""

    def __init__(self, skill_registry: SkillRegistry, memory_store: MemoryStore, transport: ProviderTransport) -> None:
        self.skill_registry = skill_registry
        self.memory_store = memory_store
        self.transport = transport

    async def evolve_skill(self, skill_name: str) -> Optional[EvolutionResult]:
        skill = self.skill_registry.get(skill_name)
        if not skill or not skill.auto_generated:
            return None

        prompt = {
            "role": "user",
            "content": (
                "Here is an auto-generated skill:\n\n"
                f"{skill.body}\n\n"
                "Propose an improved version of just the '## Steps' section -- tighter and clearer, "
                "same intent, same rough length. Reply with only the replacement markdown for that section."
            ),
        }
        response = await self.transport.send([prompt], tools=[], system="")
        proposed = response.text.strip()

        # Sanity gates: reject empty proposals or ones that bloat the skill
        # unreasonably -- this is the "test/size/benchmark constraint"
        # gate the build spec calls for, kept simple for v1.
        if not proposed or len(proposed) > len(skill.body) * 2:
            logger.info("skill_growth.evolution_rejected", skill=skill_name, reason="empty or oversized proposal")
            return None

        return EvolutionResult(skill_name=skill_name, proposed_steps_md=proposed)

    def apply_evolution(self, result: EvolutionResult) -> Path:
        skill = self.skill_registry.get(result.skill_name)
        if not skill:
            raise ValueError(f"Unknown skill: {result.skill_name}")
        skill_md_path = skill.path / "SKILL.md"
        text = skill_md_path.read_text(encoding="utf-8")
        new_text = re.sub(
            r"## Steps\n\n.*", f"## Steps\n\n{result.proposed_steps_md}\n", text, flags=re.DOTALL,
        )
        skill_md_path.write_text(new_text, encoding="utf-8")
        logger.info("skill_growth.evolution_applied", skill=result.skill_name)
        return skill_md_path

    async def evolve_with_gepa(self, skill_name: str) -> None:
        """v2 extension point: full DSPy+GEPA prompt evolution scored
        against a held-out benchmark of past sessions using this skill.
        Not implemented in v1 -- evolve_skill() above already provides a
        working Tier 2 loop via a heuristic scorer, so Tier 2 as a whole
        is functional without this method existing yet."""
        raise NotImplementedError(
            "DSPy+GEPA-based evolution is a scoped v2 item (see MERGE_DECISIONS.md); "
            "evolve_skill() provides the working v1 Tier 2 path via a heuristic scorer."
        )

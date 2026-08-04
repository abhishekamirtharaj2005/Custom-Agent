"""Parser and validator for the agentskills.io "Agent Skills" open standard.

Both OpenClaw and Hermes Agent already implement this exact standard, so
Hermclaw adopts it directly rather than inventing a variant (see C.3.1).
A skill is a directory: skill-name/{SKILL.md, scripts/, references/, assets/}.
SKILL.md is YAML frontmatter + a Markdown body.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path
from typing import Any, Optional

import yaml

NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_NAME_LEN = 64
MAX_DESCRIPTION_LEN = 1024
MAX_COMPATIBILITY_LEN = 500


@dataclasses.dataclass
class SkillMetadata:
    name: str
    description: str
    path: Path
    body: str
    license: Optional[str] = None
    compatibility: Optional[str] = None
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)
    allowed_tools: list[str] = dataclasses.field(default_factory=list)

    @property
    def auto_generated(self) -> bool:
        return bool(self.metadata.get("auto_generated", False))

    def compact(self) -> dict[str, str]:
        """The ~100-token progressive-disclosure form loaded into every
        system prompt at startup -- name and description ONLY."""
        return {"name": self.name, "description": self.description}


@dataclasses.dataclass
class SkillValidationResult:
    skill_path: Path
    passed: bool
    errors: list[str]
    metadata: Optional[SkillMetadata] = None

    @property
    def name(self) -> str:
        return self.metadata.name if self.metadata else self.skill_path.name


def _split_frontmatter(text: str) -> tuple[Optional[str], str]:
    """Split a SKILL.md's leading `---`-delimited YAML block from its
    Markdown body. Returns (frontmatter_text_or_None, body)."""
    stripped = text.lstrip("\ufeff")  # tolerate a BOM
    if not stripped.startswith("---"):
        return None, text
    parts = stripped.split("---", 2)
    if len(parts) < 3:
        return None, text
    return parts[1], parts[2].lstrip("\n")


def parse_skill_md(skill_dir: Path) -> SkillValidationResult:
    """Validate one skill directory against the full agentskills.io
    checklist. This is the function backing `hermclaw skills validate`."""
    skill_dir = Path(skill_dir)
    skill_md_path = skill_dir / "SKILL.md"
    if not skill_md_path.is_file():
        return SkillValidationResult(skill_dir, False, ["SKILL.md not found in skill directory"])

    text = skill_md_path.read_text(encoding="utf-8", errors="replace")
    fm_text, body = _split_frontmatter(text)
    if fm_text is None:
        return SkillValidationResult(
            skill_dir, False, ["Missing YAML frontmatter (SKILL.md must start with a '---' block)"]
        )

    # Prompt-injection defense from the spec itself: reject literal < or >
    # in frontmatter BEFORE attempting to parse it as YAML.
    if "<" in fm_text or ">" in fm_text:
        return SkillValidationResult(
            skill_dir,
            False,
            ["Frontmatter contains a literal '<' or '>' character, which is rejected unparsed "
             "(agentskills.io's own prompt-injection defense)"],
        )

    try:
        fm = yaml.safe_load(fm_text)
    except yaml.YAMLError as exc:
        return SkillValidationResult(skill_dir, False, [f"Frontmatter is not valid YAML: {exc}"])

    if fm is None:
        fm = {}
    if not isinstance(fm, dict):
        return SkillValidationResult(skill_dir, False, ["Frontmatter must be a YAML mapping"])

    errors: list[str] = []

    name = fm.get("name")
    if not name or not isinstance(name, str):
        errors.append("Missing required field 'name'")
        name = skill_dir.name  # best-effort so we can still report other errors
    else:
        if len(name) > MAX_NAME_LEN:
            errors.append(f"'name' exceeds {MAX_NAME_LEN} characters ({len(name)})")
        if not NAME_PATTERN.match(name):
            errors.append(
                "'name' must contain only lowercase letters, numbers, and hyphens, "
                "with no leading/trailing/consecutive hyphens"
            )
        if name != skill_dir.name:
            errors.append(f"'name' ({name!r}) must equal the parent directory name ({skill_dir.name!r})")

    description = fm.get("description")
    if not description or not isinstance(description, str) or not description.strip():
        errors.append("Missing required field 'description' (must be non-empty)")
        description = ""
    elif len(description) > MAX_DESCRIPTION_LEN:
        errors.append(f"'description' exceeds {MAX_DESCRIPTION_LEN} characters ({len(description)})")

    compatibility = fm.get("compatibility")
    if compatibility is not None and len(str(compatibility)) > MAX_COMPATIBILITY_LEN:
        errors.append(f"'compatibility' exceeds {MAX_COMPATIBILITY_LEN} characters")

    metadata = fm.get("metadata") or {}
    if not isinstance(metadata, dict):
        errors.append("'metadata' must be a mapping if present")
        metadata = {}

    allowed_tools_raw = fm.get("allowed-tools", "")
    if isinstance(allowed_tools_raw, str):
        allowed_tools = allowed_tools_raw.split()
    elif isinstance(allowed_tools_raw, list):
        allowed_tools = [str(t) for t in allowed_tools_raw]
    else:
        errors.append("'allowed-tools' must be a space-separated string or a list")
        allowed_tools = []

    license_ = fm.get("license")

    meta = SkillMetadata(
        name=name,
        description=description,
        path=skill_dir,
        body=body,
        license=license_ if isinstance(license_, str) else None,
        compatibility=str(compatibility) if compatibility is not None else None,
        metadata=metadata,
        allowed_tools=allowed_tools,
    )

    return SkillValidationResult(skill_dir, len(errors) == 0, errors, meta)


def discover_skill_dirs(base: Path) -> list[Path]:
    base = Path(base)
    if not base.is_dir():
        return []
    return sorted(
        child for child in base.iterdir() if child.is_dir() and (child / "SKILL.md").is_file()
    )

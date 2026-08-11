"""Skills hub: browse, install, validate, and manage skills.

Implements:
- Skills hub (browse/install from directory or URL)
- Skill safety guard (AST security audit)
- Skill usage analytics (tracking)
- Skill bundles (groups of related skills)
- Skill commands (slash commands from skills)
- Skill creator (auto-create skills from experience)
- Skill sync (across devices)
- Skill preprocessing
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Skill safety guard — AST security audit
# ---------------------------------------------------------------------------


class SkillSafetyGuard:
    """Audits skill code for security issues using AST analysis."""

    DANGEROUS_MODULES = {
        "subprocess", "os.system", "shutil.rmtree", "ctypes",
        "socket", "http.server", "multiprocessing",
    }

    DANGEROUS_FUNCTIONS = {
        "eval", "exec", "compile", "__import__", "globals",
        "locals", "getattr", "setattr", "delattr",
    }

    DANGEROUS_ATTRS = {
        "system", "popen", "remove", "rmdir", "unlink",
        "rmtree", "makedirs",
    }

    def audit(self, code: str, skill_name: str = "") -> list[dict[str, str]]:
        """Audit Python code for security issues."""
        issues: list[dict[str, str]] = []

        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            issues.append({"severity": "error", "message": f"Syntax error: {exc}"})
            return issues

        for node in ast.walk(tree):
            # Check imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in self.DANGEROUS_MODULES:
                        issues.append({
                            "severity": "high",
                            "message": f"Imports dangerous module: {alias.name}",
                            "line": node.lineno,
                        })

            elif isinstance(node, ast.ImportFrom):
                if node.module in self.DANGEROUS_MODULES:
                    issues.append({
                        "severity": "high",
                        "message": f"Imports from dangerous module: {node.module}",
                        "line": node.lineno,
                    })

            # Check function calls
            elif isinstance(node, ast.Call):
                func_name = self._get_call_name(node)
                if func_name in self.DANGEROUS_FUNCTIONS:
                    issues.append({
                        "severity": "critical",
                        "message": f"Calls dangerous function: {func_name}",
                        "line": node.lineno,
                    })

            # Check attribute access
            elif isinstance(node, ast.Attribute):
                if node.attr in self.DANGEROUS_ATTRS:
                    issues.append({
                        "severity": "medium",
                        "message": f"Accesses dangerous attribute: {node.attr}",
                        "line": node.lineno,
                    })

        if issues:
            logger.warning("skill_safety.issues_found", skill=skill_name, count=len(issues))
        return issues

    @staticmethod
    def _get_call_name(node: ast.Call) -> str:
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return node.func.attr
        return ""

    def is_safe(self, code: str) -> bool:
        """Quick check: returns True if no critical/high issues found."""
        issues = self.audit(code)
        return not any(i["severity"] in ("critical", "high") for i in issues)


# ---------------------------------------------------------------------------
# Skill usage analytics
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class SkillUsageRecord:
    skill_name: str
    timestamp: float
    duration_ms: float
    success: bool
    trigger: str = ""  # How it was triggered: "explicit", "keyword", "auto"


class SkillAnalytics:
    """Track skill usage for optimization and insights."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._records: list[SkillUsageRecord] = []
        self._db_path = db_path

    def record(self, skill_name: str, duration_ms: float, success: bool, trigger: str = "") -> None:
        self._records.append(SkillUsageRecord(
            skill_name=skill_name,
            timestamp=time.time(),
            duration_ms=duration_ms,
            success=success,
            trigger=trigger,
        ))

    def summary(self) -> dict[str, Any]:
        """Usage summary by skill."""
        by_skill: dict[str, dict] = defaultdict(lambda: {"calls": 0, "successes": 0, "total_ms": 0.0})
        for r in self._records:
            by_skill[r.skill_name]["calls"] += 1
            if r.success:
                by_skill[r.skill_name]["successes"] += 1
            by_skill[r.skill_name]["total_ms"] += r.duration_ms

        result = {}
        for name, data in by_skill.items():
            result[name] = {
                "calls": data["calls"],
                "success_rate": data["successes"] / data["calls"] if data["calls"] else 0,
                "avg_duration_ms": data["total_ms"] / data["calls"] if data["calls"] else 0,
            }
        return result

    def top_skills(self, n: int = 10) -> list[tuple[str, int]]:
        """Most-used skills."""
        counts: dict[str, int] = defaultdict(int)
        for r in self._records:
            counts[r.skill_name] += 1
        return sorted(counts.items(), key=lambda x: x[1], reverse=True)[:n]


# ---------------------------------------------------------------------------
# Skill bundles
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class SkillBundle:
    """A group of related skills that can be installed/enabled together."""
    name: str
    description: str
    skills: list[str]
    tags: list[str] = dataclasses.field(default_factory=list)
    version: str = "1.0.0"

    def contains(self, skill_name: str) -> bool:
        return skill_name in self.skills


# Built-in bundles
BUILTIN_BUNDLES = [
    SkillBundle("productivity", "Office and organization tools",
                ["email", "calendar", "notes", "reminders", "todo"], tags=["office"]),
    SkillBundle("development", "Software development tools",
                ["git", "code_review", "testing", "deployment"], tags=["dev"]),
    SkillBundle("creative", "Creative and media tools",
                ["image_gen", "video_gen", "music", "writing"], tags=["media"]),
    SkillBundle("research", "Research and analysis tools",
                ["web_search", "pdf_reader", "summarize", "cite"], tags=["academic"]),
    SkillBundle("social", "Social media and communication",
                ["twitter", "discord_bot", "telegram_bot"], tags=["social"]),
    SkillBundle("data_science", "Data analysis tools",
                ["pandas", "matplotlib", "jupyter", "sql"], tags=["data"]),
    SkillBundle("devops", "DevOps and infrastructure",
                ["docker", "k8s", "terraform", "monitoring"], tags=["ops"]),
    SkillBundle("smart_home", "Smart home and IoT",
                ["home_assistant", "hue_lights", "thermostat"], tags=["iot"]),
]


class BundleManager:
    """Manage skill bundles."""

    def __init__(self) -> None:
        self._bundles = {b.name: b for b in BUILTIN_BUNDLES}
        self._enabled: set[str] = set()

    def list_bundles(self) -> list[SkillBundle]:
        return list(self._bundles.values())

    def get(self, name: str) -> Optional[SkillBundle]:
        return self._bundles.get(name)

    def enable(self, name: str) -> bool:
        if name in self._bundles:
            self._enabled.add(name)
            logger.info("bundle.enabled", name=name)
            return True
        return False

    def disable(self, name: str) -> None:
        self._enabled.discard(name)

    @property
    def enabled_skills(self) -> set[str]:
        skills: set[str] = set()
        for name in self._enabled:
            bundle = self._bundles.get(name)
            if bundle:
                skills.update(bundle.skills)
        return skills


# ---------------------------------------------------------------------------
# Skill commands (slash commands from skills)
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class SkillCommand:
    """A slash command defined by a skill."""
    name: str
    description: str
    skill_name: str
    handler: str  # Function name in the skill module
    args: list[dict[str, str]] = dataclasses.field(default_factory=list)


class SkillCommandRegistry:
    """Registry of slash commands provided by skills."""

    def __init__(self) -> None:
        self._commands: dict[str, SkillCommand] = {}

    def register(self, command: SkillCommand) -> None:
        self._commands[command.name] = command
        logger.debug("skill_command.registered", name=command.name, skill=command.skill_name)

    def get(self, name: str) -> Optional[SkillCommand]:
        return self._commands.get(name.lstrip("/"))

    def list_commands(self) -> list[SkillCommand]:
        return list(self._commands.values())

    def match(self, input_text: str) -> Optional[SkillCommand]:
        """Check if input starts with a registered slash command."""
        for name, cmd in self._commands.items():
            if input_text.startswith(f"/{name}"):
                return cmd
        return None


# ---------------------------------------------------------------------------
# Skill creator (auto-create from experience)
# ---------------------------------------------------------------------------


class SkillCreator:
    """Creates new skills from agent interactions.

    When the agent performs a multi-step task, the creator can:
    1. Extract the pattern (tool sequence, prompts, logic)
    2. Generate a reusable skill definition
    3. Save it to the skills directory
    """

    def __init__(self, skills_dir: Path) -> None:
        self._skills_dir = skills_dir
        self._skills_dir.mkdir(parents=True, exist_ok=True)

    def create_from_interaction(
        self,
        name: str,
        description: str,
        steps: list[dict[str, Any]],
        tags: list[str] | None = None,
    ) -> Path:
        """Create a skill from a recorded interaction."""
        skill_dir = self._skills_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)

        # Generate the skill manifest
        manifest = {
            "name": name,
            "description": description,
            "version": "1.0.0",
            "auto_generated": True,
            "created_at": time.time(),
            "tags": tags or [],
            "steps": len(steps),
        }

        (skill_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

        # Generate the skill body (instructions)
        body_lines = [f"# {name}", "", description, "", "## Steps", ""]
        for i, step in enumerate(steps, 1):
            tool = step.get("tool", "unknown")
            args_str = json.dumps(step.get("args", {}), indent=2)
            body_lines.append(f"### Step {i}: {tool}")
            body_lines.append(f"```json\n{args_str}\n```")
            body_lines.append("")

        (skill_dir / "body.md").write_text("\n".join(body_lines), encoding="utf-8")

        logger.info("skill_creator.created", name=name, steps=len(steps))
        return skill_dir

    def create_from_code(self, name: str, description: str, code: str) -> Path:
        """Create a skill from Python code."""
        skill_dir = self._skills_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)

        manifest = {
            "name": name,
            "description": description,
            "version": "1.0.0",
            "auto_generated": True,
            "created_at": time.time(),
            "type": "python",
        }

        (skill_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        (skill_dir / "main.py").write_text(code, encoding="utf-8")

        logger.info("skill_creator.created_from_code", name=name)
        return skill_dir


# ---------------------------------------------------------------------------
# Skills hub (browse/install)
# ---------------------------------------------------------------------------


class SkillsHub:
    """Browse and install skills from a catalog.

    Skills can be loaded from:
    - Local directory
    - Git repository URL
    - Built-in skill catalog
    """

    def __init__(self, install_dir: Path) -> None:
        self._install_dir = install_dir
        self._catalog: list[dict[str, Any]] = self._load_builtin_catalog()

    def browse(self, query: str = "", tags: list[str] | None = None) -> list[dict[str, Any]]:
        """Browse available skills."""
        results = self._catalog
        if query:
            q = query.lower()
            results = [s for s in results if q in s["name"].lower() or q in s.get("description", "").lower()]
        if tags:
            results = [s for s in results if any(t in s.get("tags", []) for t in tags)]
        return results

    def install_from_dir(self, source_dir: Path, name: Optional[str] = None) -> bool:
        """Install a skill from a local directory."""
        if not source_dir.is_dir():
            logger.error("skills_hub.source_not_found", path=str(source_dir))
            return False

        target = self._install_dir / (name or source_dir.name)
        if target.exists():
            logger.warning("skills_hub.already_installed", name=target.name)
            return False

        import shutil
        shutil.copytree(source_dir, target)
        logger.info("skills_hub.installed", name=target.name)
        return True

    def uninstall(self, name: str) -> bool:
        """Uninstall a skill."""
        target = self._install_dir / name
        if not target.exists():
            return False

        import shutil
        shutil.rmtree(target)
        logger.info("skills_hub.uninstalled", name=name)
        return True

    def installed(self) -> list[str]:
        """List installed skills."""
        if not self._install_dir.exists():
            return []
        return [d.name for d in self._install_dir.iterdir() if d.is_dir()]

    @staticmethod
    def _load_builtin_catalog() -> list[dict[str, Any]]:
        return [
            {"name": "github", "description": "GitHub integration (issues, PRs, repos)", "tags": ["dev"]},
            {"name": "email", "description": "Email management and automation", "tags": ["productivity"]},
            {"name": "notes", "description": "Note-taking (Obsidian, Bear, Notion)", "tags": ["productivity"]},
            {"name": "data_science", "description": "Data analysis with pandas/matplotlib", "tags": ["data"]},
            {"name": "web_scraper", "description": "Advanced web scraping and data extraction", "tags": ["web"]},
            {"name": "code_review", "description": "Automated code review and suggestions", "tags": ["dev"]},
            {"name": "smart_home", "description": "Home Assistant integration", "tags": ["iot"]},
            {"name": "social_media", "description": "Social media posting and monitoring", "tags": ["social"]},
            {"name": "finance", "description": "Financial calculations and tracking", "tags": ["finance"]},
            {"name": "creative_writing", "description": "Story, poetry, and content generation", "tags": ["creative"]},
            {"name": "mlops", "description": "ML model training and deployment", "tags": ["ml"]},
            {"name": "security_audit", "description": "Security scanning and hardening", "tags": ["security"]},
        ]


# ---------------------------------------------------------------------------
# Skill sync
# ---------------------------------------------------------------------------


class SkillSync:
    """Sync skills across devices via a shared storage location."""

    def __init__(self, local_dir: Path, sync_dir: Optional[Path] = None) -> None:
        self._local = local_dir
        self._sync = sync_dir  # Could be a cloud drive, NFS, etc.

    def push(self) -> int:
        """Push local skills to sync directory."""
        if not self._sync:
            return 0
        import shutil
        count = 0
        for skill_dir in self._local.iterdir():
            if not skill_dir.is_dir():
                continue
            target = self._sync / skill_dir.name
            if not target.exists() or self._needs_update(skill_dir, target):
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(skill_dir, target)
                count += 1
        logger.info("skill_sync.pushed", count=count)
        return count

    def pull(self) -> int:
        """Pull skills from sync directory."""
        if not self._sync or not self._sync.exists():
            return 0
        import shutil
        count = 0
        for skill_dir in self._sync.iterdir():
            if not skill_dir.is_dir():
                continue
            target = self._local / skill_dir.name
            if not target.exists() or self._needs_update(skill_dir, target):
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(skill_dir, target)
                count += 1
        logger.info("skill_sync.pulled", count=count)
        return count

    @staticmethod
    def _needs_update(source: Path, target: Path) -> bool:
        """Check if source is newer than target."""
        try:
            return source.stat().st_mtime > target.stat().st_mtime
        except OSError:
            return True

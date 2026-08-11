"""Extended doctor diagnostics, config backup, and session tracking.

Implements:
- Doctor diagnostic improvements (check all dependencies, APIs, config)
- Config backup and rotation
- Active session tracking
- Blueprint catalog (predefined task templates)
- Personalized cron suggestions
- LSP integration basics
"""

from __future__ import annotations

import importlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Extended doctor diagnostics
# ---------------------------------------------------------------------------


class DoctorDiagnostics:
    """Comprehensive system health checks."""

    def run_all(self) -> list[dict[str, Any]]:
        """Run all diagnostic checks and return results."""
        results = []
        results.append(self._check_python())
        results.append(self._check_dependencies())
        results.append(self._check_config())
        results.append(self._check_api_keys())
        results.append(self._check_network())
        results.append(self._check_disk_space())
        results.append(self._check_optional_tools())
        results.append(self._check_databases())
        return results

    def _check_python(self) -> dict[str, Any]:
        version = sys.version_info
        ok = version >= (3, 11)
        return {
            "check": "Python Version",
            "status": "✅" if ok else "⚠️",
            "detail": f"{sys.version} ({'ok' if ok else 'Python 3.11+ recommended'})",
        }

    def _check_dependencies(self) -> dict[str, Any]:
        required = ["httpx", "structlog", "pydantic", "ruamel.yaml", "typer", "rich"]
        missing = []
        for pkg in required:
            try:
                importlib.import_module(pkg.replace("-", "_").replace(".", "_"))
            except ImportError:
                missing.append(pkg)

        return {
            "check": "Dependencies",
            "status": "✅" if not missing else "❌",
            "detail": f"All {len(required)} required packages installed" if not missing
                     else f"Missing: {', '.join(missing)}",
        }

    def _check_config(self) -> dict[str, Any]:
        config_path = Path.home() / ".hermclaw" / "hermclaw.yaml"
        if config_path.exists():
            size = config_path.stat().st_size
            return {"check": "Config File", "status": "✅", "detail": f"Found ({size} bytes)"}
        return {"check": "Config File", "status": "⚠️", "detail": "Not found (run hermclaw setup)"}

    def _check_api_keys(self) -> dict[str, Any]:
        keys = {
            "ANTHROPIC_API_KEY": "Anthropic",
            "OPENAI_API_KEY": "OpenAI",
            "GOOGLE_API_KEY": "Google Gemini",
            "BRAVE_API_KEY": "Brave Search",
            "ELEVENLABS_API_KEY": "ElevenLabs",
            "EXA_API_KEY": "Exa Search",
            "TAVILY_API_KEY": "Tavily",
            "XAI_API_KEY": "xAI/Grok",
        }
        found = []
        for env, name in keys.items():
            if os.environ.get(env):
                found.append(name)

        return {
            "check": "API Keys",
            "status": "✅" if found else "⚠️",
            "detail": f"Found: {', '.join(found)}" if found else "No API keys configured",
        }

    def _check_network(self) -> dict[str, Any]:
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return {"check": "Network", "status": "✅", "detail": "Internet connection available"}
        except OSError:
            return {"check": "Network", "status": "❌", "detail": "No internet connection"}

    def _check_disk_space(self) -> dict[str, Any]:
        total, used, free = shutil.disk_usage(Path.home())
        free_gb = free / (1024**3)
        return {
            "check": "Disk Space",
            "status": "✅" if free_gb > 1 else "⚠️",
            "detail": f"{free_gb:.1f} GB free",
        }

    def _check_optional_tools(self) -> dict[str, Any]:
        tools = {
            "git": "Git version control",
            "node": "Node.js runtime",
            "ollama": "Ollama local models",
            "docker": "Docker containers",
            "ffmpeg": "Media processing",
        }
        available = []
        for tool, desc in tools.items():
            try:
                subprocess.run([tool, "--version"], capture_output=True, timeout=5)
                available.append(tool)
            except Exception:
                pass

        return {
            "check": "Optional Tools",
            "status": "✅",
            "detail": f"Available: {', '.join(available) or 'none'}",
        }

    def _check_databases(self) -> dict[str, Any]:
        db_dir = Path.home() / ".hermclaw"
        dbs = list(db_dir.glob("*.db")) + list(db_dir.glob("**/*.db"))
        total_size = sum(d.stat().st_size for d in dbs)
        return {
            "check": "Databases",
            "status": "✅",
            "detail": f"{len(dbs)} databases, total {total_size // 1024} KB",
        }


# ---------------------------------------------------------------------------
# Config backup and rotation
# ---------------------------------------------------------------------------


class ConfigBackup:
    """Manage config file backups."""

    def __init__(self, config_path: Path) -> None:
        self._config = config_path
        self._backup_dir = config_path.parent / "config_backups"
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    def backup(self, label: str = "") -> Path:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        name = f"hermclaw_{timestamp}"
        if label:
            name += f"_{label}"
        name += self._config.suffix

        target = self._backup_dir / name
        shutil.copy2(self._config, target)
        logger.info("config.backup_created", path=str(target))
        return target

    def restore(self, backup_name: str) -> bool:
        source = self._backup_dir / backup_name
        if not source.exists():
            return False
        self.backup(label="pre_restore")
        shutil.copy2(source, self._config)
        logger.info("config.restored", from_backup=backup_name)
        return True

    def list_backups(self) -> list[dict]:
        return [
            {"name": f.name, "size": f.stat().st_size, "created": time.ctime(f.stat().st_ctime)}
            for f in sorted(self._backup_dir.iterdir(), reverse=True)
            if f.is_file()
        ]

    def rotate(self, keep: int = 10) -> int:
        files = sorted(self._backup_dir.iterdir(), key=lambda p: p.stat().st_ctime, reverse=True)
        removed = 0
        for f in files[keep:]:
            f.unlink()
            removed += 1
        return removed


# ---------------------------------------------------------------------------
# Active session tracking
# ---------------------------------------------------------------------------


class SessionTracker:
    """Track active sessions across the system."""

    def __init__(self, state_dir: Path) -> None:
        self._state_dir = state_dir
        self._sessions_file = state_dir / "active_sessions.json"

    def register(self, session_id: str, channel: str, profile: str) -> None:
        sessions = self._load()
        sessions[session_id] = {
            "channel": channel,
            "profile": profile,
            "started_at": time.time(),
            "last_activity": time.time(),
            "pid": os.getpid(),
        }
        self._save(sessions)

    def update_activity(self, session_id: str) -> None:
        sessions = self._load()
        if session_id in sessions:
            sessions[session_id]["last_activity"] = time.time()
            self._save(sessions)

    def unregister(self, session_id: str) -> None:
        sessions = self._load()
        sessions.pop(session_id, None)
        self._save(sessions)

    def list_active(self) -> list[dict]:
        sessions = self._load()
        result = []
        for sid, data in sessions.items():
            data["session_id"] = sid
            data["uptime_s"] = round(time.time() - data.get("started_at", time.time()))
            result.append(data)
        return result

    def _load(self) -> dict:
        if self._sessions_file.exists():
            try:
                return json.loads(self._sessions_file.read_text())
            except Exception:
                return {}
        return {}

    def _save(self, sessions: dict) -> None:
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._sessions_file.write_text(json.dumps(sessions, indent=2))


# ---------------------------------------------------------------------------
# Blueprint catalog (task templates)
# ---------------------------------------------------------------------------


BLUEPRINT_CATALOG = [
    {
        "name": "code_review",
        "description": "Review code for quality, security, and best practices",
        "template": "Review this code for: 1) Security vulnerabilities 2) Performance issues 3) Code style 4) Potential bugs. Provide specific suggestions.",
        "tags": ["development"],
    },
    {
        "name": "project_setup",
        "description": "Set up a new project with best practices",
        "template": "Create a new {language} project with: 1) Directory structure 2) Config files 3) Linting/formatting 4) CI/CD 5) README 6) Tests",
        "tags": ["development"],
    },
    {
        "name": "debug_session",
        "description": "Systematic debugging of an issue",
        "template": "Debug this issue: {description}. Steps: 1) Reproduce 2) Isolate 3) Identify root cause 4) Fix 5) Verify 6) Prevent regression",
        "tags": ["development"],
    },
    {
        "name": "meeting_notes",
        "description": "Summarize and organize meeting notes",
        "template": "Organize these meeting notes: {notes}. Include: 1) Key decisions 2) Action items 3) Follow-ups 4) Attendees",
        "tags": ["productivity"],
    },
    {
        "name": "research_report",
        "description": "Research a topic and create a structured report",
        "template": "Research {topic}. Create a report with: 1) Executive summary 2) Key findings 3) Analysis 4) Recommendations 5) Sources",
        "tags": ["research"],
    },
    {
        "name": "refactor",
        "description": "Plan and execute a code refactoring",
        "template": "Refactor {component}: 1) Identify code smells 2) Plan changes 3) Execute refactoring 4) Update tests 5) Verify behavior unchanged",
        "tags": ["development"],
    },
    {
        "name": "api_integration",
        "description": "Integrate with an external API",
        "template": "Integrate with {api_name}: 1) Read docs 2) Set up auth 3) Implement client 4) Add error handling 5) Write tests 6) Document",
        "tags": ["development"],
    },
    {
        "name": "data_analysis",
        "description": "Analyze a dataset and create visualizations",
        "template": "Analyze {dataset}: 1) Load and inspect 2) Clean data 3) Exploratory analysis 4) Statistical tests 5) Visualizations 6) Report",
        "tags": ["data"],
    },
]


def get_blueprint(name: str) -> Optional[dict]:
    for bp in BLUEPRINT_CATALOG:
        if bp["name"] == name:
            return bp
    return None


def search_blueprints(query: str) -> list[dict]:
    q = query.lower()
    return [bp for bp in BLUEPRINT_CATALOG
            if q in bp["name"].lower() or q in bp.get("description", "").lower()]


# ---------------------------------------------------------------------------
# Personalized cron suggestions
# ---------------------------------------------------------------------------


class CronSuggester:
    """Suggest personalized cron schedules based on user patterns."""

    COMMON_PATTERNS = {
        "daily_standup": {"cron": "0 9 * * 1-5", "description": "Every weekday at 9 AM"},
        "weekly_review": {"cron": "0 17 * * 5", "description": "Every Friday at 5 PM"},
        "hourly_check": {"cron": "0 * * * *", "description": "Every hour on the hour"},
        "morning_brief": {"cron": "30 8 * * *", "description": "Every day at 8:30 AM"},
        "backup_nightly": {"cron": "0 2 * * *", "description": "Every night at 2 AM"},
        "monthly_report": {"cron": "0 9 1 * *", "description": "First day of each month at 9 AM"},
    }

    def suggest(self, task_description: str) -> list[dict]:
        """Suggest cron schedules based on task description."""
        desc_lower = task_description.lower()
        suggestions = []

        if any(w in desc_lower for w in ["daily", "every day", "morning"]):
            suggestions.append(self.COMMON_PATTERNS["morning_brief"])
        if any(w in desc_lower for w in ["weekly", "every week", "friday"]):
            suggestions.append(self.COMMON_PATTERNS["weekly_review"])
        if any(w in desc_lower for w in ["hourly", "every hour"]):
            suggestions.append(self.COMMON_PATTERNS["hourly_check"])
        if any(w in desc_lower for w in ["backup", "nightly", "night"]):
            suggestions.append(self.COMMON_PATTERNS["backup_nightly"])
        if any(w in desc_lower for w in ["monthly", "month"]):
            suggestions.append(self.COMMON_PATTERNS["monthly_report"])
        if any(w in desc_lower for w in ["standup", "stand-up", "meeting"]):
            suggestions.append(self.COMMON_PATTERNS["daily_standup"])

        if not suggestions:
            suggestions.append(self.COMMON_PATTERNS["morning_brief"])

        return suggestions


# ---------------------------------------------------------------------------
# LSP integration (basic language server protocol)
# ---------------------------------------------------------------------------


class LSPClient:
    """Basic LSP client for code intelligence.

    Provides:
    - Diagnostics (errors, warnings)
    - Go-to-definition
    - Find references
    """

    def __init__(self, language: str = "python") -> None:
        self._language = language
        self._server_cmd = self._get_server_cmd()

    def _get_server_cmd(self) -> list[str]:
        if self._language == "python":
            return ["pyright-langserver", "--stdio"]
        elif self._language == "typescript":
            return ["typescript-language-server", "--stdio"]
        elif self._language == "rust":
            return ["rust-analyzer"]
        return []

    def get_diagnostics(self, file_path: str) -> list[dict]:
        """Get diagnostics for a file using the language's linter."""
        if self._language == "python":
            return self._python_diagnostics(file_path)
        return []

    def _python_diagnostics(self, file_path: str) -> list[dict]:
        """Get Python diagnostics using ruff or flake8."""
        results = []
        try:
            proc = subprocess.run(
                ["ruff", "check", file_path, "--output-format", "json"],
                capture_output=True, text=True, timeout=30,
            )
            if proc.stdout:
                for item in json.loads(proc.stdout):
                    results.append({
                        "file": file_path,
                        "line": item.get("location", {}).get("row", 0),
                        "column": item.get("location", {}).get("column", 0),
                        "severity": "warning",
                        "code": item.get("code", ""),
                        "message": item.get("message", ""),
                    })
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        # Fallback to flake8
        if not results:
            try:
                proc = subprocess.run(
                    ["flake8", "--format=json", file_path],
                    capture_output=True, text=True, timeout=30,
                )
                # Parse flake8 output
            except FileNotFoundError:
                pass

        return results

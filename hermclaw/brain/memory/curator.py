"""Memory curator: auto-organizes, deduplicates, and backs up memory.

Also includes:
- Context references tracking
- Memory backup/restore
- Memory sanitization
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


class MemoryCurator:
    """Autonomously organizes and curates long-term memory.

    Periodically:
    1. Deduplicates similar memories
    2. Consolidates related facts
    3. Archives old/unused memories
    4. Creates skills from recurring patterns
    """

    def __init__(self, vector_memory: Any = None) -> None:
        self._vector = vector_memory
        self._dedup_hashes: set[str] = set()

    def deduplicate(self, facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Remove duplicate or near-duplicate facts."""
        unique: list[dict[str, Any]] = []
        for fact in facts:
            content = fact.get("content", "")
            h = hashlib.md5(content.lower().strip().encode()).hexdigest()
            if h not in self._dedup_hashes:
                self._dedup_hashes.add(h)
                unique.append(fact)
        removed = len(facts) - len(unique)
        if removed:
            logger.info("curator.deduplicated", removed=removed, remaining=len(unique))
        return unique

    def consolidate(self, facts: list[dict[str, Any]], category: str = "") -> list[dict[str, Any]]:
        """Group related facts and create summaries."""
        if len(facts) < 5:
            return facts

        by_tag: dict[str, list] = {}
        for fact in facts:
            tags = fact.get("tags", ["general"])
            for tag in tags:
                by_tag.setdefault(tag, []).append(fact)

        consolidated: list[dict[str, Any]] = []
        for tag, group in by_tag.items():
            if len(group) >= 3:
                # Create a consolidated fact
                contents = [f.get("content", "") for f in group[:10]]
                summary = f"[Consolidated from {len(group)} facts about '{tag}']\n" + \
                          "\n".join(f"- {c[:100]}" for c in contents)
                consolidated.append({
                    "content": summary,
                    "tags": [tag, "consolidated"],
                    "source_count": len(group),
                })
            else:
                consolidated.extend(group)

        logger.info("curator.consolidated", original=len(facts), result=len(consolidated))
        return consolidated

    def archive_old(self, facts: list[dict[str, Any]], max_age_days: int = 90) -> tuple[list[dict], list[dict]]:
        """Split facts into active and archived based on age."""
        now = time.time()
        cutoff = now - (max_age_days * 86400)

        active = []
        archived = []
        for fact in facts:
            ts = fact.get("timestamp", now)
            if ts < cutoff and not fact.get("pinned", False):
                archived.append(fact)
            else:
                active.append(fact)

        if archived:
            logger.info("curator.archived", count=len(archived))
        return active, archived

    def curate(self, facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Full curation pipeline: deduplicate → consolidate → archive."""
        facts = self.deduplicate(facts)
        facts = self.consolidate(facts)
        active, _ = self.archive_old(facts)
        return active


class MemoryBackup:
    """Backup and restore memory databases."""

    def __init__(self, state_dir: Path) -> None:
        self._state_dir = state_dir
        self._backup_dir = state_dir / "backups"
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    def backup(self, db_path: Path, label: str = "") -> Path:
        """Create a backup of a memory database."""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        suffix = f"_{label}" if label else ""
        backup_name = f"{db_path.stem}_{timestamp}{suffix}{db_path.suffix}"
        backup_path = self._backup_dir / backup_name

        shutil.copy2(db_path, backup_path)
        logger.info("memory.backup_created", path=str(backup_path),
                    size_kb=backup_path.stat().st_size // 1024)
        return backup_path

    def restore(self, backup_path: Path, target_path: Path) -> bool:
        """Restore a memory database from backup."""
        if not backup_path.exists():
            logger.error("memory.backup_not_found", path=str(backup_path))
            return False

        # Safety: backup the current state before restoring
        if target_path.exists():
            self.backup(target_path, label="pre_restore")

        shutil.copy2(backup_path, target_path)
        logger.info("memory.restored", from_backup=str(backup_path))
        return True

    def list_backups(self) -> list[dict[str, Any]]:
        """List available backups."""
        backups = []
        for p in sorted(self._backup_dir.iterdir(), reverse=True):
            if p.is_file():
                backups.append({
                    "name": p.name,
                    "path": str(p),
                    "size_kb": p.stat().st_size // 1024,
                    "created": time.ctime(p.stat().st_ctime),
                })
        return backups

    def rotate(self, max_backups: int = 10) -> int:
        """Remove old backups, keeping only the most recent N."""
        files = sorted(self._backup_dir.iterdir(), key=lambda p: p.stat().st_ctime, reverse=True)
        removed = 0
        for f in files[max_backups:]:
            f.unlink()
            removed += 1
        if removed:
            logger.info("memory.backups_rotated", removed=removed)
        return removed


class ContextRefTracker:
    """Tracks which files, URLs, and symbols have been referenced in context."""

    def __init__(self) -> None:
        self._files: dict[str, float] = {}  # path -> last_referenced
        self._urls: dict[str, float] = {}
        self._symbols: dict[str, float] = {}  # class/function names

    def track_file(self, path: str) -> None:
        self._files[path] = time.time()

    def track_url(self, url: str) -> None:
        self._urls[url] = time.time()

    def track_symbol(self, symbol: str) -> None:
        self._symbols[symbol] = time.time()

    def recent_files(self, n: int = 10) -> list[str]:
        """Most recently referenced files."""
        return sorted(self._files, key=self._files.get, reverse=True)[:n]

    def recent_urls(self, n: int = 10) -> list[str]:
        return sorted(self._urls, key=self._urls.get, reverse=True)[:n]

    def summary(self) -> dict[str, int]:
        return {
            "files_referenced": len(self._files),
            "urls_referenced": len(self._urls),
            "symbols_referenced": len(self._symbols),
        }

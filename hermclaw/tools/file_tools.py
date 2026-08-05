"""File-system tools: read, write, edit, list_dir, grep.

These give the agent structured, safe ways to interact with files without
shelling out.  Every operation respects the configured filesystem_scope
(validated via path resolution) and goes through ToolDispatcher.
"""

from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path
from typing import Any, Optional

import structlog

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec

logger = structlog.get_logger(__name__)


def _resolve_safe(path_str: str, scope: Optional[str] = None) -> Path:
    """Resolve a path and optionally verify it's within scope."""
    p = Path(os.path.expanduser(path_str)).resolve()
    if scope:
        scope_p = Path(os.path.expanduser(scope)).resolve()
        if not str(p).startswith(str(scope_p)):
            raise PermissionError(f"Path {p} is outside allowed scope {scope_p}")
    return p


# ---------------------------------------------------------------------------
# FileRead
# ---------------------------------------------------------------------------


class FileReadTool(ToolABC):
    """Read file contents with optional line range."""

    def __init__(self, filesystem_scope: Optional[str] = None) -> None:
        self._scope = filesystem_scope

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="file_read",
            description=(
                "Read the contents of a file. Returns the text content with line numbers. "
                "Use start_line and end_line to read specific ranges (1-indexed, inclusive). "
                "Omit them to read the entire file."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative file path to read."},
                    "start_line": {"type": "integer", "description": "First line to read (1-indexed). Optional."},
                    "end_line": {"type": "integer", "description": "Last line to read (1-indexed, inclusive). Optional."},
                },
                "required": ["path"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        try:
            p = _resolve_safe(args["path"], self._scope)
            if not p.exists():
                return ToolResult(ok=False, output="", error=f"File not found: {p}")
            if not p.is_file():
                return ToolResult(ok=False, output="", error=f"Not a file: {p}")

            text = p.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            total = len(lines)

            start = args.get("start_line")
            end = args.get("end_line")
            if start is not None or end is not None:
                s = max(1, start or 1) - 1
                e = min(total, end or total)
                lines = lines[s:e]
                header = f"[{p}] lines {s+1}-{e} of {total}"
            else:
                header = f"[{p}] {total} lines"

            numbered = [f"{i+1}: {line}" for i, line in enumerate(lines, start=(start or 1) - 1)]
            return ToolResult(ok=True, output=f"{header}\n" + "\n".join(numbered))
        except PermissionError as exc:
            return ToolResult(ok=False, output="", error=str(exc))
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Error reading file: {exc}")


# ---------------------------------------------------------------------------
# FileWrite
# ---------------------------------------------------------------------------


class FileWriteTool(ToolABC):
    """Create or overwrite a file."""

    def __init__(self, filesystem_scope: Optional[str] = None) -> None:
        self._scope = filesystem_scope

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="file_write",
            description=(
                "Create a new file or overwrite an existing file with the given content. "
                "Parent directories are created automatically. Use for creating new files."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to create/write."},
                    "content": {"type": "string", "description": "The full content to write to the file."},
                },
                "required": ["path", "content"],
            },
            requires_approval_gate=True,
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        try:
            p = _resolve_safe(args["path"], self._scope)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(args["content"], encoding="utf-8")
            lines = args["content"].count("\n") + 1
            return ToolResult(ok=True, output=f"Wrote {lines} lines to {p}")
        except PermissionError as exc:
            return ToolResult(ok=False, output="", error=str(exc))
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Error writing file: {exc}")


# ---------------------------------------------------------------------------
# FileEdit
# ---------------------------------------------------------------------------


class FileEditTool(ToolABC):
    """Targeted search-and-replace editing within a file."""

    def __init__(self, filesystem_scope: Optional[str] = None) -> None:
        self._scope = filesystem_scope

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="file_edit",
            description=(
                "Edit a file by replacing specific text. Finds 'old_text' in the file and "
                "replaces it with 'new_text'. The old_text must match exactly (including "
                "whitespace and indentation). Use for targeted edits to existing files."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to edit."},
                    "old_text": {"type": "string", "description": "Exact text to find and replace."},
                    "new_text": {"type": "string", "description": "Replacement text."},
                },
                "required": ["path", "old_text", "new_text"],
            },
            requires_approval_gate=True,
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        try:
            p = _resolve_safe(args["path"], self._scope)
            if not p.exists():
                return ToolResult(ok=False, output="", error=f"File not found: {p}")

            content = p.read_text(encoding="utf-8")
            old_text = args["old_text"]
            new_text = args["new_text"]

            count = content.count(old_text)
            if count == 0:
                return ToolResult(ok=False, output="", error="old_text not found in file. Check whitespace/indentation.")
            if count > 1:
                return ToolResult(ok=False, output="", error=f"old_text found {count} times. Make it more specific to match exactly once.")

            new_content = content.replace(old_text, new_text, 1)
            p.write_text(new_content, encoding="utf-8")
            return ToolResult(ok=True, output=f"Edited {p}: replaced 1 occurrence ({len(old_text)} chars → {len(new_text)} chars)")
        except PermissionError as exc:
            return ToolResult(ok=False, output="", error=str(exc))
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Error editing file: {exc}")


# ---------------------------------------------------------------------------
# ListDir
# ---------------------------------------------------------------------------


class ListDirTool(ToolABC):
    """List contents of a directory."""

    def __init__(self, filesystem_scope: Optional[str] = None) -> None:
        self._scope = filesystem_scope

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="list_dir",
            description=(
                "List the contents of a directory. Shows files and subdirectories with "
                "sizes. Use pattern to filter by glob (e.g., '*.py'). Use recursive=true "
                "to list subdirectories too."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to list."},
                    "pattern": {"type": "string", "description": "Glob pattern to filter (e.g., '*.py'). Optional."},
                    "recursive": {"type": "boolean", "description": "Whether to list recursively. Default false."},
                },
                "required": ["path"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        try:
            p = _resolve_safe(args["path"], self._scope)
            if not p.exists():
                return ToolResult(ok=False, output="", error=f"Directory not found: {p}")
            if not p.is_dir():
                return ToolResult(ok=False, output="", error=f"Not a directory: {p}")

            pattern = args.get("pattern", "*")
            recursive = args.get("recursive", False)

            entries = []
            items = list(p.rglob(pattern)) if recursive else list(p.glob(pattern))
            items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))

            for item in items[:200]:  # cap output
                rel = item.relative_to(p)
                if item.is_dir():
                    child_count = sum(1 for _ in item.iterdir()) if item.is_dir() else 0
                    entries.append(f"  [DIR] {rel}/ ({child_count} items)")
                else:
                    size = item.stat().st_size
                    if size < 1024:
                        size_str = f"{size}B"
                    elif size < 1024 * 1024:
                        size_str = f"{size/1024:.1f}KB"
                    else:
                        size_str = f"{size/1024/1024:.1f}MB"
                    entries.append(f"  [FILE] {rel} ({size_str})")

            header = f"[{p}] {len(entries)} items"
            if len(items) > 200:
                header += f" (showing 200 of {len(items)})"
            return ToolResult(ok=True, output=header + "\n" + "\n".join(entries))
        except PermissionError as exc:
            return ToolResult(ok=False, output="", error=str(exc))
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Error listing directory: {exc}")


# ---------------------------------------------------------------------------
# GrepSearch
# ---------------------------------------------------------------------------


class GrepSearchTool(ToolABC):
    """Search files for text patterns (regex or literal)."""

    def __init__(self, filesystem_scope: Optional[str] = None) -> None:
        self._scope = filesystem_scope

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="grep_search",
            description=(
                "Search for text patterns in files. Searches recursively in the given "
                "directory. Returns matching lines with file paths and line numbers. "
                "Supports regex patterns. Use include_glob to filter file types (e.g., '*.py')."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Text or regex pattern to search for."},
                    "path": {"type": "string", "description": "Directory or file to search in."},
                    "include_glob": {"type": "string", "description": "Only search files matching this glob (e.g., '*.py'). Optional."},
                    "case_insensitive": {"type": "boolean", "description": "Case-insensitive search. Default false."},
                    "is_regex": {"type": "boolean", "description": "Treat query as regex. Default false."},
                },
                "required": ["query", "path"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        try:
            p = _resolve_safe(args["path"], self._scope)
            if not p.exists():
                return ToolResult(ok=False, output="", error=f"Path not found: {p}")

            query = args["query"]
            case_insensitive = args.get("case_insensitive", False)
            is_regex = args.get("is_regex", False)
            include_glob = args.get("include_glob")

            flags = re.IGNORECASE if case_insensitive else 0
            try:
                pattern = re.compile(query, flags) if is_regex else re.compile(re.escape(query), flags)
            except re.error as exc:
                return ToolResult(ok=False, output="", error=f"Invalid regex: {exc}")

            matches = []
            files = [p] if p.is_file() else list(p.rglob(include_glob or "*"))

            # Binary detection heuristic
            def _is_text(fp: Path) -> bool:
                try:
                    with open(fp, "rb") as f:
                        chunk = f.read(1024)
                        return b"\x00" not in chunk
                except Exception:
                    return False

            for fp in files:
                if not fp.is_file() or not _is_text(fp):
                    continue
                try:
                    for i, line in enumerate(fp.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                        if pattern.search(line):
                            rel = fp.relative_to(p) if p.is_dir() else fp.name
                            matches.append(f"  {rel}:{i}: {line.rstrip()}")
                            if len(matches) >= 50:
                                break
                except Exception:
                    continue
                if len(matches) >= 50:
                    break

            if not matches:
                return ToolResult(ok=True, output="No matches found.")
            header = f"Found {len(matches)} matches"
            if len(matches) >= 50:
                header += " (capped at 50)"
            return ToolResult(ok=True, output=header + "\n" + "\n".join(matches))
        except PermissionError as exc:
            return ToolResult(ok=False, output="", error=str(exc))
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Error searching: {exc}")

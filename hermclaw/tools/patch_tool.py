"""Unified diff/patch application tool.

Applies unified diff patches (the format produced by `git diff`, `diff -u`)
to files. This enables the agent to make complex multi-hunk edits that the
simple search-and-replace FileEditTool can't handle cleanly.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Optional

import structlog

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec

logger = structlog.get_logger(__name__)


def _resolve_safe(path_str: str, scope: Optional[str] = None) -> Path:
    p = Path(os.path.expanduser(path_str)).resolve()
    if scope:
        scope_p = Path(os.path.expanduser(scope)).resolve()
        if not str(p).startswith(str(scope_p)):
            raise PermissionError(f"Path {p} is outside allowed scope {scope_p}")
    return p


def apply_unified_diff(original: str, patch_text: str) -> str:
    """Apply a unified diff patch to the original text.

    Parses the patch hunks and applies them sequentially,
    adjusting line numbers for preceding hunks' offset changes.
    """
    lines = original.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"

    # Parse hunks from the patch
    hunk_header = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
    hunks: list[dict] = []
    current_hunk: Optional[dict] = None

    for line in patch_text.splitlines(keepends=True):
        if not line.endswith("\n"):
            line += "\n"

        m = hunk_header.match(line)
        if m:
            if current_hunk:
                hunks.append(current_hunk)
            current_hunk = {
                "old_start": int(m.group(1)),
                "old_count": int(m.group(2)) if m.group(2) else 1,
                "new_start": int(m.group(3)),
                "new_count": int(m.group(4)) if m.group(4) else 1,
                "lines": [],
            }
        elif current_hunk is not None:
            if line.startswith("---") or line.startswith("+++"):
                continue
            if line.startswith("-") or line.startswith("+") or line.startswith(" "):
                current_hunk["lines"].append(line)
            elif line.startswith("\\"):
                continue  # "\ No newline at end of file"

    if current_hunk:
        hunks.append(current_hunk)

    if not hunks:
        raise ValueError("No valid hunks found in the patch.")

    # Apply hunks in reverse order to preserve line numbers
    offset = 0
    for hunk in hunks:
        start = hunk["old_start"] - 1 + offset  # 0-indexed
        removed = []
        added = []

        for hl in hunk["lines"]:
            if hl.startswith("-"):
                removed.append(hl[1:])
            elif hl.startswith("+"):
                added.append(hl[1:])
            elif hl.startswith(" "):
                removed.append(hl[1:])
                added.append(hl[1:])

        # Verify the removed lines match
        actual = lines[start:start + len(removed)]
        for i, (expected, got) in enumerate(zip(removed, actual)):
            exp_s = expected.rstrip("\n")
            got_s = got.rstrip("\n")
            if exp_s != got_s:
                raise ValueError(
                    f"Patch mismatch at line {start + i + 1}: "
                    f"expected {exp_s!r}, got {got_s!r}"
                )

        # Apply the replacement
        lines[start:start + len(removed)] = added
        offset += len(added) - len(removed)

    return "".join(lines)


class PatchTool(ToolABC):
    """Apply a unified diff patch to a file."""

    def __init__(self, filesystem_scope: Optional[str] = None) -> None:
        self._scope = filesystem_scope

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="patch",
            description=(
                "Apply a unified diff patch to a file. The patch should be in "
                "standard unified diff format (like git diff output). "
                "Use this for complex multi-hunk edits that file_edit can't handle."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to patch."},
                    "patch": {
                        "type": "string",
                        "description": (
                            "Unified diff patch text. Must include @@ hunk headers "
                            "and lines prefixed with +, -, or space."
                        ),
                    },
                },
                "required": ["path", "patch"],
            },
            requires_approval_gate=True,
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        try:
            p = _resolve_safe(args["path"], self._scope)
            if not p.exists():
                return ToolResult(ok=False, output="", error=f"File not found: {p}")

            original = p.read_text(encoding="utf-8")
            patch_text = args["patch"]

            patched = apply_unified_diff(original, patch_text)
            p.write_text(patched, encoding="utf-8")

            # Count changes
            old_lines = original.count("\n")
            new_lines = patched.count("\n")
            diff = new_lines - old_lines
            sign = "+" if diff >= 0 else ""

            return ToolResult(
                ok=True,
                output=f"Patched {p}: {old_lines} -> {new_lines} lines ({sign}{diff})"
            )
        except PermissionError as exc:
            return ToolResult(ok=False, output="", error=str(exc))
        except ValueError as exc:
            return ToolResult(ok=False, output="", error=f"Patch error: {exc}")
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Error applying patch: {exc}")

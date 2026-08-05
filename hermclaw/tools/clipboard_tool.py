"""Clipboard tool: read from and write to the system clipboard.

Uses platform-native clipboard commands (pbcopy/pbpaste on macOS,
xclip/xsel on Linux, clip/powershell on Windows).
"""

from __future__ import annotations

import platform
import subprocess
from typing import Any

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec


class ClipboardTool(ToolABC):
    """Read from and write to the system clipboard."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="clipboard",
            description=(
                "Access the system clipboard. Actions: read (get clipboard content), "
                "write (set clipboard content). Useful for copying data between "
                "applications."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["read", "write"],
                        "description": "Clipboard action.",
                    },
                    "content": {"type": "string", "description": "Content to write to clipboard."},
                },
                "required": ["action"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        action = args.get("action", "")
        system = platform.system()

        try:
            if action == "read":
                return await self._read_clipboard(system)
            elif action == "write":
                content = args.get("content", "")
                if not content:
                    return ToolResult(ok=False, output="", error="'content' required for write.")
                return await self._write_clipboard(system, content)
            else:
                return ToolResult(ok=False, output="", error=f"Unknown action: {action}")
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Clipboard error: {exc}")

    async def _read_clipboard(self, system: str) -> ToolResult:
        if system == "Windows":
            result = subprocess.run(
                ["powershell", "-Command", "Get-Clipboard"],
                capture_output=True, text=True, timeout=5,
            )
        elif system == "Darwin":
            result = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5)
        else:
            # Linux
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True, text=True, timeout=5,
            )
        if result.returncode != 0:
            return ToolResult(ok=False, output="", error=f"Failed to read clipboard: {result.stderr}")
        return ToolResult(ok=True, output=result.stdout)

    async def _write_clipboard(self, system: str, content: str) -> ToolResult:
        if system == "Windows":
            result = subprocess.run(
                ["powershell", "-Command", f"Set-Clipboard -Value '{content}'"],
                capture_output=True, text=True, timeout=5,
            )
        elif system == "Darwin":
            result = subprocess.run(
                ["pbcopy"], input=content, capture_output=True, text=True, timeout=5,
            )
        else:
            result = subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=content, capture_output=True, text=True, timeout=5,
            )
        if result.returncode != 0:
            return ToolResult(ok=False, output="", error=f"Failed to write clipboard: {result.stderr}")
        return ToolResult(ok=True, output=f"Copied {len(content)} characters to clipboard.")

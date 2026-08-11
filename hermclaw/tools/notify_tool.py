"""Notification tool: send system notifications and alerts.

Supports:
- Windows toast notifications (via WinForms NotifyIcon)
- macOS notification center
- Linux desktop notifications (notify-send)
"""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path
from typing import Any

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec

# Path to the PowerShell notification helper script
_NOTIFY_PS1 = Path(__file__).parent / "notify.ps1"


class NotifyTool(ToolABC):
    """Send system notifications to the user."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="notify",
            description=(
                "Send a system notification to the user. Works on Windows (toast), "
                "macOS (notification center), and Linux (notify-send). "
                "Use to alert the user when a long task completes."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Notification title."},
                    "message": {"type": "string", "description": "Notification body."},
                    "urgency": {
                        "type": "string",
                        "enum": ["low", "normal", "critical"],
                        "description": "Urgency level. Default: normal.",
                    },
                },
                "required": ["message"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        title = args.get("title", "Hermclaw")
        message = args.get("message", "")
        urgency = args.get("urgency", "normal")

        if not message:
            return ToolResult(ok=False, output="", error="'message' required.")

        system = platform.system()
        try:
            if system == "Windows":
                result = subprocess.run(
                    [
                        "powershell", "-ExecutionPolicy", "Bypass",
                        "-File", str(_NOTIFY_PS1),
                        title, message,
                    ],
                    capture_output=True, text=True, timeout=15,
                )
                if result.returncode != 0:
                    return ToolResult(
                        ok=False, output="",
                        error=f"Notification failed: {result.stderr.strip()}"
                    )

            elif system == "Darwin":
                subprocess.run(
                    ["osascript", "-e", f'display notification "{message}" with title "{title}"'],
                    timeout=5,
                )
            else:
                subprocess.run(
                    ["notify-send", f"--urgency={urgency}", title, message],
                    timeout=5,
                )

            return ToolResult(ok=True, output=f"Notification sent: {title} - {message}")
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Notification failed: {exc}")


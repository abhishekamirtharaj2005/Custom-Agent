"""Notification tool: send system notifications and alerts.

Supports:
- Windows: ctypes MessageBox (always works, no dependencies)
- macOS: notification center
- Linux: notify-send
"""

from __future__ import annotations

import platform
import subprocess
import threading
from typing import Any

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec


class NotifyTool(ToolABC):
    """Send system notifications to the user."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="notify",
            description=(
                "Send a system notification to the user. Works on Windows (popup), "
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
                self._windows_notify(title, message)

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

    @staticmethod
    def _windows_notify(title: str, message: str) -> None:
        """Show a Windows notification using ctypes MessageBox in a thread.

        This is the most reliable approach on Windows — no external
        dependencies required, works from any context (console, venv, etc.).
        The MessageBox runs in a daemon thread so it doesn't block the agent.
        """
        import ctypes

        # MB_OK | MB_ICONINFORMATION | MB_SYSTEMMODAL
        # MB_SYSTEMMODAL (0x1000) makes it appear on top of all windows
        FLAGS = 0x40 | 0x1000

        def _show():
            ctypes.windll.user32.MessageBoxW(0, message, title, FLAGS)

        t = threading.Thread(target=_show, daemon=True)
        t.start()

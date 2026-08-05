"""Notification tool: send system notifications and alerts.

Supports:
- Windows toast notifications
- macOS notification center
- Linux desktop notifications (notify-send)
- Cross-platform terminal bell
"""

from __future__ import annotations

import platform
import subprocess
from typing import Any

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec


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
                # Use PowerShell toast notification
                ps_script = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$template = @"
<toast>
  <visual>
    <binding template="ToastGeneric">
      <text>{title}</text>
      <text>{message}</text>
    </binding>
  </visual>
</toast>
"@
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($template)
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Hermclaw").Show($toast)
"""
                result = subprocess.run(
                    ["powershell", "-Command", ps_script],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode != 0:
                    # Fallback to simple msg
                    subprocess.run(
                        ["powershell", "-Command", f"Write-Host '{title}: {message}'"],
                        timeout=5,
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

"""Application launcher tool: open and control system applications.

Cross-platform application launching with:
- Windows (start, PowerShell Start-Process)
- macOS (open)
- Linux (xdg-open)
"""

from __future__ import annotations

import platform
import subprocess
from typing import Any

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec


# Common application name to executable mappings (Windows)
_WIN_APP_MAP = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "paint": "mspaint.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "terminal": "wt.exe",
    "task manager": "taskmgr.exe",
    "control panel": "control.exe",
    "settings": "ms-settings:",
    "browser": "start https://",
    "chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "outlook": "outlook.exe",
    "vscode": "code",
    "vs code": "code",
    "spotify": "spotify.exe",
    "discord": "discord.exe",
    "telegram": "telegram.exe",
    "whatsapp": "WhatsApp.exe",
    "youtube": "start https://youtube.com",
    "github": "start https://github.com",
    "google": "start https://google.com",
    "gmail": "start https://mail.google.com",
    "chatgpt": "start https://chat.openai.com",
}


class AppLauncherTool(ToolABC):
    """Launch and manage system applications."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="app_launcher",
            description=(
                "Launch system applications, open files and URLs. Actions: open (launch app/file/URL), "
                "list_running (show running processes), close (terminate an app). "
                "Knows common app names (chrome, vscode, spotify, youtube, etc.)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["open", "list_running", "close"],
                        "description": "Action to perform.",
                    },
                    "target": {
                        "type": "string",
                        "description": "App name, file path, or URL to open.",
                    },
                    "args": {
                        "type": "string",
                        "description": "Additional arguments for the application.",
                    },
                },
                "required": ["action"],
            },
            requires_approval_gate=True,
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        action = args.get("action", "")
        target = args.get("target", "")
        extra_args = args.get("args", "")
        system = platform.system()

        try:
            if action == "open":
                return self._open(system, target, extra_args)
            elif action == "list_running":
                return self._list_running(system)
            elif action == "close":
                return self._close(system, target)
            else:
                return ToolResult(ok=False, output="", error=f"Unknown action: {action}")
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"App launcher error: {exc}")

    def _open(self, system: str, target: str, extra_args: str) -> ToolResult:
        if not target:
            return ToolResult(ok=False, output="", error="'target' is required.")

        target_lower = target.lower().strip()

        if system == "Windows":
            # Check common app map
            mapped = _WIN_APP_MAP.get(target_lower, "")
            if mapped:
                if mapped.startswith("start "):
                    url = mapped[6:]
                    subprocess.Popen(["cmd", "/c", "start", url], shell=False)
                    return ToolResult(ok=True, output=f"Opening: {url}")
                elif mapped.startswith("ms-"):
                    subprocess.Popen(["cmd", "/c", "start", mapped], shell=False)
                    return ToolResult(ok=True, output=f"Opening: {mapped}")
                else:
                    cmd = [mapped]
                    if extra_args:
                        cmd.extend(extra_args.split())
                    subprocess.Popen(cmd, shell=False)
                    return ToolResult(ok=True, output=f"Launched: {mapped}")

            # URL detection
            if target_lower.startswith(("http://", "https://", "www.")):
                subprocess.Popen(["cmd", "/c", "start", target], shell=False)
                return ToolResult(ok=True, output=f"Opening URL: {target}")

            # File or generic app
            cmd = ["cmd", "/c", "start", "", target]
            if extra_args:
                cmd.extend(extra_args.split())
            subprocess.Popen(cmd, shell=False)
            return ToolResult(ok=True, output=f"Opening: {target}")

        elif system == "Darwin":
            cmd = ["open"]
            if target_lower.startswith(("http://", "https://")):
                cmd.append(target)
            else:
                cmd.extend(["-a", target])
            if extra_args:
                cmd.extend(["--args"] + extra_args.split())
            subprocess.Popen(cmd)
            return ToolResult(ok=True, output=f"Opening: {target}")

        else:
            # Linux
            subprocess.Popen(["xdg-open", target])
            return ToolResult(ok=True, output=f"Opening: {target}")

    def _list_running(self, system: str) -> ToolResult:
        if system == "Windows":
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | Select-Object -Property Name, Id, MainWindowTitle | Format-Table -AutoSize"],
                capture_output=True, text=True, timeout=10,
            )
        elif system == "Darwin":
            result = subprocess.run(
                ["ps", "-eo", "pid,comm"],
                capture_output=True, text=True, timeout=5,
            )
        else:
            result = subprocess.run(
                ["ps", "-eo", "pid,comm", "--sort=-pcpu"],
                capture_output=True, text=True, timeout=5,
            )

        output = result.stdout
        if len(output) > 3000:
            output = output[:3000] + "\n... [truncated]"
        return ToolResult(ok=True, output=output)

    def _close(self, system: str, target: str) -> ToolResult:
        if not target:
            return ToolResult(ok=False, output="", error="'target' app name required.")

        if system == "Windows":
            result = subprocess.run(
                ["taskkill", "/IM", f"{target}*", "/F"],
                capture_output=True, text=True, timeout=10,
            )
        elif system == "Darwin":
            result = subprocess.run(
                ["pkill", "-f", target],
                capture_output=True, text=True, timeout=5,
            )
        else:
            result = subprocess.run(
                ["pkill", "-f", target],
                capture_output=True, text=True, timeout=5,
            )

        if result.returncode == 0:
            return ToolResult(ok=True, output=f"Closed: {target}")
        return ToolResult(ok=False, output="", error=f"Could not close {target}: {result.stderr}")

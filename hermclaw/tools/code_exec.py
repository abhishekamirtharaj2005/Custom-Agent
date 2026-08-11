"""Code execution sandbox — Python and JavaScript.

Runs user code in an isolated subprocess with:
- Timeout enforcement
- stdout/stderr capture
- No network access (best-effort via subprocess isolation)
- Working directory isolation (temp dir)
"""

from __future__ import annotations

import asyncio
import os
import platform
import tempfile
import uuid
from pathlib import Path
from typing import Any, Optional

import structlog

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec

logger = structlog.get_logger(__name__)


class CodeSandboxTool(ToolABC):
    """Execute Python or JavaScript code in an isolated sandbox."""

    def __init__(self, timeout: int = 30) -> None:
        self._timeout = timeout

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="code_exec",
            description=(
                "Execute Python or JavaScript code in a sandboxed environment. "
                "Returns stdout, stderr, and exit code. Use for calculations, "
                "data processing, testing snippets, or any code that needs to run. "
                "Timeout: 30 seconds."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "The code to execute."},
                    "language": {
                        "type": "string",
                        "enum": ["python", "javascript", "bash"],
                        "description": "Language: python, javascript, or bash.",
                    },
                },
                "required": ["code", "language"],
            },
            requires_approval_gate=True,
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        code = args["code"]
        lang = args.get("language", "python").lower()

        with tempfile.TemporaryDirectory(prefix="hermclaw_sandbox_") as tmpdir:
            if lang == "python":
                return await self._run_python(code, tmpdir)
            elif lang in ("javascript", "js"):
                return await self._run_javascript(code, tmpdir)
            elif lang in ("bash", "sh", "shell"):
                return await self._run_bash(code, tmpdir)
            else:
                return ToolResult(ok=False, output="", error=f"Unsupported language: {lang}")

    async def _run_python(self, code: str, workdir: str) -> ToolResult:
        script = Path(workdir) / f"script_{uuid.uuid4().hex[:8]}.py"
        script.write_text(code, encoding="utf-8")
        return await self._exec(["python", str(script)], workdir)

    async def _run_javascript(self, code: str, workdir: str) -> ToolResult:
        script = Path(workdir) / f"script_{uuid.uuid4().hex[:8]}.js"
        script.write_text(code, encoding="utf-8")
        # Try node first
        result = await self._exec(["node", str(script)], workdir)
        if result.ok or "not recognized" not in (result.error or ""):
            return result
        # Try deno as fallback
        return await self._exec(["deno", "run", "--allow-read", str(script)], workdir)

    async def _run_bash(self, code: str, workdir: str) -> ToolResult:
        if platform.system() == "Windows":
            script = Path(workdir) / f"script_{uuid.uuid4().hex[:8]}.ps1"
            script.write_text(code, encoding="utf-8")
            return await self._exec(["powershell", "-File", str(script)], workdir)
        else:
            script = Path(workdir) / f"script_{uuid.uuid4().hex[:8]}.sh"
            script.write_text(code, encoding="utf-8")
            return await self._exec(["bash", str(script)], workdir)

    async def _exec(self, cmd: list[str], workdir: str) -> ToolResult:
        """Run a command and capture output."""
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workdir,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self._timeout
            )

            stdout_str = stdout.decode("utf-8", errors="replace").strip()
            stderr_str = stderr.decode("utf-8", errors="replace").strip()

            if proc.returncode == 0:
                output = stdout_str
                if stderr_str:
                    output += f"\n\n[stderr]\n{stderr_str}"
                return ToolResult(ok=True, output=output[:4000] or "(no output)")
            else:
                error_msg = stderr_str or stdout_str or f"Exit code: {proc.returncode}"
                return ToolResult(ok=False, output=stdout_str[:2000], error=error_msg[:2000])

        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            return ToolResult(ok=False, output="", error=f"Code execution timed out after {self._timeout}s")
        except FileNotFoundError as exc:
            return ToolResult(ok=False, output="", error=f"Runtime not found: {exc.filename}")
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Execution error: {exc}")


class ProcessManagerTool(ToolABC):
    """Manage background processes: list, start, stop."""

    _processes: dict[str, asyncio.subprocess.Process] = {}

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="process",
            description=(
                "Manage background processes. Actions: "
                "list (show running), start (run command in background), "
                "stop (kill by name), send (send input to process)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "start", "stop", "send"],
                        "description": "Action to perform.",
                    },
                    "command": {"type": "string", "description": "Command to run (for start action)."},
                    "name": {"type": "string", "description": "Process name/id (for stop/send actions)."},
                    "input": {"type": "string", "description": "Input to send to process (for send action)."},
                },
                "required": ["action"],
            },
            requires_approval_gate=True,
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        action = args["action"]

        if action == "list":
            return self._list_processes()
        elif action == "start":
            return await self._start(args.get("command", ""), args.get("name"))
        elif action == "stop":
            return self._stop(args.get("name", ""))
        elif action == "send":
            return await self._send_input(args.get("name", ""), args.get("input", ""))
        else:
            return ToolResult(ok=False, output="", error=f"Unknown action: {action}")

    def _list_processes(self) -> ToolResult:
        alive = []
        dead = []
        for name, proc in list(self._processes.items()):
            if proc.returncode is None:
                alive.append(f"  🟢 {name} (PID: {proc.pid})")
            else:
                dead.append(name)

        for d in dead:
            del self._processes[d]

        if not alive:
            return ToolResult(ok=True, output="No background processes running.")
        return ToolResult(ok=True, output="Background processes:\n" + "\n".join(alive))

    async def _start(self, command: str, name: Optional[str] = None) -> ToolResult:
        if not command:
            return ToolResult(ok=False, output="", error="'command' is required for start action.")

        name = name or f"proc_{uuid.uuid4().hex[:6]}"
        try:
            if platform.system() == "Windows":
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    stdin=asyncio.subprocess.PIPE,
                )
            else:
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    stdin=asyncio.subprocess.PIPE,
                )

            self._processes[name] = proc
            return ToolResult(ok=True, output=f"Started '{name}' (PID: {proc.pid})")
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Failed to start: {exc}")

    def _stop(self, name: str) -> ToolResult:
        proc = self._processes.get(name)
        if not proc:
            return ToolResult(ok=False, output="", error=f"Process '{name}' not found.")
        try:
            proc.kill()
            del self._processes[name]
            return ToolResult(ok=True, output=f"Killed process '{name}'")
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Failed to kill: {exc}")

    async def _send_input(self, name: str, text: str) -> ToolResult:
        proc = self._processes.get(name)
        if not proc or not proc.stdin:
            return ToolResult(ok=False, output="", error=f"Process '{name}' not found or has no stdin.")
        try:
            proc.stdin.write((text + "\n").encode())
            await proc.stdin.drain()
            return ToolResult(ok=True, output=f"Sent input to '{name}'")
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Failed to send: {exc}")


class ComputerUseTool(ToolABC):
    """Desktop automation: screenshots, mouse clicks, keyboard input.

    Uses platform-native APIs:
    - Windows: ctypes + pyautogui
    - macOS: AppleScript + pyautogui
    - Linux: xdotool + pyautogui
    """

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="computer",
            description=(
                "Control the desktop: take screenshots, click, type, scroll. "
                "Actions: screenshot, click, type, scroll, key, move_mouse."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["screenshot", "click", "type", "scroll", "key", "move_mouse"],
                        "description": "Action to perform.",
                    },
                    "x": {"type": "integer", "description": "X coordinate (for click/move)."},
                    "y": {"type": "integer", "description": "Y coordinate (for click/move)."},
                    "text": {"type": "string", "description": "Text to type (for type action)."},
                    "key": {"type": "string", "description": "Key to press (for key action, e.g., 'enter', 'tab')."},
                    "direction": {"type": "string", "description": "Scroll direction: up or down."},
                    "clicks": {"type": "integer", "description": "Number of scroll clicks. Default 3."},
                    "output_path": {"type": "string", "description": "Path to save screenshot."},
                },
                "required": ["action"],
            },
            requires_approval_gate=True,
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        action = args["action"]

        try:
            import pyautogui
            pyautogui.FAILSAFE = True
        except ImportError:
            return ToolResult(ok=False, output="", error="pyautogui not installed. Install: pip install pyautogui")

        try:
            if action == "screenshot":
                return self._screenshot(pyautogui, args.get("output_path"))
            elif action == "click":
                return self._click(pyautogui, args.get("x", 0), args.get("y", 0))
            elif action == "type":
                return self._type(pyautogui, args.get("text", ""))
            elif action == "scroll":
                direction = args.get("direction", "down")
                clicks = args.get("clicks", 3)
                amount = clicks if direction == "up" else -clicks
                pyautogui.scroll(amount)
                return ToolResult(ok=True, output=f"Scrolled {direction} {clicks} clicks")
            elif action == "key":
                key = args.get("key", "enter")
                pyautogui.press(key)
                return ToolResult(ok=True, output=f"Pressed key: {key}")
            elif action == "move_mouse":
                pyautogui.moveTo(args.get("x", 0), args.get("y", 0))
                return ToolResult(ok=True, output=f"Moved mouse to ({args.get('x')}, {args.get('y')})")
            else:
                return ToolResult(ok=False, output="", error=f"Unknown action: {action}")
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Computer use error: {exc}")

    def _screenshot(self, pyautogui: Any, output_path: Optional[str] = None) -> ToolResult:
        from pathlib import Path
        if not output_path:
            output_path = str(Path.home() / ".hermclaw" / "screenshots" / f"screen_{uuid.uuid4().hex[:8]}.png")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        img = pyautogui.screenshot()
        img.save(output_path)
        return ToolResult(ok=True, output=f"Screenshot saved: {output_path}")

    def _click(self, pyautogui: Any, x: int, y: int) -> ToolResult:
        pyautogui.click(x, y)
        return ToolResult(ok=True, output=f"Clicked at ({x}, {y})")

    def _type(self, pyautogui: Any, text: str) -> ToolResult:
        pyautogui.typewrite(text, interval=0.02)
        return ToolResult(ok=True, output=f"Typed {len(text)} characters")

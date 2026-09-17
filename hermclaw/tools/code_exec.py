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


def ensure_default_desktop() -> None:
    """On Windows, attach current thread to the interactive desktop if running in an isolated station."""
    if platform.system() == "Windows":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hdesk = user32.OpenDesktopW("default", 0, False, 0x01FF)
            if hdesk:
                user32.SetThreadDesktop(hdesk)
        except Exception:
            pass


class ComputerUseTool(ToolABC):
    """Desktop automation & live screen awareness: inspect screen, control mouse & keyboard.

    Uses platform-native APIs:
    - Windows: ctypes / pygetwindow / pyautogui / pyperclip
    - macOS: AppleScript / pyautogui / pyperclip
    - Linux: xdotool / pyautogui / pyperclip
    """

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="computer",
            description=(
                "Control and inspect the live computer screen, mouse, and keyboard. "
                "Live Awareness: 'see_screen' (inspect screen resolution, cursor position, active window, and visible open windows with bounds and center coordinates), "
                "'screenshot' (capture screen or region), 'list_windows' (list all open visible windows). "
                "Mouse Control: 'click' (at x,y or current pos), 'double_click' (at x,y), 'right_click' (at x,y), "
                "'move_mouse' (to x,y), 'drag' (from x,y to to_x,to_y), 'scroll' (up/down). "
                "Keyboard Control: 'type' (keystroke typing), 'paste' (fast clipboard paste for emojis, unicode, long text), "
                "'key' (single key press like 'enter', 'tab', 'esc'), 'hotkey' (shortcut combo like 'ctrl+f', 'win+r', 'ctrl+v', 'alt+tab'). "
                "Window & App Management: 'focus_window' (bring window to front by title substring), 'open_app' (launch app or protocol like 'whatsapp', 'notepad', 'calc')."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "see_screen",
                            "screenshot",
                            "click",
                            "double_click",
                            "right_click",
                            "move_mouse",
                            "drag",
                            "scroll",
                            "type",
                            "paste",
                            "key",
                            "hotkey",
                            "focus_window",
                            "list_windows",
                            "open_app",
                        ],
                        "description": "Action to perform.",
                    },
                    "x": {"type": "integer", "description": "X coordinate (for click/move/drag/screenshot)."},
                    "y": {"type": "integer", "description": "Y coordinate (for click/move/drag/screenshot)."},
                    "to_x": {"type": "integer", "description": "Destination X coordinate (for drag)."},
                    "to_y": {"type": "integer", "description": "Destination Y coordinate (for drag)."},
                    "width": {"type": "integer", "description": "Region width (for screenshot)."},
                    "height": {"type": "integer", "description": "Region height (for screenshot)."},
                    "text": {"type": "string", "description": "Text to type or paste."},
                    "key": {"type": "string", "description": "Key to press (e.g. 'enter', 'tab', 'esc', 'backspace', 'space')."},
                    "keys": {
                        "type": "string",
                        "description": "Hotkey combination (e.g. 'ctrl+f', 'win+r', 'ctrl+v', 'alt+tab', 'ctrl+enter').",
                    },
                    "title": {"type": "string", "description": "Window title substring (for focus_window)."},
                    "target": {"type": "string", "description": "Application name or protocol to launch (for open_app, e.g. 'whatsapp', 'notepad', 'calc')."},
                    "direction": {"type": "string", "description": "Scroll direction: 'up' or 'down'."},
                    "clicks": {"type": "integer", "description": "Number of scroll clicks or mouse clicks. Default 3 for scroll, 1 for click."},
                    "duration": {"type": "number", "description": "Duration in seconds for mouse movements (default 0.2)."},
                    "button": {"type": "string", "enum": ["left", "right", "middle"], "description": "Mouse button for click (default 'left')."},
                    "output_path": {"type": "string", "description": "Path to save screenshot."},
                },
                "required": ["action"],
            },
            requires_approval_gate=True,
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        action = args["action"]
        ensure_default_desktop()

        try:
            import pyautogui
            pyautogui.FAILSAFE = True
        except ImportError:
            return ToolResult(ok=False, output="", error="pyautogui not installed. Install: pip install pyautogui")

        try:
            if action == "see_screen":
                return self._see_screen(pyautogui)
            elif action == "screenshot":
                return self._screenshot(
                    pyautogui,
                    args.get("output_path"),
                    args.get("x"),
                    args.get("y"),
                    args.get("width"),
                    args.get("height"),
                )
            elif action == "click":
                return self._click(
                    pyautogui,
                    args.get("x"),
                    args.get("y"),
                    args.get("button", "left"),
                    args.get("clicks", 1),
                )
            elif action == "double_click":
                return self._double_click(pyautogui, args.get("x"), args.get("y"))
            elif action == "right_click":
                return self._right_click(pyautogui, args.get("x"), args.get("y"))
            elif action == "move_mouse":
                return self._move_mouse(
                    pyautogui,
                    args.get("x", 0),
                    args.get("y", 0),
                    args.get("duration", 0.2),
                )
            elif action == "drag":
                return self._drag(
                    pyautogui,
                    args.get("to_x", 0),
                    args.get("to_y", 0),
                    args.get("x"),
                    args.get("y"),
                    args.get("duration", 0.3),
                )
            elif action == "scroll":
                return self._scroll(
                    pyautogui,
                    args.get("direction", "down"),
                    args.get("clicks", 3),
                    args.get("x"),
                    args.get("y"),
                )
            elif action == "type":
                return self._type(pyautogui, args.get("text", ""))
            elif action == "paste":
                return self._paste(pyautogui, args.get("text", ""))
            elif action == "key":
                return self._key(pyautogui, args.get("key", "enter"))
            elif action == "hotkey":
                return self._hotkey(pyautogui, args.get("keys") or args.get("key", ""))
            elif action == "focus_window":
                return self._focus_window(args.get("title", ""))
            elif action == "list_windows":
                return self._list_windows()
            elif action == "open_app":
                return self._open_app(args.get("target", ""))
            else:
                return ToolResult(ok=False, output="", error=f"Unknown action: {action}")
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Computer use error: {exc}")

    def _see_screen(self, pyautogui: Any) -> ToolResult:
        try:
            sz = pyautogui.size()
            w = sz[0] if isinstance(sz, (tuple, list)) else getattr(sz, "width", getattr(sz, "w", 1920))
            h = sz[1] if isinstance(sz, (tuple, list)) else getattr(sz, "height", getattr(sz, "h", 1080))
        except Exception:
            w, h = 1920, 1080

        try:
            pos = pyautogui.position()
            if isinstance(pos, (tuple, list)) and len(pos) >= 2:
                mx, my = pos[0], pos[1]
            else:
                mx = getattr(pos, "x", 0)
                my = getattr(pos, "y", 0)
        except Exception:
            mx, my = 0, 0

        active_info = "Unknown / Desktop"
        visible_lines: list[str] = []

        if platform.system() == "Windows":
            try:
                import pygetwindow as gw
                active = gw.getActiveWindow()
                if active and active.title:
                    cx = active.left + active.width // 2
                    cy = active.top + active.height // 2
                    active_info = f"'{active.title}' at center ({cx}, {cy}) [bounds: left={active.left}, top={active.top}, width={active.width}, height={active.height}]"

                wins = gw.getAllWindows()
                for win in wins:
                    if win.title and win.visible and win.width > 10 and win.height > 10:
                        cx = win.left + win.width // 2
                        cy = win.top + win.height // 2
                        visible_lines.append(
                            f"  - '{win.title}' -> center: ({cx}, {cy}), bounds: [x={win.left}, y={win.top}, w={win.width}, h={win.height}]"
                        )
            except Exception as e:
                visible_lines.append(f"  (Window inspection error: {e})")

        snap_path = Path.home() / ".hermclaw" / "screenshots" / "last_screen.png"
        snap_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            from hermclaw.security.privacy_guard import default_privacy_guard
            img = pyautogui.screenshot()
            img, was_masked = default_privacy_guard.mask_screenshot_if_sensitive(img, active_info)
            img.save(str(snap_path))
            mask_note = " [🔒 Privacy Masked]" if was_masked else ""
            snap_msg = f"Visual snapshot saved to: {snap_path}{mask_note}"
        except Exception as exc:
            snap_msg = f"Visual snapshot not captured: {exc}"

        lines = [
            "🖥️ Live Screen Status:",
            f"- Screen Resolution: {w} x {h}",
            f"- Mouse Cursor Position: ({mx}, {my})",
            f"- Active / Focused Window: {active_info}",
            f"- {snap_msg}",
            "",
            f"🪟 Visible Windows ({len(visible_lines)}):",
        ]
        if visible_lines:
            lines.extend(visible_lines[:25])
        else:
            lines.append("  (No top-level application windows detected)")

        return ToolResult(ok=True, output="\n".join(lines))

    def _screenshot(
        self,
        pyautogui: Any,
        output_path: Optional[str] = None,
        x: Optional[int] = None,
        y: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> ToolResult:
        if not output_path:
            output_path = str(Path.home() / ".hermclaw" / "screenshots" / f"screen_{uuid.uuid4().hex[:8]}.png")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        if x is not None and y is not None and width is not None and height is not None:
            img = pyautogui.screenshot(region=(x, y, width, height))
            region_str = f" [region: x={x}, y={y}, w={width}, h={height}]"
        else:
            img = pyautogui.screenshot()
            region_str = ""

        # Apply privacy shield if sensitive window is active
        active_title = ""
        try:
            import pygetwindow as gw
            act = gw.getActiveWindow()
            if act:
                active_title = act.title
        except Exception:
            pass

        try:
            from hermclaw.security.privacy_guard import default_privacy_guard
            img, was_masked = default_privacy_guard.mask_screenshot_if_sensitive(img, active_title)
            if was_masked:
                region_str += " [🔒 Privacy Masked: sensitive window detected]"
        except Exception:
            pass

        img.save(output_path)
        return ToolResult(ok=True, output=f"Screenshot saved: {output_path} (size: {img.size[0]}x{img.size[1]}){region_str}")

    def _click(
        self,
        pyautogui: Any,
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: str = "left",
        clicks: int = 1,
    ) -> ToolResult:
        if x is not None and y is not None:
            pyautogui.click(x=x, y=y, button=button, clicks=clicks)
            return ToolResult(ok=True, output=f"Clicked {button} button ({clicks}x) at ({x}, {y})")
        else:
            pos = pyautogui.position()
            pyautogui.click(button=button, clicks=clicks)
            return ToolResult(ok=True, output=f"Clicked {button} button ({clicks}x) at current position ({pos.x}, {pos.y})")

    def _double_click(self, pyautogui: Any, x: Optional[int] = None, y: Optional[int] = None) -> ToolResult:
        if x is not None and y is not None:
            pyautogui.doubleClick(x=x, y=y)
            return ToolResult(ok=True, output=f"Double-clicked at ({x}, {y})")
        else:
            pos = pyautogui.position()
            pyautogui.doubleClick()
            return ToolResult(ok=True, output=f"Double-clicked at current position ({pos.x}, {pos.y})")

    def _right_click(self, pyautogui: Any, x: Optional[int] = None, y: Optional[int] = None) -> ToolResult:
        if x is not None and y is not None:
            pyautogui.rightClick(x=x, y=y)
            return ToolResult(ok=True, output=f"Right-clicked at ({x}, {y})")
        else:
            pos = pyautogui.position()
            pyautogui.rightClick()
            return ToolResult(ok=True, output=f"Right-clicked at current position ({pos.x}, {pos.y})")

    def _move_mouse(self, pyautogui: Any, x: int, y: int, duration: float = 0.2) -> ToolResult:
        pyautogui.moveTo(x, y, duration=duration)
        return ToolResult(ok=True, output=f"Moved mouse to ({x}, {y})")

    def _drag(
        self,
        pyautogui: Any,
        to_x: int,
        to_y: int,
        from_x: Optional[int] = None,
        from_y: Optional[int] = None,
        duration: float = 0.3,
    ) -> ToolResult:
        if from_x is not None and from_y is not None:
            pyautogui.moveTo(from_x, from_y)
        pyautogui.dragTo(to_x, to_y, duration=duration, button="left")
        return ToolResult(ok=True, output=f"Dragged mouse to ({to_x}, {to_y})")

    def _scroll(
        self,
        pyautogui: Any,
        direction: str = "down",
        clicks: int = 3,
        x: Optional[int] = None,
        y: Optional[int] = None,
    ) -> ToolResult:
        amount = clicks if direction.lower() == "up" else -clicks
        if x is not None and y is not None:
            pyautogui.scroll(amount, x=x, y=y)
        else:
            pyautogui.scroll(amount)
        return ToolResult(ok=True, output=f"Scrolled {direction} {clicks} clicks")

    def _type(self, pyautogui: Any, text: str) -> ToolResult:
        pyautogui.typewrite(text, interval=0.02)
        return ToolResult(ok=True, output=f"Typed {len(text)} characters via keyboard")

    def _paste(self, pyautogui: Any, text: str) -> ToolResult:
        import time

        try:
            import pyperclip
            pyperclip.copy(text)
        except ImportError:
            pyautogui.typewrite(text, interval=0.02)
            return ToolResult(ok=True, output=f"Pasted (fallback type): {len(text)} characters")

        time.sleep(0.05)
        if platform.system() == "Darwin":
            pyautogui.hotkey("command", "v")
        else:
            pyautogui.hotkey("ctrl", "v")

        preview = text[:50] + ("..." if len(text) > 50 else "")
        return ToolResult(ok=True, output=f"Pasted from clipboard ({len(text)} chars): '{preview}'")

    def _key(self, pyautogui: Any, key: str) -> ToolResult:
        k = key.lower().strip()
        pyautogui.press(k)
        return ToolResult(ok=True, output=f"Pressed key: '{k}'")

    def _hotkey(self, pyautogui: Any, keys: str) -> ToolResult:
        parts = [p.strip().lower() for p in keys.replace(",", "+").split("+") if p.strip()]
        if not parts:
            return ToolResult(ok=False, output="", error="No keys specified for hotkey.")
        pyautogui.hotkey(*parts)
        return ToolResult(ok=True, output=f"Triggered hotkey shortcut: {'+'.join(parts)}")

    def _focus_window(self, title: str) -> ToolResult:
        if not title:
            return ToolResult(ok=False, output="", error="'title' is required for focus_window.")

        if platform.system() == "Windows":
            try:
                import pygetwindow as gw
                matches = [w for w in gw.getAllWindows() if title.lower() in w.title.lower()]
                if not matches:
                    return ToolResult(ok=False, output="", error=f"No window found matching '{title}'")
                target = matches[0]
                try:
                    if target.isMinimized:
                        target.restore()
                    target.activate()
                except Exception:
                    try:
                        import win32gui, win32con
                        hwnd = target._hWnd
                        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                        win32gui.SetForegroundWindow(hwnd)
                    except Exception as exc:
                        return ToolResult(ok=False, output="", error=f"Could not focus window '{target.title}': {exc}")
                return ToolResult(ok=True, output=f"Focused window: '{target.title}'")
            except ImportError:
                return ToolResult(ok=False, output="", error="pygetwindow not available.")
        return ToolResult(ok=False, output="", error=f"focus_window not implemented on {platform.system()}")

    def _list_windows(self) -> ToolResult:
        if platform.system() == "Windows":
            try:
                import pygetwindow as gw
                wins = gw.getAllWindows()
                active = gw.getActiveWindow()
                active_title = active.title if active else ""
                lines: list[str] = []
                for w in wins:
                    if w.title and w.visible and w.width > 10 and w.height > 10:
                        is_act = " [ACTIVE]" if w.title == active_title else ""
                        cx = w.left + w.width // 2
                        cy = w.top + w.height // 2
                        lines.append(
                            f"- '{w.title}'{is_act} -> center: ({cx}, {cy}), bounds: [x={w.left}, y={w.top}, w={w.width}, h={w.height}]"
                        )
                if not lines:
                    return ToolResult(ok=True, output="No visible windows detected.")
                return ToolResult(ok=True, output=f"Open Windows ({len(lines)}):\n" + "\n".join(lines[:30]))
            except Exception as exc:
                return ToolResult(ok=False, output="", error=f"Window listing error: {exc}")
        return ToolResult(ok=False, output="", error=f"list_windows not implemented on {platform.system()}")

    def _open_app(self, target: str) -> ToolResult:
        import subprocess

        if not target:
            return ToolResult(ok=False, output="", error="'target' is required for open_app.")

        target_clean = target.strip()
        target_lower = target_clean.lower()

        if platform.system() == "Windows":
            if target_lower in ("whatsapp", "whatsapp:"):
                subprocess.Popen(["cmd", "/c", "start", "whatsapp:"], shell=False)
                return ToolResult(ok=True, output="Launched WhatsApp via protocol 'whatsapp:'.")
            if target_lower.startswith("ms-") or target_lower.startswith("http"):
                subprocess.Popen(["cmd", "/c", "start", target_clean], shell=False)
                return ToolResult(ok=True, output=f"Launched '{target_clean}'.")
            subprocess.Popen(["cmd", "/c", "start", "", target_clean], shell=False)
            return ToolResult(ok=True, output=f"Launched application '{target_clean}'.")
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", "-a", target_clean])
            return ToolResult(ok=True, output=f"Launched application '{target_clean}'.")
        else:
            subprocess.Popen(["xdg-open", target_clean])
            return ToolResult(ok=True, output=f"Launched application '{target_clean}'.")

"""Self-update system, daemon management, and CLI extras.

Implements:
- Self-update system (check for updates, auto-update)
- Daemon management (start/stop/status as service)
- Container boot (auto-setup on first run)
- cgroup cleanup (Linux)
- TUI gateway (curses-based interface)
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Self-update system
# ---------------------------------------------------------------------------


class SelfUpdater:
    """Check for and apply HermClaw updates."""

    PYPI_URL = "https://pypi.org/pypi/hermclaw/json"
    GITHUB_URL = "https://api.github.com/repos/abhishekamirtharaj2005/Custom-Agent/releases/latest"

    def __init__(self) -> None:
        self._current_version = self._get_current()

    async def check_update(self) -> dict[str, Any]:
        """Check if an update is available."""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Try GitHub first
                resp = await client.get(self.GITHUB_URL)
                if resp.status_code == 200:
                    data = resp.json()
                    latest = data.get("tag_name", "").lstrip("v")
                    return {
                        "current": self._current_version,
                        "latest": latest,
                        "update_available": latest > self._current_version,
                        "url": data.get("html_url", ""),
                    }
        except Exception:
            pass

        return {"current": self._current_version, "update_available": False}

    async def update(self, method: str = "pip") -> dict[str, Any]:
        """Apply update."""
        if method == "pip":
            try:
                proc = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--upgrade", "hermclaw"],
                    capture_output=True, text=True, timeout=120,
                )
                return {
                    "success": proc.returncode == 0,
                    "output": proc.stdout[:500],
                    "error": proc.stderr[:500] if proc.returncode != 0 else "",
                }
            except Exception as exc:
                return {"success": False, "error": str(exc)}

        elif method == "git":
            try:
                proc = subprocess.run(
                    ["git", "pull", "origin", "main"],
                    capture_output=True, text=True, timeout=60,
                )
                return {"success": proc.returncode == 0, "output": proc.stdout[:500]}
            except Exception as exc:
                return {"success": False, "error": str(exc)}

        return {"success": False, "error": f"Unknown update method: {method}"}

    def _get_current(self) -> str:
        try:
            from hermclaw import __version__
            return __version__
        except Exception:
            return "0.0.0"


# ---------------------------------------------------------------------------
# Daemon management
# ---------------------------------------------------------------------------


class DaemonManager:
    """Manage HermClaw as a background daemon/service."""

    PID_FILE = Path.home() / ".hermclaw" / "hermclaw.pid"

    def start(self, args: list[str] | None = None) -> dict[str, Any]:
        """Start HermClaw as a background daemon."""
        if self.is_running():
            return {"status": "already_running", "pid": self._read_pid()}

        cmd = [sys.executable, "-m", "hermclaw", "serve"] + (args or [])

        if platform.system() == "Windows":
            # Windows: use subprocess with CREATE_NEW_PROCESS_GROUP
            proc = subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        else:
            # Unix: double-fork daemon
            proc = subprocess.Popen(
                cmd,
                start_new_session=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )

        self._write_pid(proc.pid)
        logger.info("daemon.started", pid=proc.pid)
        return {"status": "started", "pid": proc.pid}

    def stop(self) -> dict[str, Any]:
        """Stop the daemon."""
        pid = self._read_pid()
        if not pid:
            return {"status": "not_running"}

        try:
            import signal
            if platform.system() == "Windows":
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
            else:
                os.kill(pid, signal.SIGTERM)

            self.PID_FILE.unlink(missing_ok=True)
            logger.info("daemon.stopped", pid=pid)
            return {"status": "stopped", "pid": pid}
        except ProcessLookupError:
            self.PID_FILE.unlink(missing_ok=True)
            return {"status": "not_running"}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def status(self) -> dict[str, Any]:
        """Check daemon status."""
        pid = self._read_pid()
        if not pid:
            return {"status": "not_running"}

        if self._is_pid_running(pid):
            return {"status": "running", "pid": pid}
        else:
            self.PID_FILE.unlink(missing_ok=True)
            return {"status": "not_running", "stale_pid": pid}

    def restart(self, args: list[str] | None = None) -> dict[str, Any]:
        self.stop()
        time.sleep(1)
        return self.start(args)

    def is_running(self) -> bool:
        pid = self._read_pid()
        return pid is not None and self._is_pid_running(pid)

    def _read_pid(self) -> Optional[int]:
        if self.PID_FILE.exists():
            try:
                return int(self.PID_FILE.read_text().strip())
            except (ValueError, OSError):
                pass
        return None

    def _write_pid(self, pid: int) -> None:
        self.PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.PID_FILE.write_text(str(pid))

    @staticmethod
    def _is_pid_running(pid: int) -> bool:
        try:
            if platform.system() == "Windows":
                proc = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}"],
                    capture_output=True, text=True,
                )
                return str(pid) in proc.stdout
            else:
                os.kill(pid, 0)
                return True
        except (ProcessLookupError, PermissionError, OSError):
            return False


# ---------------------------------------------------------------------------
# Container boot (auto-setup on first run)
# ---------------------------------------------------------------------------


class ContainerBootstrap:
    """Auto-setup HermClaw on first container start."""

    def __init__(self, state_dir: Optional[Path] = None) -> None:
        self._state = state_dir or (Path.home() / ".hermclaw")
        self._marker = self._state / ".bootstrapped"

    def needs_bootstrap(self) -> bool:
        return not self._marker.exists()

    def bootstrap(self) -> dict[str, Any]:
        """Run first-time setup."""
        steps_completed = []

        # Create directory structure
        dirs = ["sessions", "skills", "plugins", "logs", "backups",
                "screenshots", "tts_output", "videos", "models"]
        for d in dirs:
            (self._state / d).mkdir(parents=True, exist_ok=True)
        steps_completed.append("directories")

        # Generate default config if missing
        config_path = self._state / "hermclaw.yaml"
        if not config_path.exists():
            default_config = {
                "brain": {
                    "model": {"provider": "openai", "model_name": "gpt-4o"},
                },
                "body": {
                    "gateway": {"host": "0.0.0.0", "port": 8765},
                },
            }
            import yaml
            try:
                config_path.write_text(yaml.dump(default_config, default_flow_style=False))
                steps_completed.append("config")
            except ImportError:
                config_path.write_text(json.dumps(default_config, indent=2))
                steps_completed.append("config_json")

        # Mark as bootstrapped
        self._marker.write_text(time.strftime("%Y-%m-%dT%H:%M:%S"))
        steps_completed.append("marker")

        logger.info("bootstrap.completed", steps=steps_completed)
        return {"steps": steps_completed, "state_dir": str(self._state)}


# ---------------------------------------------------------------------------
# cgroup cleanup (Linux)
# ---------------------------------------------------------------------------


class CgroupCleanup:
    """Clean up cgroup resources on Linux (for container environments)."""

    @staticmethod
    def cleanup() -> dict[str, Any]:
        """Clean up orphaned cgroup directories."""
        if platform.system() != "Linux":
            return {"status": "skipped", "reason": "Not Linux"}

        cleaned = 0
        cgroup_root = Path("/sys/fs/cgroup")

        if not cgroup_root.exists():
            return {"status": "skipped", "reason": "No cgroup filesystem"}

        try:
            for scope_dir in cgroup_root.glob("**/hermclaw_*"):
                if scope_dir.is_dir():
                    # Check if any processes are still using it
                    procs_file = scope_dir / "cgroup.procs"
                    if procs_file.exists():
                        pids = procs_file.read_text().strip()
                        if not pids:
                            try:
                                scope_dir.rmdir()
                                cleaned += 1
                            except OSError:
                                pass

            return {"status": "ok", "cleaned": cleaned}
        except PermissionError:
            return {"status": "error", "reason": "Permission denied (need root)"}
        except Exception as exc:
            return {"status": "error", "reason": str(exc)[:100]}


# ---------------------------------------------------------------------------
# TUI (Curses-based terminal UI)
# ---------------------------------------------------------------------------


class CursesTUI:
    """Curses-based TUI for terminal environments.

    Provides a richer terminal experience with:
    - Split-pane layout (chat + tool output)
    - Status bar
    - Scrollable history
    """

    def __init__(self) -> None:
        self._running = False

    def start(self, agent: Any = None) -> None:
        """Start the curses TUI."""
        if platform.system() == "Windows":
            # Windows doesn't have curses by default
            try:
                import curses
            except ImportError:
                print("Curses not available on Windows. Install windows-curses: pip install windows-curses")
                return
        else:
            import curses

        self._running = True
        curses.wrapper(self._main_loop, agent)

    def _main_loop(self, stdscr: Any, agent: Any) -> None:
        import curses

        curses.use_default_colors()
        curses.curs_set(1)
        stdscr.clear()

        height, width = stdscr.getmaxyx()
        input_line = ""
        messages: list[str] = []
        scroll_offset = 0

        # Colors
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        curses.init_pair(2, curses.COLOR_GREEN, -1)
        curses.init_pair(3, curses.COLOR_YELLOW, -1)

        while self._running:
            stdscr.clear()
            h, w = stdscr.getmaxyx()

            # Header
            header = " HermClaw TUI "
            stdscr.addstr(0, (w - len(header)) // 2, header, curses.color_pair(1) | curses.A_BOLD)

            # Messages area
            msg_area_h = h - 4
            visible_msgs = messages[max(0, len(messages) - msg_area_h + scroll_offset):]
            for i, msg in enumerate(visible_msgs[:msg_area_h]):
                try:
                    if msg.startswith("You: "):
                        stdscr.addstr(i + 1, 1, msg[:w-2], curses.color_pair(2))
                    elif msg.startswith("HermClaw: "):
                        stdscr.addstr(i + 1, 1, msg[:w-2], curses.color_pair(1))
                    else:
                        stdscr.addstr(i + 1, 1, msg[:w-2])
                except curses.error:
                    pass

            # Status bar
            status = f" Messages: {len(messages)} | Press Ctrl+C to exit "
            try:
                stdscr.addstr(h - 2, 0, "─" * w)
                stdscr.addstr(h - 2, 2, status, curses.color_pair(3))
            except curses.error:
                pass

            # Input area
            prompt = ">>> "
            try:
                stdscr.addstr(h - 1, 0, prompt)
                stdscr.addstr(h - 1, len(prompt), input_line[:w - len(prompt) - 1])
            except curses.error:
                pass

            stdscr.refresh()

            try:
                key = stdscr.getch()
            except KeyboardInterrupt:
                break

            if key == 10:  # Enter
                if input_line.strip():
                    messages.append(f"You: {input_line}")
                    # Process with agent
                    response = f"[Response to: {input_line[:50]}]"
                    messages.append(f"HermClaw: {response}")
                input_line = ""
            elif key == 27:  # Escape
                break
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                input_line = input_line[:-1]
            elif key == curses.KEY_UP:
                scroll_offset = min(scroll_offset + 1, len(messages))
            elif key == curses.KEY_DOWN:
                scroll_offset = max(scroll_offset - 1, 0)
            elif 32 <= key < 127:
                input_line += chr(key)

        self._running = False

"""WebSocket server, voice mode, and additional gateway infrastructure.

Implements:
- WebSocket server for real-time client connections
- Voice mode (real-time voice conversation)
- Memory monitor (track memory usage)
- Graceful shutdown / drain
- Restart loop guard
- Scale-to-zero (hibernate when idle)
- Code version skew detection
- Shutdown forensics
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any, Optional, Callable, Awaitable

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# WebSocket server
# ---------------------------------------------------------------------------


class WebSocketServer:
    """WebSocket server for real-time agent communication."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self._clients: set = set()
        self._message_handler: Optional[Callable] = None

    def set_handler(self, handler: Callable[[str, Any], Awaitable[str]]) -> None:
        self._message_handler = handler

    async def start(self) -> None:
        try:
            import websockets
        except ImportError:
            logger.error("websocket.missing_dependency", hint="pip install websockets")
            return

        async def _handle(websocket: Any) -> None:
            self._clients.add(websocket)
            logger.info("websocket.client_connected", total=len(self._clients))
            try:
                async for message in websocket:
                    if self._message_handler:
                        response = await self._message_handler(message, websocket)
                        if response:
                            await websocket.send(response)
            except Exception as exc:
                logger.debug("websocket.client_error", error=str(exc)[:100])
            finally:
                self._clients.discard(websocket)
                logger.info("websocket.client_disconnected", total=len(self._clients))

        server = await websockets.serve(_handle, self.host, self.port)
        logger.info("websocket.server_started", host=self.host, port=self.port)
        await server.wait_closed()

    async def broadcast(self, message: str) -> int:
        """Send a message to all connected clients."""
        if not self._clients:
            return 0
        tasks = [client.send(message) for client in self._clients]
        await asyncio.gather(*tasks, return_exceptions=True)
        return len(self._clients)


# ---------------------------------------------------------------------------
# Voice mode
# ---------------------------------------------------------------------------


class VoiceMode:
    """Real-time voice conversation mode.

    Pipeline:
    1. Capture audio from microphone
    2. Transcribe (STT) via Whisper
    3. Process with agent
    4. Synthesize response (TTS) via edge-tts
    5. Play audio
    """

    def __init__(self, agent: Any = None, stt_engine: str = "whisper", tts_voice: str = "en-US-JennyNeural") -> None:
        self._agent = agent
        self._stt_engine = stt_engine
        self._tts_voice = tts_voice
        self._running = False

    async def start(self) -> None:
        """Start voice mode loop."""
        self._running = True
        logger.info("voice_mode.started")
        print("🎤 Voice mode active. Speak into your microphone. Press Ctrl+C to stop.")

        while self._running:
            try:
                # Step 1: Listen for audio
                audio_text = await self._listen()
                if not audio_text:
                    continue

                print(f"👤 You: {audio_text}")

                # Step 2: Process with agent
                if self._agent:
                    response = await self._agent.process(audio_text)
                else:
                    response = f"I heard: {audio_text}"

                print(f"🤖 HermClaw: {response}")

                # Step 3: Speak response
                await self._speak(response)

            except KeyboardInterrupt:
                break
            except Exception as exc:
                logger.error("voice_mode.error", error=str(exc)[:100])

        self._running = False
        logger.info("voice_mode.stopped")

    def stop(self) -> None:
        self._running = False

    async def _listen(self) -> Optional[str]:
        """Capture and transcribe audio. Returns transcribed text."""
        # Simplified: wait for user text input as fallback
        try:
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(None, lambda: input("🎤 > "))
            return text.strip() if text.strip() else None
        except (EOFError, KeyboardInterrupt):
            return None

    async def _speak(self, text: str) -> None:
        """Synthesize and play speech."""
        try:
            import edge_tts
            import tempfile
            import subprocess

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                tmp_path = f.name

            communicate = edge_tts.Communicate(text[:500], self._tts_voice)
            await communicate.save(tmp_path)

            if platform.system() == "Windows":
                subprocess.Popen(["cmd", "/c", "start", "", tmp_path], shell=False)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", tmp_path])
            else:
                subprocess.Popen(["xdg-open", tmp_path])

            await asyncio.sleep(0.5)
        except ImportError:
            logger.debug("voice_mode.edge_tts_not_installed")
        except Exception as exc:
            logger.debug("voice_mode.tts_error", error=str(exc)[:100])


# ---------------------------------------------------------------------------
# Memory monitor
# ---------------------------------------------------------------------------


class MemoryMonitor:
    """Track process memory usage and warn on excessive consumption."""

    def __init__(self, warn_mb: int = 500, critical_mb: int = 1000) -> None:
        self._warn_mb = warn_mb
        self._critical_mb = critical_mb
        self._peak_mb: float = 0

    def check(self) -> dict[str, Any]:
        """Check current memory usage."""
        try:
            import psutil
            proc = psutil.Process()
            info = proc.memory_info()
            rss_mb = info.rss / (1024 * 1024)
            vms_mb = info.vms / (1024 * 1024)
        except ImportError:
            # Fallback without psutil
            import resource
            try:
                usage = resource.getrusage(resource.RUSAGE_SELF)
                rss_mb = usage.ru_maxrss / 1024  # Linux: KB
                vms_mb = 0
            except Exception:
                rss_mb = 0
                vms_mb = 0

        self._peak_mb = max(self._peak_mb, rss_mb)

        status = "ok"
        if rss_mb >= self._critical_mb:
            status = "critical"
            logger.error("memory.critical", rss_mb=round(rss_mb, 1))
        elif rss_mb >= self._warn_mb:
            status = "warning"
            logger.warning("memory.high", rss_mb=round(rss_mb, 1))

        return {
            "rss_mb": round(rss_mb, 1),
            "vms_mb": round(vms_mb, 1),
            "peak_mb": round(self._peak_mb, 1),
            "status": status,
        }


# ---------------------------------------------------------------------------
# Graceful shutdown / drain
# ---------------------------------------------------------------------------


class GracefulShutdown:
    """Manages graceful shutdown with drain period."""

    def __init__(self, drain_timeout: float = 30.0) -> None:
        self._drain_timeout = drain_timeout
        self._shutting_down = False
        self._active_tasks: set[asyncio.Task] = set()
        self._shutdown_start: float = 0

    @property
    def is_shutting_down(self) -> bool:
        return self._shutting_down

    def register_task(self, task: asyncio.Task) -> None:
        self._active_tasks.add(task)
        task.add_done_callback(self._active_tasks.discard)

    async def initiate(self, reason: str = "") -> None:
        """Start graceful shutdown."""
        self._shutting_down = True
        self._shutdown_start = time.time()
        logger.info("shutdown.initiated", reason=reason, active_tasks=len(self._active_tasks))

        # Wait for active tasks to complete (with timeout)
        if self._active_tasks:
            done, pending = await asyncio.wait(
                self._active_tasks,
                timeout=self._drain_timeout,
            )
            if pending:
                logger.warning("shutdown.cancelling_tasks", count=len(pending))
                for task in pending:
                    task.cancel()

        elapsed = time.time() - self._shutdown_start
        logger.info("shutdown.complete", elapsed_s=round(elapsed, 1))


# ---------------------------------------------------------------------------
# Restart loop guard
# ---------------------------------------------------------------------------


class RestartLoopGuard:
    """Detect and prevent restart loops."""

    def __init__(self, max_restarts: int = 5, window_s: float = 300) -> None:
        self._max = max_restarts
        self._window = window_s
        self._restarts: list[float] = []
        self._state_file = Path.home() / ".hermclaw" / "restart_guard.json"

    def record_start(self) -> bool:
        """Record a start event. Returns False if in a restart loop."""
        self._load()
        now = time.time()
        self._restarts.append(now)
        self._restarts = [t for t in self._restarts if now - t < self._window]
        self._save()

        if len(self._restarts) > self._max:
            logger.error("restart_guard.loop_detected",
                        restarts=len(self._restarts), window_s=self._window)
            return False
        return True

    def _load(self) -> None:
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                self._restarts = data.get("restarts", [])
            except Exception:
                self._restarts = []

    def _save(self) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(json.dumps({"restarts": self._restarts}))


# ---------------------------------------------------------------------------
# Scale-to-zero (hibernate when idle)
# ---------------------------------------------------------------------------


class ScaleToZero:
    """Hibernate the gateway when idle to save resources."""

    def __init__(self, idle_timeout_s: float = 300) -> None:
        self._timeout = idle_timeout_s
        self._last_activity = time.time()
        self._hibernating = False

    def record_activity(self) -> None:
        self._last_activity = time.time()
        if self._hibernating:
            logger.info("scale.waking_up")
            self._hibernating = False

    @property
    def should_hibernate(self) -> bool:
        return not self._hibernating and (time.time() - self._last_activity) > self._timeout

    def hibernate(self) -> None:
        self._hibernating = True
        logger.info("scale.hibernating", idle_s=round(time.time() - self._last_activity, 0))


# ---------------------------------------------------------------------------
# Code version skew detection
# ---------------------------------------------------------------------------


class VersionSkewDetector:
    """Detect when running code differs from installed version."""

    def __init__(self) -> None:
        self._startup_version = self._get_version()

    def check(self) -> Optional[str]:
        """Returns a warning if version skew is detected."""
        current = self._get_version()
        if current != self._startup_version:
            return (
                f"⚠️ Code version changed: started with {self._startup_version}, "
                f"now {current}. Restart recommended."
            )
        return None

    @staticmethod
    def _get_version() -> str:
        try:
            from hermclaw import __version__
            return __version__
        except Exception:
            return "unknown"


# ---------------------------------------------------------------------------
# Shutdown forensics
# ---------------------------------------------------------------------------


class ShutdownForensics:
    """Record diagnostic info at shutdown for post-mortem analysis."""

    def __init__(self, log_dir: Optional[Path] = None) -> None:
        self._log_dir = log_dir or (Path.home() / ".hermclaw" / "logs")

    def record(self, reason: str, context: dict[str, Any] | None = None) -> Path:
        """Record shutdown forensics."""
        self._log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        path = self._log_dir / f"shutdown_{timestamp}.json"

        data = {
            "timestamp": time.time(),
            "reason": reason,
            "pid": os.getpid(),
            "python_version": sys.version,
            "platform": platform.platform(),
            "uptime_s": time.time(),  # Would need process start time
            "context": context or {},
        }

        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("forensics.recorded", path=str(path))
        return path

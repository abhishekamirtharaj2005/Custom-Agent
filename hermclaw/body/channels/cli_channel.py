"""CLI channel: a local stdin/stdout REPL. Backs `hermclaw chat` and
doubles as the fully-offline reference implementation of ChannelAdapter
for the shared contract test, since it needs no network at all.

Reader/writer are constructor-injectable so tests can drive it without
touching the real terminal.
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional, TextIO

from hermclaw.body.channels.base import ChannelAdapter, ChannelHealth, IncomingMessage, OutgoingMessage

DEFAULT_USER_ID = "local"


class CliChannel(ChannelAdapter):
    def __init__(
        self,
        prompt: str = "you> ",
        reader: Optional[Callable[[], Awaitable[Optional[str]]]] = None,
        writer: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__()
        self.prompt = prompt
        self._reader = reader  # injectable for tests; defaults to real stdin below
        self._writer = writer or print
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def _default_reader(self) -> Optional[str]:
        loop = asyncio.get_running_loop()
        try:
            line = await loop.run_in_executor(None, input, self.prompt)
        except (EOFError, OSError):
            # No real TTY attached (e.g. a daemonized/headless process) --
            # stop cleanly rather than leaving a thread blocked on stdin
            # forever, which would otherwise hang interpreter shutdown.
            return None
        return line

    async def _loop(self) -> None:
        reader = self._reader or self._default_reader
        while self._running:
            line = await reader()
            if line is None:
                self._running = False
                break
            if not line.strip():
                continue
            await self._emit(IncomingMessage(channel="cli", external_user_id=DEFAULT_USER_ID, text=line))

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    async def send(self, message: OutgoingMessage) -> None:
        self._writer(message.text)

    def health(self) -> ChannelHealth:
        return ChannelHealth(connected=self._running, detail="local REPL" if self._running else "not started")

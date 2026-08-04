"""ChannelAdapter: the one interface every messaging surface implements
(cli, web, telegram, discord, slack, whatsapp), so the gateway (C.1.1)
and scheduler (C.1.4) never need channel-specific branches.

Lifecycle: construct -> start() -> [on_receive fires per inbound message,
send() called to reply] -> stop(). health() is safe to call at any point,
including before start().
"""

from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Optional


@dataclasses.dataclass
class IncomingMessage:
    channel: str
    external_user_id: str  # platform-specific user/chat identifier to reply to
    text: str
    account: Optional[str] = None  # which configured account/bot this arrived on, for multi-identity setups
    raw: Any = None


@dataclasses.dataclass
class OutgoingMessage:
    text: str
    reply_to: str  # external_user_id / chat id to send to


@dataclasses.dataclass
class ChannelHealth:
    connected: bool
    detail: str = ""


OnReceiveCallback = Callable[[IncomingMessage], Awaitable[None]]


class ChannelAdapter(ABC):
    def __init__(self) -> None:
        self.on_receive: Optional[OnReceiveCallback] = None

    @abstractmethod
    async def start(self) -> None:
        """Begin listening for inbound messages (open the socket/poll
        loop/webhook). Must be safe to call exactly once per instance."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop listening and release any held connections. Safe to call
        even if start() was never called or already failed."""

    @abstractmethod
    async def send(self, message: OutgoingMessage) -> None:
        """Deliver an outgoing message to the given recipient."""

    @abstractmethod
    def health(self) -> ChannelHealth:
        """Synchronous, side-effect-free status check -- used by
        `hermclaw doctor` and the gateway's /status endpoint."""

    async def _emit(self, message: IncomingMessage) -> None:
        """Adapters call this from their platform-specific event handlers
        when a message arrives. A no-op if nothing is listening yet."""
        if self.on_receive is not None:
            await self.on_receive(message)

    @property
    def name(self) -> str:
        return type(self).__name__

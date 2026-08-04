"""Discord channel, via discord.py's async Client. Constructor-injectable
client for testing, same pattern as the Telegram adapter."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import structlog

from hermclaw.body.channels.base import ChannelAdapter, ChannelHealth, IncomingMessage, OutgoingMessage

logger = structlog.get_logger(__name__)


class DiscordChannel(ChannelAdapter):
    def __init__(self, bot_token: str, client: Optional[Any] = None) -> None:
        super().__init__()
        self.bot_token = bot_token
        self._client = client
        self._task: Optional[asyncio.Task] = None
        self._connected = False

    def _build_client(self) -> Any:
        import discord

        intents = discord.Intents.default()
        intents.message_content = True
        return discord.Client(intents=intents)

    def _register_handlers(self, client: Any) -> None:
        @client.event
        async def on_message(message: Any) -> None:
            if client.user is not None and message.author.id == client.user.id:
                return
            await self._emit(
                IncomingMessage(channel="discord", external_user_id=str(message.channel.id), text=message.content, raw=message)
            )

    async def start(self) -> None:
        if self._client is None:
            self._client = self._build_client()
        # Registered here (not inside _build_client) so an injected test
        # client gets wired up identically to one Hermclaw builds itself.
        self._register_handlers(self._client)
        self._task = asyncio.create_task(self._client.start(self.bot_token))
        self._connected = True
        logger.info("discord.started")

    async def stop(self) -> None:
        if self._client is not None:
            await self._client.close()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        self._connected = False

    async def send(self, message: OutgoingMessage) -> None:
        if self._client is None:
            raise RuntimeError("DiscordChannel.send() called before start()")
        channel = self._client.get_channel(int(message.reply_to))
        if channel is None:
            channel = await self._client.fetch_channel(int(message.reply_to))
        await channel.send(message.text)

    def health(self) -> ChannelHealth:
        return ChannelHealth(connected=self._connected)

"""Slack channel, via slack_bolt's AsyncApp over Socket Mode (no public
webhook URL needed, matching the local-first design). Constructor-
injectable app/handler for testing, same pattern as the other adapters.
"""

from __future__ import annotations

from typing import Any, Optional

import structlog

from hermclaw.body.channels.base import ChannelAdapter, ChannelHealth, IncomingMessage, OutgoingMessage

logger = structlog.get_logger(__name__)


class SlackChannel(ChannelAdapter):
    def __init__(
        self,
        bot_token: str,
        app_token: str,
        app: Optional[Any] = None,
        handler: Optional[Any] = None,
    ) -> None:
        super().__init__()
        self.bot_token = bot_token
        self.app_token = app_token
        self._app = app
        self._handler = handler
        self._connected = False

    def _build_app(self) -> Any:
        from slack_bolt.async_app import AsyncApp

        return AsyncApp(token=self.bot_token)

    def _register_handlers(self, app: Any) -> None:
        @app.event("message")
        async def handle_message(event: dict[str, Any], say: Any) -> None:
            text = event.get("text")
            channel = event.get("channel")
            if text and channel and not event.get("bot_id"):
                await self._emit(IncomingMessage(channel="slack", external_user_id=channel, text=text, raw=event))

    async def start(self) -> None:
        from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

        if self._app is None:
            self._app = self._build_app()
        # Registered here (not inside _build_app) so an injected test app
        # gets wired up identically to one Hermclaw builds itself.
        self._register_handlers(self._app)
        if self._handler is None:
            self._handler = AsyncSocketModeHandler(self._app, self.app_token)
        await self._handler.connect_async()
        self._connected = True
        logger.info("slack.started", mode="socket_mode")

    async def stop(self) -> None:
        if self._handler is not None:
            await self._handler.disconnect_async()
        self._connected = False

    async def send(self, message: OutgoingMessage) -> None:
        if self._app is None:
            raise RuntimeError("SlackChannel.send() called before start()")
        await self._app.client.chat_postMessage(channel=message.reply_to, text=message.text)

    def health(self) -> ChannelHealth:
        return ChannelHealth(connected=self._connected, detail="socket_mode")

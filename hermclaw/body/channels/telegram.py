"""Telegram channel, via python-telegram-bot's async Application.

The underlying Application is constructor-injectable so it can be
exercised with a lightweight fake in tests without opening a real
connection to Telegram -- see tests/contracts for the shared-shape
adapter tests and tests/body/test_telegram_channel.py for wiring-specific
checks (message translation, handler registration).
"""

from __future__ import annotations

from typing import Any, Optional

import structlog

from hermclaw.body.channels.base import ChannelAdapter, ChannelHealth, IncomingMessage, OutgoingMessage

logger = structlog.get_logger(__name__)


class TelegramChannel(ChannelAdapter):
    def __init__(self, bot_token: str, mode: str = "polling", application: Optional[Any] = None) -> None:
        super().__init__()
        self.bot_token = bot_token
        self.mode = mode
        self._application = application
        self._connected = False

    def _build_application(self) -> Any:
        from telegram.ext import Application

        return Application.builder().token(self.bot_token).build()

    async def _handle_update(self, update: Any, context: Any) -> None:
        message = getattr(update, "message", None)
        if message is None or not getattr(message, "text", None):
            return
        chat_id = str(update.effective_chat.id)
        await self._emit(IncomingMessage(channel="telegram", external_user_id=chat_id, text=message.text, raw=update))

    async def start(self) -> None:
        from telegram.ext import MessageHandler, filters

        if self._application is None:
            self._application = self._build_application()

        self._application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_update))
        await self._application.initialize()
        await self._application.start()
        if self.mode == "polling" and getattr(self._application, "updater", None) is not None:
            await self._application.updater.start_polling()
        self._connected = True
        logger.info("telegram.started", mode=self.mode)

    async def stop(self) -> None:
        if self._application is None:
            self._connected = False
            return
        if self.mode == "polling" and getattr(self._application, "updater", None) is not None:
            await self._application.updater.stop()
        await self._application.stop()
        await self._application.shutdown()
        self._connected = False

    async def send(self, message: OutgoingMessage) -> None:
        if self._application is None:
            raise RuntimeError("TelegramChannel.send() called before start()")
        await self._application.bot.send_message(chat_id=int(message.reply_to), text=message.text)

    def health(self) -> ChannelHealth:
        return ChannelHealth(connected=self._connected, detail=self.mode)

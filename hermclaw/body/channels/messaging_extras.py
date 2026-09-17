"""Additional messaging platform adapters and messaging features.

Implements:
- WeChat (Weixin) adapter
- QQ Bot adapter
- Yuanbao (Tencent) adapter
- DingTalk adapter
- WhatsApp Web bridge (via whatsapp-web.js Node bridge)
- Messaging features: streaming, threading, typing, reactions, allowlists,
  message mirroring, sticker support, relay connector
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
import hashlib
import hmac
from typing import Any, Optional, Set

import httpx
import structlog

from hermclaw.body.channels.base import ChannelAdapter, ChannelHealth, IncomingMessage, OutgoingMessage

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# WeChat (Weixin) adapter
# ---------------------------------------------------------------------------


class WeChatAdapter(ChannelAdapter):
    """WeChat messaging adapter via wechaty or itchat."""

    name = "wechat"

    def __init__(self, api_url: str = "http://localhost:8788", token: str = "") -> None:
        self._api_url = api_url.rstrip("/")
        self._token = token
        self._client = httpx.AsyncClient(timeout=30.0)

    async def send_message(self, contact: str, text: str, **kwargs: Any) -> bool:
        try:
            resp = await self._client.post(
                f"{self._api_url}/api/sendText",
                json={"to": contact, "content": text},
                headers={"Authorization": f"Bearer {self._token}"} if self._token else {},
            )
            resp.raise_for_status()
            return True
        except Exception as exc:
            logger.error("wechat.send_failed", error=str(exc)[:100])
            return False

    async def send_sticker(self, contact: str, sticker_id: str) -> bool:
        try:
            resp = await self._client.post(
                f"{self._api_url}/api/sendImage",
                json={"to": contact, "url": sticker_id},
            )
            resp.raise_for_status()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        await self._client.aclose()


# ---------------------------------------------------------------------------
# QQ Bot adapter
# ---------------------------------------------------------------------------


class QQBotAdapter(ChannelAdapter):
    """QQ Bot adapter via go-cqhttp or NapCat."""

    name = "qqbot"

    def __init__(self, api_url: str = "http://localhost:5700", token: str = "") -> None:
        self._api_url = api_url.rstrip("/")
        self._token = token
        self._client = httpx.AsyncClient(timeout=30.0)

    async def send_message(self, target: str, text: str, **kwargs: Any) -> bool:
        group_id = kwargs.get("group_id")
        try:
            if group_id:
                resp = await self._client.post(f"{self._api_url}/send_group_msg", json={
                    "group_id": int(group_id), "message": text,
                })
            else:
                resp = await self._client.post(f"{self._api_url}/send_private_msg", json={
                    "user_id": int(target), "message": text,
                })
            resp.raise_for_status()
            return True
        except Exception as exc:
            logger.error("qq.send_failed", error=str(exc)[:100])
            return False

    async def send_keyboard(self, target: str, buttons: list[dict]) -> bool:
        """Send inline keyboard (QQ-specific feature)."""
        keyboard_msg = json.dumps({"type": "keyboard", "data": {"content": {"rows": buttons}}})
        return await self.send_message(target, keyboard_msg)

    async def close(self) -> None:
        await self._client.aclose()


# ---------------------------------------------------------------------------
# Yuanbao (Tencent) adapter
# ---------------------------------------------------------------------------


class YuanbaoAdapter(ChannelAdapter):
    """Tencent Yuanbao adapter."""

    name = "yuanbao"

    def __init__(self, api_url: str = "", app_id: str = "", app_secret: str = "") -> None:
        self._api_url = api_url
        self._app_id = app_id
        self._app_secret = app_secret
        self._client = httpx.AsyncClient(timeout=30.0)
        self._sticker_cache: dict[str, str] = {}

    async def send_message(self, target: str, text: str, **kwargs: Any) -> bool:
        if not self._api_url:
            logger.error("yuanbao.no_api_url")
            return False
        try:
            resp = await self._client.post(
                f"{self._api_url}/v1/messages",
                json={"target": target, "content": text, "app_id": self._app_id},
            )
            resp.raise_for_status()
            return True
        except Exception as exc:
            logger.error("yuanbao.send_failed", error=str(exc)[:100])
            return False

    async def close(self) -> None:
        await self._client.aclose()


# ---------------------------------------------------------------------------
# DingTalk adapter
# ---------------------------------------------------------------------------


class DingTalkAdapter(ChannelAdapter):
    """DingTalk (Alibaba) messaging adapter."""

    name = "dingtalk"

    def __init__(self, webhook_url: str = "", access_token: str = "", secret: str = "") -> None:
        self._webhook = webhook_url
        self._token = access_token
        self._secret = secret
        self._client = httpx.AsyncClient(timeout=30.0)

    async def send_message(self, target: str, text: str, **kwargs: Any) -> bool:
        url = target or self._webhook
        if not url:
            return False
        try:
            payload = {
                "msgtype": "text",
                "text": {"content": text},
            }
            if kwargs.get("at_mobiles"):
                payload["at"] = {"atMobiles": kwargs["at_mobiles"]}

            resp = await self._client.post(url, json=payload)
            resp.raise_for_status()
            return True
        except Exception as exc:
            logger.error("dingtalk.send_failed", error=str(exc)[:100])
            return False

    async def close(self) -> None:
        await self._client.aclose()


# ---------------------------------------------------------------------------
# WhatsApp Web bridge (Node.js whatsapp-web.js)
# ---------------------------------------------------------------------------


class WhatsAppWebBridge(ChannelAdapter):
    """WhatsApp Web bridge via whatsapp-web.js Node.js server."""

    name = "whatsapp_web"

    def __init__(self, bridge_url: str = "http://localhost:3000") -> None:
        self._url = bridge_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=30.0)

    async def send_message(self, chat_id: str, text: str, **kwargs: Any) -> bool:
        try:
            resp = await self._client.post(
                f"{self._url}/api/sendMessage",
                json={"chatId": chat_id, "message": text},
            )
            resp.raise_for_status()
            return True
        except Exception as exc:
            logger.error("whatsapp_web.send_failed", error=str(exc)[:100])
            return False

    async def send_media(self, chat_id: str, media_url: str, caption: str = "") -> bool:
        try:
            resp = await self._client.post(
                f"{self._url}/api/sendMedia",
                json={"chatId": chat_id, "mediaUrl": media_url, "caption": caption},
            )
            resp.raise_for_status()
            return True
        except Exception:
            return False

    async def get_qr_code(self) -> Optional[str]:
        """Get QR code for WhatsApp Web authentication."""
        try:
            resp = await self._client.get(f"{self._url}/api/qr")
            if resp.status_code == 200:
                return resp.text
            return None
        except Exception:
            return None

    async def close(self) -> None:
        await self._client.aclose()


# ---------------------------------------------------------------------------
# Messaging features
# ---------------------------------------------------------------------------


class StreamingResponseManager:
    """Manage streaming responses to platforms (chunk-by-chunk delivery)."""

    def __init__(self, chunk_size: int = 100, delay_ms: int = 50) -> None:
        self._chunk_size = chunk_size
        self._delay_ms = delay_ms

    async def stream_to_channel(self, adapter: ChannelAdapter, target: str,
                                 text_generator: Any) -> str:
        """Stream text generation to a channel, sending chunks as they arrive."""
        buffer = ""
        full_text = ""
        async for chunk in text_generator:
            buffer += chunk
            full_text += chunk
            if len(buffer) >= self._chunk_size:
                await adapter.send_message(target, buffer)
                buffer = ""
                await asyncio.sleep(self._delay_ms / 1000)
        if buffer:
            await adapter.send_message(target, buffer)
        return full_text


class MessageThreadManager:
    """Track message threads for threaded conversations."""

    def __init__(self) -> None:
        self._threads: dict[str, list[str]] = {}  # thread_id -> [message_ids]

    def add_to_thread(self, thread_id: str, message_id: str) -> None:
        self._threads.setdefault(thread_id, []).append(message_id)

    def get_thread(self, thread_id: str) -> list[str]:
        return self._threads.get(thread_id, [])

    def create_thread(self, initial_message_id: str) -> str:
        thread_id = f"thread_{int(time.time())}_{initial_message_id[:8]}"
        self._threads[thread_id] = [initial_message_id]
        return thread_id


class TypingIndicatorManager:
    """Manage typing indicators for platforms that support them."""

    async def send_typing(self, adapter: ChannelAdapter, target: str, duration_s: float = 3.0) -> None:
        """Send typing indicator for a duration."""
        if hasattr(adapter, 'send_typing'):
            await adapter.send_typing(target)
            await asyncio.sleep(duration_s)
            if hasattr(adapter, 'stop_typing'):
                await adapter.stop_typing(target)


class EmojiReactionManager:
    """Manage emoji reactions on messages."""

    async def react(self, adapter: ChannelAdapter, message_id: str, emoji: str) -> bool:
        if hasattr(adapter, 'add_reaction'):
            return await adapter.add_reaction(message_id, emoji)
        logger.debug("reactions.not_supported", adapter=adapter.name)
        return False


class AllowlistManager:
    """User/group allowlists for platform access control."""

    def __init__(self) -> None:
        self._user_allowlist: Set[str] = set()
        self._group_allowlist: Set[str] = set()
        self._enabled = False

    def enable(self, users: list[str] = None, groups: list[str] = None) -> None:
        self._enabled = True
        if users:
            self._user_allowlist.update(users)
        if groups:
            self._group_allowlist.update(groups)

    def is_allowed(self, user_id: str = "", group_id: str = "") -> bool:
        if not self._enabled:
            return True
        if user_id and user_id in self._user_allowlist:
            return True
        if group_id and group_id in self._group_allowlist:
            return True
        return False


class MessageMirror:
    """Mirror messages between platforms."""

    def __init__(self) -> None:
        self._mirrors: list[tuple[ChannelAdapter, str, ChannelAdapter, str]] = []

    def add_mirror(self, source: ChannelAdapter, source_target: str,
                   dest: ChannelAdapter, dest_target: str) -> None:
        self._mirrors.append((source, source_target, dest, dest_target))

    async def mirror_message(self, source_name: str, text: str) -> int:
        """Mirror a message to all registered destinations."""
        count = 0
        for src, src_t, dst, dst_t in self._mirrors:
            if src.name == source_name:
                prefix = f"[{source_name}] "
                await dst.send_message(dst_t, prefix + text)
                count += 1
        return count


class StickerManager:
    """Manage sticker cache and resolution."""

    def __init__(self) -> None:
        self._cache: dict[str, dict[str, str]] = {}  # platform -> {name: url}

    def register(self, platform: str, name: str, url: str) -> None:
        self._cache.setdefault(platform, {})[name] = url

    def get(self, platform: str, name: str) -> Optional[str]:
        return self._cache.get(platform, {}).get(name)

    def list_stickers(self, platform: str) -> list[str]:
        return list(self._cache.get(platform, {}).keys())


class RelayConnector:
    """WebSocket relay connector for bridging protocols."""

    def __init__(self, relay_url: str = "") -> None:
        self._url = relay_url
        self._connected = False

    async def connect(self) -> bool:
        if not self._url:
            return False
        try:
            import websockets
            self._ws = await websockets.connect(self._url)
            self._connected = True
            logger.info("relay.connected", url=self._url[:50])
            return True
        except Exception as exc:
            logger.error("relay.connect_failed", error=str(exc)[:100])
            return False

    async def send(self, message: dict) -> bool:
        if not self._connected:
            return False
        try:
            await self._ws.send(json.dumps(message))
            return True
        except Exception:
            return False

    async def close(self) -> None:
        if self._connected:
            await self._ws.close()
            self._connected = False


# ---------------------------------------------------------------------------
# Matrix Protocol Adapter
# ---------------------------------------------------------------------------


class MatrixAdapter(ChannelAdapter):
    """Matrix Client-Server API messaging adapter."""

    name = "matrix"

    def __init__(self, homeserver: str = "https://matrix.org", access_token: str = "", room_id: str = "") -> None:
        super().__init__()
        self._homeserver = homeserver.rstrip("/")
        self._token = access_token
        self._default_room = room_id
        self._client = httpx.AsyncClient(timeout=30.0)

    async def start(self) -> None:
        logger.info("matrix.started", homeserver=self._homeserver)

    async def stop(self) -> None:
        await self._client.aclose()

    async def send(self, message: OutgoingMessage) -> None:
        target_room = message.reply_to or self._default_room
        await self.send_message(target_room, message.text)

    def health(self) -> ChannelHealth:
        connected = bool(self._token)
        return ChannelHealth(connected=connected, detail=f"Matrix homeserver: {self._homeserver}")

    async def send_message(self, room_id: str, text: str, **kwargs: Any) -> bool:
        if not self._token:
            logger.warning("matrix.token_missing")
            return False
        try:
            txn_id = int(time.time() * 1000)
            url = f"{self._homeserver}/_matrix/client/v3/rooms/{room_id}/send/m.room.message/{txn_id}"
            resp = await self._client.put(
                url,
                headers={"Authorization": f"Bearer {self._token}"},
                json={"msgtype": "m.text", "body": text},
            )
            resp.raise_for_status()
            return True
        except Exception as exc:
            logger.error("matrix.send_failed", error=str(exc)[:100])
            return False


# ---------------------------------------------------------------------------
# Google Chat Webhook & Spaces Adapter
# ---------------------------------------------------------------------------


class GoogleChatAdapter(ChannelAdapter):
    """Google Chat incoming webhook and spaces messaging adapter."""

    name = "google_chat"

    def __init__(self, webhook_url: str = "") -> None:
        super().__init__()
        self._webhook_url = webhook_url
        self._client = httpx.AsyncClient(timeout=25.0)

    async def start(self) -> None:
        logger.info("google_chat.started")

    async def stop(self) -> None:
        await self._client.aclose()

    async def send(self, message: OutgoingMessage) -> None:
        target = message.reply_to or self._webhook_url
        await self.send_message(target, message.text)

    def health(self) -> ChannelHealth:
        return ChannelHealth(connected=bool(self._webhook_url), detail="Google Chat webhook configured")

    async def send_message(self, webhook_or_space: str, text: str, **kwargs: Any) -> bool:
        target_url = webhook_or_space if webhook_or_space.startswith("http") else self._webhook_url
        if not target_url:
            return False
        try:
            resp = await self._client.post(target_url, json={"text": text})
            resp.raise_for_status()
            return True
        except Exception as exc:
            logger.error("google_chat.send_failed", error=str(exc)[:100])
            return False


# ---------------------------------------------------------------------------
# Feishu / Lark Enterprise Bot Adapter
# ---------------------------------------------------------------------------


class FeishuLarkAdapter(ChannelAdapter):
    """Feishu (Lark) custom bot and open platform adapter."""

    name = "feishu_lark"

    def __init__(self, webhook_url: str = "", app_id: str = "", app_secret: str = "") -> None:
        super().__init__()
        self._webhook_url = webhook_url
        self._app_id = app_id
        self._app_secret = app_secret
        self._client = httpx.AsyncClient(timeout=25.0)

    async def start(self) -> None:
        logger.info("feishu_lark.started")

    async def stop(self) -> None:
        await self._client.aclose()

    async def send(self, message: OutgoingMessage) -> None:
        await self.send_message(message.reply_to, message.text)

    def health(self) -> ChannelHealth:
        connected = bool(self._webhook_url or (self._app_id and self._app_secret))
        return ChannelHealth(connected=connected, detail="Feishu/Lark bot active")

    async def send_message(self, target: str, text: str, **kwargs: Any) -> bool:
        url = target if target.startswith("http") else self._webhook_url
        if not url:
            return False
        try:
            payload = {
                "msg_type": "text",
                "content": {"text": text},
            }
            resp = await self._client.post(url, json=payload)
            resp.raise_for_status()
            return True
        except Exception as exc:
            logger.error("feishu_lark.send_failed", error=str(exc)[:100])
            return False


# ---------------------------------------------------------------------------
# Mattermost Team Chat Adapter
# ---------------------------------------------------------------------------


class MattermostAdapter(ChannelAdapter):
    """Mattermost incoming webhook and bot API adapter."""

    name = "mattermost"

    def __init__(self, server_url: str = "", token: str = "", default_channel: str = "") -> None:
        super().__init__()
        self._server_url = server_url.rstrip("/")
        self._token = token
        self._default_channel = default_channel
        self._client = httpx.AsyncClient(timeout=25.0)

    async def start(self) -> None:
        logger.info("mattermost.started", server=self._server_url)

    async def stop(self) -> None:
        await self._client.aclose()

    async def send(self, message: OutgoingMessage) -> None:
        target = message.reply_to or self._default_channel
        await self.send_message(target, message.text)

    def health(self) -> ChannelHealth:
        connected = bool(self._server_url and self._token)
        return ChannelHealth(connected=connected, detail=f"Mattermost: {self._server_url}")

    async def send_message(self, channel: str, text: str, **kwargs: Any) -> bool:
        try:
            if self._server_url.endswith("/hooks/") or "hooks" in self._server_url:
                resp = await self._client.post(self._server_url, json={"text": text, "channel": channel})
            else:
                resp = await self._client.post(
                    f"{self._server_url}/api/v4/posts",
                    headers={"Authorization": f"Bearer {self._token}"},
                    json={"channel_id": channel, "message": text},
                )
            resp.raise_for_status()
            return True
        except Exception as exc:
            logger.error("mattermost.send_failed", error=str(exc)[:100])
            return False


# ---------------------------------------------------------------------------
# Twilio SMS / WhatsApp REST Client
# ---------------------------------------------------------------------------


class TwilioSMSAdapter(ChannelAdapter):
    """Twilio programmable SMS and WhatsApp messaging adapter."""

    name = "twilio_sms"

    def __init__(self, account_sid: str = "", auth_token: str = "", from_number: str = "") -> None:
        super().__init__()
        self._sid = account_sid
        self._token = auth_token
        self._from_number = from_number
        self._client = httpx.AsyncClient(timeout=25.0)

    async def start(self) -> None:
        logger.info("twilio_sms.started")

    async def stop(self) -> None:
        await self._client.aclose()

    async def send(self, message: OutgoingMessage) -> None:
        await self.send_message(message.reply_to, message.text)

    def health(self) -> ChannelHealth:
        connected = bool(self._sid and self._token and self._from_number)
        return ChannelHealth(connected=connected, detail=f"Twilio from {self._from_number}")

    async def send_message(self, to_number: str, text: str, **kwargs: Any) -> bool:
        if not (self._sid and self._token and self._from_number):
            logger.warning("twilio.credentials_missing")
            return False
        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{self._sid}/Messages.json"
            resp = await self._client.post(
                url,
                auth=(self._sid, self._token),
                data={"From": self._from_number, "To": to_number, "Body": text},
            )
            resp.raise_for_status()
            return True
        except Exception as exc:
            logger.error("twilio.send_failed", error=str(exc)[:100])
            return False


# ---------------------------------------------------------------------------
# Universal Generic Webhook Adapter
# ---------------------------------------------------------------------------


class GenericWebhookAdapter(ChannelAdapter):
    """Universal outbound webhook adapter with HMAC-SHA256 signatures."""

    name = "generic_webhook"

    def __init__(self, webhook_url: str = "", secret: str = "") -> None:
        super().__init__()
        self._webhook_url = webhook_url
        self._secret = secret
        self._client = httpx.AsyncClient(timeout=25.0)

    async def start(self) -> None:
        logger.info("generic_webhook.started")

    async def stop(self) -> None:
        await self._client.aclose()

    async def send(self, message: OutgoingMessage) -> None:
        target = message.reply_to or self._webhook_url
        await self.send_message(target, message.text)

    def health(self) -> ChannelHealth:
        return ChannelHealth(connected=bool(self._webhook_url), detail=f"Webhook: {self._webhook_url[:40]}")

    async def send_message(self, target_url: str, text: str, **kwargs: Any) -> bool:
        url = target_url if target_url.startswith("http") else self._webhook_url
        if not url:
            return False
        try:
            payload = json.dumps({"text": text, "timestamp": time.time(), "extra": kwargs})
            headers = {"Content-Type": "application/json"}
            if self._secret:
                sig = hmac.new(self._secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
                headers["X-HermClaw-Signature"] = f"sha256={sig}"

            resp = await self._client.post(url, content=payload, headers=headers)
            resp.raise_for_status()
            return True
        except Exception as exc:
            logger.error("generic_webhook.send_failed", error=str(exc)[:100])
            return False


"""Microsoft Teams adapter.

Uses Microsoft Graph API webhooks for Teams messaging.
Requires MS_TEAMS_WEBHOOK_URL or MS Graph API credentials.
"""

from __future__ import annotations

from typing import Any, Optional

import httpx
import structlog

from hermclaw.body.channels.base import ChannelAdapter

logger = structlog.get_logger(__name__)


class TeamsAdapter(ChannelAdapter):
    """Microsoft Teams messaging adapter via incoming webhooks."""

    name = "teams"

    def __init__(self, webhook_url: str = "", tenant_id: str = "", client_id: str = "") -> None:
        self._webhook_url = webhook_url
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client = httpx.AsyncClient(timeout=30.0)

    async def send_message(self, channel: str, text: str, **kwargs: Any) -> bool:
        if not self._webhook_url:
            logger.error("teams.no_webhook_url")
            return False
        try:
            # Teams Adaptive Card format
            card = {
                "type": "message",
                "attachments": [{
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": [{"type": "TextBlock", "text": text, "wrap": True}],
                    },
                }],
            }
            resp = await self._client.post(self._webhook_url, json=card)
            resp.raise_for_status()
            logger.info("teams.message_sent", channel=channel[:20])
            return True
        except Exception as exc:
            logger.error("teams.send_failed", error=str(exc)[:100])
            return False

    async def close(self) -> None:
        await self._client.aclose()


class IMESSAGEAdapter(ChannelAdapter):
    """iMessage adapter via BlueBubbles API."""

    name = "imessage"

    def __init__(self, api_url: str = "http://localhost:1234", password: str = "") -> None:
        self._api_url = api_url.rstrip("/")
        self._password = password
        self._client = httpx.AsyncClient(timeout=30.0)

    async def send_message(self, chat_guid: str, text: str, **kwargs: Any) -> bool:
        try:
            resp = await self._client.post(
                f"{self._api_url}/api/v1/message/text",
                json={"chatGuid": chat_guid, "message": text},
                params={"password": self._password},
            )
            resp.raise_for_status()
            logger.info("imessage.message_sent")
            return True
        except Exception as exc:
            logger.error("imessage.send_failed", error=str(exc)[:100])
            return False

    async def close(self) -> None:
        await self._client.aclose()


class GenericWebhookAdapter(ChannelAdapter):
    """Generic webhook adapter for any HTTP endpoint."""

    name = "webhook"

    def __init__(self, url: str = "", headers: dict[str, str] | None = None, method: str = "POST") -> None:
        self._url = url
        self._headers = headers or {}
        self._method = method.upper()
        self._client = httpx.AsyncClient(timeout=30.0)

    async def send_message(self, target: str, text: str, **kwargs: Any) -> bool:
        url = target or self._url
        if not url:
            return False
        try:
            payload = {"text": text, "content": text, **kwargs}
            if self._method == "POST":
                resp = await self._client.post(url, json=payload, headers=self._headers)
            else:
                resp = await self._client.get(url, params=payload, headers=self._headers)
            resp.raise_for_status()
            logger.info("webhook.sent", url=url[:50])
            return True
        except Exception as exc:
            logger.error("webhook.send_failed", error=str(exc)[:100])
            return False

    async def close(self) -> None:
        await self._client.aclose()

"""Signal messaging adapter.

Uses signal-cli or signal-cli-rest-api for Signal message support.
Requires signal-cli to be installed and configured.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import httpx
import structlog

from hermclaw.body.channels.base import ChannelAdapter

logger = structlog.get_logger(__name__)


class SignalAdapter(ChannelAdapter):
    """Signal messaging platform adapter."""

    name = "signal"

    def __init__(self, api_url: str = "http://localhost:8080", phone: str = "") -> None:
        self._api_url = api_url.rstrip("/")
        self._phone = phone  # Registered phone number
        self._client = httpx.AsyncClient(timeout=30.0)

    async def send_message(self, recipient: str, text: str, **kwargs: Any) -> bool:
        try:
            resp = await self._client.post(
                f"{self._api_url}/v2/send",
                json={
                    "message": text,
                    "number": self._phone,
                    "recipients": [recipient],
                },
            )
            resp.raise_for_status()
            logger.info("signal.message_sent", recipient=recipient[:6] + "***")
            return True
        except Exception as exc:
            logger.error("signal.send_failed", error=str(exc)[:100])
            return False

    async def receive_messages(self) -> list[dict[str, Any]]:
        try:
            resp = await self._client.get(f"{self._api_url}/v1/receive/{self._phone}")
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error("signal.receive_failed", error=str(exc)[:100])
            return []

    async def close(self) -> None:
        await self._client.aclose()

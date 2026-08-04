"""Anthropic Messages API transport. The default provider (Hermes Agent
shipped Anthropic-first; OpenClaw's multi-provider list is layered on
top via openai_compat.py and bedrock.py)."""

from __future__ import annotations

import asyncio
import random
from typing import Any

import structlog

from hermclaw.brain.transports.base import (
    AgentResponse,
    ProviderTransport,
    ToolCallRequest,
    TransportError,
    Usage,
)
from hermclaw.tools.base import ToolSpec

logger = structlog.get_logger(__name__)

_RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


class AnthropicTransport(ProviderTransport):
    def __init__(
        self,
        api_key: str,
        model_name: str,
        api_base: str | None = None,
        max_tokens: int = 4096,
        max_retries: int = 3,
    ) -> None:
        import anthropic  # deferred import: keeps this optional at package-install time

        self._anthropic = anthropic
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if api_base:
            client_kwargs["base_url"] = api_base
        self._client = anthropic.AsyncAnthropic(**client_kwargs)

    def supports_prompt_cache(self) -> bool:
        return True

    @staticmethod
    def _to_anthropic_tools(tools: list[ToolSpec]) -> list[dict[str, Any]]:
        return [
            {"name": t.name, "description": t.description, "input_schema": t.parameters}
            for t in tools
        ]

    @staticmethod
    def _parse_response(resp: Any) -> AgentResponse:
        text_parts: list[str] = []
        tool_calls: list[ToolCallRequest] = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCallRequest(id=block.id, name=block.name, arguments=dict(block.input)))
        usage = Usage(
            input_tokens=getattr(resp.usage, "input_tokens", 0),
            output_tokens=getattr(resp.usage, "output_tokens", 0),
            cache_read_input_tokens=getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
            cache_creation_input_tokens=getattr(resp.usage, "cache_creation_input_tokens", 0) or 0,
        )
        return AgentResponse(
            text="\n".join(text_parts), tool_calls=tool_calls, stop_reason=resp.stop_reason or "end_turn",
            usage=usage, raw=resp,
        )

    async def send(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        system: str = "",
        stream: bool = False,
    ) -> AgentResponse:
        kwargs: dict[str, Any] = {
            "model": self.model_name,
            "max_tokens": self.max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = self._to_anthropic_tools(tools)

        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = await self._client.messages.create(**kwargs)
                return self._parse_response(resp)
            except self._anthropic.APIStatusError as exc:
                last_exc = exc
                if exc.status_code not in _RETRYABLE_STATUS or attempt == self.max_retries:
                    raise TransportError(f"Anthropic API error {exc.status_code}: {exc}") from exc
            except (self._anthropic.APIConnectionError, self._anthropic.APITimeoutError) as exc:
                last_exc = exc
                if attempt == self.max_retries:
                    raise TransportError(f"Anthropic connection error: {exc}") from exc
            backoff = min(2**attempt, 20) + random.uniform(0, 0.5)
            logger.warning("transport.retrying", provider="anthropic", attempt=attempt, backoff_s=round(backoff, 2))
            await asyncio.sleep(backoff)
        raise TransportError(f"Anthropic request failed after retries: {last_exc}")

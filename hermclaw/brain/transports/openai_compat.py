"""OpenAI-compatible /chat/completions transport.

Implemented directly over httpx rather than the `openai` SDK so any
OpenAI-compatible server -- vLLM, Ollama, LM Studio, OpenRouter, etc,
which is the whole point of this transport per the build spec -- works
without adding a second heavy SDK dependency alongside `anthropic`.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

import httpx
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


class ChatCompletionsTransport(ProviderTransport):
    def __init__(
        self,
        api_key: str | None,
        model_name: str,
        api_base: str,
        max_tokens: int = 4096,
        max_retries: int = 3,
        timeout_s: float = 120.0,
    ) -> None:
        self.model_name = model_name
        self.api_base = api_base.rstrip("/")
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.AsyncClient(headers=headers, timeout=timeout_s)

    @staticmethod
    def _to_openai_messages(messages: list[dict[str, Any]], system: str) -> list[dict[str, Any]]:
        """Converts Hermclaw's canonical (Anthropic-shaped) content blocks
        into OpenAI chat format. Canonical blocks: {"type": "text", ...},
        {"type": "tool_use", "id", "name", "input"}, {"type": "tool_result",
        "tool_use_id", "content", "is_error"}. A plain string content is
        passed through unchanged either way."""
        import json

        out: list[dict[str, Any]] = []
        if system:
            out.append({"role": "system", "content": system})

        for m in messages:
            role, content = m["role"], m["content"]
            if isinstance(content, str):
                out.append({"role": role, "content": content})
                continue

            text_parts: list[str] = []
            tool_calls: list[dict[str, Any]] = []
            tool_results: list[dict[str, Any]] = []
            for block in content:
                btype = block.get("type")
                if btype == "text":
                    text_parts.append(block["text"])
                elif btype == "tool_use":
                    tool_calls.append({
                        "id": block["id"], "type": "function",
                        "function": {"name": block["name"], "arguments": json.dumps(block["input"])},
                    })
                elif btype == "tool_result":
                    tool_results.append(block)

            if tool_results:
                # OpenAI represents each tool result as its own role="tool"
                # message rather than bundling them into the user turn.
                for tr in tool_results:
                    out.append({"role": "tool", "tool_call_id": tr["tool_use_id"], "content": tr["content"]})
                continue

            msg: dict[str, Any] = {"role": role, "content": "\n".join(text_parts) if text_parts else None}
            if tool_calls:
                msg["tool_calls"] = tool_calls
            out.append(msg)

        return out

    @staticmethod
    def _to_openai_tools(tools: list[ToolSpec]) -> list[dict[str, Any]]:
        return [
            {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
            for t in tools
        ]

    @staticmethod
    def _parse_response(data: dict[str, Any]) -> AgentResponse:
        choice = data["choices"][0]
        message = choice["message"]
        text = message.get("content") or ""
        tool_calls = []
        for tc in message.get("tool_calls") or []:
            import json

            fn = tc["function"]
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCallRequest(id=tc.get("id", ""), name=fn["name"], arguments=args))

        finish_reason = choice.get("finish_reason", "stop")
        stop_reason = {"stop": "end_turn", "tool_calls": "tool_use", "length": "max_tokens"}.get(
            finish_reason, finish_reason
        )
        usage_raw = data.get("usage") or {}
        usage = Usage(
            input_tokens=usage_raw.get("prompt_tokens", 0),
            output_tokens=usage_raw.get("completion_tokens", 0),
        )
        return AgentResponse(text=text, tool_calls=tool_calls, stop_reason=stop_reason, usage=usage, raw=data)

    async def send(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        system: str = "",
        stream: bool = False,
    ) -> AgentResponse:
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": self._to_openai_messages(messages, system),
            "max_tokens": self.max_tokens,
        }
        if tools:
            payload["tools"] = self._to_openai_tools(tools)

        url = f"{self.api_base}/chat/completions"
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = await self._client.post(url, json=payload)
                if resp.status_code in _RETRYABLE_STATUS and attempt < self.max_retries:
                    last_exc = TransportError(f"HTTP {resp.status_code}: {resp.text[:300]}")
                elif resp.status_code >= 400:
                    raise TransportError(f"HTTP {resp.status_code} from {url}: {resp.text[:300]}")
                else:
                    return self._parse_response(resp.json())
            except httpx.TransportError as exc:
                last_exc = exc
                if attempt == self.max_retries:
                    raise TransportError(f"Connection error to {url}: {exc}") from exc
            backoff = min(2**attempt, 20) + random.uniform(0, 0.5)
            logger.warning("transport.retrying", provider="openai_compat", attempt=attempt, backoff_s=round(backoff, 2))
            await asyncio.sleep(backoff)
        raise TransportError(f"Request to {url} failed after retries: {last_exc}")

    async def aclose(self) -> None:
        await self._client.aclose()

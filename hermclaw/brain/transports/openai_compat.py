"""OpenAI-compatible /chat/completions transport.

Implemented directly over httpx rather than the `openai` SDK so any
OpenAI-compatible server -- vLLM, Ollama, LM Studio, OpenRouter, etc,
which is the whole point of this transport per the build spec -- works
without adding a second heavy SDK dependency alongside `anthropic`.

Supports both streaming (SSE) and non-streaming modes.
"""

from __future__ import annotations

import asyncio
import json
import random
from typing import Any, AsyncIterator, Callable, Optional

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
        # Optional callback for streaming: called with each text chunk
        self.on_stream_chunk: Optional[Callable[[str], None]] = None

    @staticmethod
    def _to_openai_messages(messages: list[dict[str, Any]], system: str) -> list[dict[str, Any]]:
        """Converts Hermclaw's canonical (Anthropic-shaped) content blocks
        into OpenAI chat format."""
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
                for tr in tool_results:
                    out.append({"role": "tool", "tool_call_id": tr["tool_use_id"], "content": tr["content"]})
                continue

            msg: dict[str, Any] = {"role": role, "content": "\n".join(text_parts) if text_parts else ""}
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

    # -----------------------------------------------------------------------
    # Streaming: parse SSE lines into an AgentResponse
    # -----------------------------------------------------------------------

    async def _stream_response(self, resp: httpx.Response) -> AgentResponse:
        """Parse a streaming SSE response into a complete AgentResponse,
        calling on_stream_chunk for each text delta."""
        full_text = ""
        tool_calls_map: dict[int, dict[str, Any]] = {}  # index -> {id, name, arguments_str}
        finish_reason = "stop"

        async for line in resp.aiter_lines():
            line = line.strip()
            if not line or not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if data_str == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            choices = chunk.get("choices", [])
            if not choices:
                continue
            delta = choices[0].get("delta", {})
            fr = choices[0].get("finish_reason")
            if fr:
                finish_reason = fr

            # Text content
            content = delta.get("content")
            if content:
                full_text += content
                if self.on_stream_chunk:
                    self.on_stream_chunk(content)

            # Tool calls (streamed as deltas)
            for tc_delta in delta.get("tool_calls") or []:
                idx = tc_delta.get("index", 0)
                if idx not in tool_calls_map:
                    tool_calls_map[idx] = {
                        "id": tc_delta.get("id", ""),
                        "name": "",
                        "arguments_str": "",
                    }
                entry = tool_calls_map[idx]
                if tc_delta.get("id"):
                    entry["id"] = tc_delta["id"]
                fn = tc_delta.get("function", {})
                if fn.get("name"):
                    entry["name"] = fn["name"]
                if fn.get("arguments"):
                    entry["arguments_str"] += fn["arguments"]

        # Build final tool calls
        tool_calls = []
        for idx in sorted(tool_calls_map.keys()):
            entry = tool_calls_map[idx]
            try:
                args = json.loads(entry["arguments_str"] or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCallRequest(id=entry["id"], name=entry["name"], arguments=args))

        stop_reason = {"stop": "end_turn", "tool_calls": "tool_use", "length": "max_tokens"}.get(
            finish_reason, finish_reason
        )

        # Usage is usually in the final chunk or not available during streaming
        usage = Usage()

        return AgentResponse(text=full_text, tool_calls=tool_calls, stop_reason=stop_reason, usage=usage, raw=None)

    # -----------------------------------------------------------------------
    # Main send (streaming + non-streaming)
    # -----------------------------------------------------------------------

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
        if stream:
            payload["stream"] = True

        url = f"{self.api_base}/chat/completions"
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                if stream:
                    async with self._client.stream("POST", url, json=payload) as resp:
                        if resp.status_code in _RETRYABLE_STATUS and attempt < self.max_retries:
                            last_exc = TransportError(f"HTTP {resp.status_code}")
                        elif resp.status_code >= 400:
                            body = await resp.aread()
                            raise TransportError(f"HTTP {resp.status_code} from {url}: {body.decode()[:300]}")
                        else:
                            return await self._stream_response(resp)
                else:
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

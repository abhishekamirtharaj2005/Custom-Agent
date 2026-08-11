"""Google Gemini native API transport.

Uses Google's Generative AI REST API directly (not the OpenAI-compat
shim). This provides access to Gemini-specific features like native
function calling, grounding, and Google Search integration.

Requires the GOOGLE_API_KEY environment variable.
"""

from __future__ import annotations

import asyncio
import json
import random
from typing import Any, Optional

import httpx
import structlog

from hermclaw.brain.transports.base import (
    AgentResponse,
    ProviderTransport,
    ToolCallRequest,
    ToolSpec,
    TransportError,
    Usage,
)

logger = structlog.get_logger(__name__)

_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
_RETRYABLE_STATUS = {408, 429, 500, 502, 503}


class GeminiTransport(ProviderTransport):
    """Native Google Gemini API transport.

    Uses the generateContent / streamGenerateContent endpoints.
    """

    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.0-flash",
        max_tokens: int = 8192,
        max_retries: int = 2,
    ) -> None:
        self.api_key = api_key or ""
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self._client = httpx.AsyncClient(timeout=300.0)

    # ---- message conversion ----

    @staticmethod
    def _to_gemini_contents(
        messages: list[dict[str, Any]], system: str
    ) -> tuple[list[dict[str, Any]], Optional[dict[str, Any]]]:
        """Convert canonical messages to Gemini contents format.
        Returns (contents, system_instruction)."""
        system_instruction = None
        if system:
            system_instruction = {"parts": [{"text": system}]}

        contents: list[dict[str, Any]] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                # Merge into system_instruction
                text = content if isinstance(content, str) else json.dumps(content)
                if system_instruction:
                    system_instruction["parts"].append({"text": text})
                else:
                    system_instruction = {"parts": [{"text": text}]}
                continue

            gemini_role = "user" if role in ("user", "tool") else "model"
            parts: list[dict[str, Any]] = []

            if isinstance(content, str):
                if content:
                    parts.append({"text": content})
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        btype = block.get("type", "")
                        if btype == "text":
                            parts.append({"text": block.get("text", "")})
                        elif btype == "tool_use":
                            parts.append({
                                "functionCall": {
                                    "name": block.get("name", ""),
                                    "args": block.get("input", {}),
                                }
                            })
                        elif btype == "tool_result":
                            parts.append({
                                "functionResponse": {
                                    "name": block.get("tool_use_id", ""),
                                    "response": {"content": block.get("content", "")},
                                }
                            })
                        else:
                            parts.append({"text": json.dumps(block)})
                    else:
                        parts.append({"text": str(block)})

            if parts:
                contents.append({"role": gemini_role, "parts": parts})

        return contents, system_instruction

    @staticmethod
    def _to_gemini_tools(tools: list[ToolSpec]) -> list[dict[str, Any]]:
        """Convert tool specs to Gemini function declarations."""
        declarations = []
        for t in tools:
            decl: dict[str, Any] = {
                "name": t.name,
                "description": t.description,
            }
            if t.parameters:
                params = dict(t.parameters)
                params.pop("additionalProperties", None)
                decl["parameters"] = params
            declarations.append(decl)
        return [{"functionDeclarations": declarations}]

    def _parse_response(self, data: dict[str, Any]) -> AgentResponse:
        """Parse a Gemini API response."""
        if "error" in data:
            logger.warning("transport.gemini_error", error=data["error"])
            return AgentResponse(text="", tool_calls=[], stop_reason="error",
                                 usage=Usage(), raw=data)

        candidates = data.get("candidates", [])
        if not candidates:
            return AgentResponse(text="", tool_calls=[], stop_reason="error",
                                 usage=Usage(), raw=data)

        candidate = candidates[0]
        content = candidate.get("content", {})
        parts = content.get("parts", [])

        text_parts: list[str] = []
        tool_calls: list[ToolCallRequest] = []

        for part in parts:
            if "text" in part:
                text_parts.append(part["text"])
            elif "functionCall" in part:
                fc = part["functionCall"]
                tool_calls.append(ToolCallRequest(
                    id=fc.get("name", ""),  # Gemini uses name as ID
                    name=fc.get("name", ""),
                    arguments=fc.get("args", {}),
                ))

        finish_reason = candidate.get("finishReason", "STOP")
        stop_map = {
            "STOP": "end_turn",
            "MAX_TOKENS": "max_tokens",
            "SAFETY": "safety",
            "RECITATION": "recitation",
        }
        stop_reason = stop_map.get(finish_reason, finish_reason.lower())

        usage_raw = data.get("usageMetadata", {})
        usage = Usage(
            input_tokens=usage_raw.get("promptTokenCount", 0),
            output_tokens=usage_raw.get("candidatesTokenCount", 0),
        )

        return AgentResponse(
            text="".join(text_parts),
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            usage=usage,
            raw=data,
        )

    async def send(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        system: str = "",
        stream: bool = False,
    ) -> AgentResponse:
        contents, system_instruction = self._to_gemini_contents(messages, system)

        payload: dict[str, Any] = {"contents": contents}
        if system_instruction:
            payload["systemInstruction"] = system_instruction
        if tools:
            payload["tools"] = self._to_gemini_tools(tools)
        payload["generationConfig"] = {
            "maxOutputTokens": self.max_tokens,
            "temperature": 0.7,
        }

        url = f"{_GEMINI_BASE}/models/{self.model_name}:generateContent?key={self.api_key}"

        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = await self._client.post(url, json=payload)
                if resp.status_code in _RETRYABLE_STATUS and attempt < self.max_retries:
                    last_exc = TransportError(f"HTTP {resp.status_code}: {resp.text[:300]}")
                elif resp.status_code >= 400:
                    raise TransportError(f"Gemini API {resp.status_code}: {resp.text[:300]}")
                else:
                    return self._parse_response(resp.json())
            except httpx.TransportError as exc:
                last_exc = exc
                if attempt == self.max_retries:
                    raise TransportError(f"Connection error to Gemini: {exc}") from exc

            backoff = min(2**attempt, 20) + random.uniform(0, 0.5)
            logger.warning("transport.retrying", provider="gemini", attempt=attempt)
            await asyncio.sleep(backoff)

        raise TransportError(f"Gemini request failed after retries: {last_exc}")

    async def aclose(self) -> None:
        await self._client.aclose()

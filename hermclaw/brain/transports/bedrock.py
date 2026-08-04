"""AWS Bedrock transport, via the Converse API (bedrock-runtime's unified
tool-use interface across model families, rather than each model's
bespoke invoke_model body).

boto3 is an optional dependency (the `bedrock` extra) -- most installs
never touch this transport, so it's not pulled in by default. Not
exercised in the default offline test tier for the same reason the
Anthropic transport isn't: it requires real credentials against a real
service. Structural/import correctness is what's verified offline.
"""

from __future__ import annotations

import asyncio
import functools
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


class BedrockTransport(ProviderTransport):
    def __init__(
        self,
        model_name: str,
        region_name: str = "us-east-1",
        max_tokens: int = 4096,
        max_retries: int = 3,
        profile_name: str | None = None,
    ) -> None:
        import boto3  # deferred import: optional `bedrock` extra

        self.model_name = model_name
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        session_kwargs: dict[str, Any] = {"region_name": region_name}
        if profile_name:
            session_kwargs["profile_name"] = profile_name
        session = boto3.Session(**session_kwargs)
        self._client = session.client("bedrock-runtime")

    async def refresh_credentials(self) -> None:
        # boto3 Sessions already refresh short-lived (SSO/assume-role)
        # credentials transparently on each call; nothing additional to do.
        return None

    @staticmethod
    def _to_converse_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Converts Hermclaw's canonical (Anthropic-shaped) content blocks
        into the Bedrock Converse API's content block shapes."""
        out = []
        for m in messages:
            content = m["content"]
            if isinstance(content, str):
                out.append({"role": m["role"], "content": [{"text": content}]})
                continue

            blocks: list[dict[str, Any]] = []
            for block in content:
                btype = block.get("type")
                if btype == "text":
                    blocks.append({"text": block["text"]})
                elif btype == "tool_use":
                    blocks.append({"toolUse": {"toolUseId": block["id"], "name": block["name"], "input": block["input"]}})
                elif btype == "tool_result":
                    blocks.append({
                        "toolResult": {
                            "toolUseId": block["tool_use_id"],
                            "content": [{"text": block["content"]}],
                            "status": "error" if block.get("is_error") else "success",
                        }
                    })
            out.append({"role": m["role"], "content": blocks})
        return out

    @staticmethod
    def _to_converse_tools(tools: list[ToolSpec]) -> dict[str, Any] | None:
        if not tools:
            return None
        return {
            "tools": [
                {"toolSpec": {"name": t.name, "description": t.description, "inputSchema": {"json": t.parameters}}}
                for t in tools
            ]
        }

    @staticmethod
    def _parse_response(resp: dict[str, Any]) -> AgentResponse:
        message = resp["output"]["message"]
        text_parts = []
        tool_calls = []
        for block in message.get("content", []):
            if "text" in block:
                text_parts.append(block["text"])
            elif "toolUse" in block:
                tu = block["toolUse"]
                tool_calls.append(ToolCallRequest(id=tu["toolUseId"], name=tu["name"], arguments=dict(tu.get("input") or {})))
        stop_reason_map = {
            "end_turn": "end_turn", "tool_use": "tool_use", "max_tokens": "max_tokens", "stop_sequence": "end_turn",
        }
        usage_raw = resp.get("usage", {})
        usage = Usage(input_tokens=usage_raw.get("inputTokens", 0), output_tokens=usage_raw.get("outputTokens", 0))
        return AgentResponse(
            text="\n".join(text_parts), tool_calls=tool_calls,
            stop_reason=stop_reason_map.get(resp.get("stopReason", "end_turn"), "end_turn"),
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
            "modelId": self.model_name,
            "messages": self._to_converse_messages(messages),
            "inferenceConfig": {"maxTokens": self.max_tokens},
        }
        if system:
            kwargs["system"] = [{"text": system}]
        tool_config = self._to_converse_tools(tools)
        if tool_config:
            kwargs["toolConfig"] = tool_config

        loop = asyncio.get_running_loop()
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = await loop.run_in_executor(None, functools.partial(self._client.converse, **kwargs))
                return self._parse_response(resp)
            except Exception as exc:  # botocore exceptions: ClientError, EndpointConnectionError, ThrottlingException...
                last_exc = exc
                error_code = getattr(getattr(exc, "response", {}), "get", lambda *_: {})("Error", {}).get("Code", "") \
                    if hasattr(exc, "response") else ""
                retryable = error_code in {"ThrottlingException", "ServiceUnavailableException", "InternalServerException"} \
                    or "EndpointConnectionError" in type(exc).__name__
                if not retryable or attempt == self.max_retries:
                    raise TransportError(f"Bedrock request failed: {exc}") from exc
            backoff = min(2**attempt, 20) + random.uniform(0, 0.5)
            logger.warning("transport.retrying", provider="bedrock", attempt=attempt, backoff_s=round(backoff, 2))
            await asyncio.sleep(backoff)
        raise TransportError(f"Bedrock request failed after retries: {last_exc}")

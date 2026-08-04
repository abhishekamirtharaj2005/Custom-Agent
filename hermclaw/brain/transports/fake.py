"""A scriptable fake ProviderTransport for the offline default test tier.

Never selectable via real config (config.py's provider Literal doesn't
include "fake") -- tests construct this directly so the whole agent
loop, context compressor, and reflection loop can be exercised without
opening a real socket. See D.1's testing strategy.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from hermclaw.brain.transports.base import AgentResponse, ProviderTransport, ToolCallRequest, Usage
from hermclaw.tools.base import ToolSpec


class FakeTransport(ProviderTransport):
    def __init__(
        self,
        responses: Optional[list[AgentResponse]] = None,
        responder: Optional[Callable[[list[dict[str, Any]], list[ToolSpec], str], AgentResponse]] = None,
    ) -> None:
        """Either pass a fixed queue of `responses` (popped in order, one
        per call to send()) or a `responder` callback for dynamic/
        conditional behavior. Every call is recorded in `.calls` for
        assertions."""
        self._responses = list(responses) if responses else []
        self._responder = responder
        self.calls: list[dict[str, Any]] = []

    async def send(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        system: str = "",
        stream: bool = False,
    ) -> AgentResponse:
        self.calls.append({"messages": messages, "tools": tools, "system": system, "stream": stream})
        if self._responder is not None:
            return self._responder(messages, tools, system)
        if self._responses:
            return self._responses.pop(0)
        return AgentResponse(text="(fake transport: no scripted response left)", tool_calls=[],
                              stop_reason="end_turn", usage=Usage(input_tokens=10, output_tokens=5))

    def supports_prompt_cache(self) -> bool:
        return True


def text_response(text: str, stop_reason: str = "end_turn") -> AgentResponse:
    return AgentResponse(text=text, tool_calls=[], stop_reason=stop_reason,
                          usage=Usage(input_tokens=10, output_tokens=len(text.split())))


def tool_call_response(name: str, arguments: dict[str, Any], call_id: str = "call_1") -> AgentResponse:
    return AgentResponse(
        text="", tool_calls=[ToolCallRequest(id=call_id, name=name, arguments=arguments)],
        stop_reason="tool_use", usage=Usage(input_tokens=10, output_tokens=5),
    )

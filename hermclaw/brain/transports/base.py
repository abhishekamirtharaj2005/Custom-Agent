"""ProviderTransport: the one seam between HermclawAgent and any given
model API. Every concrete transport normalizes its provider's wire format
into AgentResponse/ToolCallRequest so the agent loop, context compressor,
and reflection loop never need to know which provider is behind them.
"""

from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod
from typing import Any, Optional

from hermclaw.tools.base import ToolSpec


@dataclasses.dataclass
class ToolCallRequest:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclasses.dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclasses.dataclass
class AgentResponse:
    text: str
    tool_calls: list[ToolCallRequest]
    stop_reason: str  # "end_turn" | "tool_use" | "max_tokens" | "error"
    usage: Usage
    raw: Any = None


class TransportError(Exception):
    """Raised for transient/transport-level failures. HermclawAgent
    retries these with backoff before failing over to the next configured
    fallback model (see agent_loop.py)."""


class ProviderTransport(ABC):
    @abstractmethod
    async def send(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        system: str = "",
        stream: bool = False,
    ) -> AgentResponse:
        """Send one turn to the provider and return a normalized response."""

    def supports_prompt_cache(self) -> bool:
        return False

    async def refresh_credentials(self) -> None:
        """Hook for providers with short-lived tokens (e.g. Bedrock SSO
        profiles). No-op for API-key-based providers, which is why this
        has a default implementation rather than being abstract."""
        return None

    @property
    def name(self) -> str:
        return type(self).__name__

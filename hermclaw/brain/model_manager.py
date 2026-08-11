"""Model management: switching, fallback chains, cost tracking, rate limits.

Implements the model-management layer that sits between the agent loop and
the transport layer. Features:
- Model switching mid-conversation
- Model fallback chains (auto-failover)
- Cost tracking and billing view
- Rate limit tracking and backoff
- Model cost guard (warn on expensive models)
- Prompt caching awareness
"""

from __future__ import annotations

import dataclasses
import time
from collections import defaultdict
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Cost tracking
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class UsageRecord:
    """A single API call's usage."""
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    timestamp: float = dataclasses.field(default_factory=time.time)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


# Default per-million-token costs (updated periodically)
_MODEL_COSTS: dict[str, tuple[float, float]] = {
    # (input_cost_per_1M, output_cost_per_1M)
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "o1": (15.00, 60.00),
    "o1-mini": (3.00, 12.00),
    "o3": (10.00, 40.00),
    "o3-mini": (1.10, 4.40),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-5-haiku": (0.80, 4.00),
    "claude-4-sonnet": (3.00, 15.00),
    "claude-4-opus": (15.00, 75.00),
    "claude-3-haiku": (0.25, 1.25),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.0-pro": (1.25, 5.00),
    "gemini-1.5-pro": (1.25, 5.00),
    "gemini-1.5-flash": (0.075, 0.30),
    "deepseek-chat": (0.14, 0.28),
    "deepseek-reasoner": (0.55, 2.19),
    "mistral-large": (2.00, 6.00),
    "mixtral-8x7b": (0.24, 0.24),
    "llama-3.1-70b": (0.00, 0.00),  # Local/free
    "gemma4:26b": (0.00, 0.00),  # Local/free
}


class CostTracker:
    """Tracks API costs across all model calls in a session."""

    def __init__(self, budget_usd: float = 0.0) -> None:
        self._records: list[UsageRecord] = []
        self._budget_usd = budget_usd  # 0 = no budget limit
        self._total_cost: float = 0.0

    def record(self, usage: UsageRecord) -> float:
        """Record a usage event and return its estimated cost."""
        self._records.append(usage)

        model_key = self._normalize_model(usage.model)
        costs = _MODEL_COSTS.get(model_key, (0.0, 0.0))
        input_cost = (usage.input_tokens / 1_000_000) * costs[0]
        output_cost = (usage.output_tokens / 1_000_000) * costs[1]
        # Cached tokens are typically 50% cheaper
        cached_discount = (usage.cached_tokens / 1_000_000) * costs[0] * 0.5
        call_cost = input_cost + output_cost - cached_discount

        self._total_cost += call_cost
        logger.debug("cost.recorded", model=usage.model, tokens=usage.total_tokens,
                      cost_usd=round(call_cost, 6))
        return call_cost

    @property
    def total_cost(self) -> float:
        return self._total_cost

    @property
    def total_tokens(self) -> int:
        return sum(r.total_tokens for r in self._records)

    def is_over_budget(self) -> bool:
        return self._budget_usd > 0 and self._total_cost >= self._budget_usd

    def summary(self) -> dict[str, Any]:
        """Cost summary by model."""
        by_model: dict[str, dict] = defaultdict(lambda: {"calls": 0, "tokens": 0, "cost": 0.0})
        for r in self._records:
            key = self._normalize_model(r.model)
            by_model[key]["calls"] += 1
            by_model[key]["tokens"] += r.total_tokens
            costs = _MODEL_COSTS.get(key, (0.0, 0.0))
            by_model[key]["cost"] += (r.input_tokens / 1e6) * costs[0] + (r.output_tokens / 1e6) * costs[1]

        return {
            "total_cost_usd": round(self._total_cost, 4),
            "total_tokens": self.total_tokens,
            "total_calls": len(self._records),
            "budget_usd": self._budget_usd or "unlimited",
            "by_model": dict(by_model),
        }

    @staticmethod
    def _normalize_model(name: str) -> str:
        """Normalize model name for cost lookup."""
        name = name.lower().strip()
        for key in _MODEL_COSTS:
            if key in name:
                return key
        return name


# ---------------------------------------------------------------------------
# Rate limit tracking
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class RateLimitState:
    """Per-provider rate limit state."""
    requests_remaining: Optional[int] = None
    tokens_remaining: Optional[int] = None
    reset_at: Optional[float] = None
    retry_after: Optional[float] = None

    @property
    def is_limited(self) -> bool:
        if self.retry_after and time.time() < self.retry_after:
            return True
        if self.requests_remaining is not None and self.requests_remaining <= 0:
            if self.reset_at and time.time() < self.reset_at:
                return True
        return False

    @property
    def wait_seconds(self) -> float:
        if self.retry_after:
            return max(0, self.retry_after - time.time())
        if self.reset_at:
            return max(0, self.reset_at - time.time())
        return 0


class RateLimitTracker:
    """Tracks rate limit state for each provider."""

    def __init__(self) -> None:
        self._states: dict[str, RateLimitState] = {}

    def update_from_headers(self, provider: str, headers: dict[str, str]) -> None:
        """Parse rate limit headers from API response."""
        state = self._states.setdefault(provider, RateLimitState())

        # OpenAI-style headers
        if "x-ratelimit-remaining-requests" in headers:
            state.requests_remaining = int(headers["x-ratelimit-remaining-requests"])
        if "x-ratelimit-remaining-tokens" in headers:
            state.tokens_remaining = int(headers["x-ratelimit-remaining-tokens"])
        if "x-ratelimit-reset-requests" in headers:
            try:
                state.reset_at = time.time() + self._parse_duration(headers["x-ratelimit-reset-requests"])
            except ValueError:
                pass
        if "retry-after" in headers:
            try:
                state.retry_after = time.time() + float(headers["retry-after"])
            except ValueError:
                pass

        # Anthropic-style headers
        if "anthropic-ratelimit-requests-remaining" in headers:
            state.requests_remaining = int(headers["anthropic-ratelimit-requests-remaining"])
        if "anthropic-ratelimit-tokens-remaining" in headers:
            state.tokens_remaining = int(headers["anthropic-ratelimit-tokens-remaining"])

        if state.is_limited:
            logger.warning("rate_limit.active", provider=provider,
                          wait_s=round(state.wait_seconds, 1))

    def get_state(self, provider: str) -> RateLimitState:
        return self._states.get(provider, RateLimitState())

    @staticmethod
    def _parse_duration(s: str) -> float:
        """Parse a duration string like '1m30s' or '500ms'."""
        import re
        total = 0.0
        for val, unit in re.findall(r"(\d+\.?\d*)(ms|s|m|h)", s):
            v = float(val)
            if unit == "ms":
                total += v / 1000
            elif unit == "s":
                total += v
            elif unit == "m":
                total += v * 60
            elif unit == "h":
                total += v * 3600
        return total or float(s)


# ---------------------------------------------------------------------------
# Model fallback chains
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class FallbackChain:
    """A chain of models to try in order. If the primary fails, try the next."""
    models: list[str]
    current_index: int = 0

    @property
    def current_model(self) -> str:
        return self.models[self.current_index] if self.models else ""

    def advance(self) -> Optional[str]:
        """Move to next fallback model. Returns None if exhausted."""
        self.current_index += 1
        if self.current_index < len(self.models):
            logger.warning("fallback.advancing",
                          from_model=self.models[self.current_index - 1],
                          to_model=self.models[self.current_index])
            return self.models[self.current_index]
        return None

    def reset(self) -> None:
        self.current_index = 0


# Default fallback chains for common providers
DEFAULT_FALLBACK_CHAINS: dict[str, list[str]] = {
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
    "anthropic": ["claude-4-sonnet", "claude-3-5-sonnet", "claude-3-haiku"],
    "gemini": ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
    "ollama": ["gemma4:26b", "llama3.1:8b", "mistral:7b"],
}


# ---------------------------------------------------------------------------
# Model cost guard
# ---------------------------------------------------------------------------


class ModelCostGuard:
    """Warns when an expensive model is about to be used."""

    def __init__(self, warn_threshold_per_call: float = 0.10) -> None:
        self._threshold = warn_threshold_per_call

    def check(self, model: str, estimated_input_tokens: int) -> Optional[str]:
        """Returns a warning string if the call would be expensive, else None."""
        key = CostTracker._normalize_model(model)
        costs = _MODEL_COSTS.get(key)
        if not costs:
            return None

        estimated_cost = (estimated_input_tokens / 1_000_000) * costs[0]
        if estimated_cost > self._threshold:
            return (
                f"⚠️ Estimated cost for this call: ${estimated_cost:.4f} "
                f"(model: {model}, ~{estimated_input_tokens} input tokens). "
                f"Consider using a cheaper model."
            )
        return None


# ---------------------------------------------------------------------------
# Model switcher
# ---------------------------------------------------------------------------


class ModelSwitcher:
    """Allows switching models mid-conversation."""

    def __init__(self, default_model: str, default_provider: str) -> None:
        self.current_model = default_model
        self.current_provider = default_provider
        self._history: list[tuple[str, str, float]] = []

    def switch(self, model: str, provider: Optional[str] = None) -> str:
        """Switch to a new model. Returns the new model name."""
        old = self.current_model
        self._history.append((old, self.current_provider, time.time()))
        self.current_model = model
        if provider:
            self.current_provider = provider
        logger.info("model.switched", from_model=old, to_model=model)
        return model

    def revert(self) -> Optional[str]:
        """Revert to the previous model."""
        if self._history:
            prev_model, prev_provider, _ = self._history.pop()
            self.current_model = prev_model
            self.current_provider = prev_provider
            return prev_model
        return None

    @property
    def switch_history(self) -> list[dict]:
        return [
            {"model": m, "provider": p, "timestamp": t}
            for m, p, t in self._history
        ]

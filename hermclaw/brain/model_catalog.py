"""Model catalog: metadata for all known LLM providers and models.

Provides:
- Model metadata (context window, pricing, capabilities)
- Model aliasing (e.g., 'fast' → 'gemma4:12b')
- Provider configurations
- Mid-conversation model switching
- Cost tracking
"""

from __future__ import annotations

import dataclasses
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclasses.dataclass
class ModelInfo:
    """Metadata for a single model."""
    name: str
    provider: str  # openai_compat, anthropic, bedrock, google
    context_window: int = 128_000
    max_output_tokens: int = 4096
    supports_tools: bool = True
    supports_vision: bool = False
    supports_streaming: bool = True
    input_cost_per_1m: float = 0.0  # USD per 1M input tokens
    output_cost_per_1m: float = 0.0  # USD per 1M output tokens
    description: str = ""
    aliases: list[str] = dataclasses.field(default_factory=list)
    api_base: str = ""  # override default API base


# ---------------------------------------------------------------------------
# Built-in model catalog
# ---------------------------------------------------------------------------

_BUILTIN_MODELS: list[ModelInfo] = [
    # --- Ollama / Local ---
    ModelInfo(
        name="gemma4:12b", provider="openai_compat",
        context_window=128_000, max_output_tokens=8192,
        supports_vision=True, description="Google Gemma 4 12B (local via Ollama)",
        aliases=["gemma4", "default", "local"],
        api_base="http://localhost:11434/v1",
    ),
    ModelInfo(
        name="llama3.1:8b", provider="openai_compat",
        context_window=128_000, max_output_tokens=4096,
        description="Meta Llama 3.1 8B (local via Ollama)",
        aliases=["llama3", "llama"],
        api_base="http://localhost:11434/v1",
    ),
    ModelInfo(
        name="qwen2.5:14b", provider="openai_compat",
        context_window=128_000, max_output_tokens=8192,
        description="Alibaba Qwen 2.5 14B (local via Ollama)",
        aliases=["qwen", "qwen2"],
        api_base="http://localhost:11434/v1",
    ),
    ModelInfo(
        name="deepseek-r1:14b", provider="openai_compat",
        context_window=128_000, max_output_tokens=8192,
        description="DeepSeek R1 14B reasoning model (local via Ollama)",
        aliases=["deepseek", "r1"],
        api_base="http://localhost:11434/v1",
    ),
    ModelInfo(
        name="mistral:7b", provider="openai_compat",
        context_window=32_000, max_output_tokens=4096,
        description="Mistral 7B (local via Ollama)",
        aliases=["mistral"],
        api_base="http://localhost:11434/v1",
    ),
    ModelInfo(
        name="codellama:13b", provider="openai_compat",
        context_window=16_000, max_output_tokens=4096,
        description="Meta Code Llama 13B (local via Ollama)",
        aliases=["codellama"],
        api_base="http://localhost:11434/v1",
    ),

    # --- OpenAI ---
    ModelInfo(
        name="gpt-4o", provider="openai_compat",
        context_window=128_000, max_output_tokens=16_384,
        supports_vision=True, description="OpenAI GPT-4o",
        aliases=["gpt4o", "4o"],
        input_cost_per_1m=2.50, output_cost_per_1m=10.00,
        api_base="https://api.openai.com/v1",
    ),
    ModelInfo(
        name="gpt-4o-mini", provider="openai_compat",
        context_window=128_000, max_output_tokens=16_384,
        supports_vision=True, description="OpenAI GPT-4o Mini (cheap, fast)",
        aliases=["mini", "4o-mini"],
        input_cost_per_1m=0.15, output_cost_per_1m=0.60,
        api_base="https://api.openai.com/v1",
    ),
    ModelInfo(
        name="o1", provider="openai_compat",
        context_window=200_000, max_output_tokens=100_000,
        supports_vision=True, description="OpenAI o1 reasoning model",
        aliases=["o1"],
        input_cost_per_1m=15.00, output_cost_per_1m=60.00,
        api_base="https://api.openai.com/v1",
    ),
    ModelInfo(
        name="o3-mini", provider="openai_compat",
        context_window=200_000, max_output_tokens=100_000,
        supports_vision=False, description="OpenAI o3-mini reasoning model (fast, math/code)",
        aliases=["o3", "o3mini"],
        input_cost_per_1m=1.10, output_cost_per_1m=4.40,
        api_base="https://api.openai.com/v1",
    ),

    # --- Anthropic ---
    ModelInfo(
        name="claude-3-7-sonnet-latest", provider="anthropic",
        context_window=200_000, max_output_tokens=16_384,
        supports_vision=True, description="Anthropic Claude 3.7 Sonnet (Hybrid Reasoning)",
        aliases=["claude-3-7-sonnet", "claude-3.7-sonnet", "sonnet-3.7"],
        input_cost_per_1m=3.00, output_cost_per_1m=15.00,
    ),
    ModelInfo(
        name="claude-3-5-sonnet-latest", provider="anthropic",
        context_window=200_000, max_output_tokens=8192,
        supports_vision=True, description="Anthropic Claude 3.5 Sonnet",
        aliases=["claude-3-5-sonnet", "claude-3.5-sonnet", "sonnet-3.5"],
        input_cost_per_1m=3.00, output_cost_per_1m=15.00,
    ),
    ModelInfo(
        name="claude-sonnet-4-20250514", provider="anthropic",
        context_window=200_000, max_output_tokens=16_384,
        supports_vision=True, description="Anthropic Claude Sonnet 4",
        aliases=["claude", "sonnet", "claude4"],
        input_cost_per_1m=3.00, output_cost_per_1m=15.00,
    ),
    ModelInfo(
        name="claude-3-5-haiku-20241022", provider="anthropic",
        context_window=200_000, max_output_tokens=8192,
        description="Anthropic Claude 3.5 Haiku (fast, cheap)",
        aliases=["haiku", "claude-3-5-haiku", "claude-3.5-haiku"],
        input_cost_per_1m=0.80, output_cost_per_1m=4.00,
    ),

    # --- Google ---
    ModelInfo(
        name="gemini-3.8-flash", provider="gemini",
        context_window=1_000_000, max_output_tokens=65_536,
        supports_vision=True, description="Google Gemini 3.8 Flash (High Speed)",
        aliases=["gemini-3.8", "gemini-3.8-flash"],
        input_cost_per_1m=0.15, output_cost_per_1m=0.60,
    ),
    ModelInfo(
        name="gemini-3.5-flash", provider="gemini",
        context_window=1_000_000, max_output_tokens=65_536,
        supports_vision=True, description="Google Gemini 3.5 Flash",
        aliases=["gemini-3.5", "gemini-3.5-flash"],
        input_cost_per_1m=0.15, output_cost_per_1m=0.60,
    ),
    ModelInfo(
        name="gemini-3-flash-preview", provider="gemini",
        context_window=1_000_000, max_output_tokens=65_536,
        supports_vision=True, description="Google Gemini 3 Flash Preview",
        aliases=["gemini-3-flash", "gemini-3"],
        input_cost_per_1m=0.15, output_cost_per_1m=0.60,
    ),
    ModelInfo(
        name="gemini-flash-latest", provider="gemini",
        context_window=1_000_000, max_output_tokens=65_536,
        supports_vision=True, description="Google Gemini Flash Latest",
        aliases=["flash-latest"],
        input_cost_per_1m=0.15, output_cost_per_1m=0.60,
    ),
    ModelInfo(
        name="gemini-2.5-pro", provider="gemini",
        context_window=1_000_000, max_output_tokens=65_536,
        supports_vision=True, description="Google Gemini 2.5 Pro",
        aliases=["gemini", "gemini-pro"],
        input_cost_per_1m=1.25, output_cost_per_1m=10.00,
    ),
    ModelInfo(
        name="gemini-2.5-flash", provider="gemini",
        context_window=1_000_000, max_output_tokens=65_536,
        supports_vision=True, description="Google Gemini 2.5 Flash (fast, cheap)",
        aliases=["flash", "gemini-flash"],
        input_cost_per_1m=0.15, output_cost_per_1m=0.60,
    ),
    ModelInfo(
        name="gemini-2.0-flash", provider="gemini",
        context_window=1_000_000, max_output_tokens=8192,
        supports_vision=True, description="Google Gemini 2.0 Flash",
        aliases=["gemini-2", "gemini-2.0"],
        input_cost_per_1m=0.10, output_cost_per_1m=0.40,
    ),
    ModelInfo(
        name="gemini-1.5-flash", provider="gemini",
        context_window=1_000_000, max_output_tokens=8192,
        supports_vision=True, description="Google Gemini 1.5 Flash",
        aliases=["gemini-1.5", "gemini-1.5-flash"],
        input_cost_per_1m=0.075, output_cost_per_1m=0.30,
    ),
    ModelInfo(
        name="gemini-1.5-pro", provider="gemini",
        context_window=2_000_000, max_output_tokens=8192,
        supports_vision=True, description="Google Gemini 1.5 Pro",
        aliases=["gemini-1.5-pro"],
        input_cost_per_1m=1.25, output_cost_per_1m=5.00,
    ),

    # --- DeepSeek ---
    ModelInfo(
        name="deepseek-chat", provider="openai_compat",
        context_window=64_000, max_output_tokens=8192,
        description="DeepSeek V3 (Chat & Coding)",
        aliases=["deepseek-v3"],
        input_cost_per_1m=0.14, output_cost_per_1m=0.28,
        api_base="https://api.deepseek.com/v1",
    ),
    ModelInfo(
        name="deepseek-reasoner", provider="openai_compat",
        context_window=64_000, max_output_tokens=8192,
        description="DeepSeek R1 (Reasoner)",
        aliases=["deepseek-r1-api"],
        input_cost_per_1m=0.55, output_cost_per_1m=2.19,
        api_base="https://api.deepseek.com/v1",
    ),

    # --- OpenRouter ---
    ModelInfo(
        name="openrouter/auto", provider="openai_compat",
        context_window=128_000, max_output_tokens=16_384,
        supports_vision=True, description="OpenRouter auto-routing",
        aliases=["openrouter", "router"],
        api_base="https://openrouter.ai/api/v1",
    ),

    # --- Groq ---
    ModelInfo(
        name="llama-3.3-70b-versatile", provider="openai_compat",
        context_window=128_000, max_output_tokens=32_768,
        description="Groq Llama 3.3 70B (ultra-fast inference)",
        aliases=["groq", "groq-llama"],
        api_base="https://api.groq.com/openai/v1",
    ),

    # --- Together AI ---
    ModelInfo(
        name="meta-llama/Llama-3.3-70B-Instruct-Turbo", provider="openai_compat",
        context_window=128_000, max_output_tokens=4096,
        description="Together AI Llama 3.3 70B Turbo",
        aliases=["together", "together-llama"],
        input_cost_per_1m=0.88, output_cost_per_1m=0.88,
        api_base="https://api.together.xyz/v1",
    ),
]



class ModelCatalog:
    """Registry of all known models with lookup by name or alias."""

    def __init__(self) -> None:
        self._models: dict[str, ModelInfo] = {}
        self._aliases: dict[str, str] = {}
        for m in _BUILTIN_MODELS:
            self.register(m)

    def register(self, model: ModelInfo) -> None:
        self._models[model.name] = model
        for alias in model.aliases:
            self._aliases[alias.lower()] = model.name

    def resolve(self, name_or_alias: str) -> Optional[ModelInfo]:
        """Look up a model by exact name or alias, with smart dynamic fallbacks for cloud providers."""
        key = name_or_alias.lower().strip()
        if key in self._models:
            return self._models[key]
        real_name = self._aliases.get(key)
        if real_name:
            return self._models.get(real_name)
        # Fuzzy: check if the key is a substring of any model name
        for model_name, model in self._models.items():
            if key in model_name.lower():
                return model

        # Dynamic fallback for Gemini models: if it starts with gemini, resolve as Gemini cloud model
        if key.startswith("gemini") or "gemini" in key:
            return ModelInfo(
                name=name_or_alias.strip(),
                provider="gemini",
                context_window=1_000_000,
                max_output_tokens=65_536,
                description=f"{name_or_alias.strip()} (Google Gemini Cloud)",
            )

        # Dynamic fallback for Claude models:
        if key.startswith("claude"):
            return ModelInfo(
                name=name_or_alias.strip(),
                provider="anthropic",
                context_window=200_000,
                max_output_tokens=16_384,
                description=f"{name_or_alias.strip()} (Anthropic Claude Cloud)",
            )

        # Dynamic fallback for GPT/OpenAI models:
        if key.startswith(("gpt-", "o1", "o3", "chatgpt")):
            return ModelInfo(
                name=name_or_alias.strip(),
                provider="openai_compat",
                api_base="https://api.openai.com/v1",
                context_window=128_000,
                max_output_tokens=16_384,
                description=f"{name_or_alias.strip()} (OpenAI Cloud)",
            )

        # Dynamic fallback for DeepSeek models (without colon):
        if key.startswith("deepseek") and ":" not in key:
            return ModelInfo(
                name=name_or_alias.strip(),
                provider="openai_compat",
                api_base="https://api.deepseek.com/v1",
                context_window=64_000,
                max_output_tokens=8192,
                description=f"{name_or_alias.strip()} (DeepSeek Cloud)",
            )

        # Dynamic fallback for OpenRouter models:
        if key.startswith("openrouter/"):
            return ModelInfo(
                name=name_or_alias.strip(),
                provider="openai_compat",
                api_base="https://openrouter.ai/api/v1",
                context_window=128_000,
                max_output_tokens=16_384,
                description=f"{name_or_alias.strip()} (OpenRouter Cloud)",
            )

        return None

    def list_all(self) -> list[ModelInfo]:
        return list(self._models.values())

    def list_by_provider(self, provider: str) -> list[ModelInfo]:
        return [m for m in self._models.values() if m.provider == provider]

    def format_table(self) -> str:
        """Format a human-readable table of all models."""
        lines = ["Available Models:", ""]
        for m in self._models.values():
            aliases = ", ".join(m.aliases) if m.aliases else "—"
            cost = f"${m.input_cost_per_1m:.2f}/${m.output_cost_per_1m:.2f}" if m.input_cost_per_1m > 0 else "free/local"
            ctx = f"{m.context_window // 1000}K"
            lines.append(f"  {m.name}")
            lines.append(f"    Aliases: {aliases} | Context: {ctx} | Cost: {cost}")
            lines.append(f"    {m.description}")
            lines.append("")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Cost tracker
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class CostEntry:
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


class CostTracker:
    """Track API costs per session and cumulative."""

    def __init__(self) -> None:
        self._entries: list[CostEntry] = []

    def record(self, model_name: str, input_tokens: int, output_tokens: int, catalog: ModelCatalog) -> CostEntry:
        info = catalog.resolve(model_name)
        if info and info.input_cost_per_1m > 0:
            cost = (input_tokens * info.input_cost_per_1m + output_tokens * info.output_cost_per_1m) / 1_000_000
        else:
            cost = 0.0
        entry = CostEntry(model=model_name, input_tokens=input_tokens, output_tokens=output_tokens, cost_usd=cost)
        self._entries.append(entry)
        return entry

    @property
    def total_cost(self) -> float:
        return sum(e.cost_usd for e in self._entries)

    @property
    def total_tokens(self) -> int:
        return sum(e.input_tokens + e.output_tokens for e in self._entries)

    def summary(self) -> str:
        if not self._entries:
            return "No API usage tracked."
        return (
            f"Session cost: ${self.total_cost:.4f} | "
            f"Total tokens: {self.total_tokens:,} | "
            f"Turns: {len(self._entries)}"
        )

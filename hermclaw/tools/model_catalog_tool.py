"""Model catalog tool — lets the agent list, inspect, and switch models.

Exposes the ModelCatalog as a callable tool so the agent can answer
questions like "what model are you?", "list available models", and
"switch to claude".
"""

from __future__ import annotations

from typing import Any, Optional

import structlog

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec

logger = structlog.get_logger(__name__)


class ModelCatalogTool(ToolABC):
    """Tool that lets the agent query the model catalog and report model info."""

    def __init__(self) -> None:
        # Lazy-load catalog to avoid circular imports at module level
        self._catalog = None
        self._current_model: str = ""
        self._cost_tracker = None

    def _ensure_catalog(self) -> None:
        if self._catalog is None:
            from hermclaw.brain.model_catalog import CostTracker, ModelCatalog
            self._catalog = ModelCatalog()
            if self._cost_tracker is None:
                self._cost_tracker = CostTracker()

    def set_current_model(self, model_name: str) -> None:
        """Called by runtime to set the currently active model."""
        self._current_model = model_name

    def set_cost_tracker(self, tracker: Any) -> None:
        """Called by runtime to inject the shared cost tracker."""
        self._cost_tracker = tracker

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="model_catalog",
            description=(
                "Query the AI model catalog. Actions:\n"
                "- 'list': List all available models with pricing and capabilities.\n"
                "- 'current': Show the currently active model, provider, and context window.\n"
                "- 'info <model>': Get detailed info about a specific model (by name or alias).\n"
                "- 'cost': Show current session token usage and estimated cost.\n"
                "Use this whenever the user asks about models, pricing, switching, or usage costs."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "current", "info", "cost"],
                        "description": "The action to perform.",
                    },
                    "model_name": {
                        "type": "string",
                        "description": "Model name or alias (only for 'info' action).",
                    },
                },
                "required": ["action"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        self._ensure_catalog()
        action = args.get("action", "list")

        if action == "list":
            return ToolResult(ok=True, output=self._catalog.format_table())

        elif action == "current":
            if not self._current_model:
                return ToolResult(ok=True, output="No model info available — model name not set.")
            info = self._catalog.resolve(self._current_model)
            if info:
                lines = [
                    f"Currently active model:",
                    f"  Name:           {info.name}",
                    f"  Provider:       {info.provider}",
                    f"  Description:    {info.description}",
                    f"  Context window: {info.context_window:,} tokens",
                    f"  Max output:     {info.max_output_tokens:,} tokens",
                    f"  Vision:         {'Yes' if info.supports_vision else 'No'}",
                    f"  Tools:          {'Yes' if info.supports_tools else 'No'}",
                    f"  Streaming:      {'Yes' if info.supports_streaming else 'No'}",
                ]
                if info.input_cost_per_1m > 0:
                    lines.append(f"  Input cost:     ${info.input_cost_per_1m:.2f} / 1M tokens")
                    lines.append(f"  Output cost:    ${info.output_cost_per_1m:.2f} / 1M tokens")
                else:
                    lines.append(f"  Cost:           Free (local model)")
                if info.aliases:
                    lines.append(f"  Aliases:        {', '.join(info.aliases)}")
                return ToolResult(ok=True, output="\n".join(lines))
            else:
                return ToolResult(ok=True, output=f"Active model: {self._current_model} (not found in catalog)")

        elif action == "info":
            model_name = args.get("model_name", "")
            if not model_name:
                return ToolResult(ok=False, output="", error="Please specify a model name or alias.")
            info = self._catalog.resolve(model_name)
            if not info:
                # Suggest closest matches
                all_models = self._catalog.list_all()
                suggestions = [m.name for m in all_models if model_name.lower() in m.name.lower() or
                               any(model_name.lower() in a.lower() for a in m.aliases)]
                msg = f"Model '{model_name}' not found."
                if suggestions:
                    msg += f" Did you mean: {', '.join(suggestions[:5])}?"
                return ToolResult(ok=False, output="", error=msg)

            lines = [
                f"Model: {info.name}",
                f"  Provider:       {info.provider}",
                f"  Description:    {info.description}",
                f"  Context window: {info.context_window:,} tokens",
                f"  Max output:     {info.max_output_tokens:,} tokens",
                f"  Vision:         {'Yes' if info.supports_vision else 'No'}",
                f"  Tools:          {'Yes' if info.supports_tools else 'No'}",
            ]
            if info.input_cost_per_1m > 0:
                lines.append(f"  Input cost:     ${info.input_cost_per_1m:.2f} / 1M tokens")
                lines.append(f"  Output cost:    ${info.output_cost_per_1m:.2f} / 1M tokens")
            else:
                lines.append(f"  Cost:           Free (local model)")
            if info.aliases:
                lines.append(f"  Aliases:        {', '.join(info.aliases)}")
            if info.api_base:
                lines.append(f"  API base:       {info.api_base}")
            return ToolResult(ok=True, output="\n".join(lines))

        elif action == "cost":
            if self._cost_tracker:
                return ToolResult(ok=True, output=self._cost_tracker.summary())
            return ToolResult(ok=True, output="No cost tracking data available yet.")

        return ToolResult(ok=False, output="", error=f"Unknown action: {action}")

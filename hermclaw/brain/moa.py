"""Mixture-of-Agents (MoA): query multiple models and merge responses.

Sends the same prompt to N models in parallel, then uses a final
synthesizer model to merge all responses into a single, higher-quality
answer. This produces better outputs at the cost of latency and tokens.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class MoAResult:
    """Result of a Mixture-of-Agents run."""
    individual_responses: list[dict] = field(default_factory=list)
    merged_response: str = ""
    total_time_s: float = 0.0
    models_used: list[str] = field(default_factory=list)


async def run_mixture_of_agents(
    transports: list[Any],
    model_configs: list[Any],
    messages: list[dict],
    system_prompt: str = "",
    merge_instruction: str = "",
) -> MoAResult:
    """Run MoA: query all models in parallel, then merge.

    Args:
        transports: List of ProviderTransport instances.
        model_configs: Corresponding ModelConfig for each transport.
        messages: The conversation messages to send.
        system_prompt: System prompt for all models.
        merge_instruction: Custom instruction for the merge step.

    Returns:
        MoAResult with individual and merged responses.
    """
    if not transports:
        return MoAResult()

    start = time.monotonic()

    # Phase 1: Query all models in parallel
    async def _query_one(transport, model_cfg, idx: int) -> dict:
        t0 = time.monotonic()
        try:
            response = await transport.send(
                messages=messages,
                model=model_cfg.model,
                system_prompt=system_prompt,
                tools=[],
            )
            return {
                "index": idx,
                "model": model_cfg.model,
                "text": response.text,
                "time_s": round(time.monotonic() - t0, 2),
                "ok": True,
            }
        except Exception as exc:
            return {
                "index": idx,
                "model": model_cfg.model,
                "text": "",
                "error": str(exc),
                "time_s": round(time.monotonic() - t0, 2),
                "ok": False,
            }

    tasks = [_query_one(t, mc, i) for i, (t, mc) in enumerate(zip(transports, model_configs))]
    individual = await asyncio.gather(*tasks)

    # Filter successful responses
    successful = [r for r in individual if r["ok"] and r["text"]]
    if not successful:
        return MoAResult(
            individual_responses=list(individual),
            merged_response="All models failed to respond.",
            total_time_s=round(time.monotonic() - start, 2),
        )

    if len(successful) == 1:
        return MoAResult(
            individual_responses=list(individual),
            merged_response=successful[0]["text"],
            total_time_s=round(time.monotonic() - start, 2),
            models_used=[successful[0]["model"]],
        )

    # Phase 2: Merge responses using the first transport as synthesizer
    merge_prompt = merge_instruction or (
        "You are synthesizing responses from multiple AI models into a single, optimal answer. "
        "Take the best elements from each response, resolve any contradictions, and produce "
        "a comprehensive, accurate, and well-structured final answer.\n\n"
    )

    response_texts = []
    for i, r in enumerate(successful):
        response_texts.append(f"=== Model {i+1} ({r['model']}) ===\n{r['text']}\n")

    merge_messages = messages + [{
        "role": "user",
        "content": merge_prompt + "\n".join(response_texts) + "\n\nPlease synthesize the above into a single best response:",
    }]

    try:
        merge_response = await transports[0].send(
            messages=merge_messages,
            model=model_configs[0].model,
            system_prompt="You are a response synthesizer. Combine multiple AI responses into one optimal answer.",
            tools=[],
        )
        merged_text = merge_response.text
    except Exception as exc:
        logger.error("moa.merge_failed", error=str(exc))
        merged_text = successful[0]["text"]

    return MoAResult(
        individual_responses=list(individual),
        merged_response=merged_text,
        total_time_s=round(time.monotonic() - start, 2),
        models_used=[r["model"] for r in successful],
    )

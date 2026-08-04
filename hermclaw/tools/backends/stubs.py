"""Thin stub adapters for backends out of scope for v1.

Ported from Hermes Agent's six-backend set for parity (singularity, modal,
daytona). These deliberately raise NotImplementedError with a tracking
message rather than silently no-op-ing, per the build spec's explicit
instruction: "implement stubs with a clear NotImplementedError and a
tracking TODO if full support is out of scope for v1 -- do not silently
no-op."
"""

from __future__ import annotations

from hermclaw.tools.base import ToolResult


async def run_singularity_command(command: str, **kwargs) -> ToolResult:
    raise NotImplementedError(
        "TODO(hermclaw): Singularity backend is not implemented in v1. "
        "Tracked as a parity gap with Hermes Agent's six-backend set. "
        "Use tools.backend: local or docker instead."
    )


async def run_modal_command(command: str, **kwargs) -> ToolResult:
    raise NotImplementedError(
        "TODO(hermclaw): Modal backend is not implemented in v1. "
        "Tracked as a parity gap with Hermes Agent's six-backend set. "
        "Use tools.backend: local or docker instead."
    )


async def run_daytona_command(command: str, **kwargs) -> ToolResult:
    raise NotImplementedError(
        "TODO(hermclaw): Daytona backend is not implemented in v1. "
        "Tracked as a parity gap with Hermes Agent's six-backend set. "
        "Use tools.backend: local or docker instead."
    )

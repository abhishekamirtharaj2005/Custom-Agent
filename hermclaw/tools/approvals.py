"""Approvals configuration and gate construction.

approvals.mode:
  manual (default) -- every flagged call pauses for user confirmation
  smart             -- a cheap auxiliary model call classifies risk; only
                        genuinely uncertain calls escalate to the user
  off               -- explicit opt-out only, never a default, logged
                        loudly when active

The hardline subset (see tools/base.py's HARDLINE_PATTERNS) is enforced
regardless of mode, including "off".
"""

from __future__ import annotations

from typing import Awaitable, Callable, Optional

import structlog

from hermclaw.tools.base import ApprovalGate, ApprovalsConfig

logger = structlog.get_logger(__name__)


def build_approval_gate(
    mode: str = "manual",
    confirm_callback: Optional[Callable[[str, dict], Awaitable[bool]]] = None,
    smart_classifier: Optional[Callable[[str, dict], Awaitable[bool]]] = None,
) -> ApprovalGate:
    if mode not in ("manual", "smart", "off"):
        raise ValueError(f"Invalid approvals.mode: {mode}")
    if mode == "off":
        logger.warning(
            "approvals.mode_off",
            message="approvals.mode is 'off'. Only the hardline pattern subset "
            "will be enforced. This must be an explicit user opt-in.",
        )
    config = ApprovalsConfig(mode=mode)
    return ApprovalGate(config, confirm_callback=confirm_callback, smart_classifier=smart_classifier)


async def cli_confirm_callback(tool_name: str, args: dict) -> bool:
    """Default interactive confirmation surface for the CLI channel."""
    print(f"\n[approval required] Tool: {tool_name}")
    print(f"Arguments: {args}")
    resp = input("Allow this call? [y/N]: ").strip().lower()
    return resp in ("y", "yes")

"""The single Tool ABC that every execution path in Hermclaw is forced through.

This module is the highest-priority feature in the whole codebase (see
C.3.4 of the build spec). There must be no second path to a shell, ever.
Every tool that can touch the filesystem, shell, or network -- including
MCP tools, the shell tool itself, and any future code-execution tool --
implements ToolABC and is invoked exclusively through ToolDispatcher.

Design note (closes a documented bug class): Hermes Agent's own issue
tracker records a case where a "sandboxed" code-exec tool could call a
raw terminal() RPC and skip the approval system entirely. In Hermclaw,
that RPC simply does not exist -- code-exec and the shell tool share the
exact same dispatcher and the exact same approval gate below.
"""

from __future__ import annotations

import abc
import dataclasses
import re
import time
from typing import Any, Awaitable, Callable, Optional

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class ToolSpec:
    """Describes a tool to the model: name, description, and a JSON schema
    for its arguments (as sent in the `tools` field of a transport call)."""

    name: str
    description: str
    parameters: dict[str, Any]
    # Tools that touch shell/filesystem/network must set this True so the
    # dispatcher knows to route through the approval gate.
    requires_approval_gate: bool = False


@dataclasses.dataclass
class ToolResult:
    ok: bool
    output: str
    error: Optional[str] = None
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)


class ToolExecutionDenied(Exception):
    """Raised when a call is blocked by the approval gate or a hardline rule."""


# ---------------------------------------------------------------------------
# The Tool ABC
# ---------------------------------------------------------------------------


class ToolABC(abc.ABC):
    """Every tool -- built-in, MCP-sourced, or future -- implements this."""

    @abc.abstractmethod
    def spec(self) -> ToolSpec:
        ...

    @abc.abstractmethod
    async def execute(self, args: dict[str, Any]) -> ToolResult:
        ...


# ---------------------------------------------------------------------------
# Hardline dangerous-command detection
# ---------------------------------------------------------------------------
#
# Ported from Hermes Agent's ~78-pattern dangerous-command detector, reduced
# here to a representative, extensible starting set covering the categories
# named explicitly in the build spec: recursive delete, destructive SQL
# without a WHERE clause, and permission changes like chmod 777 / recursive
# chown. Patterns in HARDLINE_PATTERNS are enforced even when
# approvals.mode == "off" -- there is no config path that disables them.

HARDLINE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("rm_rf_root", re.compile(r"rm\s+(-\w*r\w*f\w*|-\w*f\w*r\w*)\s+/(\s|$)")),
    ("rm_rf_root_star", re.compile(r"rm\s+-rf\s+/\*")),
    ("delete_state_db", re.compile(r"rm\s+.*state\.db")),
    ("recursive_delete_home", re.compile(r"rm\s+-rf\s+(~|\$HOME)(\s|$|/)")),
    ("dd_to_device", re.compile(r"dd\s+.*of=/dev/(sd|nvme|hd)")),
    ("fork_bomb", re.compile(r":\(\)\s*\{\s*:\|\s*:\s*&\s*\}\s*;\s*:")),
    ("mkfs", re.compile(r"\bmkfs\.\w+\s+/dev/")),
]

DANGEROUS_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("recursive_delete", re.compile(r"rm\s+-\w*r\w*", re.IGNORECASE)),
    ("chmod_777", re.compile(r"chmod\s+(-R\s+)?0?777\b")),
    ("recursive_chown", re.compile(r"chown\s+-R\b")),
    ("destructive_sql_no_where", re.compile(
        r"\b(DELETE\s+FROM|UPDATE)\b(?!.*\bWHERE\b)", re.IGNORECASE)),
    ("drop_table", re.compile(r"\bDROP\s+(TABLE|DATABASE)\b", re.IGNORECASE)),
    ("curl_pipe_shell", re.compile(r"(curl|wget)[^|]*\|\s*(sudo\s+)?(bash|sh)\b")),
    ("sudo", re.compile(r"\bsudo\b")),
]


def check_dangerous_command(command: str) -> tuple[bool, bool, list[str]]:
    """Classify a shell command string.

    Returns (is_hardline, is_dangerous, matched_pattern_names).
    is_hardline commands are blocked unconditionally, regardless of
    approvals.mode (including "off").
    is_dangerous commands require approval when approvals.mode is "manual"
    or "smart"; only skipped when mode is "off" AND not hardline.
    """
    matched: list[str] = []
    is_hardline = False
    for name, pattern in HARDLINE_PATTERNS:
        if pattern.search(command):
            matched.append(name)
            is_hardline = True
    is_dangerous = is_hardline
    for name, pattern in DANGEROUS_PATTERNS:
        if pattern.search(command):
            matched.append(name)
            is_dangerous = True
    return is_hardline, is_dangerous, matched


# ---------------------------------------------------------------------------
# Approval gate
# ---------------------------------------------------------------------------

ApprovalCallback = Callable[[str, dict[str, Any]], Awaitable[bool]]


@dataclasses.dataclass
class ApprovalsConfig:
    mode: str = "manual"  # manual | smart | off


class ApprovalGate:
    """Gates every flagged tool call. This is the ONE place approval
    decisions are made; the dispatcher below is the ONE place that consults
    it before executing anything shell/filesystem/network-capable."""

    def __init__(
        self,
        config: ApprovalsConfig,
        confirm_callback: Optional[ApprovalCallback] = None,
        smart_classifier: Optional[Callable[[str, dict[str, Any]], Awaitable[bool]]] = None,
    ) -> None:
        self.config = config
        self._confirm_callback = confirm_callback
        self._smart_classifier = smart_classifier

    async def check(self, tool_name: str, args: dict[str, Any], command_text: str = "") -> None:
        """Raises ToolExecutionDenied if the call should not proceed."""
        is_hardline, is_dangerous, matched = check_dangerous_command(command_text)

        if is_hardline:
            logger.warning("tool.hardline_blocked", tool=tool_name, patterns=matched)
            raise ToolExecutionDenied(
                f"Blocked: '{tool_name}' matched hardline-restricted pattern(s) "
                f"{matched}. This category is never permitted, regardless of "
                f"approvals.mode."
            )

        if self.config.mode == "off":
            logger.warning("tool.approval_bypassed", tool=tool_name, mode="off")
            return

        if self.config.mode == "manual":
            approved = await self._ask_user(tool_name, args)
            if not approved:
                raise ToolExecutionDenied(f"User declined approval for '{tool_name}'.")
            return

        if self.config.mode == "smart":
            if is_dangerous:
                approved = await self._ask_user(tool_name, args)
                if not approved:
                    raise ToolExecutionDenied(f"User declined approval for '{tool_name}'.")
                return
            if self._smart_classifier is not None:
                risky = await self._smart_classifier(tool_name, args)
                if risky:
                    approved = await self._ask_user(tool_name, args)
                    if not approved:
                        raise ToolExecutionDenied(f"User declined approval for '{tool_name}'.")
            return

    async def _ask_user(self, tool_name: str, args: dict[str, Any]) -> bool:
        if self._confirm_callback is None:
            # No interactive surface wired up -- fail closed.
            logger.warning("tool.no_confirm_callback", tool=tool_name)
            return False
        return await self._confirm_callback(tool_name, args)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


class ToolDispatcher:
    """THE single entry point for executing any tool call. Nothing in
    Hermclaw is permitted to call subprocess/Popen/docker/etc. except the
    concrete backends registered here."""

    def __init__(self, approval_gate: ApprovalGate) -> None:
        self._tools: dict[str, ToolABC] = {}
        self._approval_gate = approval_gate

    def register(self, tool: ToolABC) -> None:
        name = tool.spec().name
        if name in self._tools:
            raise ValueError(f"Tool '{name}' already registered")
        self._tools[name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def specs(self) -> list[ToolSpec]:
        """The tool list sent to the model. Gated tools that are disabled
        by config are simply never registered, so they never appear here."""
        return [t.spec() for t in self._tools.values()]

    async def dispatch(self, tool_name: str, args: dict[str, Any]) -> ToolResult:
        tool = self._tools.get(tool_name)
        if tool is None:
            return ToolResult(ok=False, output="", error=f"Unknown tool: {tool_name}")

        spec = tool.spec()
        command_text = str(args.get("command", "") or args.get("query", ""))

        if spec.requires_approval_gate:
            try:
                await self._approval_gate.check(tool_name, args, command_text)
            except ToolExecutionDenied as exc:
                logger.info("tool.denied", tool=tool_name, reason=str(exc))
                return ToolResult(ok=False, output="", error=str(exc))

        start = time.monotonic()
        try:
            result = await tool.execute(args)
        except Exception as exc:  # noqa: BLE001 - surface as ToolResult, don't crash the loop
            logger.error("tool.execution_error", tool=tool_name, error=str(exc))
            return ToolResult(ok=False, output="", error=str(exc))
        finally:
            elapsed = time.monotonic() - start
            logger.info("tool.executed", tool=tool_name, elapsed_s=round(elapsed, 3))
        return result

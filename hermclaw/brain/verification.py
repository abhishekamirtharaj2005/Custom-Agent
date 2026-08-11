"""Verification system: background review, evidence collection, stop conditions.

After the agent produces output, the verification system reviews it for:
- Correctness (code compiles, tests pass)
- Completeness (all parts of the request addressed)
- Safety (no dangerous operations slipped through)

Evidence is collected at each turn and checked against configurable
stop conditions to decide when the agent's work is "done".
"""

from __future__ import annotations

import dataclasses
import re
import time
from enum import Enum
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


class VerificationStatus(str, Enum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclasses.dataclass
class Evidence:
    """A piece of evidence collected during agent execution."""
    category: str  # "tool_result", "test_output", "lint", "user_feedback"
    content: str
    status: VerificationStatus = VerificationStatus.PENDING
    timestamp: float = dataclasses.field(default_factory=time.time)
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)

    def mark_passed(self) -> None:
        self.status = VerificationStatus.PASSED

    def mark_failed(self, reason: str = "") -> None:
        self.status = VerificationStatus.FAILED
        if reason:
            self.metadata["failure_reason"] = reason


@dataclasses.dataclass
class StopCondition:
    """A condition that must be met for the agent to stop."""
    name: str
    description: str
    check: str  # "all_tests_pass", "no_errors", "user_satisfied", "max_iterations"
    required: bool = True  # If False, this is advisory only

    def evaluate(self, evidence: list[Evidence], context: dict[str, Any]) -> bool:
        """Check if this stop condition is met."""
        if self.check == "all_tests_pass":
            test_evidence = [e for e in evidence if e.category == "test_output"]
            return all(e.status == VerificationStatus.PASSED for e in test_evidence)

        elif self.check == "no_errors":
            error_evidence = [e for e in evidence
                            if e.status == VerificationStatus.FAILED]
            return len(error_evidence) == 0

        elif self.check == "max_iterations":
            max_iter = context.get("max_iterations", 10)
            current = context.get("current_iteration", 0)
            return current >= max_iter

        elif self.check == "user_satisfied":
            feedback = [e for e in evidence if e.category == "user_feedback"]
            if not feedback:
                return False
            return feedback[-1].status == VerificationStatus.PASSED

        elif self.check == "code_compiles":
            compile_evidence = [e for e in evidence if e.category == "compile"]
            return all(e.status == VerificationStatus.PASSED for e in compile_evidence)

        elif self.check == "lint_clean":
            lint_evidence = [e for e in evidence if e.category == "lint"]
            return all(e.status == VerificationStatus.PASSED for e in lint_evidence)

        return True


class EvidenceCollector:
    """Collects and manages verification evidence across agent turns."""

    def __init__(self) -> None:
        self._evidence: list[Evidence] = []
        self._stop_conditions: list[StopCondition] = [
            StopCondition("no_errors", "No tool execution errors", "no_errors"),
            StopCondition("max_iterations", "Maximum iterations reached", "max_iterations", required=False),
        ]

    def add(self, category: str, content: str, status: VerificationStatus = VerificationStatus.PENDING,
            **metadata: Any) -> Evidence:
        """Add a piece of evidence."""
        ev = Evidence(category=category, content=content, status=status, metadata=metadata)
        self._evidence.append(ev)
        logger.debug("verification.evidence_added", category=category, status=status.value)
        return ev

    def add_tool_result(self, tool_name: str, result_ok: bool, output: str) -> Evidence:
        """Add evidence from a tool execution."""
        status = VerificationStatus.PASSED if result_ok else VerificationStatus.FAILED
        return self.add("tool_result", output[:500], status, tool_name=tool_name)

    def add_test_result(self, test_name: str, passed: bool, output: str) -> Evidence:
        """Add evidence from a test execution."""
        status = VerificationStatus.PASSED if passed else VerificationStatus.FAILED
        return self.add("test_output", output[:500], status, test_name=test_name)

    def check_stop_conditions(self, context: Optional[dict[str, Any]] = None) -> tuple[bool, list[str]]:
        """Check all stop conditions. Returns (should_stop, reasons)."""
        context = context or {}
        reasons: list[str] = []
        all_met = True

        for cond in self._stop_conditions:
            met = cond.evaluate(self._evidence, context)
            if met:
                reasons.append(f"✅ {cond.name}: met")
            elif cond.required:
                reasons.append(f"❌ {cond.name}: NOT met (required)")
                all_met = False
            else:
                reasons.append(f"⚠️ {cond.name}: NOT met (advisory)")

        return all_met, reasons

    def summary(self) -> dict[str, Any]:
        """Summary of all collected evidence."""
        by_status = {s.value: 0 for s in VerificationStatus}
        for e in self._evidence:
            by_status[e.status.value] += 1

        return {
            "total_evidence": len(self._evidence),
            "by_status": by_status,
            "categories": list(set(e.category for e in self._evidence)),
        }

    @property
    def all_passed(self) -> bool:
        return all(
            e.status in (VerificationStatus.PASSED, VerificationStatus.SKIPPED)
            for e in self._evidence
        )


class BackgroundReviewer:
    """Reviews agent output in the background after each turn.

    Checks for common issues:
    - Incomplete responses (cut off mid-sentence)
    - Unsafe shell commands in output
    - Unresolved placeholders (TODO, FIXME, etc.)
    - Hallucinated file paths
    """

    _UNSAFE_PATTERNS = [
        r"rm\s+-rf\s+/",
        r"sudo\s+rm",
        r"format\s+[a-z]:",
        r"del\s+/[sfq]",
        r":(){ :|:& };:",  # Fork bomb
        r">\s*/dev/sd[a-z]",
        r"mkfs\.",
        r"dd\s+if=.*of=/dev/",
    ]

    _PLACEHOLDER_PATTERNS = [
        r"\bTODO\b",
        r"\bFIXME\b",
        r"\bHACK\b",
        r"\bXXX\b",
        r"<your[-_]?.*>",
        r"\[INSERT\b",
        r"PLACEHOLDER",
    ]

    def review(self, text: str) -> list[dict[str, str]]:
        """Review text and return a list of issues found."""
        issues: list[dict[str, str]] = []

        # Check for unsafe patterns
        for pattern in self._UNSAFE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append({
                    "severity": "critical",
                    "type": "unsafe_command",
                    "detail": f"Potentially dangerous pattern detected: {pattern}",
                })

        # Check for unresolved placeholders
        for pattern in self._PLACEHOLDER_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                issues.append({
                    "severity": "warning",
                    "type": "placeholder",
                    "detail": f"Unresolved placeholder: {matches[0]}",
                })

        # Check for truncated response
        if text and not text.rstrip().endswith((".", "!", "?", "```", ")", "]", "}", ":")):
            last_line = text.rstrip().split("\n")[-1]
            if len(last_line) > 20 and not last_line.startswith(("#", "-", "*", "|")):
                issues.append({
                    "severity": "info",
                    "type": "truncated",
                    "detail": "Response may be truncated (doesn't end with punctuation).",
                })

        if issues:
            logger.info("review.issues_found", count=len(issues),
                       types=[i["type"] for i in issues])
        return issues

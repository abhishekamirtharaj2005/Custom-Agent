"""Agent core capabilities still missing.

Implements:
- Think-tag scrubbing (remove <think>...</think> from model outputs)
- Error classification and retry logic
- Tool guardrails (safety checks before tool execution)
- Tool schema sanitization
- Lazy dependency installation
- Tool search/discovery
- Turn context management
- Turn finalization (post-processing)
- Bounded response length enforcement
- Iteration budget control
"""

from __future__ import annotations

import importlib
import re
import subprocess
import sys
import time
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Think-tag scrubbing
# ---------------------------------------------------------------------------


class ThinkTagScrubber:
    """Remove think/reasoning tags from model outputs.

    Handles:
    - <think>...</think> (Anthropic/DeepSeek)
    - <reasoning>...</reasoning>
    - <internal_monologue>...</internal_monologue>
    - <scratchpad>...</scratchpad>
    """

    PATTERNS = [
        (re.compile(r"<think>.*?</think>", re.DOTALL), "think"),
        (re.compile(r"<thinking>.*?</thinking>", re.DOTALL), "thinking"),
        (re.compile(r"<reasoning>.*?</reasoning>", re.DOTALL), "reasoning"),
        (re.compile(r"<internal_monologue>.*?</internal_monologue>", re.DOTALL), "internal_monologue"),
        (re.compile(r"<scratchpad>.*?</scratchpad>", re.DOTALL), "scratchpad"),
        (re.compile(r"<reflection>.*?</reflection>", re.DOTALL), "reflection"),
    ]

    def scrub(self, text: str) -> tuple[str, list[str]]:
        """Remove think tags from text. Returns (cleaned_text, extracted_thoughts)."""
        thoughts: list[str] = []
        cleaned = text
        for pattern, tag_name in self.PATTERNS:
            matches = pattern.findall(cleaned)
            for m in matches:
                # Extract the thought content
                inner = re.sub(rf"</?{tag_name}>", "", m).strip()
                if inner:
                    thoughts.append(inner)
            cleaned = pattern.sub("", cleaned)

        # Clean up excess whitespace
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

        if thoughts:
            logger.debug("think_scrubber.removed", count=len(thoughts),
                        total_chars=sum(len(t) for t in thoughts))
        return cleaned, thoughts

    def has_think_tags(self, text: str) -> bool:
        return any(p.search(text) for p, _ in self.PATTERNS)


# ---------------------------------------------------------------------------
# Error classification and retry
# ---------------------------------------------------------------------------


class ErrorClassifier:
    """Classify API/tool errors and determine retry strategy."""

    class Category:
        RATE_LIMIT = "rate_limit"
        AUTH = "authentication"
        TIMEOUT = "timeout"
        SERVER = "server_error"
        CLIENT = "client_error"
        NETWORK = "network"
        QUOTA = "quota_exceeded"
        CONTEXT_LENGTH = "context_length"
        CONTENT_FILTER = "content_filter"
        UNKNOWN = "unknown"

    RETRYABLE = {Category.RATE_LIMIT, Category.TIMEOUT, Category.SERVER, Category.NETWORK}

    PATTERNS = {
        Category.RATE_LIMIT: [
            r"rate.?limit", r"429", r"too many requests", r"retry.?after",
            r"quota.*exceeded", r"throttl",
        ],
        Category.AUTH: [
            r"401", r"403", r"unauthorized", r"forbidden", r"invalid.*api.*key",
            r"authentication.*failed", r"access.*denied",
        ],
        Category.TIMEOUT: [
            r"timeout", r"timed.?out", r"deadline.*exceeded", r"504",
        ],
        Category.SERVER: [
            r"500", r"502", r"503", r"internal.*server.*error", r"service.*unavailable",
            r"bad.*gateway",
        ],
        Category.CONTEXT_LENGTH: [
            r"context.*length", r"maximum.*tokens", r"too.*long", r"token.*limit",
            r"max.*context",
        ],
        Category.CONTENT_FILTER: [
            r"content.*filter", r"safety", r"refused", r"inappropriate",
            r"content.*policy",
        ],
        Category.NETWORK: [
            r"connection.*refused", r"connection.*reset", r"dns", r"ssl",
            r"certificate", r"unreachable",
        ],
    }

    def classify(self, error: Exception | str) -> str:
        error_str = str(error).lower()
        for category, patterns in self.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, error_str):
                    return category
        return self.Category.UNKNOWN

    def is_retryable(self, error: Exception | str) -> bool:
        return self.classify(error) in self.RETRYABLE

    def suggest_delay(self, error: Exception | str, attempt: int = 1) -> float:
        """Suggest delay before retry (exponential backoff)."""
        category = self.classify(error)
        base_delays = {
            self.Category.RATE_LIMIT: 5.0,
            self.Category.TIMEOUT: 2.0,
            self.Category.SERVER: 3.0,
            self.Category.NETWORK: 1.0,
        }
        base = base_delays.get(category, 2.0)
        return min(base * (2 ** (attempt - 1)), 120.0)  # Max 2 minutes


# ---------------------------------------------------------------------------
# Tool guardrails
# ---------------------------------------------------------------------------


class ToolGuardrails:
    """Safety checks before tool execution."""

    DANGEROUS_TOOLS = {"shell", "code_exec", "process", "computer"}
    ALWAYS_ALLOW = {"web_search", "memory_search", "session_search", "system_info"}

    def __init__(self, auto_approve: bool = False) -> None:
        self._auto_approve = auto_approve
        self._history: list[dict] = []

    def check(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Check if tool call is safe. Returns {allowed, reason, needs_approval}."""
        result = {"allowed": True, "reason": "", "needs_approval": False}

        if tool_name in self.ALWAYS_ALLOW:
            return result

        if tool_name in self.DANGEROUS_TOOLS:
            result["needs_approval"] = not self._auto_approve
            if tool_name == "shell":
                cmd = args.get("command", "")
                from hermclaw.security.threat_detect import ThreatDetector
                detector = ThreatDetector()
                threats = detector.scan_command(cmd)
                if detector.has_critical(threats):
                    result["allowed"] = False
                    result["reason"] = f"Blocked: {threats[0].description}"
                elif detector.has_high_or_above(threats):
                    result["needs_approval"] = True
                    result["reason"] = f"Warning: {threats[0].description}"

        self._history.append({
            "tool": tool_name, "allowed": result["allowed"],
            "time": time.time(),
        })
        return result


# ---------------------------------------------------------------------------
# Tool schema sanitization
# ---------------------------------------------------------------------------


class ToolSchemaSanitizer:
    """Sanitize tool schemas for model consumption.

    Ensures schemas are compatible with each provider's requirements:
    - Remove unsupported JSON Schema keywords
    - Normalize enum values
    - Strip internal metadata
    """

    STRIP_KEYWORDS = {"$schema", "$id", "$ref", "examples", "default", "deprecated",
                      "readOnly", "writeOnly", "x-internal"}

    def sanitize(self, schema: dict[str, Any], provider: str = "") -> dict[str, Any]:
        """Sanitize a tool parameter schema."""
        cleaned = self._deep_clean(schema)

        # Provider-specific adjustments
        if provider == "anthropic":
            cleaned = self._anthropic_compat(cleaned)
        elif provider == "gemini":
            cleaned = self._gemini_compat(cleaned)

        return cleaned

    def _deep_clean(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {
                k: self._deep_clean(v) for k, v in obj.items()
                if k not in self.STRIP_KEYWORDS
            }
        elif isinstance(obj, list):
            return [self._deep_clean(item) for item in obj]
        return obj

    def _anthropic_compat(self, schema: dict) -> dict:
        """Anthropic requires 'type' on all properties."""
        if "properties" in schema:
            for key, prop in schema["properties"].items():
                if isinstance(prop, dict) and "type" not in prop:
                    prop["type"] = "string"
        return schema

    def _gemini_compat(self, schema: dict) -> dict:
        """Gemini doesn't support certain JSON Schema features."""
        # Remove anyOf/oneOf
        if "anyOf" in schema:
            schema = schema["anyOf"][0] if schema["anyOf"] else {"type": "string"}
        if "oneOf" in schema:
            schema = schema["oneOf"][0] if schema["oneOf"] else {"type": "string"}
        return schema


# ---------------------------------------------------------------------------
# Lazy dependency installation
# ---------------------------------------------------------------------------


class LazyDependencyInstaller:
    """Install Python packages on-demand when a tool requires them."""

    _installed: set[str] = set()

    @classmethod
    def ensure(cls, package: str, pip_name: Optional[str] = None) -> bool:
        """Ensure a package is available, installing if needed."""
        if package in cls._installed:
            return True

        try:
            importlib.import_module(package)
            cls._installed.add(package)
            return True
        except ImportError:
            pass

        install_name = pip_name or package
        logger.info("lazy_deps.installing", package=install_name)
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", install_name, "--quiet"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=120,
            )
            cls._installed.add(package)
            logger.info("lazy_deps.installed", package=install_name)
            return True
        except Exception as exc:
            logger.error("lazy_deps.install_failed", package=install_name, error=str(exc)[:100])
            return False

    @classmethod
    def require(cls, *packages: str) -> list[str]:
        """Ensure multiple packages, return list of failures."""
        failures = []
        for pkg in packages:
            if not cls.ensure(pkg):
                failures.append(pkg)
        return failures


# ---------------------------------------------------------------------------
# Tool search/discovery
# ---------------------------------------------------------------------------


class ToolDiscovery:
    """Search and discover tools by name, description, or capability."""

    def __init__(self, dispatcher: Any = None) -> None:
        self._dispatcher = dispatcher

    def search(self, query: str) -> list[dict[str, str]]:
        """Search tools by name or description keyword."""
        if not self._dispatcher:
            return []

        query_lower = query.lower()
        results = []
        for tool in self._dispatcher.all_tools():
            spec = tool.spec()
            name_match = query_lower in spec.name.lower()
            desc_match = query_lower in (spec.description or "").lower()
            if name_match or desc_match:
                results.append({
                    "name": spec.name,
                    "description": spec.description[:200],
                    "match": "name" if name_match else "description",
                })
        return results

    def list_all(self) -> list[dict[str, str]]:
        """List all available tools."""
        if not self._dispatcher:
            return []
        return [
            {"name": t.spec().name, "description": (t.spec().description or "")[:100]}
            for t in self._dispatcher.all_tools()
        ]


# ---------------------------------------------------------------------------
# Turn context management
# ---------------------------------------------------------------------------


class TurnContextManager:
    """Manage context for each turn of conversation.

    Tracks:
    - Files mentioned or modified
    - Tools used
    - Tokens consumed
    - Errors encountered
    """

    def __init__(self) -> None:
        self._turns: list[dict] = []
        self._current: dict = self._new_turn()

    def _new_turn(self) -> dict:
        return {
            "started_at": time.time(),
            "tools_used": [],
            "files_touched": [],
            "tokens_in": 0,
            "tokens_out": 0,
            "errors": [],
        }

    def start_turn(self) -> None:
        if self._current["tools_used"]:
            self._turns.append(self._current)
        self._current = self._new_turn()

    def record_tool(self, name: str, duration_ms: float = 0) -> None:
        self._current["tools_used"].append({"name": name, "duration_ms": duration_ms})

    def record_file(self, path: str, action: str = "read") -> None:
        self._current["files_touched"].append({"path": path, "action": action})

    def record_tokens(self, input_tokens: int, output_tokens: int) -> None:
        self._current["tokens_in"] += input_tokens
        self._current["tokens_out"] += output_tokens

    def record_error(self, error: str) -> None:
        self._current["errors"].append(error[:200])

    def finalize_turn(self) -> dict:
        """Finalize current turn and return summary."""
        self._current["ended_at"] = time.time()
        self._current["duration_s"] = self._current["ended_at"] - self._current["started_at"]
        summary = self._current.copy()
        self._turns.append(self._current)
        self._current = self._new_turn()
        return summary

    @property
    def turn_count(self) -> int:
        return len(self._turns)

    def total_tokens(self) -> dict[str, int]:
        total_in = sum(t["tokens_in"] for t in self._turns) + self._current["tokens_in"]
        total_out = sum(t["tokens_out"] for t in self._turns) + self._current["tokens_out"]
        return {"input": total_in, "output": total_out, "total": total_in + total_out}


# ---------------------------------------------------------------------------
# Iteration budget control
# ---------------------------------------------------------------------------


class IterationBudget:
    """Control the maximum iterations/tool calls per conversation turn."""

    def __init__(self, max_iterations: int = 25, max_tool_calls: int = 50) -> None:
        self._max_iter = max_iterations
        self._max_tools = max_tool_calls
        self._current_iter = 0
        self._current_tools = 0

    def tick_iteration(self) -> bool:
        """Record an iteration. Returns False if budget exhausted."""
        self._current_iter += 1
        if self._current_iter > self._max_iter:
            logger.warning("budget.iterations_exhausted", max=self._max_iter)
            return False
        return True

    def tick_tool_call(self) -> bool:
        """Record a tool call. Returns False if budget exhausted."""
        self._current_tools += 1
        if self._current_tools > self._max_tools:
            logger.warning("budget.tool_calls_exhausted", max=self._max_tools)
            return False
        return True

    def reset(self) -> None:
        self._current_iter = 0
        self._current_tools = 0

    @property
    def remaining_iterations(self) -> int:
        return max(0, self._max_iter - self._current_iter)

    @property
    def remaining_tools(self) -> int:
        return max(0, self._max_tools - self._current_tools)


# ---------------------------------------------------------------------------
# Bounded response length enforcement
# ---------------------------------------------------------------------------


class ResponseLengthEnforcer:
    """Enforce maximum response lengths."""

    def __init__(self, max_chars: int = 8000, truncation_message: str = "\n\n[Response truncated]") -> None:
        self._max = max_chars
        self._truncation_msg = truncation_message

    def enforce(self, text: str) -> str:
        if len(text) <= self._max:
            return text
        truncated = text[:self._max - len(self._truncation_msg)]
        # Try to truncate at sentence boundary
        last_period = truncated.rfind(".")
        if last_period > self._max * 0.8:
            truncated = truncated[:last_period + 1]
        return truncated + self._truncation_msg

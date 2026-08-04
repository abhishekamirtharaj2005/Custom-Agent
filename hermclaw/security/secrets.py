"""Secrets and credential handling.

Every credential field in the config schema is declared as an env-var
*reference* (e.g. bot_token_env: "TELEGRAM_BOT_TOKEN"), never a literal
value. This module resolves those references at load time and provides a
redact() helper used by every log line and by GET /config, closing
OpenClaw's documented plaintext-credential exposure pattern.
"""

from __future__ import annotations

import copy
import os
import re
from typing import Any, Optional

_SENSITIVE_KEY_PATTERN = re.compile(
    r"(token|secret|key|password|passwd|credential|api_key|bearer)", re.IGNORECASE
)
_REDACTED_PLACEHOLDER = "***REDACTED***"


class MissingSecretError(Exception):
    pass


def resolve_env_ref(env_var_name: Optional[str], required: bool = False) -> Optional[str]:
    """Resolve a config field declared as `<name>_env: "SOME_ENV_VAR"` to its
    actual value. Never writes the resolved value back to disk -- callers
    must keep it in memory only."""
    if not env_var_name:
        if required:
            raise MissingSecretError("No env var reference configured")
        return None
    value = os.environ.get(env_var_name)
    if value is None and required:
        raise MissingSecretError(
            f"Environment variable '{env_var_name}' is not set. "
            f"Set it before starting Hermclaw, e.g.: export {env_var_name}=..."
        )
    return value


def redact(obj: Any) -> Any:
    """Recursively redact any dict key matching a token/secret/key/password
    pattern. Safe to call on arbitrary nested config/log payloads."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(k, str) and _SENSITIVE_KEY_PATTERN.search(k):
                out[k] = _REDACTED_PLACEHOLDER
            else:
                out[k] = redact(v)
        return out
    if isinstance(obj, list):
        return [redact(item) for item in obj]
    return obj


def redact_copy(obj: dict) -> dict:
    """Non-mutating variant of redact() for callers that want to keep the
    original dict untouched (e.g. before serializing for GET /config)."""
    return redact(copy.deepcopy(obj))


def scrub_string(text: str, secret_values: list[str]) -> str:
    """Best-effort scrub of known secret literal values out of free text
    (e.g. before writing an error message to logs)."""
    for value in secret_values:
        if value:
            text = text.replace(value, _REDACTED_PLACEHOLDER)
    return text

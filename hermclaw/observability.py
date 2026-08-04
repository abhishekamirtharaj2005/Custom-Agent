"""Structured logging: structlog processors shared by every module in
this package, rendered as pretty console output for a human at a
terminal and as JSON lines to a rotating file for later inspection
(`hermclaw doctor`, `hermclaw status`, external tooling).

Every log line passes through a redaction step before rendering, as
defense in depth alongside security/secrets.py's config-level redaction
-- a stray secret in a log line is just as much a leak as one in
GET /config's response.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path
from typing import Optional

import structlog

from hermclaw.config import hermclaw_home
from hermclaw.security.secrets import redact

MAX_LOG_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 5


def _redact_event(logger: object, method_name: str, event_dict: dict) -> dict:
    return redact(event_dict)


def configure_logging(
    level: int = logging.INFO,
    log_to_file: bool = True,
    log_dir: Optional[Path] = None,
    console: bool = True,
) -> Path:
    """Idempotent: safe to call more than once (e.g. once at CLI startup,
    then again if `hermclaw serve` reconfigures verbosity). Returns the
    resolved log file path."""
    log_dir = log_dir or (hermclaw_home() / "logs")
    log_path = log_dir / "hermclaw.log"

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        _redact_event,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]

    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    handlers: list[logging.Handler] = []

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, structlog.dev.ConsoleRenderer()],
            )
        )
        handlers.append(console_handler)

    if log_to_file:
        log_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        file_handler = logging.handlers.RotatingFileHandler(
            log_path, maxBytes=MAX_LOG_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8",
        )
        file_handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, structlog.processors.JSONRenderer()],
            )
        )
        handlers.append(file_handler)

    root = logging.getLogger()
    root.handlers = handlers
    root.setLevel(level)
    return log_path


def bind_turn_context(*, profile: Optional[str] = None, session_id: Optional[str] = None, channel: Optional[str] = None) -> None:
    """Every log line emitted while a turn is in flight carries these,
    without every call site needing to pass them explicitly."""
    kwargs = {k: v for k, v in {"profile": profile, "session_id": session_id, "channel": channel}.items() if v is not None}
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_turn_context() -> None:
    structlog.contextvars.clear_contextvars()

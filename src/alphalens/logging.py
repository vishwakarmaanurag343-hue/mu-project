"""Structured logging configuration with secret redaction."""

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

from alphalens.config import get_settings

SENSITIVE_KEYWORDS = ("key", "token", "secret", "password", "authorization")


def redact_secrets(_logger: WrappedLogger, _name: str, event_dict: EventDict) -> EventDict:
    """Recursively redact dictionary keys that contain sensitive words."""

    def _redact(val: Any) -> Any:
        if isinstance(val, MutableMapping):
            cleaned: dict[str, Any] = {}
            for k, v in val.items():
                if any(kw in str(k).lower() for kw in SENSITIVE_KEYWORDS):
                    cleaned[k] = "[REDACTED]"
                else:
                    cleaned[k] = _redact(v)
            return cleaned
        if isinstance(val, list | tuple):
            return [_redact(item) for item in val]
        return val

    return _redact(event_dict)  # type: ignore[no-any-return]


def configure_logging() -> None:
    """Configure structlog and standard logging."""
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        redact_secrets,
    ]

    if settings.app_env == "prod":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.UnicodeDecoder(),
            renderer,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog bound logger."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]

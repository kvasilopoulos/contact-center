"""Logging configuration: human-readable for development, JSON for production.

Configure once at application startup. Use structured logs via the extra dict:
    logger.info("message", extra={"key": value})
"""

from datetime import datetime, timezone
import json
import logging
import sys
from typing import Any

# Third-party loggers: always WARNING so they don't flood output regardless of app level.
THIRD_PARTY_LOGGER_LEVELS: dict[str, str] = {
    "uvicorn": "WARNING",
    "uvicorn.error": "WARNING",
    "uvicorn.access": "WARNING",
    "watchfiles": "WARNING",
}

# Standard LogRecord attribute names to exclude from extra-field output.
_RECORD_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "created",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "exc_info",
        "exc_text",
        "message",
        "thread",
        "threadName",
        "taskName",
        "getMessage",
    }
)

# Third-party / display-only attributes to never include in output (e.g. ANSI color codes).
_EXCLUDE_EXTRAS = frozenset({"color_message"})


def _extra_fields(record: logging.LogRecord) -> dict[str, Any]:
    """Extract user-supplied extra fields from a log record."""
    return {
        key: value
        for key, value in record.__dict__.items()
        if key not in _RECORD_ATTRS and key not in _EXCLUDE_EXTRAS and value is not None
    }


class JsonFormatter(logging.Formatter):
    """Format log records as one JSON object per line for centralized ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(_extra_fields(record))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str) + "\n"


class DevFormatter(logging.Formatter):
    """Human-readable formatter for local development.

    Output example:
        2025-01-15 10:23:45 | INFO     | app.factory | Starting application  app=MyApp version=0.1.0
    """

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        level = record.levelname.ljust(8)
        message = record.getMessage()

        extras = _extra_fields(record)
        extras_str = "  " + " ".join(f"{k}={v}" for k, v in extras.items()) if extras else ""

        line = f"{ts} | {level} | {record.name} | {message}{extras_str}"

        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            indented = "\n".join(f"  {line_text}" for line_text in exc_text.splitlines())
            line = f"{line}\n{indented}"

        return line


def configure_logging(
    level: str | int = "INFO",
    *,
    environment: str = "production",
    stream: Any = None,
    logger_levels: dict[str, str | int] | None = None,
) -> None:
    """Configure root logger. Call once at application startup.

    Args:
        level: Root logger level (e.g. "INFO", logging.INFO).
        environment: "development" for human-readable output, anything else for JSON.
        stream: Output stream; defaults to sys.stdout.
        logger_levels: Optional mapping of logger names to levels.
    """
    if stream is None:
        stream = sys.stdout
    root = logging.getLogger()
    root.setLevel(level if isinstance(level, int) else getattr(logging, level.upper()))
    root.handlers.clear()

    handler = logging.StreamHandler(stream)
    formatter = DevFormatter() if environment == "development" else JsonFormatter()
    handler.setFormatter(formatter)
    handler.setLevel(root.level)
    root.addHandler(handler)

    levels = {**THIRD_PARTY_LOGGER_LEVELS, **(logger_levels or {})}
    for name, lvl in levels.items():
        log = logging.getLogger(name)
        log.setLevel(lvl if isinstance(lvl, int) else getattr(logging, lvl.upper()))


__all__ = [
    "THIRD_PARTY_LOGGER_LEVELS",
    "DevFormatter",
    "JsonFormatter",
    "configure_logging",
]

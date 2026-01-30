"""Production-grade JSON logging configuration using the standard library.

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

# Standard LogRecord attribute names to exclude from the JSON payload (extra only).
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


class JsonFormatter(logging.Formatter):
    """Format log records as one JSON object per line for centralized ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RECORD_ATTRS and value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str) + "\n"


def configure_logging(
    level: str | int = "INFO",
    stream: Any = None,
    logger_levels: dict[str, str | int] | None = None,
) -> None:
    """Configure root logger with JSON output. Call once at application startup.

    Args:
        level: Root logger level (e.g. "INFO", logging.INFO).
        stream: Output stream; defaults to sys.stdout.
        logger_levels: Optional mapping of logger names to levels, e.g.
            {"uvicorn": "WARNING", "watchfiles": "WARNING"} to reduce noise from
            third-party loggers.
    """
    if stream is None:
        stream = sys.stdout
    root = logging.getLogger()
    root.setLevel(level if isinstance(level, int) else getattr(logging, level.upper()))
    root.handlers.clear()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.setLevel(root.level)
    root.addHandler(handler)

    levels = {**THIRD_PARTY_LOGGER_LEVELS, **(logger_levels or {})}
    for name, lvl in levels.items():
        log = logging.getLogger(name)
        log.setLevel(lvl if isinstance(lvl, int) else getattr(logging, lvl.upper()))


__all__ = ["THIRD_PARTY_LOGGER_LEVELS", "JsonFormatter", "configure_logging"]

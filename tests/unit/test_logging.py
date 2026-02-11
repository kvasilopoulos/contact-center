"""Tests for logging configuration (JSON + human-readable formatters)."""

from io import StringIO
import json
import logging
import sys

from app.core import DevFormatter, JsonFormatter, configure_logging

# ---------------------------------------------------------------------------
# JsonFormatter
# ---------------------------------------------------------------------------


def test_json_formatter_outputs_valid_json_one_object_per_line() -> None:
    """Each formatted record is a single line of valid JSON."""
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Test message",
        args=(),
        exc_info=None,
    )
    record.request_id = "abc-123"
    record.duration_ms = 10
    output = formatter.format(record)
    lines = output.strip().split("\n")
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["message"] == "Test message"
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test.logger"
    assert "timestamp" in parsed
    assert parsed["request_id"] == "abc-123"
    assert parsed["duration_ms"] == 10


def test_json_formatter_includes_exception_when_present() -> None:
    """Exception info is included in the JSON payload when exc_info is set."""
    formatter = JsonFormatter()
    try:
        raise ValueError("test error")
    except ValueError:
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Failed",
            args=(),
            exc_info=sys.exc_info(),
        )
    output = formatter.format(record)
    parsed = json.loads(output.strip())
    assert parsed["message"] == "Failed"
    assert "exception" in parsed
    assert "ValueError" in parsed["exception"]
    assert "test error" in parsed["exception"]


def test_json_formatter_excludes_color_message() -> None:
    """Uvicorn-style color_message (ANSI codes) is excluded from JSON output."""
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="uvicorn.error",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Uvicorn running on %s://%s:%d (Press CTRL+C to quit)",
        args=("http", "127.0.0.1", 8001),
        exc_info=None,
    )
    record.color_message = "Uvicorn running on \x1b[1m%s://%s:%d\x1b[0m (Press CTRL+C to quit)"
    output = formatter.format(record)
    parsed = json.loads(output.strip())
    assert parsed["message"] == "Uvicorn running on http://127.0.0.1:8001 (Press CTRL+C to quit)"
    assert "color_message" not in parsed


# ---------------------------------------------------------------------------
# DevFormatter
# ---------------------------------------------------------------------------


def test_dev_formatter_outputs_human_readable_line() -> None:
    """DevFormatter produces a pipe-delimited, human-readable line."""
    formatter = DevFormatter()
    record = logging.LogRecord(
        name="app.factory",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Starting application",
        args=(),
        exc_info=None,
    )
    record.app_name = "MyApp"
    record.version = "1.0"
    output = formatter.format(record)
    assert "INFO" in output
    assert "app.factory" in output
    assert "Starting application" in output
    assert "app_name=MyApp" in output
    assert "version=1.0" in output
    # Must be a single line (no embedded newlines)
    assert "\n" not in output


def test_dev_formatter_includes_exception() -> None:
    """DevFormatter includes indented exception traceback."""
    formatter = DevFormatter()
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Something failed",
            args=(),
            exc_info=sys.exc_info(),
        )
    output = formatter.format(record)
    assert "Something failed" in output
    assert "RuntimeError: boom" in output
    # Exception lines should be indented
    exc_lines = output.split("\n")[1:]
    assert all(line.startswith("  ") for line in exc_lines if line)


def test_dev_formatter_no_extras_no_trailing_whitespace() -> None:
    """When there are no extras, no trailing spaces after the message."""
    formatter = DevFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.WARNING,
        pathname="",
        lineno=0,
        msg="Simple message",
        args=(),
        exc_info=None,
    )
    output = formatter.format(record)
    assert output.endswith("Simple message")


# ---------------------------------------------------------------------------
# configure_logging (environment switching)
# ---------------------------------------------------------------------------


def test_configure_logging_uses_json_by_default() -> None:
    """Default (production) environment uses JsonFormatter."""
    stream = StringIO()
    configure_logging(level="INFO", stream=stream)
    try:
        logger = logging.getLogger("test.json_default")
        logger.info("Structured log", extra={"key": "value", "count": 42})
        output = stream.getvalue()
        parsed = json.loads(output.strip())
        assert parsed["message"] == "Structured log"
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.json_default"
        assert parsed["key"] == "value"
        assert parsed["count"] == 42
    finally:
        configure_logging(level="INFO")


def test_configure_logging_uses_dev_formatter_for_development() -> None:
    """environment='development' produces human-readable output, not JSON."""
    stream = StringIO()
    configure_logging(level="INFO", environment="development", stream=stream)
    try:
        logger = logging.getLogger("test.dev_env")
        logger.info("Hello dev", extra={"request_id": "abc-123"})
        output = stream.getvalue().strip()
        # Should NOT be valid JSON
        is_json = True
        try:
            json.loads(output)
        except json.JSONDecodeError:
            is_json = False
        assert not is_json, "Development output should not be JSON"
        assert "Hello dev" in output
        assert "request_id=abc-123" in output
    finally:
        configure_logging(level="INFO")


def test_configure_logging_uses_json_for_production() -> None:
    """environment='production' produces JSON output."""
    stream = StringIO()
    configure_logging(level="INFO", environment="production", stream=stream)
    try:
        logger = logging.getLogger("test.prod_env")
        logger.info("Hello prod", extra={"request_id": "xyz-789"})
        output = stream.getvalue()
        parsed = json.loads(output.strip())
        assert parsed["message"] == "Hello prod"
        assert parsed["request_id"] == "xyz-789"
    finally:
        configure_logging(level="INFO")

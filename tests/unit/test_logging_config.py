"""Tests for JSON logging configuration."""

from io import StringIO
import json
import logging
import sys

from app.logging_config import JsonFormatter, configure_logging


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


def test_configure_logging_is_deterministic_and_testable() -> None:
    """configure_logging with a stream allows deterministic, testable output."""
    stream = StringIO()
    configure_logging(level="INFO", stream=stream)
    try:
        logger = logging.getLogger("test.deterministic")
        logger.info("Structured log", extra={"key": "value", "count": 42})
        output = stream.getvalue()
        parsed = json.loads(output.strip())
        assert parsed["message"] == "Structured log"
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.deterministic"
        assert parsed["key"] == "value"
        assert parsed["count"] == 42
    finally:
        configure_logging(level="INFO")

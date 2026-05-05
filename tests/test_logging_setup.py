"""Unit tests for logging_setup.py.

Covers:
1. Text format output — handler writes to stdout, message contains expected fields
2. JSON format output — each record is valid JSON with required keys
3. DEBUG entries emitted only when verbose=True
4. Idempotency — calling setup_logging multiple times does not add duplicate handlers
5. Extra fields passed via extra={} appear in JSON output

Requirements: 7.3, 7.4
"""

from __future__ import annotations

import io
import json
import logging
import sys

import pytest

from jira_repo_automation.logging_setup import setup_logging, _LOGGER_NAME


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_logger() -> logging.Logger:
    """Return the package logger with all handlers removed."""
    logger = logging.getLogger(_LOGGER_NAME)
    logger.handlers.clear()
    return logger


def _capture_output(logger: logging.Logger) -> io.StringIO:
    """Replace the logger's first handler stream with a StringIO buffer and
    return that buffer so tests can inspect what was written."""
    buf = io.StringIO()
    assert logger.handlers, "Logger has no handlers — call setup_logging first"
    logger.handlers[0].stream = buf
    return buf


# ---------------------------------------------------------------------------
# 1. Text format output
# ---------------------------------------------------------------------------


class TestTextFormat:
    """setup_logging(log_format='text') produces human-readable output."""

    def setup_method(self):
        _fresh_logger()

    def test_handler_writes_to_stdout_by_default(self):
        setup_logging(log_format="text")
        logger = logging.getLogger(_LOGGER_NAME)
        assert logger.handlers, "Expected at least one handler"
        handler = logger.handlers[0]
        assert isinstance(handler, logging.StreamHandler)
        assert handler.stream is sys.stdout

    def test_text_output_contains_level(self):
        setup_logging(log_format="text")
        logger = logging.getLogger(_LOGGER_NAME)
        buf = _capture_output(logger)

        logger.info("hello world")

        output = buf.getvalue()
        assert "INFO" in output

    def test_text_output_contains_message(self):
        setup_logging(log_format="text")
        logger = logging.getLogger(_LOGGER_NAME)
        buf = _capture_output(logger)

        logger.info("unique-message-xyz")

        assert "unique-message-xyz" in buf.getvalue()

    def test_text_output_contains_logger_name(self):
        setup_logging(log_format="text")
        logger = logging.getLogger(_LOGGER_NAME)
        buf = _capture_output(logger)

        logger.info("msg")

        assert _LOGGER_NAME in buf.getvalue()

    def test_text_output_contains_timestamp(self):
        setup_logging(log_format="text")
        logger = logging.getLogger(_LOGGER_NAME)
        buf = _capture_output(logger)

        logger.info("msg")

        # ISO 8601 timestamps contain 'T' and 'Z'
        output = buf.getvalue()
        assert "T" in output and "Z" in output


# ---------------------------------------------------------------------------
# 2. JSON format output
# ---------------------------------------------------------------------------


class TestJsonFormat:
    """setup_logging(log_format='json') produces valid JSON records."""

    def setup_method(self):
        _fresh_logger()

    def test_json_output_is_valid_json(self):
        setup_logging(log_format="json")
        logger = logging.getLogger(_LOGGER_NAME)
        buf = _capture_output(logger)

        logger.info("test message")

        line = buf.getvalue().strip()
        record = json.loads(line)  # must not raise
        assert isinstance(record, dict)

    def test_json_output_has_timestamp_field(self):
        setup_logging(log_format="json")
        logger = logging.getLogger(_LOGGER_NAME)
        buf = _capture_output(logger)

        logger.info("msg")

        record = json.loads(buf.getvalue().strip())
        assert "timestamp" in record
        # ISO 8601 format check
        assert "T" in record["timestamp"]
        assert record["timestamp"].endswith("Z")

    def test_json_output_has_level_field(self):
        setup_logging(log_format="json")
        logger = logging.getLogger(_LOGGER_NAME)
        buf = _capture_output(logger)

        logger.warning("msg")

        record = json.loads(buf.getvalue().strip())
        assert record["level"] == "WARNING"

    def test_json_output_has_logger_field(self):
        setup_logging(log_format="json")
        logger = logging.getLogger(_LOGGER_NAME)
        buf = _capture_output(logger)

        logger.info("msg")

        record = json.loads(buf.getvalue().strip())
        assert record["logger"] == _LOGGER_NAME

    def test_json_output_has_message_field(self):
        setup_logging(log_format="json")
        logger = logging.getLogger(_LOGGER_NAME)
        buf = _capture_output(logger)

        logger.info("my-unique-message")

        record = json.loads(buf.getvalue().strip())
        assert record["message"] == "my-unique-message"

    def test_json_output_includes_extra_fields(self):
        setup_logging(log_format="json")
        logger = logging.getLogger(_LOGGER_NAME)
        buf = _capture_output(logger)

        logger.info("msg", extra={"ticket_id": "PROJ-123", "operation": "clone"})

        record = json.loads(buf.getvalue().strip())
        assert record.get("ticket_id") == "PROJ-123"
        assert record.get("operation") == "clone"

    def test_json_extra_fields_multiple_values(self):
        """Multiple extra fields all appear in the JSON output."""
        setup_logging(log_format="json")
        logger = logging.getLogger(_LOGGER_NAME)
        buf = _capture_output(logger)

        logger.info(
            "multi-extra",
            extra={"ticket_id": "PROJ-999", "repo_url": "https://gitlab.com/org/repo"},
        )

        record = json.loads(buf.getvalue().strip())
        assert record.get("ticket_id") == "PROJ-999"
        assert record.get("repo_url") == "https://gitlab.com/org/repo"
        # Core fields must still be present.
        assert record["message"] == "multi-extra"
        assert record["level"] == "INFO"


# ---------------------------------------------------------------------------
# 3. Verbose / DEBUG level control
# ---------------------------------------------------------------------------


class TestVerboseFlag:
    """DEBUG entries are emitted only when verbose=True."""

    def setup_method(self):
        _fresh_logger()

    def test_debug_entries_emitted_when_verbose_true(self):
        setup_logging(log_format="text", verbose=True)
        logger = logging.getLogger(_LOGGER_NAME)
        buf = _capture_output(logger)

        logger.debug("debug-entry")

        assert "debug-entry" in buf.getvalue()

    def test_debug_entries_suppressed_when_verbose_false(self):
        setup_logging(log_format="text", verbose=False)
        logger = logging.getLogger(_LOGGER_NAME)
        buf = _capture_output(logger)

        logger.debug("should-not-appear")

        assert "should-not-appear" not in buf.getvalue()

    def test_info_entries_emitted_when_verbose_false(self):
        setup_logging(log_format="text", verbose=False)
        logger = logging.getLogger(_LOGGER_NAME)
        buf = _capture_output(logger)

        logger.info("info-entry")

        assert "info-entry" in buf.getvalue()

    def test_logger_level_is_debug_when_verbose_true(self):
        setup_logging(log_format="text", verbose=True)
        logger = logging.getLogger(_LOGGER_NAME)
        assert logger.level == logging.DEBUG

    def test_logger_level_is_info_when_verbose_false(self):
        setup_logging(log_format="text", verbose=False)
        logger = logging.getLogger(_LOGGER_NAME)
        assert logger.level == logging.INFO

    def test_json_debug_entries_emitted_when_verbose_true(self):
        setup_logging(log_format="json", verbose=True)
        logger = logging.getLogger(_LOGGER_NAME)
        buf = _capture_output(logger)

        logger.debug("debug-json-entry")

        output = buf.getvalue().strip()
        assert output, "Expected debug output but got nothing"
        record = json.loads(output)
        assert record["level"] == "DEBUG"
        assert record["message"] == "debug-json-entry"


# ---------------------------------------------------------------------------
# 4. Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    """Calling setup_logging multiple times must not add duplicate handlers."""

    def setup_method(self):
        _fresh_logger()

    def test_single_handler_after_multiple_calls(self):
        setup_logging(log_format="text")
        setup_logging(log_format="text")
        setup_logging(log_format="json")

        logger = logging.getLogger(_LOGGER_NAME)
        assert len(logger.handlers) == 1

    def test_reconfigure_changes_formatter(self):
        setup_logging(log_format="text")
        setup_logging(log_format="json")

        logger = logging.getLogger(_LOGGER_NAME)
        buf = _capture_output(logger)
        logger.info("reconfigure-test")

        # After switching to JSON, output must be valid JSON.
        record = json.loads(buf.getvalue().strip())
        assert record["message"] == "reconfigure-test"

    def test_reconfigure_changes_level(self):
        setup_logging(log_format="text", verbose=False)
        setup_logging(log_format="text", verbose=True)

        logger = logging.getLogger(_LOGGER_NAME)
        assert logger.level == logging.DEBUG

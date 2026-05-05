# Feature: jira-repo-automation, Property 20: Error log entry contains operation name, error message, and ticket ID

"""Property-based tests for logging_setup.py.

**Validates: Requirements 7.2**
"""

from __future__ import annotations

import io
import json
import logging

from hypothesis import given, settings
from hypothesis import strategies as st

from jira_repo_automation.logging_setup import setup_logging, _LOGGER_NAME

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# A safe printable-text strategy that avoids null bytes and control characters
# which could interfere with log output parsing.
_safe_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters="-_./: @#",
    ),
    min_size=1,
    max_size=64,
)


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
# Property 20: Error log entry contains operation name, error message, and ticket ID
# (text format)
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(
    operation=_safe_text,
    error_message=_safe_text,
    ticket_id=_safe_text,
)
def test_error_log_entry_contains_all_fields_text_format(
    operation: str,
    error_message: str,
    ticket_id: str,
) -> None:
    """Property 20 (text format): For any operation name, error message, and
    ticket ID, an ERROR-level log entry emitted with those values as extra
    fields should contain all three values in the text output.

    **Validates: Requirements 7.2**
    """
    _fresh_logger()
    setup_logging(log_format="text")
    logger = logging.getLogger(_LOGGER_NAME)
    buf = _capture_output(logger)

    logger.error(
        error_message,
        extra={
            "operation": operation,
            "ticket_id": ticket_id,
        },
    )

    output = buf.getvalue()
    assert operation in output, (
        f"Expected operation {operation!r} in text log output, got: {output!r}"
    )
    assert error_message in output, (
        f"Expected error_message {error_message!r} in text log output, got: {output!r}"
    )
    assert ticket_id in output, (
        f"Expected ticket_id {ticket_id!r} in text log output, got: {output!r}"
    )


# ---------------------------------------------------------------------------
# Property 20: Error log entry contains operation name, error message, and ticket ID
# (JSON format)
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(
    operation=_safe_text,
    error_message=_safe_text,
    ticket_id=_safe_text,
)
def test_error_log_entry_contains_all_fields_json_format(
    operation: str,
    error_message: str,
    ticket_id: str,
) -> None:
    """Property 20 (JSON format): For any operation name, error message, and
    ticket ID, an ERROR-level log entry emitted with those values as extra
    fields should contain all three values in the JSON output, with the
    correct level set to "ERROR".

    **Validates: Requirements 7.2**
    """
    _fresh_logger()
    setup_logging(log_format="json")
    logger = logging.getLogger(_LOGGER_NAME)
    buf = _capture_output(logger)

    logger.error(
        error_message,
        extra={
            "operation": operation,
            "ticket_id": ticket_id,
        },
    )

    raw = buf.getvalue().strip()
    assert raw, "Expected JSON log output but got nothing"

    record = json.loads(raw)

    assert record.get("level") == "ERROR", (
        f"Expected level 'ERROR', got {record.get('level')!r}"
    )
    assert record.get("message") == error_message, (
        f"Expected message {error_message!r}, got {record.get('message')!r}"
    )
    assert record.get("operation") == operation, (
        f"Expected operation {operation!r} in JSON record, got {record.get('operation')!r}"
    )
    assert record.get("ticket_id") == ticket_id, (
        f"Expected ticket_id {ticket_id!r} in JSON record, got {record.get('ticket_id')!r}"
    )

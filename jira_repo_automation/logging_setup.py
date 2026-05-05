"""Structured logging configuration for Jira Repo Automation.

Provides a single entry point, ``setup_logging``, that configures the root
logger (or the package-level ``jira_repo_automation`` logger) to write to
stdout in either plain-text or JSON format.

Usage::

    from jira_repo_automation.logging_setup import setup_logging

    setup_logging(log_format="json", verbose=True)
    import logging
    log = logging.getLogger("jira_repo_automation")
    log.info("Starting pipeline", extra={"ticket_id": "PROJ-123"})
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

# The logger hierarchy root used by this package.
_LOGGER_NAME = "jira_repo_automation"


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


class _TextFormatter(logging.Formatter):
    """Plain-text formatter.

    Format: ``%(asctime)s  %(levelname)-8s  %(name)s  %(message)s  [key=value ...]``

    The timestamp is emitted in ISO 8601 format (UTC).  Any extra fields
    passed via ``extra={}`` in the log call are appended as ``key=value``
    pairs enclosed in square brackets.
    """

    _FMT = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
    _DATEFMT = "%Y-%m-%dT%H:%M:%S"

    # Standard LogRecord attributes that should not be forwarded as extras.
    _LOGRECORD_ATTRS = frozenset(
        {
            "args",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "message",
            "module",
            "msecs",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "taskName",
            "thread",
            "threadName",
        }
    )

    def __init__(self) -> None:
        super().__init__(fmt=self._FMT, datefmt=self._DATEFMT)

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:  # noqa: N802
        """Return an ISO 8601 UTC timestamp."""
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return dt.strftime(datefmt or self._DATEFMT) + "Z"

    def format(self, record: logging.LogRecord) -> str:
        """Format the record, appending any extra fields as key=value pairs."""
        base = super().format(record)

        # Collect extra fields not part of the standard LogRecord attributes.
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in self._LOGRECORD_ATTRS and not key.startswith("_")
        }

        if extras:
            pairs = "  ".join(f"{k}={v}" for k, v in extras.items())
            return f"{base}  [{pairs}]"
        return base


class _JsonFormatter(logging.Formatter):
    """JSON formatter.

    Each log record is emitted as a single-line JSON object with the fields:

    * ``timestamp`` — ISO 8601 string in UTC (e.g. ``"2024-01-15T12:34:56.789Z"``)
    * ``level``     — uppercase level name (e.g. ``"INFO"``)
    * ``logger``    — logger name
    * ``message``   — formatted log message

    Any extra fields passed via ``extra={}`` in the log call are merged into
    the top-level JSON object, provided they do not shadow the four reserved
    keys above.
    """

    # Keys that are always present and must not be overwritten by extra fields.
    _RESERVED = frozenset({"timestamp", "level", "logger", "message"})

    # Standard LogRecord attributes that should not be forwarded as extras.
    _LOGRECORD_ATTRS = frozenset(
        {
            "args",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "message",
            "module",
            "msecs",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "taskName",
            "thread",
            "threadName",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        # Ensure record.message is populated.
        record.message = record.getMessage()

        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        timestamp = dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"

        entry: dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.message,
        }

        # Merge extra fields, skipping reserved keys and standard LogRecord attrs.
        for key, value in record.__dict__.items():
            if key in self._RESERVED or key in self._LOGRECORD_ATTRS:
                continue
            # Skip private / dunder attributes.
            if key.startswith("_"):
                continue
            entry[key] = value

        # Append exception info if present.
        if record.exc_info:
            entry["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(entry, default=str)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def setup_logging(log_format: str = "text", verbose: bool = False) -> None:
    """Configure the ``jira_repo_automation`` logger.

    Parameters
    ----------
    log_format:
        ``"text"`` for human-readable plain-text output (default), or
        ``"json"`` for structured JSON output.  Any other value falls back to
        ``"text"``.
    verbose:
        When ``True``, set the logger level to ``DEBUG`` so that DEBUG-level
        entries are emitted.  When ``False`` (default), the level is ``INFO``.

    The function is **idempotent**: calling it multiple times will not add
    duplicate handlers.  Each call reconfigures the existing handler (or adds
    one if none is present) and updates the log level and formatter.

    Log output is written to **stdout** (not stderr).
    """
    logger = logging.getLogger(_LOGGER_NAME)

    level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)

    # Prevent log records from propagating to the root logger, which may have
    # its own handlers that would produce duplicate output.
    logger.propagate = False

    # Choose formatter.
    formatter: logging.Formatter
    if log_format == "json":
        formatter = _JsonFormatter()
    else:
        formatter = _TextFormatter()

    if logger.handlers:
        # Reconfigure the existing handler(s) rather than adding a new one.
        for handler in logger.handlers:
            handler.setLevel(level)
            handler.setFormatter(formatter)
    else:
        # First call: add a single StreamHandler writing to stdout.
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setLevel(level)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

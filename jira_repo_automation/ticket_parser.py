"""Ticket parsing for Jira Repo Automation.

Extracts structured information from a raw ``jira.Issue`` object:

* ``repo_url``   — from the ``git url`` custom field
* ``branch``     — from the ``branch`` custom field
* ``summary``    — from the standard Jira ``summary`` field
* ``description``— from the standard Jira ``description`` field

All parsing is pure (no I/O).  Malformed or absent fields raise
:class:`~jira_repo_automation.exceptions.TicketParseError` with a message
that contains both the field name and the ticket ID.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from jira_repo_automation.exceptions import TicketParseError

log = logging.getLogger("jira_repo_automation.ticket_parser")


@dataclass
class ParsedTicket:
    """Structured representation of a Jira ticket after parsing.

    Attributes
    ----------
    ticket_id:
        The Jira issue key, e.g. ``"PROJ-123"``.
    repo_url:
        The GitLab repository URL extracted from the ``git url`` custom field.
    branch:
        The target branch name extracted from the ``branch`` custom field.
    summary:
        The Jira ticket summary line.
    description:
        The Jira ticket description body.
    """

    ticket_id: str
    repo_url: str
    branch: str
    summary: str
    description: str


class TicketParser:
    """Parses a raw ``jira.Issue`` into a :class:`ParsedTicket`.

    Extracts the git URL and branch name directly from custom fields
    without expecting any prefix.
    """

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_custom_field(issue: Any, field_name: str) -> str | None:
        """Return the value of a Jira custom field by its display name or ID.

        The ``jira`` library exposes custom fields as ``customfield_NNNNN``
        in the raw fields dict. We search by looking for fields that contain
        the field_name value (for git URL and branch fields).

        For simplicity and robustness we look for the field value by:
        1. Checking the ``names`` mapping if available
        2. Iterating raw fields dict and matching by value content
        3. Iterating all fields and looking for a matching attribute name
        """
        # Approach 1: use the ``names`` mapping if the issue was fetched with
        # ``expand='names'`` (common in production usage).
        names: dict[str, str] = {}
        if hasattr(issue, "raw") and isinstance(issue.raw, dict):
            names = issue.raw.get("names", {})

        if names:
            # names maps customfield_id → display name
            for cf_id, display_name in names.items():
                if display_name.lower() == field_name.lower():
                    return getattr(issue.fields, cf_id, None)

        # Approach 2: iterate raw fields dict and look for fields that match
        # by their value content (e.g., git URL fields contain "http")
        if hasattr(issue, "raw") and isinstance(issue.raw, dict):
            raw_fields: dict[str, Any] = issue.raw.get("fields", {})
            for key, value in raw_fields.items():
                if key.startswith("customfield_"):
                    # For git url field, look for http URLs
                    if field_name.lower() == "git url" and isinstance(value, str) and value.startswith("http"):
                        return value
                    # For branch field, look for non-URL strings
                    if field_name.lower() == "branch" and isinstance(value, str) and not value.startswith("http"):
                        return value

        # Approach 3: iterate all fields and look for a matching attribute
        # name (some test mocks expose fields directly by display name).
        if hasattr(issue.fields, field_name):
            return getattr(issue.fields, field_name)

        return None

    def _parse_field(
        self,
        issue: Any,
        field_name: str,
        ticket_id: str,
    ) -> str:
        """Extract the value from a custom field.

        Parameters
        ----------
        issue:
            The raw ``jira.Issue`` object.
        field_name:
            The display name of the custom field (used in error messages).
        ticket_id:
            The Jira issue key (used in error messages).

        Returns
        -------
        str
            The field value stripped of whitespace.

        Raises
        ------
        TicketParseError
            If the field is absent or empty.
        """
        raw_value = self._get_custom_field(issue, field_name)

        if raw_value is None or not str(raw_value).strip():
            raise TicketParseError(
                f"Missing required field '{field_name}' in ticket {ticket_id}"
            )

        return str(raw_value).strip()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, issue: Any) -> ParsedTicket:
        """Parse a raw Jira issue into a :class:`ParsedTicket`.

        Parameters
        ----------
        issue:
            A ``jira.Issue`` object (or any object with a compatible
            ``.fields`` attribute and ``.key`` attribute).

        Returns
        -------
        ParsedTicket
            The structured ticket data.

        Raises
        ------
        TicketParseError
            If any required field is absent or malformed.  The error message
            contains both the field name and the ticket ID.
        """
        ticket_id: str = issue.key

        log.debug("Parsing Jira ticket", extra={"ticket_id": ticket_id})
        
        # Debug: log all available fields
        if hasattr(issue, "raw") and isinstance(issue.raw, dict):
            raw_fields = issue.raw.get("fields", {})
            field_keys = list(raw_fields.keys())
            log.debug(
                "Available raw fields",
                extra={"field_keys": str(field_keys)},
            )
            # Also log field values for debugging
            for key, value in raw_fields.items():
                if isinstance(value, str) and ("git" in value.lower() or "branch" in value.lower() or "http" in value.lower()):
                    log.debug(
                        "Potential field match",
                        extra={"key": key, "value": str(value)[:100]},
                    )

        # --- Extract repo URL ---
        repo_url = self._parse_field(
            issue,
            field_name="git url",
            ticket_id=ticket_id,
        )

        # --- Extract branch ---
        branch = self._parse_field(
            issue,
            field_name="branch",
            ticket_id=ticket_id,
        )

        # --- Extract summary ---
        summary: str = getattr(issue.fields, "summary", None) or ""
        if not summary:
            raise TicketParseError(
                f"Missing required field 'summary' in ticket {ticket_id}"
            )

        # --- Extract description (optional but included) ---
        description: str = getattr(issue.fields, "description", None) or ""

        parsed = ParsedTicket(
            ticket_id=ticket_id,
            repo_url=repo_url,
            branch=branch,
            summary=summary,
            description=description,
        )

        log.debug(
            "Ticket parsed successfully",
            extra={"ticket_id": ticket_id, "repo_url": repo_url, "branch": branch},
        )

        return parsed

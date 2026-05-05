"""Jira REST API client for Jira Repo Automation.

Authenticates with the Jira REST API using HTTP Basic auth (username +
API token for Jira Cloud, or PAT for Jira Server/Data Center) and exposes
a single ``get_ticket`` method that fetches a full Jira issue.

Error mapping
-------------
* 401 / 403  → :class:`~jira_repo_automation.exceptions.JiraAuthError`
* 404        → :class:`~jira_repo_automation.exceptions.JiraTicketNotFoundError`
* Network /
  other HTTP → :class:`~jira_repo_automation.exceptions.JiraConnectionError`
"""

from __future__ import annotations

import logging

import jira as jira_lib
import requests

from jira_repo_automation.config import Config
from jira_repo_automation.exceptions import (
    JiraAuthError,
    JiraConnectionError,
    JiraTicketNotFoundError,
)

log = logging.getLogger("jira_repo_automation.jira_client")


class JiraClient:
    """Thin wrapper around the ``jira`` library.

    Parameters
    ----------
    config:
        A fully-populated :class:`~jira_repo_automation.config.Config`
        instance.  The client reads ``jira_base_url``, ``jira_username``,
        and ``jira_api_token`` from it.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._client: jira_lib.JIRA | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_client(self) -> jira_lib.JIRA:
        """Return a lazily-initialised ``jira.JIRA`` instance.

        Authentication errors are mapped to :class:`JiraAuthError` here so
        that callers never see raw ``jira`` exceptions.
        """
        if self._client is not None:
            return self._client

        log.debug(
            "Initialising Jira client",
            extra={"base_url": self._config.jira_base_url},
        )
        try:
            self._client = jira_lib.JIRA(
                server=self._config.jira_base_url,
                basic_auth=(self._config.jira_username, self._config.jira_api_token),
            )
        except jira_lib.exceptions.JIRAError as exc:
            self._raise_from_jira_error(exc, ticket_id=None)
        except requests.exceptions.ConnectionError as exc:
            raise JiraConnectionError(
                f"Unable to connect to Jira at {self._config.jira_base_url}: {exc}"
            ) from exc

        return self._client  # type: ignore[return-value]

    @staticmethod
    def _raise_from_jira_error(
        exc: jira_lib.exceptions.JIRAError,
        ticket_id: str | None,
    ) -> None:
        """Map a ``jira.JIRAError`` to the appropriate :class:`AutomationError`.

        This method always raises; the return type is ``None`` only to satisfy
        type checkers when used in a ``raise``-less context.
        """
        status = getattr(exc, "status_code", None)

        if status in (401, 403):
            raise JiraAuthError(
                f"Jira authentication failed (HTTP {status}): "
                "check JIRA_USERNAME and JIRA_API_TOKEN"
            ) from exc

        if status == 404:
            if ticket_id:
                raise JiraTicketNotFoundError(
                    f"Jira ticket not found: {ticket_id}"
                ) from exc
            raise JiraTicketNotFoundError(
                f"Jira resource not found (HTTP 404)"
            ) from exc

        # Anything else is treated as a connection / server error.
        raise JiraConnectionError(
            f"Jira request failed (HTTP {status}): {exc}"
        ) from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_ticket(self, ticket_id: str) -> jira_lib.Issue:
        """Fetch a Jira issue by its ticket ID.

        Parameters
        ----------
        ticket_id:
            The Jira issue key, e.g. ``"PROJ-123"``.

        Returns
        -------
        jira.Issue
            The raw Jira issue object returned by the ``jira`` library.

        Raises
        ------
        JiraAuthError
            If the server returns 401 or 403.
        JiraTicketNotFoundError
            If the server returns 404.  The error message contains
            ``ticket_id``.
        JiraConnectionError
            If the server is unreachable or returns an unexpected status.
            The error message contains the base URL.
        """
        log.info(
            "Fetching Jira ticket",
            extra={"ticket_id": ticket_id, "base_url": self._config.jira_base_url},
        )

        client = self._get_client()

        try:
            issue = client.issue(ticket_id)
        except jira_lib.exceptions.JIRAError as exc:
            self._raise_from_jira_error(exc, ticket_id=ticket_id)
        except requests.exceptions.ConnectionError as exc:
            raise JiraConnectionError(
                f"Unable to connect to Jira at {self._config.jira_base_url}: {exc}"
            ) from exc

        log.info(
            "Jira ticket fetched successfully",
            extra={"ticket_id": ticket_id},
        )

        return issue  # type: ignore[return-value]

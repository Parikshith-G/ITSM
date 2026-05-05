"""Custom exception hierarchy for Jira Repo Automation.

All exceptions inherit from AutomationError so callers can catch the entire
hierarchy with a single except clause when needed.
"""


class AutomationError(Exception):
    """Base exception for all Jira Repo Automation errors."""


# ---------------------------------------------------------------------------
# Configuration errors
# ---------------------------------------------------------------------------


class ConfigError(AutomationError):
    """Raised when required configuration or credentials are missing or invalid.

    The error message must contain the name of the missing/invalid credential
    so the user knows exactly what to fix.
    """


# ---------------------------------------------------------------------------
# Jira API errors
# ---------------------------------------------------------------------------


class JiraAuthError(AutomationError):
    """Raised when the Jira REST API returns a 401 or 403 response.

    The error message must identify the credential type that failed and the
    HTTP status code returned.
    """


class JiraTicketNotFoundError(AutomationError):
    """Raised when the Jira REST API returns a 404 for the requested ticket.

    The error message must contain the ticket ID that was not found.
    """


class JiraConnectionError(AutomationError):
    """Raised when the Jira REST API is unreachable due to a network failure
    or an unexpected non-2xx HTTP status.

    The error message must contain the attempted endpoint URL and the HTTP
    status code or underlying network error detail.
    """


# ---------------------------------------------------------------------------
# Ticket parsing errors
# ---------------------------------------------------------------------------


class TicketParseError(AutomationError):
    """Raised when a required Jira custom field is absent or does not match
    the expected format.

    The error message must contain both the field name and the ticket ID.
    """


# ---------------------------------------------------------------------------
# Git / repository errors
# ---------------------------------------------------------------------------


class RepoError(AutomationError):
    """Raised when a git clone, fetch, or push operation fails.

    The error message must contain the repository URL and the git error output.
    """


class BranchNotFoundError(RepoError):
    """Raised when the target branch does not exist on the remote.

    The error message must identify the branch name and the repository URL.
    """


class PushConflictError(RepoError):
    """Raised when a push is rejected due to a non-fast-forward conflict.

    The tool never force-pushes automatically; the user must resolve the
    conflict manually.  The error message must identify the branch name and
    the repository URL.
    """


# ---------------------------------------------------------------------------
# Spec generation errors
# ---------------------------------------------------------------------------


class SpecGenerationError(AutomationError):
    """Raised when the SpecGenerator fails to write a spec file to disk (e.g.
    due to a permission error or a full filesystem).

    The error message must contain the target file path that could not be
    written.
    """


# ---------------------------------------------------------------------------
# Change-set errors
# ---------------------------------------------------------------------------


class EmptyChangeSetError(AutomationError):
    """Raised when the change set is empty after Kiro task execution, meaning
    no files were modified, created, or deleted.

    The tool must not create an empty git commit; instead it raises this
    exception and exits non-zero.
    """

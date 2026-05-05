"""CLI entry point for Jira Repo Automation.

Usage::

    jira-repo-automation TICKET_ID [options]

    # or

    python -m jira_repo_automation.main TICKET_ID [options]

Options
-------
TICKET_ID
    The Jira issue key to process (e.g. ``PROJ-123``).

--dry-run
    Perform all steps up to spec generation without writing files or
    creating git commits.  Prints a spec summary to stdout.

--config PATH
    Path to a ``.env``-format config file.  Environment variables take
    precedence over values in this file.

--log-format {text,json}
    Log output format.  Defaults to ``text``.

--verbose
    Enable DEBUG-level logging.
"""

from __future__ import annotations

import argparse
import sys

from jira_repo_automation.config import ConfigLoader
from jira_repo_automation.exceptions import AutomationError
from jira_repo_automation.logging_setup import setup_logging
from jira_repo_automation.orchestrator import Orchestrator


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jira-repo-automation",
        description=(
            "Fetch a Jira ticket, clone the target repository, generate a "
            "Kiro spec, and wire a post-task hook to commit and push the "
            "feature branch once Kiro finishes executing the spec tasks."
        ),
    )
    parser.add_argument(
        "ticket_id",
        metavar="TICKET_ID",
        help="Jira issue key to process (e.g. PROJ-123)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help=(
            "Preview what would happen without writing files or creating "
            "git commits"
        ),
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        default=None,
        help="Path to a .env-format config file",
    )
    parser.add_argument(
        "--log-format",
        choices=["text", "json"],
        default="text",
        help="Log output format (default: text)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable DEBUG-level logging",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Parameters
    ----------
    argv:
        Argument list (defaults to ``sys.argv[1:]``).

    Returns
    -------
    int
        Exit code: 0 on success, non-zero on failure.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Configure logging before anything else.
    setup_logging(log_format=args.log_format, verbose=args.verbose)

    # Load configuration.
    try:
        loader = ConfigLoader()
        config = loader.load(config_file=args.config)
    except AutomationError as exc:
        # ConfigError before logging is fully wired — print to stderr.
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    # Apply CLI overrides.
    config.dry_run = args.dry_run or config.dry_run
    config.log_format = args.log_format
    config.verbose = args.verbose or config.verbose

    # Run the pipeline.
    orchestrator = Orchestrator(config)
    orchestrator.run(args.ticket_id)

    # orchestrator.run calls sys.exit(1) on AutomationError, so reaching
    # here means success.
    return 0


if __name__ == "__main__":
    sys.exit(main())

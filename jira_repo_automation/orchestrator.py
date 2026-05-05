"""Pipeline orchestrator for Jira Repo Automation.

Drives the full automation pipeline:

    ConfigLoader → JiraClient → TicketParser → RepoManager.prepare
    → SpecGenerator.generate

In dry-run mode the pipeline short-circuits after ``SpecGenerator.generate``
and prints a spec summary to stdout without writing any files or creating
any git commits.

All :class:`~jira_repo_automation.exceptions.AutomationError` subclasses are
caught, logged at ERROR level (with operation name, error message, and ticket
ID), and cause a non-zero exit.  Unexpected exceptions propagate so that the
caller sees a full stack trace.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from jira_repo_automation.config import Config
from jira_repo_automation.exceptions import AutomationError
from jira_repo_automation.jira_client import JiraClient
from jira_repo_automation.repo_manager import RepoManager
from jira_repo_automation.spec_generator import SpecGenerator
from jira_repo_automation.ticket_parser import TicketParser

log = logging.getLogger("jira_repo_automation.orchestrator")


class Orchestrator:
    """Drives the full Jira → Git → Kiro spec pipeline.

    Parameters
    ----------
    config:
        A fully-populated :class:`~jira_repo_automation.config.Config`
        instance.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._jira_client = JiraClient(config)
        self._ticket_parser = TicketParser()
        self._repo_manager = RepoManager(config)
        self._spec_generator = SpecGenerator(config)

    def run(self, ticket_id: str) -> None:
        """Execute the full pipeline for the given ticket ID.

        Parameters
        ----------
        ticket_id:
            The Jira issue key, e.g. ``"PROJ-123"``.

        Raises
        ------
        SystemExit
            With exit code 1 if any :class:`AutomationError` is raised.
            Unexpected exceptions propagate normally.
        """
        log.info("Starting pipeline", extra={"ticket_id": ticket_id})

        try:
            self._run_pipeline(ticket_id)
        except AutomationError as exc:
            # Determine the operation name from the exception type.
            operation = type(exc).__name__.replace("Error", "").replace("Jira", "Jira ")
            log.error(
                "Pipeline failed",
                extra={
                    "operation": operation,
                    "error": str(exc),
                    "ticket_id": ticket_id,
                },
            )
            sys.exit(1)

    def _run_pipeline(self, ticket_id: str) -> None:
        """Internal pipeline execution (no error handling)."""
        dry_run = self._config.dry_run

        # --- Step 1: Fetch Jira ticket ---
        log.info("Fetching Jira ticket", extra={"ticket_id": ticket_id})
        issue = self._jira_client.get_ticket(ticket_id)

        # --- Step 2: Parse ticket ---
        log.info("Parsing ticket", extra={"ticket_id": ticket_id})
        parsed_ticket = self._ticket_parser.parse(issue)

        # --- Step 3: Prepare repository ---
        log.info(
            "Preparing repository",
            extra={
                "ticket_id": ticket_id,
                "repo_url": parsed_ticket.repo_url,
                "branch": parsed_ticket.branch,
            },
        )
        working_dir = self._repo_manager.prepare(
            repo_url=parsed_ticket.repo_url,
            branch=parsed_ticket.branch,
            ticket_id=ticket_id,
        )

        # Copy .env into the working directory so the hook can find it
        import shutil
        env_file = Path(".env")
        if env_file.exists():
            shutil.copy(env_file, working_dir / ".env")
            log.debug("Copied .env to working directory", extra={"path": str(working_dir / ".env")})

        # --- Step 4: Generate Kiro spec ---
        log.info("Generating Kiro spec", extra={"ticket_id": ticket_id})
        kiro_spec = self._spec_generator.generate(
            working_dir=working_dir,
            parsed_ticket=parsed_ticket,
            dry_run=dry_run,
        )

        if dry_run:
            # Print spec summary and exit cleanly.
            print(f"\n=== Dry-run spec summary for {ticket_id} ===")
            print(f"  Spec directory : {kiro_spec.spec_dir}")
            print(f"  Requirements   : {kiro_spec.requirements_path}")
            print(f"  Design         : {kiro_spec.design_path}")
            print(f"  Tasks          : {kiro_spec.tasks_path}")
            print(f"  Config         : {kiro_spec.config_path}")
            print(f"\n  Summary        : {parsed_ticket.summary}")
            print(f"  Repository     : {parsed_ticket.repo_url}")
            print(f"  Branch         : {parsed_ticket.branch}")
            print("\n(No files written — dry-run mode)")
            log.info("Dry-run complete", extra={"ticket_id": ticket_id})
            return

        log.info(
            "Spec written — awaiting Kiro task execution",
            extra={
                "ticket_id": ticket_id,
                "spec_dir": str(kiro_spec.spec_dir),
            },
        )

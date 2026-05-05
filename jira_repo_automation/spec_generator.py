"""Kiro spec file generator for Jira Repo Automation.

Generates a ``.kiro/specs/<ticket_id>/`` directory inside the cloned
repository, containing:

* ``.config.kiro``   — spec metadata (specId, workflowType, specType)
* ``requirements.md``— EARS-style requirements derived from the ticket
* ``design.md``      — minimal design stub with ticket context
* ``tasks.md``       — numbered task list, one task per acceptance criterion

Also writes the post-task hook JSON to
``<working_dir>/.kiro/hooks/commit-and-push.json``.

In ``dry_run=True`` mode the generator returns a :class:`KiroSpec` without
writing any files to disk.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from jira_repo_automation.config import Config
from jira_repo_automation.exceptions import SpecGenerationError
from jira_repo_automation.ticket_parser import ParsedTicket

log = logging.getLogger("jira_repo_automation.spec_generator")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class KiroSpec:
    """Paths to the generated Kiro spec files.

    Attributes
    ----------
    spec_dir:
        Absolute path to ``.kiro/specs/<ticket_id>/`` inside the working dir.
    requirements_path:
        Path to ``requirements.md``.
    design_path:
        Path to ``design.md``.
    tasks_path:
        Path to ``tasks.md``.
    config_path:
        Path to ``.config.kiro``.
    """

    spec_dir: Path
    requirements_path: Path
    design_path: Path
    tasks_path: Path
    config_path: Path


# ---------------------------------------------------------------------------
# SpecGenerator
# ---------------------------------------------------------------------------


class SpecGenerator:
    """Generates Kiro spec files from a :class:`~jira_repo_automation.ticket_parser.ParsedTicket`.

    Parameters
    ----------
    config:
        A fully-populated :class:`~jira_repo_automation.config.Config`
        instance (currently unused but kept for API consistency and future
        extension).
    """

    def __init__(self, config: Config) -> None:
        self._config = config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        working_dir: Path,
        parsed_ticket: ParsedTicket,
        dry_run: bool = False,
    ) -> KiroSpec:
        """Generate Kiro spec files from ticket content.

        Parameters
        ----------
        working_dir:
            The local working directory (returned by
            :meth:`~jira_repo_automation.repo_manager.RepoManager.prepare`).
        parsed_ticket:
            The structured ticket data.
        dry_run:
            When ``True``, return a :class:`KiroSpec` without writing any
            files to disk.

        Returns
        -------
        KiroSpec
            Paths to the (potentially unwritten) spec files.

        Raises
        ------
        SpecGenerationError
            If any file cannot be written.  The error message contains the
            target file path.
        """
        ticket_id = parsed_ticket.ticket_id

        log.info(
            "Generating Kiro spec",
            extra={"ticket_id": ticket_id, "working_dir": str(working_dir), "dry_run": dry_run},
        )

        spec_dir = working_dir / ".kiro" / "specs" / ticket_id
        config_path = spec_dir / ".config.kiro"
        requirements_path = spec_dir / "requirements.md"
        design_path = spec_dir / "design.md"
        tasks_path = spec_dir / "tasks.md"

        kiro_spec = KiroSpec(
            spec_dir=spec_dir,
            requirements_path=requirements_path,
            design_path=design_path,
            tasks_path=tasks_path,
            config_path=config_path,
        )

        if dry_run:
            log.info(
                "Dry-run mode: skipping file writes",
                extra={"ticket_id": ticket_id},
            )
            return kiro_spec

        # --- Create spec directory ---
        self._safe_mkdir(spec_dir)

        # --- Write .config.kiro ---
        config_content = json.dumps(
            {
                "specId": str(uuid.uuid4()),
                "workflowType": "requirements-first",
                "specType": "feature",
            },
            indent=2,
        )
        self._safe_write(config_path, config_content)

        # --- Write requirements.md ---
        requirements_content = self._render_requirements(parsed_ticket)
        self._safe_write(requirements_path, requirements_content)

        # --- Write design.md ---
        design_content = self._render_design(parsed_ticket, working_dir)
        self._safe_write(design_path, design_content)

        # --- Write tasks.md ---
        tasks_content = self._render_tasks(parsed_ticket)
        self._safe_write(tasks_path, tasks_content)

        # --- Write post-task hook ---
        hooks_dir = working_dir / ".kiro" / "hooks"
        self._safe_mkdir(hooks_dir)
        hook_path = hooks_dir / "commit-and-push.json"
        hook_content = self._render_hook(ticket_id)
        self._safe_write(hook_path, hook_content)

        log.info(
            "Kiro spec generated",
            extra={"spec_dir": str(spec_dir), "ticket_id": ticket_id},
        )

        return kiro_spec

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _render_requirements(ticket: ParsedTicket) -> str:
        """Render ``requirements.md`` from ticket content."""
        lines: list[str] = [
            "# Requirements Document",
            "",
            "## Introduction",
            "",
            ticket.description or ticket.summary,
            "",
            "---",
            "",
            "## Requirements",
            "",
            f"### Requirement 1: {ticket.summary}",
            "",
            "**User Story:** As a developer, I want to implement the changes described "
            f"in Jira ticket {ticket.ticket_id}, so that the required functionality is delivered.",
            "",
            "#### Acceptance Criteria",
            "",
        ]

        # Extract EARS-style criteria from the description if present.
        criteria = SpecGenerator._extract_criteria(ticket.description)
        if criteria:
            for i, criterion in enumerate(criteria, start=1):
                lines.append(f"{i}. {criterion}")
        else:
            # Fall back to the full description as a single criterion.
            lines.append(f"1. {ticket.description or ticket.summary}")

        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _render_design(ticket: ParsedTicket, working_dir: Path) -> str:
        """Render ``design.md`` from ticket content."""
        return "\n".join([
            f"# Design: {ticket.ticket_id} — {ticket.summary}",
            "",
            "## Overview",
            "",
            f"Apply changes described in Jira ticket {ticket.ticket_id} to the "
            f"repository at `{working_dir}`.",
            "",
            "## Context",
            "",
            f"- **Ticket ID**: {ticket.ticket_id}",
            f"- **Repository**: {ticket.repo_url}",
            f"- **Branch**: {ticket.branch}",
            f"- **Summary**: {ticket.summary}",
            "",
            "## Change Description",
            "",
            ticket.description or ticket.summary,
            "",
        ])

    @staticmethod
    def _render_tasks(ticket: ParsedTicket) -> str:
        """Render ``tasks.md`` from ticket content."""
        lines: list[str] = [
            "# Tasks",
            "",
        ]

        criteria = SpecGenerator._extract_criteria(ticket.description)
        if criteria:
            for i, criterion in enumerate(criteria, start=1):
                # Convert criterion to an imperative action.
                action = SpecGenerator._criterion_to_action(criterion)
                lines.append(f"- [ ] {i}. {action}")
        else:
            # Single task derived from the summary.
            lines.append(f"- [ ] 1. Implement: {ticket.summary}")

        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _render_hook(ticket_id: str) -> str:
        """Render the post-task hook JSON."""
        hook = {
            "id": "jira-commit-and-push",
            "name": "Commit and Push Feature Branch",
            "description": (
                "After Kiro task execution completes, stage all changes, "
                "commit with the ticket ID and summary, and push the feature "
                "branch to the remote."
            ),
            "version": "1.0.0",
            "when": {
                "type": "postTaskExecution",
            },
            "then": {
                "type": "runCommand",
                "command": (
                    f"python -m jira_repo_automation.hooks.commit_and_push "
                    f"--spec-dir .kiro/specs/{ticket_id} --working-dir ."
                ),
            },
            "timeout": 120,
        }
        return json.dumps(hook, indent=2)

    # ------------------------------------------------------------------
    # Criteria extraction
    # ------------------------------------------------------------------

    # Patterns that indicate EARS-style acceptance criteria lines.
    _EARS_PATTERN = re.compile(
        r"^\s*(WHEN|THEN|IF|SHALL|THE\s+\w+\s+SHALL|WHERE)\b",
        re.IGNORECASE,
    )
    # Numbered or bulleted list items.
    _LIST_ITEM_PATTERN = re.compile(r"^\s*(\d+[\.\)]\s+|\*\s+|-\s+)")

    @classmethod
    def _extract_criteria(cls, description: str) -> list[str]:
        """Extract acceptance criteria from a ticket description.

        Tries three strategies in order:

        1. EARS-style lines (``WHEN``/``THEN``/``IF``/``SHALL``).
        2. Numbered or bulleted list items.
        3. Non-empty lines (each line becomes a criterion).

        Returns an empty list if the description is empty.
        """
        if not description or not description.strip():
            return []

        lines = description.splitlines()

        # Strategy 1: EARS-style lines.
        ears_lines = [
            line.strip()
            for line in lines
            if cls._EARS_PATTERN.match(line) and line.strip()
        ]
        if ears_lines:
            return ears_lines

        # Strategy 2: List items.
        list_items = []
        for line in lines:
            m = cls._LIST_ITEM_PATTERN.match(line)
            if m:
                list_items.append(line[m.end():].strip())
        if list_items:
            return list_items

        # Strategy 3: Non-empty lines.
        non_empty = [line.strip() for line in lines if line.strip()]
        return non_empty if non_empty else []

    @staticmethod
    def _criterion_to_action(criterion: str) -> str:
        """Convert an acceptance criterion sentence to an imperative task action.

        Strips leading EARS keywords and reformats as an imperative sentence.
        """
        # Remove leading EARS keywords.
        cleaned = re.sub(
            r"^(WHEN|THEN|IF|WHERE|THE\s+\w+\s+SHALL)\s+",
            "",
            criterion,
            flags=re.IGNORECASE,
        ).strip()
        # Capitalise first letter.
        if cleaned:
            cleaned = cleaned[0].upper() + cleaned[1:]
        return cleaned or criterion

    # ------------------------------------------------------------------
    # Filesystem helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_mkdir(path: Path) -> None:
        """Create a directory, raising :class:`SpecGenerationError` on failure."""
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise SpecGenerationError(
                f"Failed to create directory {path}: {exc}"
            ) from exc

    @staticmethod
    def _safe_write(path: Path, content: str) -> None:
        """Write ``content`` to ``path``, raising :class:`SpecGenerationError` on failure."""
        try:
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            raise SpecGenerationError(
                f"Failed to write spec file {path}: {exc}"
            ) from exc

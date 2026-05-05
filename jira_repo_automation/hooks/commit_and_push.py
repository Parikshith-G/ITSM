"""Post-task hook: commit and push the feature branch.

This script is invoked by the Kiro ``postTaskExecution`` hook after the
task execution engine has finished applying code changes.  It:

1. Reads the ticket ID and summary from the spec's ``requirements.md``
   front-matter (written by :class:`~jira_repo_automation.spec_generator.SpecGenerator`).
2. Uses ``git diff --name-status HEAD`` (via GitPython) to detect all files
   modified, created, or deleted by Kiro's task execution.
3. Builds a :class:`~jira_repo_automation.repo_manager.ChangeSet` from the
   diff output.
4. Calls :meth:`~jira_repo_automation.repo_manager.RepoManager.commit_and_push`.
5. Exits non-zero on :class:`~jira_repo_automation.exceptions.EmptyChangeSetError`
   or :class:`~jira_repo_automation.exceptions.PushConflictError`.

Usage::

    python -m jira_repo_automation.hooks.commit_and_push \\
        --spec-dir .kiro/specs/PROJ-123 \\
        --working-dir /path/to/repo
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

import git
import git.exc

from jira_repo_automation.config import Config, ConfigLoader
from jira_repo_automation.exceptions import (
    AutomationError,
    EmptyChangeSetError,
    PushConflictError,
)
from jira_repo_automation.logging_setup import setup_logging
from jira_repo_automation.repo_manager import ChangeSet, RepoManager

log = logging.getLogger("jira_repo_automation.hooks.commit_and_push")


# ---------------------------------------------------------------------------
# Front-matter parsing
# ---------------------------------------------------------------------------

# Matches lines like:  ticket_id: PROJ-123
_FRONTMATTER_PATTERN = re.compile(r"^(\w+):\s*(.+)$", re.MULTILINE)


def _read_frontmatter(requirements_path: Path) -> dict[str, str]:
    """Parse simple ``key: value`` front-matter from ``requirements.md``.

    The front-matter is expected to be at the top of the file, before the
    first blank line or Markdown heading.  Lines that do not match
    ``key: value`` are ignored.
    """
    metadata: dict[str, str] = {}
    if not requirements_path.exists():
        return metadata

    content = requirements_path.read_text(encoding="utf-8")

    # Only scan the first 20 lines for front-matter.
    for line in content.splitlines()[:20]:
        m = _FRONTMATTER_PATTERN.match(line)
        if m:
            metadata[m.group(1).lower()] = m.group(2).strip()

    return metadata


def _extract_ticket_info(spec_dir: Path) -> tuple[str, str]:
    """Extract ticket ID and summary from the spec directory.

    Reads ``requirements.md`` front-matter first; falls back to deriving
    the ticket ID from the spec directory name.

    Returns
    -------
    tuple[str, str]
        ``(ticket_id, summary)``
    """
    requirements_path = spec_dir / "requirements.md"
    metadata = _read_frontmatter(requirements_path)

    ticket_id = metadata.get("ticket_id") or spec_dir.name
    summary = metadata.get("summary") or ""

    # If summary is still empty, try to extract it from the requirements.md
    # heading (e.g. "### Requirement 1: <summary>").
    if not summary and requirements_path.exists():
        content = requirements_path.read_text(encoding="utf-8")
        m = re.search(r"^###\s+Requirement\s+\d+:\s+(.+)$", content, re.MULTILINE)
        if m:
            summary = m.group(1).strip()

    return ticket_id, summary


# ---------------------------------------------------------------------------
# Change set detection
# ---------------------------------------------------------------------------

def _build_change_set(repo: git.Repo) -> ChangeSet:
    """Build a :class:`ChangeSet` from ``git diff --name-status HEAD``.

    Detects all staged and unstaged changes relative to HEAD.
    """
    change_set = ChangeSet()

    # Staged changes (index vs HEAD).
    try:
        diff_staged = repo.index.diff("HEAD")
    except git.exc.BadName:
        # No commits yet — treat all indexed files as created.
        diff_staged = []

    for diff_item in diff_staged:
        change_type = diff_item.change_type
        path = diff_item.b_path or diff_item.a_path
        if change_type == "A":
            change_set.created.append(path)
        elif change_type == "D":
            change_set.deleted.append(path)
        else:
            change_set.modified.append(path)

    # Unstaged changes (working tree vs index).
    diff_unstaged = repo.index.diff(None)
    for diff_item in diff_unstaged:
        change_type = diff_item.change_type
        path = diff_item.b_path or diff_item.a_path
        if path not in change_set.all_paths:
            if change_type == "A":
                change_set.created.append(path)
            elif change_type == "D":
                change_set.deleted.append(path)
            else:
                change_set.modified.append(path)

    # Untracked files (new files not yet staged).
    for untracked in repo.untracked_files:
        if untracked not in change_set.all_paths:
            change_set.created.append(untracked)

    return change_set


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Commit and push the feature branch after Kiro task execution."
    )
    parser.add_argument(
        "--spec-dir",
        required=True,
        help="Path to the Kiro spec directory (e.g. .kiro/specs/PROJ-123)",
    )
    parser.add_argument(
        "--working-dir",
        required=True,
        help="Path to the local git working directory",
    )
    parser.add_argument(
        "--log-format",
        default="text",
        choices=["text", "json"],
        help="Log output format (default: text)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG-level logging",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point for the commit-and-push hook.

    Returns
    -------
    int
        Exit code: 0 on success, non-zero on failure.
    """
    args = _parse_args(argv)
    setup_logging(log_format=args.log_format, verbose=args.verbose)

    spec_dir = Path(args.spec_dir)
    working_dir = Path(args.working_dir).resolve()

    # Resolve spec_dir relative to working_dir if it is not absolute.
    if not spec_dir.is_absolute():
        spec_dir = working_dir / spec_dir

    log.info(
        "Starting commit-and-push hook",
        extra={"spec_dir": str(spec_dir), "working_dir": str(working_dir)},
    )

    # --- Extract ticket info ---
    ticket_id, summary = _extract_ticket_info(spec_dir)
    log.info(
        "Ticket info extracted",
        extra={"ticket_id": ticket_id, "summary": summary},
    )

    # --- Open the git repo ---
    try:
        repo = git.Repo(working_dir)
    except git.exc.InvalidGitRepositoryError:
        log.error(
            "Not a valid git repository",
            extra={"working_dir": str(working_dir)},
        )
        return 1

    # --- Build change set ---
    change_set = _build_change_set(repo)
    log.info(
        "Change set detected",
        extra={"files": len(change_set.all_paths)},
    )
    log.debug("Change set details:\n%s", change_set.summary())

    # --- Load config and commit/push ---
    try:
        # Try to load from .env in current directory first, then fall back to env vars
        config_file = None
        if Path(".env").exists():
            config_file = ".env"
        config = ConfigLoader().load(config_file=config_file)
    except AutomationError as exc:
        log.error("Configuration error: %s", exc)
        return 1

    repo_manager = RepoManager(config)

    try:
        repo_manager.commit_and_push(
            working_dir=working_dir,
            change_set=change_set,
            ticket_id=ticket_id,
            summary=summary,
        )
    except EmptyChangeSetError as exc:
        log.error(
            "Empty change set — nothing to commit",
            extra={"ticket_id": ticket_id, "error": str(exc)},
        )
        return 1
    except PushConflictError as exc:
        log.error(
            "Push conflict — resolve manually and re-run",
            extra={"ticket_id": ticket_id, "error": str(exc)},
        )
        return 1
    except AutomationError as exc:
        log.error(
            "Commit/push failed",
            extra={"ticket_id": ticket_id, "error": str(exc)},
        )
        return 1

    log.info(
        "Commit and push completed successfully",
        extra={"ticket_id": ticket_id},
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

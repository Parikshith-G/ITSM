"""Git repository management for Jira Repo Automation.

Handles cloning, fetching, branch checkout, feature branch creation,
staging, committing, and pushing using GitPython.

Error mapping
-------------
* Clone / fetch failure  → :class:`~jira_repo_automation.exceptions.RepoError`
* Branch absent on remote→ :class:`~jira_repo_automation.exceptions.BranchNotFoundError`
* Non-fast-forward push  → :class:`~jira_repo_automation.exceptions.PushConflictError`
* Empty change set       → :class:`~jira_repo_automation.exceptions.EmptyChangeSetError`
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence
from urllib.parse import urlparse, urlunparse

import git
import git.exc

from jira_repo_automation.config import Config
from jira_repo_automation.exceptions import (
    BranchNotFoundError,
    EmptyChangeSetError,
    PushConflictError,
    RepoError,
)

log = logging.getLogger("jira_repo_automation.repo_manager")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ChangeSet:
    """Represents the set of files modified, created, or deleted by Kiro.

    Attributes
    ----------
    modified:
        Paths of files that were modified.
    created:
        Paths of files that were newly created.
    deleted:
        Paths of files that were deleted.
    """

    modified: list[str] = field(default_factory=list)
    created: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)

    @property
    def all_paths(self) -> list[str]:
        """Return all affected paths in a single flat list."""
        return self.modified + self.created + self.deleted

    @property
    def is_empty(self) -> bool:
        """Return ``True`` if no files were changed."""
        return not self.all_paths

    def summary(self) -> str:
        """Return a human-readable summary of the change set."""
        lines: list[str] = []
        for path in self.modified:
            lines.append(f"  modified:  {path}")
        for path in self.created:
            lines.append(f"  created:   {path}")
        for path in self.deleted:
            lines.append(f"  deleted:   {path}")
        if not lines:
            return "  (no changes)"
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# RepoManager
# ---------------------------------------------------------------------------


class RepoManager:
    """Manages all Git operations for the automation pipeline.

    Parameters
    ----------
    config:
        A fully-populated :class:`~jira_repo_automation.config.Config`
        instance.
    """

    def __init__(self, config: Config) -> None:
        self._config = config

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _working_dir(self, ticket_id: str) -> Path:
        """Return the local working directory path for a given ticket."""
        return Path(self._config.working_dir_base) / ticket_id

    def _inject_pat_into_url(self, repo_url: str) -> str:
        """Inject the PAT into an HTTPS remote URL.

        Transforms ``https://gitlab.com/org/repo`` into
        ``https://oauth2:<PAT>@gitlab.com/org/repo``.
        """
        pat = self._config.git_pat
        if not pat:
            return repo_url
        parsed = urlparse(repo_url)
        if parsed.scheme not in ("http", "https"):
            return repo_url
        authed = parsed._replace(netloc=f"oauth2:{pat}@{parsed.hostname}{':' + str(parsed.port) if parsed.port else ''}{parsed.path.split('/')[0]}")
        # Simpler approach: rebuild netloc manually.
        host = parsed.hostname or ""
        port_part = f":{parsed.port}" if parsed.port else ""
        new_netloc = f"oauth2:{pat}@{host}{port_part}"
        authed = parsed._replace(netloc=new_netloc)
        return urlunparse(authed)

    def _git_env(self) -> dict[str, str]:
        """Return extra environment variables for Git operations.

        If ``git_ssh_key_path`` is configured, sets ``GIT_SSH_COMMAND`` to
        use that key.
        """
        env: dict[str, str] = {}
        if self._config.git_ssh_key_path:
            env["GIT_SSH_COMMAND"] = (
                f"ssh -i {self._config.git_ssh_key_path} "
                "-o StrictHostKeyChecking=no"
            )
        return env

    def _effective_url(self, repo_url: str) -> str:
        """Return the repo URL with credentials injected if applicable."""
        if self._config.git_pat:
            return self._inject_pat_into_url(repo_url)
        return repo_url

    # ------------------------------------------------------------------
    # Public API — prepare
    # ------------------------------------------------------------------

    def prepare(self, repo_url: str, branch: str, ticket_id: str) -> Path:
        """Clone or fetch the repository, check out the target branch, and
        create a feature branch named after ``ticket_id``.

        Parameters
        ----------
        repo_url:
            The remote repository URL.
        branch:
            The target branch to check out.
        ticket_id:
            The Jira ticket ID; used as the feature branch name and the
            local working directory name.

        Returns
        -------
        Path
            The absolute path to the local working directory.

        Raises
        ------
        RepoError
            If the clone or fetch operation fails.
        BranchNotFoundError
            If ``branch`` does not exist on the remote.
        """
        working_dir = self._working_dir(ticket_id)
        effective_url = self._effective_url(repo_url)
        git_env = self._git_env()

        log.info(
            "Preparing repository",
            extra={"repo_url": repo_url, "branch": branch, "ticket_id": ticket_id},
        )

        repo = self._clone_or_fetch(working_dir, effective_url, repo_url, git_env)
        self._checkout_branch(repo, branch, repo_url, git_env)
        self._create_feature_branch(repo, ticket_id)

        log.info(
            "Repository prepared",
            extra={
                "working_dir": str(working_dir),
                "branch": branch,
                "feature_branch": ticket_id,
            },
        )

        return working_dir

    def _clone_or_fetch(
        self,
        working_dir: Path,
        effective_url: str,
        repo_url: str,
        git_env: dict[str, str],
    ) -> git.Repo:
        """Clone the repo if it doesn't exist locally; otherwise fetch."""
        if working_dir.exists():
            log.debug("Local copy found, fetching latest", extra={"path": str(working_dir)})
            try:
                repo = git.Repo(working_dir)
                with repo.git.custom_environment(**git_env):
                    repo.remotes.origin.fetch()
            except git.exc.GitCommandError as exc:
                raise RepoError(
                    f"Failed to fetch repository {repo_url}: {exc}"
                ) from exc
        else:
            log.debug("No local copy found, cloning", extra={"repo_url": repo_url})
            working_dir.parent.mkdir(parents=True, exist_ok=True)
            try:
                env = {**os.environ, **git_env}
                repo = git.Repo.clone_from(
                    effective_url,
                    str(working_dir),
                    env=env,
                )
            except git.exc.GitCommandError as exc:
                raise RepoError(
                    f"Failed to clone repository {repo_url}: {exc}"
                ) from exc

        return repo

    def _checkout_branch(
        self,
        repo: git.Repo,
        branch: str,
        repo_url: str,
        git_env: dict[str, str],
    ) -> None:
        """Check out ``branch`` from the remote, raising BranchNotFoundError if absent."""
        log.debug("Checking out branch", extra={"branch": branch})

        # Check if the branch exists on the remote.
        remote = repo.remotes.origin
        remote_refs = [ref.name for ref in remote.refs]
        remote_branch_ref = f"origin/{branch}"

        if remote_branch_ref not in remote_refs:
            raise BranchNotFoundError(
                f"Branch '{branch}' not found on remote {repo_url}"
            )

        try:
            # Check out the branch, tracking the remote.
            if branch in [b.name for b in repo.branches]:
                repo.git.checkout(branch)
            else:
                repo.git.checkout("-b", branch, f"origin/{branch}")
        except git.exc.GitCommandError as exc:
            raise RepoError(
                f"Failed to checkout branch '{branch}' in {repo_url}: {exc}"
            ) from exc

    def _create_feature_branch(self, repo: git.Repo, ticket_id: str) -> None:
        """Create a new feature branch named ``ticket_id``."""
        log.debug("Creating feature branch", extra={"feature_branch": ticket_id})

        # If the feature branch already exists, just check it out.
        existing_branches = [b.name for b in repo.branches]
        if ticket_id in existing_branches:
            log.debug(
                "Feature branch already exists, checking out",
                extra={"feature_branch": ticket_id},
            )
            repo.git.checkout(ticket_id)
        else:
            repo.git.checkout("-b", ticket_id)

    # ------------------------------------------------------------------
    # Public API — commit_and_push
    # ------------------------------------------------------------------

    def commit_and_push(
        self,
        working_dir: Path,
        change_set: ChangeSet,
        ticket_id: str,
        summary: str,
    ) -> None:
        """Stage all files in ``change_set``, commit, and push the feature branch.

        Parameters
        ----------
        working_dir:
            The local working directory (returned by :meth:`prepare`).
        change_set:
            The set of files to stage and commit.
        ticket_id:
            The Jira ticket ID; used in the commit message and as the
            feature branch name.
        summary:
            The Jira ticket summary; used in the commit message.

        Raises
        ------
        EmptyChangeSetError
            If ``change_set`` is empty.
        PushConflictError
            If the push is rejected due to a non-fast-forward conflict.
        RepoError
            If any other git operation fails.
        """
        if change_set.is_empty:
            raise EmptyChangeSetError(
                f"No changes to commit for ticket {ticket_id}"
            )

        log.info(
            "Committing and pushing changes",
            extra={"ticket_id": ticket_id, "working_dir": str(working_dir)},
        )

        try:
            repo = git.Repo(working_dir)
        except git.exc.InvalidGitRepositoryError as exc:
            raise RepoError(
                f"Not a valid git repository: {working_dir}"
            ) from exc

        # Stage all files in the change set.
        for path in change_set.modified + change_set.created:
            log.debug("Staging file", extra={"path": path})
            repo.index.add([path])

        for path in change_set.deleted:
            log.debug("Removing file from index", extra={"path": path})
            repo.index.remove([path])

        # Create the commit.
        commit_message = f"{ticket_id}: {summary}"
        log.debug("Creating commit", extra={"message": commit_message})
        repo.index.commit(commit_message)

        # Push the feature branch.
        git_env = self._git_env()
        log.debug("Pushing feature branch", extra={"branch": ticket_id})

        try:
            with repo.git.custom_environment(**git_env):
                push_info_list = repo.remotes.origin.push(
                    refspec=f"{ticket_id}:{ticket_id}"
                )
        except git.exc.GitCommandError as exc:
            error_str = str(exc).lower()
            if "non-fast-forward" in error_str or "rejected" in error_str:
                raise PushConflictError(
                    f"Push rejected (non-fast-forward) for branch '{ticket_id}'. "
                    "Resolve the conflict manually and re-run."
                ) from exc
            raise RepoError(f"Push failed for branch '{ticket_id}': {exc}") from exc

        # Check push info flags for rejection.
        for push_info in push_info_list:
            if push_info.flags & git.remote.PushInfo.ERROR:
                if push_info.flags & git.remote.PushInfo.REJECTED:
                    raise PushConflictError(
                        f"Push rejected (non-fast-forward) for branch '{ticket_id}'. "
                        "Resolve the conflict manually and re-run."
                    )
                raise RepoError(
                    f"Push failed for branch '{ticket_id}': {push_info.summary}"
                )

        log.info(
            "Changes committed and pushed",
            extra={"ticket_id": ticket_id, "branch": ticket_id},
        )

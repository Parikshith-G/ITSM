"""Configuration loading for Jira Repo Automation.

Reads credentials and tool behaviour settings from environment variables
and an optional .env config file. Environment variables always take
precedence over config file values.
"""

import os
from dataclasses import dataclass, field

from dotenv import dotenv_values

from jira_repo_automation.exceptions import ConfigError


@dataclass
class Config:
    # Jira
    jira_base_url: str
    jira_username: str
    jira_api_token: str
    # Git
    git_ssh_key_path: str | None
    git_pat: str | None
    # Tool behaviour
    working_dir_base: str = r"D:\Others\MainProjs\pullnupshpulls"
    log_format: str = "text"   # "text" | "json"
    verbose: bool = False
    dry_run: bool = False


class ConfigLoader:
    """Loads and merges configuration from a config file and environment variables."""

    def load(self, config_file: str | None = None) -> Config:
        """Load and merge config. Raises ConfigError if required credentials are absent.

        Config file values (if provided) are loaded first, then environment
        variables are overlaid on top so that env vars always take precedence.
        """
        # Start with config file values (if any), then overlay env vars.
        file_values: dict[str, str | None] = {}
        if config_file is not None:
            file_values = dotenv_values(config_file)

        def get(key: str) -> str | None:
            """Return the env var value if set, otherwise fall back to the config file."""
            env_val = os.environ.get(key)
            if env_val is not None:
                return env_val
            return file_values.get(key) or None

        # --- Required Jira credentials ---
        jira_base_url = get("JIRA_BASE_URL")
        if not jira_base_url:
            raise ConfigError("Missing required credential: JIRA_BASE_URL")

        jira_username = get("JIRA_USERNAME")
        if not jira_username:
            raise ConfigError("Missing required credential: JIRA_USERNAME")

        jira_api_token = get("JIRA_API_TOKEN")
        if not jira_api_token:
            raise ConfigError("Missing required credential: JIRA_API_TOKEN")

        # --- Git credentials (at least one required) ---
        git_ssh_key_path = get("GIT_SSH_KEY_PATH")
        git_pat = get("GIT_PAT")

        if not git_ssh_key_path and not git_pat:
            raise ConfigError(
                "Missing required credential: at least one of GIT_SSH_KEY_PATH or GIT_PAT must be set"
            )

        # --- Optional behaviour overrides ---
        working_dir_base = get("WORKING_DIR_BASE") or r"D:\Others\MainProjs\pullnupshpulls"
        log_format = get("LOG_FORMAT") or "text"

        verbose_raw = get("VERBOSE") or ""
        verbose = verbose_raw.lower() in ("1", "true", "yes")

        dry_run_raw = get("DRY_RUN") or ""
        dry_run = dry_run_raw.lower() in ("1", "true", "yes")

        return Config(
            jira_base_url=jira_base_url,
            jira_username=jira_username,
            jira_api_token=jira_api_token,
            git_ssh_key_path=git_ssh_key_path,
            git_pat=git_pat,
            working_dir_base=working_dir_base,
            log_format=log_format,
            verbose=verbose,
            dry_run=dry_run,
        )

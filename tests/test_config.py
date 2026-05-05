"""Unit tests for ConfigLoader.

Covers:
1. Successful load from env vars only (all required vars set, no config file)
2. Successful load from config file only (no env vars, config file has all values)
3. Env var overrides config file value for each Jira credential key
4. ConfigError raised when JIRA_BASE_URL is missing
5. ConfigError raised when JIRA_USERNAME is missing
6. ConfigError raised when JIRA_API_TOKEN is missing
7. ConfigError raised when both GIT_SSH_KEY_PATH and GIT_PAT are missing
8. ConfigError message contains the missing credential name in each case
9. Optional fields use defaults when not set (working_dir_base, log_format, verbose, dry_run)

Requirements: 6.1, 6.2, 6.3, 6.4
"""

import os
from unittest.mock import patch

import pytest

from jira_repo_automation.config import Config, ConfigLoader
from jira_repo_automation.exceptions import ConfigError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# A minimal set of valid env vars that satisfies all required credentials.
_VALID_ENV = {
    "JIRA_BASE_URL": "https://example.atlassian.net",
    "JIRA_USERNAME": "user@example.com",
    "JIRA_API_TOKEN": "token-abc123",
    "GIT_PAT": "pat-xyz789",
}


def _write_env_file(path, mapping: dict) -> None:
    """Write a .env file from a dict of key=value pairs."""
    with open(path, "w", encoding="utf-8") as fh:
        for key, value in mapping.items():
            fh.write(f'{key}="{value}"\n')


# ---------------------------------------------------------------------------
# 1. Successful load from env vars only
# ---------------------------------------------------------------------------


class TestLoadFromEnvVarsOnly:
    """ConfigLoader.load with all required vars in env, no config file."""

    def test_returns_config_with_jira_credentials(self):
        with patch.dict(os.environ, _VALID_ENV, clear=True):
            config = ConfigLoader().load()

        assert config.jira_base_url == "https://example.atlassian.net"
        assert config.jira_username == "user@example.com"
        assert config.jira_api_token == "token-abc123"

    def test_returns_config_with_git_pat(self):
        with patch.dict(os.environ, _VALID_ENV, clear=True):
            config = ConfigLoader().load()

        assert config.git_pat == "pat-xyz789"
        assert config.git_ssh_key_path is None

    def test_returns_config_with_git_ssh_key(self):
        env = {**_VALID_ENV}
        del env["GIT_PAT"]
        env["GIT_SSH_KEY_PATH"] = "/home/user/.ssh/id_rsa"

        with patch.dict(os.environ, env, clear=True):
            config = ConfigLoader().load()

        assert config.git_ssh_key_path == "/home/user/.ssh/id_rsa"
        assert config.git_pat is None

    def test_returns_config_with_both_git_credentials(self):
        env = {**_VALID_ENV, "GIT_SSH_KEY_PATH": "/home/user/.ssh/id_rsa"}

        with patch.dict(os.environ, env, clear=True):
            config = ConfigLoader().load()

        assert config.git_ssh_key_path == "/home/user/.ssh/id_rsa"
        assert config.git_pat == "pat-xyz789"

    def test_returns_config_instance(self):
        with patch.dict(os.environ, _VALID_ENV, clear=True):
            config = ConfigLoader().load()

        assert isinstance(config, Config)


# ---------------------------------------------------------------------------
# 2. Successful load from config file only
# ---------------------------------------------------------------------------


class TestLoadFromConfigFileOnly:
    """ConfigLoader.load with all required values in a config file, no env vars."""

    def test_reads_jira_credentials_from_file(self, tmp_path):
        env_file = tmp_path / ".env"
        _write_env_file(
            env_file,
            {
                "JIRA_BASE_URL": "https://file.atlassian.net",
                "JIRA_USERNAME": "file-user@example.com",
                "JIRA_API_TOKEN": "file-token",
                "GIT_PAT": "file-pat",
            },
        )

        with patch.dict(os.environ, {}, clear=True):
            config = ConfigLoader().load(config_file=str(env_file))

        assert config.jira_base_url == "https://file.atlassian.net"
        assert config.jira_username == "file-user@example.com"
        assert config.jira_api_token == "file-token"

    def test_reads_git_pat_from_file(self, tmp_path):
        env_file = tmp_path / ".env"
        _write_env_file(
            env_file,
            {
                "JIRA_BASE_URL": "https://file.atlassian.net",
                "JIRA_USERNAME": "file-user@example.com",
                "JIRA_API_TOKEN": "file-token",
                "GIT_PAT": "file-pat",
            },
        )

        with patch.dict(os.environ, {}, clear=True):
            config = ConfigLoader().load(config_file=str(env_file))

        assert config.git_pat == "file-pat"

    def test_reads_git_ssh_key_from_file(self, tmp_path):
        env_file = tmp_path / ".env"
        _write_env_file(
            env_file,
            {
                "JIRA_BASE_URL": "https://file.atlassian.net",
                "JIRA_USERNAME": "file-user@example.com",
                "JIRA_API_TOKEN": "file-token",
                "GIT_SSH_KEY_PATH": "/home/user/.ssh/id_rsa",
            },
        )

        with patch.dict(os.environ, {}, clear=True):
            config = ConfigLoader().load(config_file=str(env_file))

        assert config.git_ssh_key_path == "/home/user/.ssh/id_rsa"


# ---------------------------------------------------------------------------
# 3. Env var overrides config file value
# ---------------------------------------------------------------------------


class TestEnvVarOverridesConfigFile:
    """Env vars take precedence over config file values for each Jira credential."""

    def test_env_overrides_jira_base_url(self, tmp_path):
        env_file = tmp_path / ".env"
        _write_env_file(
            env_file,
            {
                "JIRA_BASE_URL": "https://file.atlassian.net",
                "JIRA_USERNAME": "file-user@example.com",
                "JIRA_API_TOKEN": "file-token",
                "GIT_PAT": "file-pat",
            },
        )

        env = {**_VALID_ENV, "JIRA_BASE_URL": "https://env-override.atlassian.net"}
        with patch.dict(os.environ, env, clear=True):
            config = ConfigLoader().load(config_file=str(env_file))

        assert config.jira_base_url == "https://env-override.atlassian.net"

    def test_env_overrides_jira_username(self, tmp_path):
        env_file = tmp_path / ".env"
        _write_env_file(
            env_file,
            {
                "JIRA_BASE_URL": "https://file.atlassian.net",
                "JIRA_USERNAME": "file-user@example.com",
                "JIRA_API_TOKEN": "file-token",
                "GIT_PAT": "file-pat",
            },
        )

        env = {**_VALID_ENV, "JIRA_USERNAME": "env-user@example.com"}
        with patch.dict(os.environ, env, clear=True):
            config = ConfigLoader().load(config_file=str(env_file))

        assert config.jira_username == "env-user@example.com"

    def test_env_overrides_jira_api_token(self, tmp_path):
        env_file = tmp_path / ".env"
        _write_env_file(
            env_file,
            {
                "JIRA_BASE_URL": "https://file.atlassian.net",
                "JIRA_USERNAME": "file-user@example.com",
                "JIRA_API_TOKEN": "file-token",
                "GIT_PAT": "file-pat",
            },
        )

        env = {**_VALID_ENV, "JIRA_API_TOKEN": "env-token-override"}
        with patch.dict(os.environ, env, clear=True):
            config = ConfigLoader().load(config_file=str(env_file))

        assert config.jira_api_token == "env-token-override"

    def test_env_overrides_git_pat(self, tmp_path):
        env_file = tmp_path / ".env"
        _write_env_file(
            env_file,
            {
                "JIRA_BASE_URL": "https://file.atlassian.net",
                "JIRA_USERNAME": "file-user@example.com",
                "JIRA_API_TOKEN": "file-token",
                "GIT_PAT": "file-pat",
            },
        )

        env = {**_VALID_ENV, "GIT_PAT": "env-pat-override"}
        with patch.dict(os.environ, env, clear=True):
            config = ConfigLoader().load(config_file=str(env_file))

        assert config.git_pat == "env-pat-override"


# ---------------------------------------------------------------------------
# 4–7. ConfigError raised for each missing required credential
# ---------------------------------------------------------------------------


class TestMissingRequiredCredentials:
    """ConfigError is raised when a required credential is absent."""

    def test_raises_config_error_when_jira_base_url_missing(self):
        env = {k: v for k, v in _VALID_ENV.items() if k != "JIRA_BASE_URL"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigError):
                ConfigLoader().load()

    def test_raises_config_error_when_jira_username_missing(self):
        env = {k: v for k, v in _VALID_ENV.items() if k != "JIRA_USERNAME"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigError):
                ConfigLoader().load()

    def test_raises_config_error_when_jira_api_token_missing(self):
        env = {k: v for k, v in _VALID_ENV.items() if k != "JIRA_API_TOKEN"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigError):
                ConfigLoader().load()

    def test_raises_config_error_when_both_git_credentials_missing(self):
        env = {
            "JIRA_BASE_URL": "https://example.atlassian.net",
            "JIRA_USERNAME": "user@example.com",
            "JIRA_API_TOKEN": "token-abc123",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigError):
                ConfigLoader().load()


# ---------------------------------------------------------------------------
# 8. ConfigError message contains the missing credential name
# ---------------------------------------------------------------------------


class TestConfigErrorMessageContainsCredentialName:
    """ConfigError messages must identify the missing credential."""

    def test_error_message_contains_jira_base_url(self):
        env = {k: v for k, v in _VALID_ENV.items() if k != "JIRA_BASE_URL"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigError) as exc_info:
                ConfigLoader().load()

        assert "JIRA_BASE_URL" in str(exc_info.value)

    def test_error_message_contains_jira_username(self):
        env = {k: v for k, v in _VALID_ENV.items() if k != "JIRA_USERNAME"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigError) as exc_info:
                ConfigLoader().load()

        assert "JIRA_USERNAME" in str(exc_info.value)

    def test_error_message_contains_jira_api_token(self):
        env = {k: v for k, v in _VALID_ENV.items() if k != "JIRA_API_TOKEN"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigError) as exc_info:
                ConfigLoader().load()

        assert "JIRA_API_TOKEN" in str(exc_info.value)

    def test_error_message_contains_git_credential_name_when_both_missing(self):
        env = {
            "JIRA_BASE_URL": "https://example.atlassian.net",
            "JIRA_USERNAME": "user@example.com",
            "JIRA_API_TOKEN": "token-abc123",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigError) as exc_info:
                ConfigLoader().load()

        error_msg = str(exc_info.value)
        assert "GIT_SSH_KEY_PATH" in error_msg or "GIT_PAT" in error_msg


# ---------------------------------------------------------------------------
# 9. Optional fields use defaults when not set
# ---------------------------------------------------------------------------


class TestOptionalFieldDefaults:
    """Optional config fields fall back to their documented defaults."""

    def test_working_dir_base_defaults_to_tmp(self):
        with patch.dict(os.environ, _VALID_ENV, clear=True):
            config = ConfigLoader().load()

        assert config.working_dir_base == "/tmp/jira-repo-automation"

    def test_log_format_defaults_to_text(self):
        with patch.dict(os.environ, _VALID_ENV, clear=True):
            config = ConfigLoader().load()

        assert config.log_format == "text"

    def test_verbose_defaults_to_false(self):
        with patch.dict(os.environ, _VALID_ENV, clear=True):
            config = ConfigLoader().load()

        assert config.verbose is False

    def test_dry_run_defaults_to_false(self):
        with patch.dict(os.environ, _VALID_ENV, clear=True):
            config = ConfigLoader().load()

        assert config.dry_run is False

    def test_optional_fields_can_be_set_via_env(self):
        env = {
            **_VALID_ENV,
            "WORKING_DIR_BASE": "/custom/workdir",
            "LOG_FORMAT": "json",
            "VERBOSE": "true",
            "DRY_RUN": "1",
        }
        with patch.dict(os.environ, env, clear=True):
            config = ConfigLoader().load()

        assert config.working_dir_base == "/custom/workdir"
        assert config.log_format == "json"
        assert config.verbose is True
        assert config.dry_run is True

    def test_verbose_truthy_values(self):
        for truthy in ("1", "true", "yes", "True", "YES"):
            env = {**_VALID_ENV, "VERBOSE": truthy}
            with patch.dict(os.environ, env, clear=True):
                config = ConfigLoader().load()
            assert config.verbose is True, f"Expected verbose=True for VERBOSE={truthy!r}"

    def test_dry_run_truthy_values(self):
        for truthy in ("1", "true", "yes", "True", "YES"):
            env = {**_VALID_ENV, "DRY_RUN": truthy}
            with patch.dict(os.environ, env, clear=True):
                config = ConfigLoader().load()
            assert config.dry_run is True, f"Expected dry_run=True for DRY_RUN={truthy!r}"

    def test_verbose_falsy_values(self):
        for falsy in ("0", "false", "no", ""):
            env = {**_VALID_ENV, "VERBOSE": falsy}
            with patch.dict(os.environ, env, clear=True):
                config = ConfigLoader().load()
            assert config.verbose is False, f"Expected verbose=False for VERBOSE={falsy!r}"

    def test_optional_fields_from_config_file(self, tmp_path):
        env_file = tmp_path / ".env"
        _write_env_file(
            env_file,
            {
                "JIRA_BASE_URL": "https://file.atlassian.net",
                "JIRA_USERNAME": "file-user@example.com",
                "JIRA_API_TOKEN": "file-token",
                "GIT_PAT": "file-pat",
                "WORKING_DIR_BASE": "/file/workdir",
                "LOG_FORMAT": "json",
                "VERBOSE": "true",
                "DRY_RUN": "1",
            },
        )

        with patch.dict(os.environ, {}, clear=True):
            config = ConfigLoader().load(config_file=str(env_file))

        assert config.working_dir_base == "/file/workdir"
        assert config.log_format == "json"
        assert config.verbose is True
        assert config.dry_run is True

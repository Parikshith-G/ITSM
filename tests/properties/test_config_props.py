# Feature: jira-repo-automation, Property 18: Env var takes precedence over config file value

"""Property-based tests for ConfigLoader.

**Validates: Requirements 6.3**
"""

import os
import tempfile
import unittest.mock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from jira_repo_automation.config import ConfigLoader

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# The three Jira credential keys that ConfigLoader reads.
JIRA_KEYS = ["JIRA_BASE_URL", "JIRA_USERNAME", "JIRA_API_TOKEN"]

# A safe printable-text strategy that avoids null bytes (which would break
# dotenv parsing) and is guaranteed non-empty so it doesn't look "falsy".
_safe_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters="-_./:",
    ),
    min_size=1,
    max_size=64,
)


def _write_env_file(path: str, key: str, value: str) -> None:
    """Write a minimal .env file containing a single key=value pair."""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f'{key}="{value}"\n')


# ---------------------------------------------------------------------------
# Property 18: Env var takes precedence over config file value
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(
    config_key=st.sampled_from(JIRA_KEYS),
    file_value=_safe_text,
    env_value=_safe_text,
)
def test_env_var_takes_precedence_over_config_file(
    config_key: str,
    file_value: str,
    env_value: str,
) -> None:
    """Property 18: For any config key, when the same key is present in both
    the config file and as an environment variable, ConfigLoader.load should
    return the environment variable value.

    **Validates: Requirements 6.3**
    """
    # Ensure the two values are distinct so the assertion is meaningful.
    # Hypothesis may occasionally generate equal values; skip those cases.
    if file_value == env_value:
        return

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".env", delete=False
    ) as tmp:
        tmp_path = tmp.name

    try:
        _write_env_file(tmp_path, config_key, file_value)

        # Build a complete set of env vars so ConfigLoader.load() doesn't
        # raise ConfigError for unrelated missing credentials.
        base_env = {
            "JIRA_BASE_URL": "https://example.atlassian.net",
            "JIRA_USERNAME": "user@example.com",
            "JIRA_API_TOKEN": "base-token",
            "GIT_PAT": "base-pat",
        }
        # Override the key under test with the env var value.
        base_env[config_key] = env_value

        with unittest.mock.patch.dict(os.environ, base_env, clear=False):
            # Remove any pre-existing value for the key under test from the
            # *real* environment so only our patched value is visible.
            loader = ConfigLoader()
            config = loader.load(config_file=tmp_path)

        # Map the config key to the corresponding Config attribute.
        attr_map = {
            "JIRA_BASE_URL": "jira_base_url",
            "JIRA_USERNAME": "jira_username",
            "JIRA_API_TOKEN": "jira_api_token",
        }
        attr = attr_map[config_key]
        actual = getattr(config, attr)

        assert actual == env_value, (
            f"Expected env var value {env_value!r} for key {config_key!r}, "
            f"but got {actual!r} (config file had {file_value!r})"
        )
    finally:
        os.unlink(tmp_path)


# Feature: jira-repo-automation, Property 19: Missing credential error contains the credential name

"""Property 19: Missing credential error contains the credential name.

**Validates: Requirements 6.4**
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from jira_repo_automation.config import ConfigLoader
from jira_repo_automation.exceptions import ConfigError

# ---------------------------------------------------------------------------
# Helpers for Property 19
# ---------------------------------------------------------------------------

# All required credentials that ConfigLoader validates individually.
_INDIVIDUAL_REQUIRED_KEYS = [
    "JIRA_BASE_URL",
    "JIRA_USERNAME",
    "JIRA_API_TOKEN",
]

# The git credential pair: both must be absent to trigger the error.
_GIT_CREDENTIAL_KEYS = ["GIT_SSH_KEY_PATH", "GIT_PAT"]

# A complete set of valid credentials used to fill in all *other* keys so
# that only the credential under test is missing.
_FULL_VALID_ENV = {
    "JIRA_BASE_URL": "https://example.atlassian.net",
    "JIRA_USERNAME": "user@example.com",
    "JIRA_API_TOKEN": "token-abc123",
    "GIT_PAT": "pat-xyz789",
}


# ---------------------------------------------------------------------------
# Property 19: Missing credential error contains the credential name
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(missing_key=st.sampled_from(_INDIVIDUAL_REQUIRED_KEYS))
def test_missing_individual_credential_error_contains_name(
    missing_key: str,
) -> None:
    """Property 19 (individual Jira credentials): When a required Jira
    credential is absent from both env vars and config file, ConfigLoader.load
    raises ConfigError whose message contains the missing credential name.

    **Validates: Requirements 6.4**
    """
    # Build an env that has every required credential *except* the one under test.
    env_without_key = {k: v for k, v in _FULL_VALID_ENV.items() if k != missing_key}

    with unittest.mock.patch.dict(os.environ, env_without_key, clear=True):
        loader = ConfigLoader()
        with pytest.raises(ConfigError) as exc_info:
            loader.load()  # no config file → only env vars

    assert missing_key in str(exc_info.value), (
        f"Expected ConfigError message to contain {missing_key!r}, "
        f"but got: {exc_info.value!r}"
    )


@settings(max_examples=200)
@given(
    # Hypothesis iterates over the two git credential key names so we can
    # document which name the error message should contain.
    git_key=st.sampled_from(_GIT_CREDENTIAL_KEYS),
)
def test_missing_git_credentials_error_contains_name(git_key: str) -> None:
    """Property 19 (git credential pair): When both GIT_SSH_KEY_PATH and
    GIT_PAT are absent from both env vars and config file, ConfigLoader.load
    raises ConfigError whose message contains at least one of the git
    credential names.

    **Validates: Requirements 6.4**
    """
    # Remove both git credential keys so the error is triggered.
    env_without_git = {
        k: v
        for k, v in _FULL_VALID_ENV.items()
        if k not in _GIT_CREDENTIAL_KEYS
    }

    with unittest.mock.patch.dict(os.environ, env_without_git, clear=True):
        loader = ConfigLoader()
        with pytest.raises(ConfigError) as exc_info:
            loader.load()  # no config file → only env vars

    error_message = str(exc_info.value)
    assert any(key in error_message for key in _GIT_CREDENTIAL_KEYS), (
        f"Expected ConfigError message to contain at least one of "
        f"{_GIT_CREDENTIAL_KEYS!r}, but got: {error_message!r}"
    )

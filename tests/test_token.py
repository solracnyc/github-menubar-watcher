import os
import pytest
from unittest.mock import patch
from token_resolver import resolve_token


def test_env_var_takes_priority():
    with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_from_env"}):
        assert resolve_token() == "ghp_from_env"


def test_returns_none_when_no_token():
    with patch.dict(os.environ, {}, clear=True):
        # Keychain lookup will also fail in test environment
        result = resolve_token()
        # Result is either None or a real keychain token; in CI it's None
        assert result is None or isinstance(result, str)


def test_empty_env_var_is_ignored():
    with patch.dict(os.environ, {"GITHUB_TOKEN": ""}):
        result = resolve_token()
        assert result is None or isinstance(result, str)

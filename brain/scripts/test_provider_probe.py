"""Tests for provider_probe.py auth.json fallback mechanism."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

# Import the module under test
import sys
sys.path.insert(0, str(Path(__file__).parent))
from provider_probe import resolve_env, load_config, clear_auth_cache


class TestResolveEnvWithAuthFallback:
    """Test resolve_env with auth.json fallback."""

    @pytest.fixture(autouse=True)
    def reset_auth_cache(self):
        """Clear auth cache before each test."""
        clear_auth_cache()
        yield
        clear_auth_cache()

    @pytest.fixture
    def temp_auth_json(self):
        """Create a temporary auth.json fixture."""
        auth_data = {
            "version": 1,
            "credential_pool": {
                "minimax": [
                    {
                        "id": "test123",
                        "label": "MINIMAX_API_KEY",
                        "auth_type": "api_key",
                        "priority": 0,
                        "source": "env:MINIMAX_API_KEY",
                        "access_token": "secret_minimax_token",
                        "last_status": "ok",
                    },
                    {
                        "id": "test456",
                        "label": "MINIMAX_API_KEY",
                        "auth_type": "api_key",
                        "priority": 1,
                        "source": "env:MINIMAX_API_KEY",
                        "access_token": "secret_minimax_token_p1",
                        "last_status": None,
                    },
                ],
                "kimi-coding": [
                    {
                        "id": "kimi789",
                        "label": "KIMI_API_KEY",
                        "auth_type": "api_key",
                        "priority": 0,
                        "source": "env:KIMI_API_KEY",
                        "access_token": "secret_kimi_token",
                        "last_status": "ok",
                    }
                ],
                "openrouter": [
                    {
                        "id": "or001",
                        "label": "OPENROUTER_API_KEY",
                        "auth_type": "api_key",
                        "priority": 0,
                        "source": "env:OPENROUTER_API_KEY",
                        "access_token": "secret_openrouter_token",
                        "last_status": None,
                    }
                ],
            }
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(auth_data, f)
            temp_path = f.name
        yield Path(temp_path)
        os.unlink(temp_path)

    def test_env_var_present_wins_over_auth_json(self, temp_auth_json, monkeypatch):
        """When env var is set, it takes precedence over auth.json."""
        monkeypatch.setenv("MINIMAX_API_KEY", "env_var_token")

        missing = []
        result = resolve_env("${MINIMAX_API_KEY}", missing, auth_path=temp_auth_json)

        assert result == "env_var_token"
        assert "MINIMAX_API_KEY" not in missing

    def test_env_var_missing_auth_json_has_match(self, temp_auth_json, monkeypatch):
        """When env var is missing but auth.json has matching label, use auth.json."""
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)

        missing = []
        result = resolve_env("${MINIMAX_API_KEY}", missing, auth_path=temp_auth_json)

        assert result == "secret_minimax_token"
        assert "MINIMAX_API_KEY" not in missing

    def test_env_var_missing_no_auth_label_remains_missing(self, temp_auth_json, monkeypatch):
        """When env var is missing and no auth label matches, keep placeholder."""
        monkeypatch.delenv("SOME_UNKNOWN_VAR", raising=False)

        missing = []
        result = resolve_env("${SOME_UNKNOWN_VAR}", missing, auth_path=temp_auth_json)

        assert result == "${SOME_UNKNOWN_VAR}"
        assert "SOME_UNKNOWN_VAR" in missing

    def test_multiple_auth_entries_choose_lowest_priority(self, temp_auth_json, monkeypatch):
        """When multiple credentials match label, choose lowest priority."""
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)

        missing = []
        result = resolve_env("${MINIMAX_API_KEY}", missing, auth_path=temp_auth_json)

        # Should get priority=0, not priority=1
        assert result == "secret_minimax_token"
        assert "MINIMAX_API_KEY" not in missing

    def test_auth_json_not_set_no_crash(self, monkeypatch):
        """When auth_path is None and no default auth file, should not crash."""
        monkeypatch.delenv("HERMES_AUTH_JSON_PATH", raising=False)
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
        # Use a non-existent default path by temporarily patching DEFAULT_AUTH_PATH
        import provider_probe
        original = provider_probe.DEFAULT_AUTH_PATH
        provider_probe.DEFAULT_AUTH_PATH = Path("/nonexistent/.hermes/auth.json")
        # Clear cache to pick up the new path
        clear_auth_cache()

        missing = []
        result = resolve_env("${MINIMAX_API_KEY}", missing, auth_path=None)

        provider_probe.DEFAULT_AUTH_PATH = original
        clear_auth_cache()

        assert result == "${MINIMAX_API_KEY}"
        assert "MINIMAX_API_KEY" in missing

    def test_auth_json_path_invalid_no_crash(self, monkeypatch):
        """When auth_path points to invalid file, should not crash."""
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
        invalid_path = Path("/nonexistent/path.json")

        missing = []
        result = resolve_env("${MINIMAX_API_KEY}", missing, auth_path=invalid_path)

        assert result == "${MINIMAX_API_KEY}"
        assert "MINIMAX_API_KEY" in missing

    def test_nested_dict_with_env_and_auth_fallback(self, temp_auth_json, monkeypatch):
        """Nested dict structures resolve correctly with auth fallback."""
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)

        entry = {
            "url": "https://api.minimax.io/v1/chat/completions",
            "headers": {
                "Authorization": "Bearer ${MINIMAX_API_KEY}"
            },
        }

        missing = []
        resolved = resolve_env(entry, missing, auth_path=temp_auth_json)

        assert resolved["headers"]["Authorization"] == "Bearer secret_minimax_token"
        assert "MINIMAX_API_KEY" not in missing

    def test_list_with_env_and_auth_fallback(self, temp_auth_json, monkeypatch):
        """List values resolve correctly with auth fallback."""
        monkeypatch.delenv("KIMI_API_KEY", raising=False)

        entry = [
            {"role": "user", "content": "Hello ${KIMI_API_KEY}"},
            "Bearer ${KIMI_API_KEY}",
        ]

        missing = []
        resolved = resolve_env(entry, missing, auth_path=temp_auth_json)

        assert resolved[0]["content"] == "Hello secret_kimi_token"
        assert resolved[1] == "Bearer secret_kimi_token"
        assert "KIMI_API_KEY" not in missing

    def test_resolve_env_returns_correct_type_for_non_string(self):
        """Non-string values pass through unchanged."""
        missing = []

        assert resolve_env(123, missing, auth_path=None) == 123
        assert resolve_env(True, missing, auth_path=None) is True
        assert resolve_env(None, missing, auth_path=None) is None
        assert resolve_env(["a", "b"], missing, auth_path=None) == ["a", "b"]
        assert resolve_env({"key": "val"}, missing, auth_path=None) == {"key": "val"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""TDD tests for vault classification module."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermesoptimizer.vault.classify import classify_key, load_classification_override


class TestClassifyKey:
    """Tests for classify_key function."""

    def test_exact_secret_names(self) -> None:
        """Exact secret names should be classified as 'secret'."""
        secret_names = [
            "password",
            "secret",
            "token",
            "api_key",
            "apikey",
            "access_key",
            "private_key",
            "auth_token",
            "bearer_token",
            "refresh_token",
            "client_secret",
        ]
        for name in secret_names:
            assert classify_key(name) == "secret", f"Expected {name} to be classified as secret"

    def test_secret_suffix_patterns(self) -> None:
        """Keys ending with secret-like suffixes should be classified as 'secret'."""
        secret_patterns = [
            "SECRET_KEY",
            "SECRET_TOKEN",
            "SECRET",
            "PASSWORD",
            "API_KEY",
            "ACCESS_KEY",
            "PRIVATE_KEY",
            "MY_API_KEY",
            "DATABASE_PASSWORD",
            "SERVICE_TOKEN",
            "ADMIN_PASS",
            "USER_PASSWORD",
            "APP_SECRET",
            "SERVICE_AUTH",
            "API_CREDENTIAL",
            "USER_CREDENTIAL",
        ]
        for pattern in secret_patterns:
            assert classify_key(pattern) == "secret", f"Expected {pattern} to be classified as secret"

    def test_metadata_suffix_patterns(self) -> None:
        """Keys ending with URL/endpoint-like suffixes should be classified as 'metadata'."""
        metadata_patterns = [
            "_URL",
            "_ENDPOINT",
            "_HOST",
            "_PORT",
            "_REGION",
            "_BASE_URL",
            "_API_URL",
            "_SERVER",
            "API_URL",
            "BASE_URL",
            "WEBHOOK_URL",
            "SERVICE_HOST",
            "DATABASE_PORT",
        ]
        for pattern in metadata_patterns:
            assert classify_key(pattern) == "metadata", f"Expected {pattern} to be classified as metadata"

    def test_case_insensitive_suffix_matching(self) -> None:
        """Suffix matching should be case-insensitive."""
        assert classify_key("api_key") == "secret"
        assert classify_key("API_KEY") == "secret"
        assert classify_key("Api_Key") == "secret"
        assert classify_key("password") == "secret"
        assert classify_key("PASSWORD") == "secret"
        assert classify_key("Password") == "secret"

    def test_unknown_keys_default_to_metadata(self) -> None:
        """Keys that don't match any pattern should default to 'metadata' (safe default)."""
        unknown_keys = [
            "DATABASE_HOST",
            "REDIS_URL",
            "LOG_LEVEL",
            "TIMEOUT",
            "MAX_RETRIES",
            "ENVIRONMENT",
            "DEBUG_MODE",
            "SERVICE_NAME",
            "version",
            "name",
            "description",
        ]
        for key in unknown_keys:
            assert classify_key(key) == "metadata", f"Expected {key} to be classified as metadata"

    def test_metadata_takes_precedence_for_url_suffix(self) -> None:
        """_URL suffix should classify as metadata, not secret."""
        assert classify_key("API_URL") == "metadata"
        assert classify_key("WEBHOOK_URL") == "metadata"
        assert classify_key("BASE_URL") == "metadata"

    def test_secret_takes_precedence_for_auth_suffix(self) -> None:
        """_AUTH suffix should classify as secret."""
        assert classify_key("SERVICE_AUTH") == "secret"
        assert classify_key("API_AUTH") == "secret"

    def test_exact_match_secret_takes_precedence(self) -> None:
        """Exact secret name match should work regardless of case."""
        assert classify_key("token") == "secret"
        assert classify_key("TOKEN") == "secret"
        assert classify_key("Token") == "secret"


class TestLoadClassificationOverride:
    """Tests for load_classification_override function."""

    def test_load_override_file(self, tmp_path: Path) -> None:
        """Should load KEY=secret and KEY=metadata lines from override file."""
        override_file = tmp_path / ".vault" / ".classification"
        override_file.parent.mkdir(parents=True)
        override_file.write_text(
            "CUSTOM_SECRET=secret\n"
            "CUSTOM_URL=metadata\n"
            "ANOTHER_KEY=secret\n",
            encoding="utf-8",
        )

        overrides = load_classification_override(override_file)

        assert overrides["CUSTOM_SECRET"] == "secret"
        assert overrides["CUSTOM_URL"] == "metadata"
        assert overrides["ANOTHER_KEY"] == "secret"

    def test_empty_override_file(self, tmp_path: Path) -> None:
        """Empty override file should return empty dict."""
        override_file = tmp_path / ".vault" / ".classification"
        override_file.parent.mkdir(parents=True)
        override_file.write_text("", encoding="utf-8")

        overrides = load_classification_override(override_file)

        assert overrides == {}

    def test_override_file_with_comments_and_empty_lines(self, tmp_path: Path) -> None:
        """Override file should ignore comments and empty lines."""
        override_file = tmp_path / ".vault" / ".classification"
        override_file.parent.mkdir(parents=True)
        override_file.write_text(
            "# This is a comment\n"
            "\n"
            "OVERRIDE_KEY=secret\n"
            "   \n"
            "# Another comment\n"
            "ANOTHER_OVERRIDE=metadata\n",
            encoding="utf-8",
        )

        overrides = load_classification_override(override_file)

        assert overrides["OVERRIDE_KEY"] == "secret"
        assert overrides["ANOTHER_OVERRIDE"] == "metadata"
        assert len(overrides) == 2

    def test_override_file_missing(self, tmp_path: Path) -> None:
        """Missing override file should return empty dict."""
        override_file = tmp_path / ".vault" / ".classification"

        overrides = load_classification_override(override_file)

        assert overrides == {}

    def test_override_invalid_lines_ignored(self, tmp_path: Path) -> None:
        """Invalid lines (missing = or invalid classification) should be ignored."""
        override_file = tmp_path / ".vault" / ".classification"
        override_file.parent.mkdir(parents=True)
        override_file.write_text(
            "VALID_KEY=secret\n"
            "NO_EQUALS\n"
            "INVALID_CLASS=not_secret_or_metadata\n"
            "=missing_key\n",
            encoding="utf-8",
        )

        overrides = load_classification_override(override_file)

        assert overrides["VALID_KEY"] == "secret"
        assert "NO_EQUALS" not in overrides
        assert "INVALID_CLASS" not in overrides
        assert "missing_key" not in overrides

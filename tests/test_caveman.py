"""Tests for caveman mode output compression."""
from __future__ import annotations

import pytest

from hermesoptimizer.caveman import (
    enable,
    disable,
    toggle,
    is_enabled,
    compress,
    caveman_wrapper,
    full_mode_guard,
)


class TestCavemanToggle:
    """Tests for caveman mode toggle functions."""

    def test_caveman_disabled_by_default(self) -> None:
        """Caveman mode should be OFF by default."""
        disable()  # Ensure off
        assert is_enabled() is False

    def test_enable_turns_on_caveman(self) -> None:
        """enable() should turn caveman mode on."""
        disable()
        enable()
        assert is_enabled() is True

    def test_disable_turns_off_caveman(self) -> None:
        """disable() should turn caveman mode off."""
        enable()
        disable()
        assert is_enabled() is False

    def test_toggle_flips_state(self) -> None:
        """toggle() should flip the current state."""
        disable()
        assert toggle() is True
        assert toggle() is False
        assert toggle() is True


class TestCompressBasic:
    """Tests for basic compression functionality."""

    def test_compress_returns_original_when_disabled(self) -> None:
        """When caveman is disabled, compress returns text unchanged."""
        disable()
        text = "This is a test message."
        assert compress(text) == text

    def test_compress_drops_filler_words(self) -> None:
        """Filler words should be dropped."""
        enable()
        text = "This is actually a really simple test."
        result = compress(text)
        assert "actually" not in result.lower()
        assert "really" not in result.lower()

    def test_compress_drops_hedging(self) -> None:
        """Hedging phrases should be dropped."""
        enable()
        text = "I think you should consider this option."
        result = compress(text)
        assert "I think" not in result
        assert "consider" not in result.lower()

    def test_compress_drops_pleasantries(self) -> None:
        """Pleasantries should be dropped."""
        enable()
        text = "Sure, I'd be happy to help with that."
        result = compress(text)
        assert "Sure" not in result
        assert "happy to" not in result.lower()

    def test_compress_drops_articles(self) -> None:
        """Articles should be dropped."""
        enable()
        text = "This is the test file."
        result = compress(text)
        # Articles before nouns should be reduced
        assert result != text  # Some compression happened

    def test_compress_cleans_whitespace(self) -> None:
        """Extra whitespace should be cleaned up."""
        enable()
        text = "This   is   a   test."
        result = compress(text)
        assert "  " not in result  # No double spaces


class TestSafetyCritical:
    """Tests for safety-critical path protection."""

    def test_safety_critical_always_full_mode(self) -> None:
        """Safety-critical text should always return unchanged."""
        enable()
        text = "write-back mutation: config.yaml"
        assert compress(text) == text

    def test_vault_operations_full_mode(self) -> None:
        """Vault operations should stay in full mode."""
        enable()
        text = "vault write-back confirmed"
        assert compress(text) == text

    def test_credential_messages_full_mode(self) -> None:
        """Credential-related messages should stay in full mode."""
        enable()
        text = "auth token expired"
        assert compress(text) == text

    def test_setup_instructions_full_mode(self) -> None:
        """Setup/onboarding should stay in full mode."""
        enable()
        text = "setup instructions for new users"
        assert compress(text) == text

    def test_force_full_override(self) -> None:
        """force_full=True should always return unchanged."""
        enable()
        text = "This is a regular message."
        assert compress(text, force_full=True) == text


class TestCavemanWrapper:
    """Tests for the caveman_wrapper decorator."""

    def test_wrapper_compresses_string_output(self) -> None:
        """Wrapper should compress string output when enabled."""
        enable()

        @caveman_wrapper
        def greet():
            return "Hello, I am actually happy to help."

        result = greet()
        assert "actually" not in result.lower()
        assert "happy to" not in result.lower()

    def test_wrapper_returns_non_string_unchanged(self) -> None:
        """Wrapper should return non-string output unchanged."""
        enable()

        @caveman_wrapper
        def get_number():
            return 42

        assert get_number() == 42

    def test_wrapper_disabled_returns_unchanged(self) -> None:
        """Wrapper should return unchanged when caveman disabled."""
        disable()

        @caveman_wrapper
        def greet():
            return "Hello, I am happy to help."

        result = greet()
        assert result == "Hello, I am happy to help."


class TestFullModeGuard:
    """Tests for the full_mode_guard decorator."""

    def test_guard_forces_full_mode(self) -> None:
        """Guard should force full mode regardless of caveman state."""
        enable()

        @full_mode_guard
        def vault_write():
            return "write-back mutation: config.yaml"

        result = vault_write()
        assert result == "write-back mutation: config.yaml"

    def test_guard_returns_non_string_unchanged(self) -> None:
        """Guard should return non-string output unchanged."""
        enable()

        @full_mode_guard
        def get_count():
            return 100

        assert get_count() == 100

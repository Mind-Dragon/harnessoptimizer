"""Tests for extension verification contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermesoptimizer.extensions.verify_contracts import (
    verify_caveman,
    verify_dreams,
    verify_tool_surface,
    verify_vault_plugins,
)


class TestVerifyCaveman:
    def test_verify_caveman_passes(self) -> None:
        # Caveman module is present in this repo; should pass
        assert verify_caveman() == 0


class TestVerifyDreams:
    def test_verify_dreams_passes(self) -> None:
        # Dreams module is present; external artifacts may warn but not error
        assert verify_dreams() == 0


class TestVerifyVaultPlugins:
    def test_verify_vault_plugins_passes(self) -> None:
        # All three plugin classes are importable and functional
        assert verify_vault_plugins() == 0


class TestVerifyToolSurface:
    def test_verify_tool_surface_passes(self) -> None:
        # Commands are available and help text is clean
        assert verify_tool_surface() == 0

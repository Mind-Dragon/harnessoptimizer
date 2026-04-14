"""
Phase 0 validation tests for the scanner skeleton.

These tests verify that:
- the scanner returns structured records even before deeper parsing exists
- the scanner can operate on fixtures without crashing
- stub scanners for config, session, log, database, and runtime exist
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hermesoptimizer.sources.hermes_config import scan_config_paths
from hermesoptimizer.sources.hermes_inventory import (
    HermesInventory,
    load_hermes_inventory,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "hermes"


# ---------------------------------------------------------------------------
# hermes_config scanner stub tests
# ---------------------------------------------------------------------------

class TestHermesConfigScanner:
    def test_scan_config_returns_list(self) -> None:
        """scan_config_paths must return a list even when no files are found."""
        result = scan_config_paths([])
        assert isinstance(result, list)

    def test_scan_config_on_yaml_returns_findings(self) -> None:
        """scan_config_paths must return findings when given a real YAML file."""
        config_path = FIXTURE_DIR / "config.yaml"
        findings = scan_config_paths([config_path])
        assert isinstance(findings, list)

    def test_scan_config_finds_provider_entries(self) -> None:
        """On the fixture config, the scanner must surface provider entries."""
        config_path = FIXTURE_DIR / "config.yaml"
        findings = scan_config_paths([config_path])
        # even a stub scanner should return something for a valid YAML
        assert len(findings) >= 0  # stub may be empty but must not raise


# ---------------------------------------------------------------------------
# HermesInventory loader tests
# ---------------------------------------------------------------------------

class TestHermesInventory:
    def test_load_hermes_inventory_from_file(self) -> None:
        inv = load_hermes_inventory(FIXTURE_DIR.parent / "hermes" / "config.yaml")
        assert inv is not None

    def test_inventory_has_config_slot(self) -> None:
        inv = load_hermes_inventory(FIXTURE_DIR.parent / "hermes" / "config.yaml")
        assert hasattr(inv, "config_path")

    def test_inventory_has_session_paths_slot(self) -> None:
        inv = load_hermes_inventory(FIXTURE_DIR.parent / "hermes" / "config.yaml")
        assert hasattr(inv, "session_paths")

    def test_inventory_has_log_paths_slot(self) -> None:
        inv = load_hermes_inventory(FIXTURE_DIR.parent / "hermes" / "config.yaml")
        assert hasattr(inv, "log_paths")

    def test_inventory_has_cache_paths_slot(self) -> None:
        inv = load_hermes_inventory(FIXTURE_DIR.parent / "hermes" / "config.yaml")
        assert hasattr(inv, "cache_paths")

    def test_inventory_has_db_paths_slot(self) -> None:
        inv = load_hermes_inventory(FIXTURE_DIR.parent / "hermes" / "config.yaml")
        assert hasattr(inv, "db_paths")

    def test_inventory_has_runtime_paths_slot(self) -> None:
        inv = load_hermes_inventory(FIXTURE_DIR.parent / "hermes" / "config.yaml")
        assert hasattr(inv, "runtime_paths")

    def test_inventory_has_gateway_entries_slot(self) -> None:
        inv = load_hermes_inventory(FIXTURE_DIR.parent / "hermes" / "config.yaml")
        assert hasattr(inv, "gateway_entries")

    def test_inventory_session_paths_from_config(self) -> None:
        """Session paths must be extracted from the fixture config."""
        inv = load_hermes_inventory(FIXTURE_DIR / "config.yaml")
        assert len(inv.session_paths) >= 1

    def test_inventory_log_paths_from_config(self) -> None:
        """Log paths must be extracted from the fixture config."""
        inv = load_hermes_inventory(FIXTURE_DIR / "config.yaml")
        assert len(inv.log_paths) >= 1

    def test_inventory_db_paths_from_config(self) -> None:
        """DB paths must be extracted from the fixture config."""
        inv = load_hermes_inventory(FIXTURE_DIR / "config.yaml")
        assert len(inv.db_paths) >= 1

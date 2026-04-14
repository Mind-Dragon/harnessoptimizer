"""
Phase 0 discovery tests for Hermes source inventory.

These tests verify that the Hermes source inventory can:
1. Load a source inventory from a machine-readable file
2. Discover Hermes paths on the live filesystem
3. Classify discovered paths by type (config, session, log, cache, db, runtime, gateway)
4. Handle missing paths gracefully
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hermesoptimizer.sources.hermes_discover import (
    SourceInventory,
    SourceEntry,
    discover_live_paths,
    load_inventory,
    classify_path,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "hermes"


@pytest.fixture
def inventory_file(tmp_path: Path) -> Path:
    """Write a minimal source inventory file."""
    content = """\
config:
  - path: ~/.hermes/config.yaml
    type: config
    authoritative: true
session:
  - path: ~/.hermes/sessions
    type: session
    authoritative: true
log:
  - path: ~/.hermes/logs
    type: log
    authoritative: true
cache:
  - path: ~/.hermes/cache
    type: cache
    authoritative: false
db:
  - path: ~/.hermes/state.db
    type: database
    authoritative: true
runtime:
  - path: ~/.hermes/runtime
    type: runtime
    authoritative: false
gateway:
  - command: hermes gateway status
    type: gateway
    authoritative: true
"""
    f = tmp_path / "inventory.yaml"
    f.write_text(content, encoding="utf-8")
    return f


@pytest.fixture
def minimal_entry() -> SourceEntry:
    return SourceEntry(
        path="~/.hermes/config.yaml",
        type="config",
        authoritative=True,
    )


# ---------------------------------------------------------------------------
# SourceEntry tests
# ---------------------------------------------------------------------------

class TestSourceEntry:
    def test_entry_has_required_fields(self, minimal_entry: SourceEntry) -> None:
        assert minimal_entry.path == "~/.hermes/config.yaml"
        assert minimal_entry.type == "config"
        assert minimal_entry.authoritative is True

    def test_entry_expands_user_home(self, minimal_entry: SourceEntry) -> None:
        expanded = minimal_entry.expand_path()
        assert expanded.startswith("/")

    def test_entry_is_live_equivalent(self, minimal_entry: SourceEntry) -> None:
        assert minimal_entry.path != minimal_entry.expand_path()


# ---------------------------------------------------------------------------
# SourceInventory tests
# ---------------------------------------------------------------------------

class TestSourceInventory:
    def test_load_from_yaml(self, inventory_file: Path) -> None:
        inv = load_inventory(inventory_file)
        assert "config" in inv.sources
        assert "session" in inv.sources
        assert "log" in inv.sources
        assert "cache" in inv.sources
        assert "db" in inv.sources
        assert "runtime" in inv.sources
        assert "gateway" in inv.sources

    def test_load_inventory_config_paths(self, inventory_file: Path) -> None:
        inv = load_inventory(inventory_file)
        config_entries = inv.sources.get("config", [])
        assert len(config_entries) == 1
        assert config_entries[0].type == "config"
        assert "hermes" in config_entries[0].path.lower()

    def test_load_inventory_gateway_entry(self, inventory_file: Path) -> None:
        inv = load_inventory(inventory_file)
        gateway_entries = inv.sources.get("gateway", [])
        assert len(gateway_entries) == 1
        assert gateway_entries[0].type == "gateway"
        assert gateway_entries[0].command is not None

    def test_inventory_keys_match_phase0_categories(self, inventory_file: Path) -> None:
        inv = load_inventory(inventory_file)
        expected = {"config", "session", "log", "cache", "db", "runtime", "gateway"}
        assert set(inv.sources.keys()) == expected

    def test_inventory_has_run_marker_slot(self, inventory_file: Path) -> None:
        inv = load_inventory(inventory_file)
        assert hasattr(inv, "run_marker")
        assert inv.run_marker is None  # not run yet


# ---------------------------------------------------------------------------
# classify_path tests
# ---------------------------------------------------------------------------

class TestClassifyPath:
    def test_classifies_yaml_as_config(self) -> None:
        assert classify_path("~/.hermes/config.yaml") == "config"

    def test_classifies_json_session(self) -> None:
        assert classify_path("~/.hermes/sessions/001.json") == "session"

    def test_classifies_log_file(self) -> None:
        assert classify_path("~/.hermes/logs/app.log") == "log"

    def test_classifies_db_file(self) -> None:
        assert classify_path("~/.hermes/state.db") == "database"

    def test_classifies_cache_dir(self) -> None:
        assert classify_path("~/.hermes/cache/") == "cache"

    def test_classifies_unknown(self) -> None:
        assert classify_path("~/.hermes/unknown.bin") == "unknown"


# ---------------------------------------------------------------------------
# discover_live_paths tests
# ---------------------------------------------------------------------------

class TestDiscoverLivePaths:
    def test_discover_respects_authoritative_flag(self, inventory_file: Path) -> None:
        inv = load_inventory(inventory_file)
        live = discover_live_paths(inv)
        for category, entries in live.items():
            for entry in entries:
                src = inv.sources.get(category, [])
                matching = [s for s in src if s.path == entry.path]
                if matching:
                    assert entry.exists == (matching[0].authoritative or Path(matching[0].expand_path()).exists())

    def test_discover_returns_source_entry_with_exists_field(self, inventory_file: Path) -> None:
        inv = load_inventory(inventory_file)
        live = discover_live_paths(inv)
        for category, entries in live.items():
            for entry in entries:
                assert hasattr(entry, "exists")
                assert isinstance(entry.exists, bool)

    def test_discover_on_fixture_inventory_reports_exists_correctly(self, inventory_file: Path) -> None:
        """The exists flag must match the actual filesystem state."""
        inv = load_inventory(inventory_file)
        live = discover_live_paths(inv)
        for category, entries in live.items():
            for entry in entries:
                expected = Path(entry.expand_path()).exists()
                assert entry.exists == expected, (
                    f"exists flag mismatch for {entry.path}: "
                    f"got {entry.exists}, expected {expected}"
                )

    def test_discover_categorizes_all_seven_phase0_types(self, inventory_file: Path) -> None:
        inv = load_inventory(inventory_file)
        live = discover_live_paths(inv)
        assert set(live.keys()) == {"config", "session", "log", "cache", "db", "runtime", "gateway"}

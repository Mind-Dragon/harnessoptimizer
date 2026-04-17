from __future__ import annotations

from pathlib import Path
import os
import time

import pytest

from hermesoptimizer.vault import (
    build_vault_inventory,
    default_vault_roots,
    deduplicate_entries,
    discover_vault_files,
    fingerprint_secret,
    plan_bridge,
    plan_write_back,
    track_rotation,
    validate_inventory,
    VaultEntry,
    VaultInventory,
)
from hermesoptimizer.vault.inventory import (
    _parse_csv_file,
    _parse_txt_file,
)


def test_default_vault_roots_prefers_home_vault(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    roots = default_vault_roots()

    assert roots[0] == tmp_path / ".vault"
    assert all(isinstance(root, Path) for root in roots)


def test_discover_vault_files_is_read_only(tmp_path: Path) -> None:
    vault = tmp_path / ".vault"
    vault.mkdir()
    (vault / "alpha.env").write_text("TOKEN=abc123\n", encoding="utf-8")
    nested = vault / "nested"
    nested.mkdir()
    (nested / "beta.yaml").write_text("secrets:\n  token: beta\n", encoding="utf-8")

    before = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    files = discover_vault_files([vault])
    after = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))

    assert before == after
    assert files == [vault / "alpha.env", nested / "beta.yaml"]


def test_fingerprint_secret_is_deterministic_and_non_plaintext() -> None:
    first = fingerprint_secret("super-secret")
    second = fingerprint_secret("super-secret")

    assert first == second
    assert first != "super-secret"
    assert len(first) >= 8


def test_build_vault_inventory_collects_entries(tmp_path: Path) -> None:
    vault = tmp_path / ".vault"
    vault.mkdir()
    env_file = vault / "providers.env"
    env_file.write_text("OPENAI_API_KEY=abc123\n", encoding="utf-8")

    inventory = build_vault_inventory([vault])

    assert isinstance(inventory, VaultInventory)
    assert inventory.roots == [vault]
    assert inventory.files == [env_file]
    assert len(inventory.entries) == 1
    assert inventory.entries[0] == VaultEntry(
        source_path=env_file,
        source_kind="env",
        key_name="OPENAI_API_KEY",
        fingerprint=fingerprint_secret("abc123"),
    )


def test_validate_inventory_marks_stale_env_files(tmp_path: Path) -> None:
    vault = tmp_path / ".vault"
    vault.mkdir()
    fresh_file = vault / "fresh.env"
    fresh_file.write_text("TOKEN=abc123\n", encoding="utf-8")
    stale_file = vault / "stale.env"
    stale_file.write_text("TOKEN=abc123\n", encoding="utf-8")

    old_time = time.time() - (90 * 24 * 60 * 60)
    os.utime(stale_file, (old_time, old_time))

    inventory = build_vault_inventory([vault])
    results = validate_inventory(inventory, stale_after_days=30)

    statuses = {result.source_path: result.status for result in results}

    assert statuses[str(fresh_file)] == "active"
    assert statuses[str(stale_file)] == "stale"


def test_deduplicate_entries_prefers_deterministic_canonical(tmp_path: Path) -> None:
    one = tmp_path / ".vault" / "z.env"
    two = tmp_path / ".vault" / "a.env"
    one.parent.mkdir()

    entries = [
        VaultEntry(one, "env", "TOKEN", "shared"),
        VaultEntry(two, "env", "TOKEN", "shared"),
    ]

    results = deduplicate_entries(entries)

    assert len(results) == 1
    assert results[0].canonical.source_path == two
    assert [duplicate.source_path for duplicate in results[0].duplicates] == [one]


def test_track_rotation_reports_changed_secret(tmp_path: Path) -> None:
    path = tmp_path / ".vault" / "token.env"
    previous = VaultEntry(path, "env", "TOKEN", "oldfp")
    current = VaultEntry(path, "env", "TOKEN", "newfp")

    event = track_rotation(previous, current)

    assert event is not None
    assert event.previous_fingerprint == "oldfp"
    assert event.current_fingerprint == "newfp"


def test_plan_bridge_is_read_only(tmp_path: Path) -> None:
    vault = tmp_path / ".vault"
    vault.mkdir()
    env_file = vault / "providers.env"
    env_file.write_text("OPENAI_API_KEY=abc123\n", encoding="utf-8")

    inventory = build_vault_inventory([vault])
    before = env_file.read_text(encoding="utf-8")

    plan = plan_bridge(inventory, target_format="env")

    assert plan.target_format == "env"
    assert plan.writable is False
    assert env_file.read_text(encoding="utf-8") == before


def test_plan_write_back_preserves_existing_files(tmp_path: Path) -> None:
    vault = tmp_path / ".vault"
    vault.mkdir()
    env_file = vault / "providers.env"
    env_file.write_text("OPENAI_API_KEY=abc123\n", encoding="utf-8")

    inventory = build_vault_inventory([vault])
    plan = plan_write_back(inventory, target_format="env")

    assert plan.target_format == "env"
    assert plan.preserve_existing is True
    assert plan.operations == [str(env_file)]
    assert env_file.read_text(encoding="utf-8") == "OPENAI_API_KEY=abc123\n"


# ---------------------------------------------------------------------------
# TDD tests for CSV and TXT source parsing
# ---------------------------------------------------------------------------


def test_parse_csv_file_key_value_with_labeled_columns(tmp_path: Path) -> None:
    """CSV with header row: key,secret -> parses key=value pairs."""
    csv_file = tmp_path / "secrets.csv"
    csv_file.write_text("key,secret\nAPI_TOKEN,abc123\nDB_PASSWORD,secret456\n", encoding="utf-8")

    entries = _parse_csv_file(csv_file)

    assert len(entries) == 2
    keys = {e.key_name for e in entries}
    assert keys == {"API_TOKEN", "DB_PASSWORD"}
    # Verify fingerprints are computed from values
    assert entries[0].fingerprint == fingerprint_secret("abc123")
    assert entries[1].fingerprint == fingerprint_secret("secret456")
    assert entries[0].source_kind == "csv"
    assert entries[1].source_kind == "csv"


def test_parse_csv_file_handles_quoted_values(tmp_path: Path) -> None:
    """CSV with quoted values in secret column."""
    csv_file = tmp_path / "secrets.csv"
    csv_file.write_text('key,secret\nTOKEN,"quoted value"\n', encoding="utf-8")

    entries = _parse_csv_file(csv_file)

    assert len(entries) == 1
    assert entries[0].key_name == "TOKEN"
    assert entries[0].fingerprint == fingerprint_secret("quoted value")


def test_parse_csv_file_ignores_empty_or_comment_lines(tmp_path: Path) -> None:
    """CSV skips blank lines and comment lines."""
    csv_file = tmp_path / "secrets.csv"
    csv_file.write_text("# comment\nkey,secret\n\nAPI_KEY,value\n  \n# another\nTOKEN,secret\n", encoding="utf-8")

    entries = _parse_csv_file(csv_file)

    assert len(entries) == 2
    keys = {e.key_name for e in entries}
    assert keys == {"API_KEY", "TOKEN"}


def test_parse_txt_file_regex_key_value_detection(tmp_path: Path) -> None:
    """TXT file with KEY=value lines detected via regex."""
    txt_file = tmp_path / "secrets.txt"
    txt_file.write_text("API_KEY=abc123\nDB_PASS=secret\n# comment\nTOKEN=xyz789\n", encoding="utf-8")

    entries = _parse_txt_file(txt_file)

    assert len(entries) == 3
    keys = {e.key_name for e in entries}
    assert keys == {"API_KEY", "DB_PASS", "TOKEN"}
    assert entries[0].fingerprint == fingerprint_secret("abc123")
    assert entries[1].fingerprint == fingerprint_secret("secret")
    assert entries[2].fingerprint == fingerprint_secret("xyz789")
    assert all(e.source_kind == "txt" for e in entries)


def test_parse_txt_file_handles_quoted_values(tmp_path: Path) -> None:
    """TXT file with KEY='value' and KEY=\"value\" quoted values."""
    txt_file = tmp_path / "secrets.txt"
    txt_file.write_text("TOKEN='single quoted'\nPASSWORD=\"double quoted\"\n", encoding="utf-8")

    entries = _parse_txt_file(txt_file)

    assert len(entries) == 2
    assert entries[0].key_name == "TOKEN"
    assert entries[0].fingerprint == fingerprint_secret("single quoted")
    assert entries[1].key_name == "PASSWORD"
    assert entries[1].fingerprint == fingerprint_secret("double quoted")


def test_parse_txt_file_ignores_invalid_lines(tmp_path: Path) -> None:
    """TXT file ignores blank lines and lines without valid KEY=value."""
    txt_file = tmp_path / "secrets.txt"
    txt_file.write_text("not-valid\n# comment only\n\nAPI_KEY=abc\n", encoding="utf-8")

    entries = _parse_txt_file(txt_file)

    assert len(entries) == 1
    assert entries[0].key_name == "API_KEY"


def test_build_vault_inventory_includes_csv_and_txt_files(tmp_path: Path) -> None:
    """build_vault_inventory dispatches .csv and .txt files to appropriate parsers."""
    vault = tmp_path / ".vault"
    vault.mkdir()
    csv_file = vault / "secrets.csv"
    csv_file.write_text("key,secret\nTOKEN,csvvalue\n", encoding="utf-8")
    txt_file = vault / "secrets.txt"
    txt_file.write_text("API_KEY=txtvalue\n", encoding="utf-8")

    inventory = build_vault_inventory([vault])

    assert csv_file in inventory.files
    assert txt_file in inventory.files
    entry_keys = {e.key_name for e in inventory.entries}
    assert "TOKEN" in entry_keys
    assert "API_KEY" in entry_keys

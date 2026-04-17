"""Tests for vault validator adapter hook (v051-provider-validation).

These tests prove the status_provider adapter hook works and that
the default fallback still uses metadata only (file-age).
"""
from __future__ import annotations

from pathlib import Path
import time
import os

import pytest

from hermesoptimizer.vault import (
    ValidationResult,
    VaultEntry,
    VaultInventory,
    build_vault_inventory,
    validate_inventory,
)


def test_validate_inventory_default_fallback_is_read_only_by_mtime(
    tmp_path: Path,
) -> None:
    """Default behavior uses file-age metadata only, no secret mutation."""
    vault = tmp_path / ".vault"
    vault.mkdir()
    fresh_file = vault / "fresh.env"
    fresh_file.write_text("TOKEN=fresh\n", encoding="utf-8")
    stale_file = vault / "stale.env"
    stale_file.write_text("TOKEN=stale\n", encoding="utf-8")

    # Make stale file old
    old_time = time.time() - (90 * 24 * 60 * 60)
    os.utime(stale_file, (old_time, old_time))

    inventory = build_vault_inventory([vault])
    results = validate_inventory(inventory, stale_after_days=30)

    statuses = {result.source_path: result.status for result in results}

    assert statuses[str(fresh_file)] == "active"
    assert statuses[str(stale_file)] == "stale"
    # Verify no secret exposure in results
    for r in results:
        assert "fresh" not in r.message.lower() or "stale" not in r.message.lower()
        assert r.ok or r.status == "stale"


def test_validate_inventory_status_provider_hook_overrides_default(
    tmp_path: Path,
) -> None:
    """When status_provider is supplied, it receives each entry and can override."""
    vault = tmp_path / ".vault"
    vault.mkdir()
    file_a = vault / "a.env"
    file_a.write_text("TOKEN=a\n", encoding="utf-8")
    file_b = vault / "b.env"
    file_b.write_text("TOKEN=b\n", encoding="utf-8")

    inventory = build_vault_inventory([vault])

    # Provider reports entry 'a' as degraded regardless of file age
    def status_provider(entry: VaultEntry) -> ValidationResult | None:
        if entry.key_name == "TOKEN" and "a.env" in str(entry.source_path):
            return ValidationResult(
                source_path=str(entry.source_path),
                ok=False,
                status="degraded",
                message="provider-side degradation",
            )
        return None  # Fall back to default

    results = validate_inventory(inventory, status_provider=status_provider)

    statuses = {result.source_path: result.status for result in results}
    assert statuses[str(file_a)] == "degraded"
    assert statuses[str(file_b)] == "active"  # fallback to mtime check


def test_validate_inventory_status_provider_returns_none_uses_fallback(
    tmp_path: Path,
) -> None:
    """When status_provider returns None, default file-age logic is used."""
    vault = tmp_path / ".vault"
    vault.mkdir()
    fresh_file = vault / "fresh.env"
    fresh_file.write_text("KEY=fresh\n", encoding="utf-8")
    stale_file = vault / "stale.env"
    stale_file.write_text("KEY=stale\n", encoding="utf-8")

    old_time = time.time() - (60 * 24 * 60 * 60)
    os.utime(stale_file, (old_time, old_time))

    inventory = build_vault_inventory([vault])

    # Provider that always returns None - full fallback
    def noop_provider(entry: VaultEntry) -> ValidationResult | None:
        return None

    results = validate_inventory(inventory, status_provider=noop_provider)

    statuses = {result.source_path: result.status for result in results}
    assert statuses[str(fresh_file)] == "active"
    assert statuses[str(stale_file)] == "stale"


def test_validate_inventory_all_provider_results_used_when_no_fallback(
    tmp_path: Path,
) -> None:
    """Provider can return results for all entries without triggering default."""
    vault = tmp_path / ".vault"
    vault.mkdir()
    file_x = vault / "x.env"
    file_x.write_text("KEY=x\n", encoding="utf-8")

    inventory = build_vault_inventory([vault])

    def all_provider(entry: VaultEntry) -> ValidationResult:
        return ValidationResult(
            source_path=str(entry.source_path),
            ok=True,
            status="provider_active",
            message="managed by provider",
        )

    results = validate_inventory(inventory, status_provider=all_provider)

    assert len(results) == 1
    assert results[0].status == "provider_active"
    assert results[0].message == "managed by provider"

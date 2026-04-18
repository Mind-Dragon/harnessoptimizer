"""TDD tests for vault fingerprint upgrade from 12 to 20 hex characters.

These tests verify:
1. fingerprint_secret() returns 'fp20:' + 20 hex chars (total 25 chars)
2. migrate_fingerprint() converts old 12-char fingerprints to new format
3. dedup.py handles mixed fp12/fp20 fingerprints
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from hermesoptimizer.vault.dedup import deduplicate_entries
from hermesoptimizer.vault.fingerprint import fingerprint_secret, migrate_fingerprint


class TestFingerprintSecret:
    """Tests for upgraded fingerprint_secret() returning fp20: prefix."""

    def test_fingerprint_is_20_chars_with_prefix(self) -> None:
        """fingerprint_secret should return a 25-char string: 'fp20:' + 20 hex chars."""
        fp = fingerprint_secret("my_secret")
        assert len(fp) == 25, f"Expected 25 chars, got {len(fp)}: {fp}"

    def test_fingerprint_starts_with_fp20(self) -> None:
        """fingerprint_secret should return a string starting with 'fp20:'."""
        fp = fingerprint_secret("my_secret")
        assert fp.startswith("fp20:"), f"Expected 'fp20:' prefix, got: {fp}"

    def test_fingerprint_hex_portion_is_20_chars(self) -> None:
        """The hex portion after 'fp20:' should be exactly 20 hex characters."""
        fp = fingerprint_secret("test_secret")
        hex_portion = fp[5:]  # after 'fp20:'
        assert len(hex_portion) == 20, f"Expected 20 hex chars, got {len(hex_portion)}"
        assert all(c in "0123456789abcdef" for c in hex_portion), f"Non-hex chars in: {hex_portion}"

    def test_same_secret_produces_same_fingerprint(self) -> None:
        """Same secret should always produce the same fingerprint."""
        fp1 = fingerprint_secret("consistent_secret")
        fp2 = fingerprint_secret("consistent_secret")
        assert fp1 == fp2

    def test_different_secrets_produce_different_fingerprints(self) -> None:
        """Different secrets should produce different fingerprints."""
        fp1 = fingerprint_secret("secret_one")
        fp2 = fingerprint_secret("secret_two")
        assert fp1 != fp2


class TestMigrateFingerprint:
    """Tests for migrate_fingerprint() converting old 12-char fingerprints."""

    def test_migrate_legacy_fingerprint(self) -> None:
        """migrate_fingerprint should convert old 12-char fingerprints with 'fp12:' prefix."""
        old_fp = "a1b2c3d4e5f6"  # 12 hex chars
        migrated = migrate_fingerprint(old_fp)
        assert migrated.startswith("fp12:"), f"Expected 'fp12:' prefix, got: {migrated}"
        assert "a1b2c3d4e5f6" in migrated

    def test_migrate_fp20_fingerprint_passthrough(self) -> None:
        """New fp20 fingerprints should pass through unchanged."""
        new_fp = "fp20:a1b2c3d4e5f6a1b2c3d4e5"
        migrated = migrate_fingerprint(new_fp)
        assert migrated == new_fp

    def test_migrate_fp12_fingerprint_passthrough(self) -> None:
        """Already migrated fp12 fingerprints should pass through unchanged."""
        old_migrated = "fp12:a1b2c3d4e5f6"
        migrated = migrate_fingerprint(old_migrated)
        assert migrated == old_migrated

    def test_migrate_unknown_format_legacy(self) -> None:
        """Unknown format fingerprints should be treated as legacy fp12."""
        unknown_fp = "z1y2x3w4v5u6"  # doesn't start with fp20: or fp12:
        migrated = migrate_fingerprint(unknown_fp)
        assert migrated.startswith("fp12:")


class TestDedupMixedFingerprints:
    """Tests for deduplicate_entries() handling mixed fp12/fp20 fingerprints."""

    @dataclass(frozen=True, slots=True)
    class MockVaultEntry:
        source_path: Path
        source_kind: str
        key_name: str
        fingerprint: str

    def test_dedup_handles_mixed_fingerprint_formats(self) -> None:
        """Entries with fp12 and fp20 versions of same secret should not be mixed."""
        # Same logical secret, but different fingerprint formats
        entry_fp12 = self.MockVaultEntry(
            source_path=Path("/vault/.env"),
            source_kind="env",
            key_name="API_KEY",
            fingerprint="fp12:a1b2c3d4e5f6",
        )
        entry_fp20 = self.MockVaultEntry(
            source_path=Path("/vault/.env"),
            source_kind="env",
            key_name="API_KEY",
            fingerprint="fp20:a1b2c3d4e5f6a1b2c3d4e5",
        )

        # These are the same secret but different formats - should NOT be deduplicated
        # because they have different fingerprint values
        results = deduplicate_entries([entry_fp12, entry_fp20])

        # Since fingerprints are different strings, they go into different groups
        assert len(results) == 2

    def test_dedup_groups_same_fp20_fingerprints(self) -> None:
        """Entries with identical fp20 fingerprints should be deduplicated."""
        entry1 = self.MockVaultEntry(
            source_path=Path("/vault/.env"),
            source_kind="env",
            key_name="API_KEY",
            fingerprint="fp20:a1b2c3d4e5f6a1b2c3d4e5",
        )
        entry2 = self.MockVaultEntry(
            source_path=Path("/vault/other.env"),
            source_kind="env",
            key_name="API_KEY",
            fingerprint="fp20:a1b2c3d4e5f6a1b2c3d4e5",
        )

        results = deduplicate_entries([entry1, entry2])

        assert len(results) == 1
        assert len(results[0].duplicates) == 1
        assert results[0].canonical.source_path == Path("/vault/.env")

    def test_dedup_groups_same_fp12_fingerprints(self) -> None:
        """Entries with identical fp12 fingerprints should be deduplicated."""
        entry1 = self.MockVaultEntry(
            source_path=Path("/vault/.env"),
            source_kind="env",
            key_name="API_KEY",
            fingerprint="fp12:a1b2c3d4e5f6",
        )
        entry2 = self.MockVaultEntry(
            source_path=Path("/vault/other.env"),
            source_kind="env",
            key_name="API_KEY",
            fingerprint="fp12:a1b2c3d4e5f6",
        )

        results = deduplicate_entries([entry1, entry2])

        assert len(results) == 1
        assert len(results[0].duplicates) == 1

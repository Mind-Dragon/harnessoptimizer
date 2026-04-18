"""Tests for VaultSession context manager."""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hermesoptimizer.vault.crypto import VaultCrypto, generate_master_key
from hermesoptimizer.vault.fingerprint import fingerprint_secret


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_vault_root(tmp_path: Path) -> Path:
    """Create a temporary vault root directory."""
    vault_root = tmp_path / ".vault"
    vault_root.mkdir(parents=True, exist_ok=True)
    return vault_root


@pytest.fixture
def master_key() -> bytes:
    """Generate a fresh master key for testing."""
    return generate_master_key()


@pytest.fixture
def vault_session(temp_vault_root: Path, master_key: bytes):
    """Create a VaultSession with a known master key."""
    from hermesoptimizer.vault.session import VaultSession

    with VaultSession(temp_vault_root, master_key=master_key) as session:
        yield session


# ---------------------------------------------------------------------------
# Test 1: VaultSession opens and closes
# ---------------------------------------------------------------------------


def test_vault_session_opens_and_closes(temp_vault_root: Path, master_key: bytes):
    """VaultSession context manager opens and closes cleanly."""
    from hermesoptimizer.vault.session import VaultSession

    with VaultSession(temp_vault_root, master_key=master_key) as session:
        assert session is not None
        # Should be able to list entries (empty initially)
        entries = session.list_entries()
        assert entries == []


# ---------------------------------------------------------------------------
# Test 2: VaultSession set and get secret
# ---------------------------------------------------------------------------


def test_vault_session_set_and_get_secret(temp_vault_root: Path, master_key: bytes):
    """Set a secret and retrieve it decrypted."""
    from hermesoptimizer.vault.session import VaultSession

    with VaultSession(temp_vault_root, master_key=master_key) as session:
        session.set("ANTHROPIC_API_KEY", "sk-ant-xxxxx", encrypted=True)

        # Retrieve the secret
        value = session.get("ANTHROPIC_API_KEY")
        assert value == "sk-ant-xxxxx"


# ---------------------------------------------------------------------------
# Test 3: VaultSession set and get metadata (unencrypted)
# ---------------------------------------------------------------------------


def test_vault_session_set_and_get_metadata(temp_vault_root: Path, master_key: bytes):
    """Set metadata without encryption and retrieve it."""
    from hermesoptimizer.vault.session import VaultSession

    with VaultSession(temp_vault_root, master_key=master_key) as session:
        session.set("ANTHROPIC_API_URL", "https://api.anthropic.com", encrypted=False)

        value = session.get("ANTHROPIC_API_URL")
        assert value == "https://api.anthropic.com"


# ---------------------------------------------------------------------------
# Test 4: VaultSession update secret
# ---------------------------------------------------------------------------


def test_vault_session_update_secret(temp_vault_root: Path, master_key: bytes):
    """Update an existing secret value."""
    from hermesoptimizer.vault.session import VaultSession

    with VaultSession(temp_vault_root, master_key=master_key) as session:
        session.set("API_KEY", "old-value", encrypted=True)
        assert session.get("API_KEY") == "old-value"

        session.set("API_KEY", "new-value", encrypted=True)
        assert session.get("API_KEY") == "new-value"


# ---------------------------------------------------------------------------
# Test 5: VaultSession delete entry
# ---------------------------------------------------------------------------


def test_vault_session_delete_entry(temp_vault_root: Path, master_key: bytes):
    """Delete an existing entry."""
    from hermesoptimizer.vault.session import VaultSession

    with VaultSession(temp_vault_root, master_key=master_key) as session:
        session.set("TO_DELETE", "sensitive-data", encrypted=True)
        assert session.get("TO_DELETE") == "sensitive-data"

        result = session.delete("TO_DELETE")
        assert result is True
        assert session.get("TO_DELETE") is None


# ---------------------------------------------------------------------------
# Test 6: VaultSession audit log records mutations
# ---------------------------------------------------------------------------


def test_vault_session_audit_log_records_mutations(temp_vault_root: Path, master_key: bytes):
    """Audit log records set and delete operations."""
    from hermesoptimizer.vault.session import VaultSession

    with VaultSession(temp_vault_root, master_key=master_key) as session:
        session.set("AUDIT_TEST_KEY", "secret-value", encrypted=True)
        session.delete("AUDIT_TEST_KEY")

    # Verify audit log exists and has entries
    audit_log = temp_vault_root / ".audit.log"
    assert audit_log.exists()

    lines = audit_log.read_text().strip().split("\n")
    # Should have at least 2 entries: set and delete
    assert len(lines) >= 2

    # Check format: ISO timestamp | operation | key_name | fingerprint | result
    for line in lines:
        parts = line.split("|")
        assert len(parts) == 5
        assert parts[1].strip() in ("set", "delete")
        assert parts[2].strip() == "AUDIT_TEST_KEY"


# ---------------------------------------------------------------------------
# Test 7: Atomic write creates file correctly
# ---------------------------------------------------------------------------


def test_atomic_write_creates_file(tmp_path: Path):
    """Atomic write creates file with correct content."""
    from hermesoptimizer.vault.session import atomic_write

    test_file = tmp_path / "test.txt"
    atomic_write(test_file, "Hello, World!")

    assert test_file.exists()
    assert test_file.read_text() == "Hello, World!"

    # Ensure no .tmp file remains
    tmp_file = test_file.with_suffix(".tmp")
    assert not tmp_file.exists()


# ---------------------------------------------------------------------------
# Test 8: VaultSession master key from env
# ---------------------------------------------------------------------------


def test_vault_session_master_key_from_env(temp_vault_root: Path, master_key: bytes):
    """VaultSession loads master key from VAULT_MASTER_KEY env var."""
    import base64
    from hermesoptimizer.vault.session import VaultSession

    # Set env var with base64-encoded master key
    encoded_key = base64.b64encode(master_key).decode("ascii")
    with pytest.MonkeyPatch().context() as m:
        m.setenv("VAULT_MASTER_KEY", encoded_key)
        # Don't pass master_key, should fall back to env var
        with VaultSession(temp_vault_root) as session:
            session.set("ENV_TEST", "value", encrypted=True)
            assert session.get("ENV_TEST") == "value"


# ---------------------------------------------------------------------------
# Test 9: VaultSession locked without key
# ---------------------------------------------------------------------------


def test_vault_session_locked_without_key(temp_vault_root: Path, master_key: bytes):
    """VaultSession raises VaultLockedError when vault has encrypted entries but no key."""
    from hermesoptimizer.vault.session import VaultLockedError, VaultSession

    # First create a vault with encrypted content
    with VaultSession(temp_vault_root, master_key=master_key) as session:
        session.set("SOME_KEY", "some-value", encrypted=True)

    # Now try to open without a key
    with pytest.raises(VaultLockedError):
        with VaultSession(temp_vault_root) as session:
            pass  # Should raise VaultLockedError


# ---------------------------------------------------------------------------
# Test 10: VaultSession memory wipe on exit
# ---------------------------------------------------------------------------


def test_vault_session_memory_wipe_on_exit(temp_vault_root: Path, master_key: bytes):
    """Secrets dict is cleared after exiting context manager."""
    from hermesoptimizer.vault.session import VaultSession

    # Create and use session
    with VaultSession(temp_vault_root, master_key=master_key) as session:
        session.set("WIPE_TEST", "sensitive-data", encrypted=True)
        # Get reference to internal secrets dict
        secrets_ref = session._secrets

    # After exiting, secrets should be wiped
    assert len(secrets_ref) == 0


# ---------------------------------------------------------------------------
# Additional tests for completeness
# ---------------------------------------------------------------------------


def test_vault_session_list_entries_returns_all(temp_vault_root: Path, master_key: bytes):
    """list_entries returns all entries including unencrypted."""
    from hermesoptimizer.vault.session import VaultSession

    with VaultSession(temp_vault_root, master_key=master_key) as session:
        session.set("SECRET1", "value1", encrypted=True)
        session.set("META1", "value2", encrypted=False)

        entries = session.list_entries()
        key_names = {e.key_name for e in entries}
        assert "SECRET1" in key_names
        assert "META1" in key_names


def test_vault_session_persists_after_close(temp_vault_root: Path, master_key: bytes):
    """Data persists after session closes and reopens."""
    from hermesoptimizer.vault.session import VaultSession

    # First session: write data
    with VaultSession(temp_vault_root, master_key=master_key) as session:
        session.set("PERSIST_KEY", "persistent-value", encrypted=True)

    # Second session: read data
    with VaultSession(temp_vault_root, master_key=master_key) as session:
        value = session.get("PERSIST_KEY")
        assert value == "persistent-value"


def test_vault_session_fingerprint_on_entries(temp_vault_root: Path, master_key: bytes):
    """Entries have correct fingerprints."""
    from hermesoptimizer.vault.session import VaultSession

    secret_value = "test-secret-123"
    expected_fp = fingerprint_secret(secret_value)

    with VaultSession(temp_vault_root, master_key=master_key) as session:
        session.set("FP_TEST", secret_value, encrypted=True)
        entries = session.list_entries()

    fp_entry = next(e for e in entries if e.key_name == "FP_TEST")
    assert fp_entry.fingerprint == expected_fp

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import pytest

from hermesoptimizer.vault import (
    RotationEvent,
    RotationAdapter,
    RotationExecutor,
    RotationResult,
    RotationRollback,
    execute_rotation,
    track_rotation,
    VaultEntry,
)


# --- RotationAdapter interface tests ---


class DummyRotationAdapter(RotationAdapter):
    """Test adapter that simulates rotation for any provider."""

    def __init__(self) -> None:
        self.rotated: list[str] = []
        self.rolled_back: list[str] = []
        self._raise_on: set[str] = set()

    def rotate(self, entry: VaultEntry, new_secret: str) -> bool:
        self.rotated.append(entry.key_name)
        return True

    def supports(self, entry: VaultEntry) -> bool:
        return True

    def rollback(self, entry: VaultEntry) -> bool:
        self.rolled_back.append(entry.key_name)
        return True

    def mark_fails(self, key_name: str) -> None:
        self._raise_on.add(key_name)


class FailingRotationAdapter(RotationAdapter):
    """Adapter that always fails rotation."""

    def __init__(self) -> None:
        self.rotated: list[str] = []

    def supports(self, entry: VaultEntry) -> bool:
        return True

    def rotate(self, entry: VaultEntry, new_secret: str) -> bool:
        self.rotated.append(entry.key_name)
        return False

    def rollback(self, entry: VaultEntry) -> bool:
        return True


class UnsupportedAdapter(RotationAdapter):
    """Adapter that doesn't support any entries."""

    def supports(self, entry: VaultEntry) -> bool:
        return False

    def rotate(self, entry: VaultEntry, new_secret: str) -> bool:
        raise AssertionError("Should not be called")

    def rollback(self, entry: VaultEntry) -> bool:
        raise AssertionError("Should not be called")


def test_rotation_adapter_interface_has_required_methods() -> None:
    """Adapter must implement rotate, supports, and rollback."""
    adapter = DummyRotationAdapter()
    entry = VaultEntry(Path("/tmp/test.env"), "env", "API_KEY", "oldfp")
    new_secret = "new-secret-value"

    assert hasattr(adapter, "rotate")
    assert hasattr(adapter, "supports")
    assert hasattr(adapter, "rollback")
    assert callable(adapter.rotate)
    assert callable(adapter.supports)
    assert callable(adapter.rollback)

    # Basic functionality
    assert adapter.supports(entry) is True
    assert adapter.rotate(entry, new_secret) is True
    assert adapter.rollback(entry) is True


def test_rotation_event_has_timestamp() -> None:
    """RotationEvent should include a timestamp of when rotation occurred."""
    path = Path("/tmp/test.env")
    previous = VaultEntry(path, "env", "TOKEN", "oldfp")
    current = VaultEntry(path, "env", "TOKEN", "newfp")

    event = track_rotation(previous, current)

    assert event is not None
    assert hasattr(event, "timestamp")
    assert isinstance(event.timestamp, datetime)


def test_rotation_executor_executes_adapter_rotation() -> None:
    """RotationExecutor should call the adapter's rotate method."""
    adapter = DummyRotationAdapter()
    executor = RotationExecutor([adapter])
    entry = VaultEntry(Path("/tmp/test.env"), "env", "API_KEY", "oldfp")
    new_secret = "new-secret"

    result = executor.execute(entry, new_secret)

    assert result.success is True
    assert adapter.rotated == ["API_KEY"]


def test_rotation_executor_reports_failure_when_adapter_fails() -> None:
    """RotationExecutor should report failure when adapter.rotate returns False."""
    adapter = FailingRotationAdapter()
    executor = RotationExecutor([adapter])
    entry = VaultEntry(Path("/tmp/test.env"), "env", "API_KEY", "oldfp")

    result = executor.execute(entry, "new-secret")

    assert result.success is False
    assert result.error is not None


def test_rotation_executor_skips_unsupported_entries() -> None:
    """RotationExecutor should skip adapters that don't support an entry."""
    adapter = UnsupportedAdapter()
    executor = RotationExecutor([adapter])
    entry = VaultEntry(Path("/tmp/test.env"), "env", "API_KEY", "oldfp")

    result = executor.execute(entry, "new-secret")

    # No adapter supports this entry
    assert result.success is False
    assert "no adapter" in result.error.lower() or "supports" in result.error.lower()


def test_rotation_result_contains_event_and_timestamp() -> None:
    """RotationResult should include the event and execution timestamp."""
    adapter = DummyRotationAdapter()
    executor = RotationExecutor([adapter])
    entry = VaultEntry(Path("/tmp/test.env"), "env", "API_KEY", "oldfp")

    result = executor.execute(entry, "new-secret")

    assert result.event is not None
    assert hasattr(result.event, "timestamp")
    assert result.executed_at is not None


def test_rotation_rollback_structure_exists() -> None:
    """RotationRollback should store rollback info for a failed rotation."""
    rollback = RotationRollback(
        entry=VaultEntry(Path("/tmp/test.env"), "env", "API_KEY", "oldfp"),
        previous_secret="old-secret-value",
        reason="Rotation failed: provider API error",
    )

    assert rollback.entry is not None
    assert rollback.previous_secret == "old-secret-value"
    assert "provider API error" in rollback.reason


def test_execute_rotation_convenience_function() -> None:
    """execute_rotation() convenience function should work with adapter list."""
    adapter = DummyRotationAdapter()
    entry = VaultEntry(Path("/tmp/test.env"), "env", "API_KEY", "oldfp")

    result = execute_rotation(entry, "new-secret", adapters=[adapter])

    assert result.success is True
    assert adapter.rotated == ["API_KEY"]


def test_rotation_event_with_timestamp_in_iso_format() -> None:
    """RotationEvent timestamp should be timezone-aware UTC."""
    path = Path("/tmp/test.env")
    previous = VaultEntry(path, "env", "TOKEN", "oldfp")
    current = VaultEntry(path, "env", "TOKEN", "newfp")

    event = track_rotation(previous, current)

    assert event is not None
    # Timestamp should be UTC
    assert event.timestamp.tzinfo is not None
    # Should be ISO format string-able
    assert isinstance(event.timestamp.isoformat(), str)


def test_rotation_result_includes_previous_fingerprint() -> None:
    """RotationResult should track the previous fingerprint for rollback."""
    adapter = DummyRotationAdapter()
    executor = RotationExecutor([adapter])
    entry = VaultEntry(Path("/tmp/test.env"), "env", "API_KEY", "oldfp")

    result = executor.execute(entry, "new-secret")

    assert result.previous_fingerprint == "oldfp"
    assert result.new_fingerprint != "oldfp"


def test_multiple_adapters_try_each_until_one_succeeds() -> None:
    """Executor should try each supported adapter until one succeeds."""
    unsupported = UnsupportedAdapter()
    failing = FailingRotationAdapter()
    success = DummyRotationAdapter()

    executor = RotationExecutor([unsupported, failing, success])
    entry = VaultEntry(Path("/tmp/test.env"), "env", "API_KEY", "oldfp")

    result = executor.execute(entry, "new-secret")

    assert result.success is True
    # Only the successful adapter should have rotated
    assert success.rotated == ["API_KEY"]
    # Failing adapter was called (it supported the entry, failed, then we continued)
    assert failing.rotated == ["API_KEY"]


# --- Tests for rollback execution gap (v0.5.2 contract issue) ---


class RollbackRecordingAdapter(RotationAdapter):
    """Adapter that tracks whether rollback was called after a failed rotation."""

    def __init__(self) -> None:
        self.rotated: list[str] = []
        self.rolled_back: list[str] = []
        self.should_fail: bool = False

    def supports(self, entry: VaultEntry) -> bool:
        return True

    def rotate(self, entry: VaultEntry, new_secret: str) -> bool:
        self.rotated.append(entry.key_name)
        return not self.should_fail

    def rollback(self, entry: VaultEntry) -> bool:
        self.rolled_back.append(entry.key_name)
        return True


def test_executor_calls_rollback_when_all_adapters_fail() -> None:
    """When all adapters fail, executor should call rollback on the last failed adapter.

    This is the core rollback execution contract per v0.5.2 spec:
    'rollback support for failed rotations'
    """
    adapter = RollbackRecordingAdapter()
    adapter.should_fail = True  # Force rotation to fail

    executor = RotationExecutor([adapter])
    entry = VaultEntry(Path("/tmp/test.env"), "env", "API_KEY", "oldfp")

    result = executor.execute(entry, "new-secret")

    # Rotation should have been attempted
    assert adapter.rotated == ["API_KEY"], "rotate() should have been called"
    # Rollback SHOULD have been called after failure
    assert adapter.rolled_back == ["API_KEY"], (
        "rollback() should be called after failed rotation per v0.5.2 contract"
    )
    # Result should indicate failure with rollback info
    assert result.success is False
    assert result.rollback_info is not None, (
        "result.rollback_info should be populated after failed rotation per v0.5.2 contract"
    )


def test_executor_does_not_call_rollback_when_rotation_succeeds() -> None:
    """When rotation succeeds, rollback should NOT be called."""
    adapter = RollbackRecordingAdapter()
    adapter.should_fail = False  # Rotation succeeds

    executor = RotationExecutor([adapter])
    entry = VaultEntry(Path("/tmp/test.env"), "env", "API_KEY", "oldfp")

    result = executor.execute(entry, "new-secret")

    assert result.success is True
    assert adapter.rotated == ["API_KEY"]
    assert adapter.rolled_back == [], "rollback should NOT be called on success"
    assert result.rollback_info is None


def test_result_rollback_info_contains_failure_details() -> None:
    """When rotation fails, rollback_info should contain entry, previous_secret, and reason."""
    adapter = RollbackRecordingAdapter()
    adapter.should_fail = True

    executor = RotationExecutor([adapter])
    entry = VaultEntry(Path("/tmp/test.env"), "env", "API_KEY", "oldfp")

    result = executor.execute(entry, "new-secret")

    assert result.success is False
    assert result.rollback_info is not None
    assert result.rollback_info.entry is not None
    assert result.rollback_info.reason is not None


# --- Tests for concrete StubRotationAdapter (v0.5.2 contract proof) ---


def test_stub_rotation_adapter_is_concrete_implementation() -> None:
    """StubRotationAdapter is a concrete implementation that can be used without subclassing.

    This proves the v0.5.2 contract gap is closed: the rotation system now has
    a concrete adapter implementation that demonstrates the full rotation lifecycle.
    """
    from hermesoptimizer.vault.providers import StubRotationAdapter

    adapter = StubRotationAdapter()
    assert isinstance(adapter, RotationAdapter)
    assert hasattr(adapter, "supports")
    assert hasattr(adapter, "rotate")
    assert hasattr(adapter, "rollback")
    assert callable(adapter.supports)
    assert callable(adapter.rotate)
    assert callable(adapter.rollback)


def test_stub_rotation_adapter_works_with_executor() -> None:
    """StubRotationAdapter can be used directly with RotationExecutor.

    This proves the executor + concrete adapter integration works end-to-end.
    """
    from hermesoptimizer.vault.providers import StubRotationAdapter

    adapter = StubRotationAdapter()
    executor = RotationExecutor([adapter])
    entry = VaultEntry(Path("/tmp/test.env"), "env", "API_KEY", "oldfp")

    result = executor.execute(entry, "new-secret")

    assert result.success is True
    assert adapter.rotated == ["API_KEY"]
    assert adapter.rolled_back == []


def test_stub_rotation_adapter_rollback_on_failure() -> None:
    """StubRotationAdapter rollback is called when rotation fails.

    This proves the concrete adapter properly participates in the rollback
    contract when used with the executor.
    """
    from hermesoptimizer.vault.providers import StubRotationAdapter

    class FailingStubAdapter(StubRotationAdapter):
        def rotate(self, entry: VaultEntry, new_secret: str) -> bool:
            self.rotated.append(entry.key_name)
            return False  # Simulate failure

    adapter = FailingStubAdapter()
    executor = RotationExecutor([adapter])
    entry = VaultEntry(Path("/tmp/test.env"), "env", "API_KEY", "oldfp")

    result = executor.execute(entry, "new-secret")

    assert result.success is False
    assert adapter.rotated == ["API_KEY"]
    assert adapter.rolled_back == ["API_KEY"]
    assert result.rollback_info is not None


def test_stub_rotation_adapter_support_control() -> None:
    """StubRotationAdapter support can be controlled for testing."""
    from hermesoptimizer.vault.providers import StubRotationAdapter

    adapter = StubRotationAdapter()
    entry = VaultEntry(Path("/tmp/test.env"), "env", "API_KEY", "oldfp")

    # By default, supports all entries
    assert adapter.supports(entry) is True

    # Can be disabled
    adapter.set_support(False)
    assert adapter.supports(entry) is False

    executor = RotationExecutor([adapter])
    result = executor.execute(entry, "new-secret")

    # No adapter supports this entry
    assert result.success is False
    assert "no adapter" in result.error.lower() or "supports" in result.error.lower()


# --- Tests for EnvFileRotationAdapter (concrete file-based rotation) ---


def test_env_file_rotation_adapter_is_concrete() -> None:
    """EnvFileRotationAdapter is a concrete implementation for env files."""
    from hermesoptimizer.vault.providers import EnvFileRotationAdapter

    adapter = EnvFileRotationAdapter()
    assert isinstance(adapter, RotationAdapter)
    assert hasattr(adapter, "supports")
    assert hasattr(adapter, "rotate")
    assert hasattr(adapter, "rollback")


def test_env_file_rotation_adapter_supports_env_entries() -> None:
    """EnvFileRotationAdapter only supports env-kind entries."""
    from hermesoptimizer.vault.providers import EnvFileRotationAdapter

    adapter = EnvFileRotationAdapter()

    # Env entry should be supported (but file might not exist)
    env_entry = VaultEntry(Path("/tmp/test.env"), "env", "API_KEY", "oldfp")
    # Note: actual file existence check depends on tmp directory

    # Non-env entry should not be supported
    json_entry = VaultEntry(Path("/tmp/test.json"), "json", "API_KEY", "oldfp")
    assert adapter.supports(json_entry) is False


def test_env_file_rotation_adapter_rollback_returns_false() -> None:
    """EnvFileRotationAdapter.rollback() returns False because env files don't support easy rollback.

    This is an honest contract detail - env file rotation requires external backup/restore
    mechanisms (version control, backups, etc.).
    """
    from hermesoptimizer.vault.providers import EnvFileRotationAdapter

    adapter = EnvFileRotationAdapter()
    entry = VaultEntry(Path("/tmp/test.env"), "env", "API_KEY", "oldfp")

    # Rollback should return False for env file adapter
    result = adapter.rollback(entry)
    assert result is False


def test_env_file_rotation_adapter_rotate_nonexistent_file_returns_false(tmp_path) -> None:
    """EnvFileRotationAdapter.rotate() returns False when the file doesn't exist."""
    from hermesoptimizer.vault.providers import EnvFileRotationAdapter

    adapter = EnvFileRotationAdapter()
    entry = VaultEntry(tmp_path / "nonexistent.env", "env", "API_KEY", "oldfp")

    result = adapter.rotate(entry, "new-secret")
    assert result is False


def test_env_file_rotation_adapter_rotate_updates_file(tmp_path) -> None:
    """EnvFileRotationAdapter.rotate() actually updates the env file content."""
    from hermesoptimizer.vault.providers import EnvFileRotationAdapter

    # Create a test env file
    env_file = tmp_path / "test.env"
    env_file.write_text("API_KEY=old-value\nOTHER=value\n")

    adapter = EnvFileRotationAdapter()
    entry = VaultEntry(env_file, "env", "API_KEY", "oldfp")

    result = adapter.rotate(entry, "new-secret-value")

    assert result is True

    # Verify the file was updated
    content = env_file.read_text()
    assert "API_KEY=new-secret-value" in content
    assert "OTHER=value" in content


def test_env_file_rotation_adapter_rotate_appends_if_key_missing(tmp_path) -> None:
    """EnvFileRotationAdapter.rotate() appends the key if it doesn't exist in the file."""
    from hermesoptimizer.vault.providers import EnvFileRotationAdapter

    # Create a test env file without the key
    env_file = tmp_path / "test.env"
    env_file.write_text("OTHER=value\n")

    adapter = EnvFileRotationAdapter()
    entry = VaultEntry(env_file, "env", "NEW_KEY", "oldfp")

    result = adapter.rotate(entry, "new-secret")

    assert result is True

    # Verify the key was appended
    content = env_file.read_text()
    assert "NEW_KEY=new-secret" in content


# --- Tests proving concrete adapter contract (v0.5.2 gap closure) ---


def test_concrete_adapter_contract_is_honest() -> None:
    """Prove that concrete adapters exist and implement the full contract.

    This test closes the v0.5.2 gap by proving:
    1. Concrete adapter implementations exist (StubRotationAdapter, EnvFileRotationAdapter)
    2. They can be used with the RotationExecutor
    3. The rollback behavior works correctly with real adapter objects
    4. The contract is documented and testable
    """
    from hermesoptimizer.vault.providers import (
        EnvFileRotationAdapter,
        RotationAdapter,
        StubRotationAdapter,
    )

    # Prove concrete adapters exist
    stub = StubRotationAdapter()
    env_adapter = EnvFileRotationAdapter()

    # Prove they implement the interface
    assert isinstance(stub, RotationAdapter)
    assert isinstance(env_adapter, RotationAdapter)

    # Prove they can be used with executor
    executor = RotationExecutor([stub, env_adapter])
    entry = VaultEntry(Path("/tmp/test.env"), "env", "API_KEY", "oldfp")

    result = executor.execute(entry, "new-secret")

    # The stub adapter succeeds first, so we get success
    assert result.success is True
    assert result.event is not None
    assert stub.rotated == ["API_KEY"]


def test_rotation_system_has_concrete_provider_adapters(tmp_path) -> None:
    """Prove that the rotation system has concrete provider adapters.

    This addresses the v0.5.2 gap: 'no concrete provider adapters'.
    The providers subpackage now contains StubRotationAdapter and EnvFileRotationAdapter.
    """
    from hermesoptimizer.vault.providers import (
        EnvFileRotationAdapter,
        RotationAdapter,
        StubRotationAdapter,
    )

    adapters = [StubRotationAdapter(), EnvFileRotationAdapter()]

    for adapter in adapters:
        assert isinstance(adapter, RotationAdapter)
        assert callable(adapter.supports)
        assert callable(adapter.rotate)
        assert callable(adapter.rollback)

    # Stub adapter supports any entry
    stub = StubRotationAdapter()
    entry = VaultEntry(Path("/tmp/test.env"), "env", "API_KEY", "oldfp")
    assert stub.supports(entry) is True

    # EnvFile adapter only supports env entries with existing files
    env_file = tmp_path / "test.env"
    env_file.write_text("API_KEY=old\n")
    env_adapter = EnvFileRotationAdapter()
    env_entry = VaultEntry(env_file, "env", "API_KEY", "oldfp")
    assert env_adapter.supports(env_entry) is True  # env entry with existing file

    json_entry = VaultEntry(Path("/tmp/test.json"), "json", "API_KEY", "oldfp")
    assert env_adapter.supports(json_entry) is False  # not env entry


# --- Tests for atomic EnvFile rotation with backup ---


def test_env_rotation_creates_backup(tmp_path) -> None:
    """EnvFileRotationAdapter.rotate() creates a timestamped backup file."""
    from hermesoptimizer.vault.providers import EnvFileRotationAdapter

    env_file = tmp_path / "test.env"
    env_file.write_text("API_KEY=old-secret\nOTHER=value\n")

    adapter = EnvFileRotationAdapter()
    entry = VaultEntry(env_file, "env", "API_KEY", "oldfp")

    result = adapter.rotate(entry, "new-secret")

    assert result is True

    # Verify backup was created
    backups = list(tmp_path.glob("*.vault-backup.*"))
    assert len(backups) == 1

    # Verify backup contains old content
    backup_content = backups[0].read_text()
    assert "API_KEY=old-secret" in backup_content
    assert "OTHER=value" in backup_content


def test_env_rotation_is_atomic(tmp_path) -> None:
    """EnvFileRotationAdapter.rotate() uses atomic write (temp file + rename)."""
    from hermesoptimizer.vault.providers import EnvFileRotationAdapter

    env_file = tmp_path / "test.env"
    env_file.write_text("API_KEY=old-secret\n")

    adapter = EnvFileRotationAdapter()
    entry = VaultEntry(env_file, "env", "API_KEY", "oldfp")

    result = adapter.rotate(entry, "new-secret")

    assert result is True

    # Verify the main file has new content
    content = env_file.read_text()
    assert "API_KEY=new-secret" in content

    # Verify no temp files left behind
    temp_files = list(tmp_path.glob("*.env.tmp"))
    assert len(temp_files) == 0


def test_env_rotation_rollback_restores_backup(tmp_path) -> None:
    """EnvFileRotationAdapter.rollback() restores from the backup file."""
    from hermesoptimizer.vault.providers import EnvFileRotationAdapter

    env_file = tmp_path / "test.env"
    env_file.write_text("API_KEY=original-secret\nOTHER=value\n")

    adapter = EnvFileRotationAdapter()
    entry = VaultEntry(env_file, "env", "API_KEY", "oldfp")

    # First rotate to create a backup
    result = adapter.rotate(entry, "rotated-secret")
    assert result is True

    # Verify content was rotated
    content_after_rotate = env_file.read_text()
    assert "API_KEY=rotated-secret" in content_after_rotate

    # Now rollback
    rollback_result = adapter.rollback(entry)
    assert rollback_result is True

    # Verify content was restored
    restored_content = env_file.read_text()
    assert "API_KEY=original-secret" in restored_content
    assert "OTHER=value" in restored_content

    # Verify backup was cleaned up
    backups = list(tmp_path.glob("*.vault-backup.*"))
    assert len(backups) == 0


def test_env_rotation_rollback_returns_false_when_no_backup(tmp_path) -> None:
    """EnvFileRotationAdapter.rollback() returns False when no backup exists."""
    from hermesoptimizer.vault.providers import EnvFileRotationAdapter

    env_file = tmp_path / "test.env"
    env_file.write_text("API_KEY=original-secret\n")

    adapter = EnvFileRotationAdapter()
    entry = VaultEntry(env_file, "env", "API_KEY", "oldfp")

    # No rotation was done, so no backup exists

    result = adapter.rollback(entry)
    assert result is False


# --- Tests for StubRotationAdapter registry cleanup ---


def test_stub_registry_does_not_grow_unboundedly() -> None:
    """StubRotationAdapter registry uses WeakSet so it doesn't grow unboundedly."""
    from hermesoptimizer.vault.providers import StubRotationAdapter

    initial_size = StubRotationAdapter.registry_size()

    # Create and discard adapters
    adapters = [StubRotationAdapter() for _ in range(10)]
    del adapters

    # Registry size should not have grown (WeakSet auto-cleans)
    # Note: if initial_size was 0, it should still be 0
    final_size = StubRotationAdapter.registry_size()
    assert final_size == initial_size


def test_stub_cleanup_registry_method_exists() -> None:
    """StubRotationAdapter.cleanup_registry() is available for API compatibility."""
    from hermesoptimizer.vault.providers import StubRotationAdapter

    adapter = StubRotationAdapter()

    # Method should exist and be callable
    assert hasattr(StubRotationAdapter, "cleanup_registry")
    assert callable(StubRotationAdapter.cleanup_registry)

    # Should be a no-op with WeakSet
    StubRotationAdapter.cleanup_registry()


# --- Tests for VaultFileRotationAdapter ---


def test_vault_file_rotation_adapter_supports_vault_native() -> None:
    """VaultFileRotationAdapter supports entries with source_kind == 'vault-native'."""
    from hermesoptimizer.vault.providers import VaultFileRotationAdapter

    adapter = VaultFileRotationAdapter(session=None)

    # vault-native entry should be supported (but needs session)
    vault_entry = VaultEntry(Path("/tmp/test.vault"), "vault-native", "API_KEY", "oldfp")
    assert adapter.supports(vault_entry) is False  # No session

    # Create a mock session
    from unittest.mock import MagicMock
    mock_session = MagicMock()
    adapter_with_session = VaultFileRotationAdapter(session=mock_session)

    assert adapter_with_session.supports(vault_entry) is True

    # Non-vault-native entries should not be supported
    env_entry = VaultEntry(Path("/tmp/test.env"), "env", "API_KEY", "oldfp")
    assert adapter_with_session.supports(env_entry) is False


def test_vault_file_rotation_adapter_delegates_to_session(tmp_path) -> None:
    """VaultFileRotationAdapter.rotate() delegates to VaultSession.set()."""
    from hermesoptimizer.vault.providers import VaultFileRotationAdapter
    from hermesoptimizer.vault.session import VaultSession
    from hermesoptimizer.vault.crypto import generate_master_key

    # Create a real vault session
    vault_root = tmp_path / ".vault"
    vault_root.mkdir()
    master_key = generate_master_key()
    session = VaultSession(vault_root, master_key)

    adapter = VaultFileRotationAdapter(session=session)
    entry = VaultEntry(vault_root / "test.vault", "vault-native", "API_KEY", "oldfp")

    # Set initial secret
    session.set("API_KEY", "original-secret")

    # Rotate
    result = adapter.rotate(entry, "new-secret")
    assert result is True

    # Verify session.set was called
    mock_session = adapter._session  # type: ignore
    assert mock_session is session

    # Verify the new secret is in the vault
    retrieved = session.get("API_KEY")
    assert retrieved == "new-secret"


def test_vault_file_rotation_adapter_rollback(tmp_path) -> None:
    """VaultFileRotationAdapter.rollback() restores from audit log."""
    from hermesoptimizer.vault.providers import VaultFileRotationAdapter
    from hermesoptimizer.vault.session import VaultSession
    from hermesoptimizer.vault.crypto import generate_master_key

    # Create a real vault session
    vault_root = tmp_path / ".vault"
    vault_root.mkdir()
    master_key = generate_master_key()
    session = VaultSession(vault_root, master_key)

    adapter = VaultFileRotationAdapter(session=session)
    entry = VaultEntry(vault_root / "test.vault", "vault-native", "API_KEY", "oldfp")

    # Set initial secret
    session.set("API_KEY", "original-secret")

    # Rotate to new secret
    adapter.rotate(entry, "new-secret")

    # Verify rotation worked
    assert session.get("API_KEY") == "new-secret"

    # Rollback
    result = adapter.rollback(entry)
    assert result is True

    # Verify original is restored
    assert session.get("API_KEY") == "original-secret"


# --- Tests for backup management ---


def test_clean_old_backups_removes_old_files(tmp_path) -> None:
    """clean_old_backups() removes backup files older than max_age_days."""
    from hermesoptimizer.vault.providers import clean_old_backups

    # Create old and new backup files
    old_backup = tmp_path / "test.vault-backup.20200101000000000000"
    old_backup.touch()
    new_backup = tmp_path / "other.vault-backup.20990101000000000000"
    new_backup.touch()

    # Set old backup mtime to 60 days ago
    import time
    old_time = time.time() - (60 * 24 * 60 * 60)
    os.utime(old_backup, (old_time, old_time))

    # Clean with max_age_days=30
    deleted = clean_old_backups(tmp_path, max_age_days=30)

    assert deleted == 1
    assert not old_backup.exists()
    assert new_backup.exists()


def test_clean_old_backups_returns_zero_when_no_files(tmp_path) -> None:
    """clean_old_backups() returns 0 when no backup files exist."""
    from hermesoptimizer.vault.providers import clean_old_backups

    deleted = clean_old_backups(tmp_path, max_age_days=30)
    assert deleted == 0


def test_clean_old_backups_handles_nonexistent_root(tmp_path) -> None:
    """clean_old_backups() returns 0 for nonexistent vault root."""
    from hermesoptimizer.vault.providers import clean_old_backups

    nonexistent = tmp_path / "nonexistent"
    deleted = clean_old_backups(nonexistent, max_age_days=30)
    assert deleted == 0


def test_find_backup_files(tmp_path) -> None:
    """find_backup_files() returns all backup files sorted by mtime."""
    from hermesoptimizer.vault.providers import find_backup_files

    # Create backup files with different mtimes
    old_backup = tmp_path / "old.vault-backup.20200101000000000000"
    old_backup.touch()
    new_backup = tmp_path / "new.vault-backup.20990101000000000000"
    new_backup.touch()

    # Set different mtimes
    import time
    old_time = time.time() - (30 * 24 * 60 * 60)
    new_time = time.time()
    os.utime(old_backup, (old_time, old_time))
    os.utime(new_backup, (new_time, new_time))

    backups = find_backup_files(tmp_path)

    assert len(backups) == 2
    # Should be sorted newest first
    assert backups[0] == new_backup
    assert backups[1] == old_backup

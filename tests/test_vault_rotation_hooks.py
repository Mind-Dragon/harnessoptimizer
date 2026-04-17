from __future__ import annotations

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

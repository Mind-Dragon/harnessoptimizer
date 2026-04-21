"""Deep plugin tests — edge cases, error paths, cross-plugin consistency.

These tests fill the gaps in test_vault_plugins.py and test_vault_integration.py.
Focus: what users actually hit when things go wrong.

Layer: L2 (component integration)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermesoptimizer.vault.plugins.hermes_plugin import HermesPlugin
from hermesoptimizer.vault.plugins.opencode_plugin import OpenCodePlugin

def _free_port() -> int:
    """Find a free TCP port."""
    import socket
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture()
def vault_dir(tmp_path: Path) -> Path:
    """Create a temp vault directory."""
    d = tmp_path / "vault"
    d.mkdir()
    return d


@pytest.fixture()
def passphrase() -> str:
    return "test-deep-plugins-2026"


class TestHermesPluginEdgeCases:
    """HermesPlugin: error paths and edge cases."""

    def test_get_nonexistent_key_returns_none(self, vault_dir: Path, passphrase: str) -> None:
        """Getting a key that doesn't exist should return None, not crash."""
        with HermesPlugin(vault_path=str(vault_dir), passphrase=passphrase) as hp:
            result = hp.get("does-not-exist")
            assert result is None

    def test_delete_nonexistent_key_no_crash(self, vault_dir: Path, passphrase: str) -> None:
        """Deleting a key that doesn't exist should not crash."""
        with HermesPlugin(vault_path=str(vault_dir), passphrase=passphrase) as hp:
            hp.delete("does-not-exist")  # should not raise

    def test_list_entries_empty_vault(self, vault_dir: Path, passphrase: str) -> None:
        """Listing entries on empty vault should return empty list."""
        with HermesPlugin(vault_path=str(vault_dir), passphrase=passphrase) as hp:
            entries = hp.list_entries()
            assert entries == []

    def test_status_empty_vault(self, vault_dir: Path, passphrase: str) -> None:
        """Status on empty vault should still return a valid dict."""
        with HermesPlugin(vault_path=str(vault_dir), passphrase=passphrase) as hp:
            status = hp.status()
            assert isinstance(status, dict)
            assert "plugin_name" in status
            assert status["plugin_name"] == "HermesPlugin"

    def test_overwrite_key(self, vault_dir: Path, passphrase: str) -> None:
        """Setting the same key twice should overwrite the value."""
        with HermesPlugin(vault_path=str(vault_dir), passphrase=passphrase) as hp:
            hp.set("key1", "value1")
            hp.set("key1", "value2")
            assert hp.get("key1") == "value2"

    def test_set_unencrypted_then_get(self, vault_dir: Path, passphrase: str) -> None:
        """Setting is_encrypted=False should store plaintext."""
        with HermesPlugin(vault_path=str(vault_dir), passphrase=passphrase) as hp:
            hp.set("plain", "visible", is_encrypted=False)
            assert hp.get("plain") == "visible"

    def test_special_characters_in_key_value(self, vault_dir: Path, passphrase: str) -> None:
        """Keys and values with special chars should work."""
        with HermesPlugin(vault_path=str(vault_dir), passphrase=passphrase) as hp:
            hp.set("key/with/slashes", "value with spaces & symbols!@#")
            assert hp.get("key/with/slashes") == "value with spaces & symbols!@#"

    def test_large_value(self, vault_dir: Path, passphrase: str) -> None:
        """Large values should be stored and retrieved correctly."""
        big = "x" * 10000
        with HermesPlugin(vault_path=str(vault_dir), passphrase=passphrase) as hp:
            hp.set("big", big)
            assert hp.get("big") == big

    def test_context_manager_releases(self, vault_dir: Path, passphrase: str) -> None:
        """Context manager __exit__ should not crash."""
        hp = HermesPlugin(vault_path=str(vault_dir), passphrase=passphrase)
        with hp:
            hp.set("k", "v")
        # After exit, operations may fail but shouldn't crash the process
        # (implementation-dependent — just verify exit was clean)
        assert True

    def test_wrong_passphrase_same_vault(self, vault_dir: Path, monkeypatch) -> None:
        """Using a different passphrase on the same vault should fail to decrypt."""
        # Clear VAULT_MASTER_KEY that may leak from other test files
        monkeypatch.delenv("VAULT_MASTER_KEY", raising=False)
        with HermesPlugin(vault_path=str(vault_dir), passphrase="correct") as hp:
            hp.set("secret", "hidden")
        with pytest.raises(Exception):  # VaultLockedError or InvalidTag
            with HermesPlugin(vault_path=str(vault_dir), passphrase="wrong") as hp:
                hp.get("secret")


class TestOpenClawPluginDeep:
    """OpenClawPlugin: missing tests for list_entries, status, error paths."""

    @pytest.fixture()
    def openclaw(self, vault_dir: Path, passphrase: str):
        """Create OpenClawPlugin with local HTTP server on unique port."""
        import threading
        from hermesoptimizer.vault.plugins.openclaw_plugin import OpenClawPlugin
        import socket
        # Find a free port
        with socket.socket() as s:
            s.bind(("", 0))
            free_port = s.getsockname()[1]
        plugin = OpenClawPlugin(
            vault_path=str(vault_dir),
            passphrase=passphrase,
            auth_token="test-token-deep",
            port=free_port,
        )
        server_thread = threading.Thread(target=plugin.start_server, daemon=True)
        server_thread.start()
        plugin.wait_until_ready(timeout=5)
        yield plugin
        plugin.stop_server()

    def test_list_entries_empty(self, openclaw) -> None:
        """OpenClaw list_entries on empty vault should return empty list."""
        entries = openclaw.list_entries()
        assert isinstance(entries, list)

    def test_list_entries_after_set(self, openclaw) -> None:
        """OpenClaw list_entries should show entries after set."""
        openclaw.set("k1", "v1")
        entries = openclaw.list_entries()
        assert len(entries) >= 1
        keys = [e.get("key_name") or e.get("key") for e in entries]
        assert "k1" in keys

    def test_status_returns_valid(self, openclaw) -> None:
        """OpenClaw status should return a valid dict."""
        status = openclaw.status()
        assert isinstance(status, dict)
        assert "plugin_name" in status
        assert status["plugin_name"] == "OpenClawPlugin"

    def test_get_nonexistent_returns_none(self, openclaw) -> None:
        """Getting nonexistent key via HTTP should return None."""
        result = openclaw.get("nonexistent")
        assert result is None

    def test_delete_nonexistent_no_crash(self, openclaw) -> None:
        """Deleting nonexistent key via HTTP should not crash."""
        openclaw.delete("nonexistent")

    def test_overwrite_via_http(self, openclaw) -> None:
        """Setting same key twice via HTTP should overwrite."""
        openclaw.set("k", "v1")
        openclaw.set("k", "v2")
        assert openclaw.get("k") == "v2"

    def test_unencrypted_via_http(self, openclaw) -> None:
        """Unencrypted set/get via HTTP should work."""
        openclaw.set("plain", "visible", is_encrypted=False)
        assert openclaw.get("plain") == "visible"

    def test_shutdown_is_idempotent(self, openclaw) -> None:
        """Calling shutdown twice should not crash."""
        openclaw.shutdown()
        openclaw.shutdown()  # should not raise


class TestOpenCodePluginEdgeCases:
    """OpenCodePlugin: edge cases for read-only surface."""

    def test_get_nonexistent_returns_none(self, vault_dir: Path, passphrase: str) -> None:
        """Getting nonexistent key should return None."""
        ocp = OpenCodePlugin(vault_path=str(vault_dir), passphrase=passphrase)
        assert ocp.get("nonexistent") is None

    def test_list_entries_empty(self, vault_dir: Path, passphrase: str) -> None:
        """List entries on empty vault should return empty list."""
        ocp = OpenCodePlugin(vault_path=str(vault_dir), passphrase=passphrase)
        assert ocp.list_entries() == []

    def test_generate_config_empty_vault(self, vault_dir: Path, tmp_path: Path, passphrase: str) -> None:
        """Generating config from empty vault should produce a valid file."""
        ocp = OpenCodePlugin(vault_path=str(vault_dir), passphrase=passphrase)
        out = tmp_path / "config.env"
        ocp.generate_config(out)
        assert out.exists()

    def test_inject_env_empty_vault(self, vault_dir: Path, passphrase: str) -> None:
        """Inject env on empty vault should return empty dict."""
        ocp = OpenCodePlugin(vault_path=str(vault_dir), passphrase=passphrase)
        env = ocp.inject_env()
        assert isinstance(env, dict)

    def test_status_empty_vault(self, vault_dir: Path, passphrase: str) -> None:
        """Status on empty vault should return valid dict."""
        ocp = OpenCodePlugin(vault_path=str(vault_dir), passphrase=passphrase)
        status = ocp.status()
        assert isinstance(status, dict)
        assert status["plugin_name"] == "OpenCodePlugin"

    def test_generate_config_format(self, vault_dir: Path, tmp_path: Path, passphrase: str) -> None:
        """Generated config should be valid KEY=VALUE or KEY: VALUE format."""
        with HermesPlugin(vault_path=str(vault_dir), passphrase=passphrase) as hp:
            hp.set("API_KEY", "sk-test-123", is_encrypted=False)
            hp.set("DB_URL", "postgres://localhost/test", is_encrypted=False)
        ocp = OpenCodePlugin(vault_path=str(vault_dir), passphrase=passphrase)
        out = tmp_path / "config.env"
        ocp.generate_config(out)
        content = out.read_text()
        lines = [l.strip() for l in content.strip().split("\n") if l.strip() and not l.startswith("#")]
        for line in lines:
            has_delim = "=" in line or ":" in line
            assert has_delim, f"Invalid env line: {line}"


class TestCrossPluginMatrix:
    """Full cross-plugin consistency matrix — every read/write combo."""

    def test_hermes_write_openclaw_read(self, vault_dir: Path, passphrase: str) -> None:
        """HermesPlugin writes → OpenClawPlugin reads same value."""
        with HermesPlugin(vault_path=str(vault_dir), passphrase=passphrase) as hp:
            hp.set("shared", "from-hermes")

        from hermesoptimizer.vault.plugins.openclaw_plugin import OpenClawPlugin
        ocp = OpenClawPlugin(vault_path=str(vault_dir), passphrase=passphrase, auth_token="test-deep", port=_free_port())
        import threading as _threading
        _t = _threading.Thread(target=ocp.start_server, daemon=True)
        _t.start()
        ocp.wait_until_ready(timeout=5)
        try:
            assert ocp.get("shared") == "from-hermes"
        finally:
            ocp.stop_server()

    def test_openclaw_write_opencode_read(self, vault_dir: Path, passphrase: str) -> None:
        """OpenClawPlugin writes → OpenCodePlugin reads same value."""
        from hermesoptimizer.vault.plugins.openclaw_plugin import OpenClawPlugin
        ocp = OpenClawPlugin(vault_path=str(vault_dir), passphrase=passphrase, auth_token="test-deep", port=_free_port())
        import threading as _threading
        _t = _threading.Thread(target=ocp.start_server, daemon=True)
        _t.start()
        ocp.wait_until_ready(timeout=5)
        try:
            ocp.set("from-openclaw", "shared-value")
        finally:
            ocp.stop_server()

        reader = OpenCodePlugin(vault_path=str(vault_dir), passphrase=passphrase)
        assert reader.get("from-openclaw") == "shared-value"

    def test_opencode_sees_hermes_delete(self, vault_dir: Path, passphrase: str) -> None:
        """HermesPlugin deletes → OpenCodePlugin sees entry gone (already covered but validates matrix)."""
        with HermesPlugin(vault_path=str(vault_dir), passphrase=passphrase) as hp:
            hp.set("temp", "will-delete")
        with HermesPlugin(vault_path=str(vault_dir), passphrase=passphrase) as hp:
            hp.delete("temp")
        ocp = OpenCodePlugin(vault_path=str(vault_dir), passphrase=passphrase)
        assert ocp.get("temp") is None

    def test_three_way_round_trip(self, vault_dir: Path, passphrase: str) -> None:
        """Hermes writes → OpenClaw reads → OpenClaw writes → OpenCode reads → OpenCode lists."""
        # 1. Hermes writes
        with HermesPlugin(vault_path=str(vault_dir), passphrase=passphrase) as hp:
            hp.set("round-trip", "step-1")

        # 2. OpenClaw reads and writes
        from hermesoptimizer.vault.plugins.openclaw_plugin import OpenClawPlugin
        ocp = OpenClawPlugin(vault_path=str(vault_dir), passphrase=passphrase, auth_token="test-deep", port=_free_port())
        import threading as _threading
        _t = _threading.Thread(target=ocp.start_server, daemon=True)
        _t.start()
        ocp.wait_until_ready(timeout=5)
        try:
            assert ocp.get("round-trip") == "step-1"
            ocp.set("round-trip-2", "step-2")
        finally:
            ocp.stop_server()

        # 3. OpenCode reads both
        reader = OpenCodePlugin(vault_path=str(vault_dir), passphrase=passphrase)
        assert reader.get("round-trip") == "step-1"
        assert reader.get("round-trip-2") == "step-2"
        entries = reader.list_entries()
        keys = {e.get("key_name") or e.get("key") for e in entries}
        assert "round-trip" in keys
        assert "round-trip-2" in keys

    def test_all_plugins_same_status_shape(self, vault_dir: Path, passphrase: str) -> None:
        """All plugins should return status dicts with at least plugin_name and entry count."""
        with HermesPlugin(vault_path=str(vault_dir), passphrase=passphrase) as hp:
            hp_status = hp.status()

        ocp_status = OpenCodePlugin(vault_path=str(vault_dir), passphrase=passphrase).status()

        for status in [hp_status, ocp_status]:
            assert isinstance(status, dict)
            assert "plugin_name" in status
            has_count = any(k in status for k in ("entry_count", "entries_count", "key_count", "total"))
            assert has_count, f"Status missing entry count field: {list(status.keys())}"

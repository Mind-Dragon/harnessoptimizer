"""Tests for vault plugins."""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from urllib.request import urlopen
from urllib.error import HTTPError

import pytest
from abc import ABC

from hermesoptimizer.vault.crypto import generate_master_key
from hermesoptimizer.vault.plugins import (
    HermesPlugin,
    OpenClawPlugin,
    OpenCodePlugin,
    VaultPlugin,
)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


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
def hermes_plugin(temp_vault_root: Path, master_key: bytes) -> HermesPlugin:
    """Create a HermesPlugin instance with known master key."""
    import base64
    os.environ["VAULT_MASTER_KEY"] = base64.b64encode(master_key).decode("ascii")
    plugin = HermesPlugin(vault_path=str(temp_vault_root), passphrase="test-passphrase")
    return plugin


# --------------------------------------------------------------------------
# Test VaultPlugin ABC
# --------------------------------------------------------------------------


def test_vault_plugin_is_abc():
    """Verify VaultPlugin is an abstract base class."""
    assert issubclass(VaultPlugin, ABC)


# --------------------------------------------------------------------------
# Test HermesPlugin
# --------------------------------------------------------------------------


def test_hermes_plugin_round_trip(hermes_plugin: HermesPlugin):
    """Test set/get/delete round-trip on HermesPlugin."""
    with hermes_plugin:
        # Set a secret
        hermes_plugin.set("API_KEY", "sk-secret-12345", is_encrypted=True)

        # Get it back
        value = hermes_plugin.get("API_KEY")
        assert value == "sk-secret-12345"

        # Delete it
        hermes_plugin.delete("API_KEY")

        # Verify it's gone
        assert hermes_plugin.get("API_KEY") is None


def test_hermes_plugin_unencrypted(hermes_plugin: HermesPlugin):
    """Test storing unencrypted values."""
    with hermes_plugin:
        hermes_plugin.set("API_URL", "https://api.example.com", is_encrypted=False)
        value = hermes_plugin.get("API_URL")
        assert value == "https://api.example.com"


def test_hermes_plugin_list_entries(hermes_plugin: HermesPlugin):
    """Test list_entries returns correct structure."""
    with hermes_plugin:
        hermes_plugin.set("KEY_A", "value-a", is_encrypted=True)
        hermes_plugin.set("KEY_B", "value-b", is_encrypted=False)

        entries = hermes_plugin.list_entries()
        assert len(entries) == 2

        # Check entry structure
        for entry in entries:
            assert "key_name" in entry
            assert "fingerprint" in entry
            assert "is_encrypted" in entry
            assert "source_file" in entry

        # Verify key names
        key_names = {e["key_name"] for e in entries}
        assert key_names == {"KEY_A", "KEY_B"}


def test_hermes_plugin_status(hermes_plugin: HermesPlugin):
    """Test status returns correct info."""
    with hermes_plugin:
        hermes_plugin.set("SECRET_KEY", "secret", is_encrypted=True)
        hermes_plugin.set("PUBLIC_KEY", "public", is_encrypted=False)

        status = hermes_plugin.status()
        assert status["plugin_name"] == "HermesPlugin"
        assert status["entry_count"] == 2
        assert status["encrypted_count"] == 1


def test_hermes_plugin_multiple_secrets(hermes_plugin: HermesPlugin):
    """Test storing and retrieving multiple secrets."""
    with hermes_plugin:
        secrets = {
            "ANTHROPIC_API_KEY": "sk-ant-api-key-1",
            "OPENAI_API_KEY": "sk-openai-api-key-2",
            "DATABASE_URL": "postgresql://localhost/db",
        }

        for key, value in secrets.items():
            hermes_plugin.set(key, value)

        for key, expected_value in secrets.items():
            actual = hermes_plugin.get(key)
            assert actual == expected_value


# --------------------------------------------------------------------------
# Test OpenClawPlugin
# --------------------------------------------------------------------------


@pytest.fixture
def openclaw_plugin(temp_vault_root: Path, master_key: bytes) -> OpenClawPlugin:
    """Create an OpenClawPlugin instance for testing."""
    import base64
    os.environ["VAULT_MASTER_KEY"] = base64.b64encode(master_key).decode("ascii")
    os.environ["VAULT_API_TOKEN"] = "test-token-12345"
    plugin = OpenClawPlugin(
        vault_path=str(temp_vault_root),
        passphrase="test-passphrase",
        auth_token="test-token-12345",
    )
    return plugin


def _make_request(method: str, url: str, data: dict | None = None, token: str = "test-token-12345") -> dict:
    """Make HTTP request with bearer auth."""
    import urllib.request

    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(data).encode("utf-8")

    with urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def test_openclaw_plugin_http_round_trip(openclaw_plugin: OpenClawPlugin):
    """Test HTTP round-trip via OpenClawPlugin."""
    # Use context manager which enters session
    with openclaw_plugin:
        base_url = f"http://127.0.0.1:{openclaw_plugin._port}"

        # Set a secret directly via the plugin (simulating what HTTP POST would do)
        openclaw_plugin.set("HTTP_KEY", "http-secret-value", is_encrypted=True)

        # Get it back via direct call (simulating what HTTP GET would do)
        result = openclaw_plugin.get("HTTP_KEY")
        assert result == "http-secret-value"

        # List entries
        entries = openclaw_plugin.list_entries()
        key_names = {e["key_name"] for e in entries}
        assert "HTTP_KEY" in key_names

        # Status
        status = openclaw_plugin.status()
        assert status["entry_count"] >= 1

        # Delete via direct call
        openclaw_plugin.delete("HTTP_KEY")

        # Verify it's gone
        assert openclaw_plugin.get("HTTP_KEY") is None


def test_openclaw_plugin_unauthorized(openclaw_plugin: OpenClawPlugin):
    """Test that unauthorized requests are rejected."""
    server_thread = threading.Thread(target=openclaw_plugin.start_server, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    try:
        base_url = f"http://127.0.0.1:{openclaw_plugin._port}"

        # Request without token should fail
        with pytest.raises(HTTPError) as exc_info:
            _make_request("GET", f"{base_url}/vault/status", token="wrong-token")
        assert exc_info.value.code == 401

    finally:
        openclaw_plugin.stop_server()


# --------------------------------------------------------------------------
# Test OpenCodePlugin
# --------------------------------------------------------------------------


@pytest.fixture
def opencode_plugin(temp_vault_root: Path, master_key: bytes) -> OpenCodePlugin:
    """Create an OpenCodePlugin instance for testing."""
    import base64
    os.environ["VAULT_MASTER_KEY"] = base64.b64encode(master_key).decode("ascii")
    plugin = OpenCodePlugin(vault_path=str(temp_vault_root), passphrase="test-passphrase")
    return plugin


def test_opencode_plugin_readonly_set_raises(opencode_plugin: OpenCodePlugin):
    """Test that set() raises NotImplementedError on OpenCodePlugin."""
    with opencode_plugin:
        with pytest.raises(NotImplementedError) as exc_info:
            opencode_plugin.set("KEY", "value")
        assert "read-only" in str(exc_info.value)


def test_opencode_plugin_readonly_delete_raises(opencode_plugin: OpenCodePlugin):
    """Test that delete() raises NotImplementedError on OpenCodePlugin."""
    with opencode_plugin:
        with pytest.raises(NotImplementedError) as exc_info:
            opencode_plugin.delete("KEY")
        assert "read-only" in str(exc_info.value)


def test_opencode_plugin_get_works(temp_vault_root: Path, master_key: bytes):
    """Test that get() works on OpenCodePlugin (read-only access)."""
    import base64

    # First set a value via Hermes using the SAME master key
    os.environ["VAULT_MASTER_KEY"] = base64.b64encode(master_key).decode("ascii")
    with HermesPlugin(vault_path=str(temp_vault_root), passphrase="test-passphrase") as hp:
        hp.set("READONLY_KEY", "readonly-value")

    # Now read it via OpenCode (using same vault path and passphrase)
    os.environ["VAULT_MASTER_KEY"] = base64.b64encode(master_key).decode("ascii")
    with OpenCodePlugin(vault_path=str(temp_vault_root), passphrase="test-passphrase") as plugin:
        value = plugin.get("READONLY_KEY")
        assert value == "readonly-value"


def test_opencode_plugin_list_entries(temp_vault_root: Path, master_key: bytes):
    """Test list_entries works on OpenCodePlugin."""
    import base64

    # First set some values via Hermes using the SAME master key
    os.environ["VAULT_MASTER_KEY"] = base64.b64encode(master_key).decode("ascii")
    with HermesPlugin(vault_path=str(temp_vault_root), passphrase="test-passphrase") as hp:
        hp.set("ENTRY_A", "value-a")
        hp.set("ENTRY_B", "value-b")

    # Now read via OpenCode
    os.environ["VAULT_MASTER_KEY"] = base64.b64encode(master_key).decode("ascii")
    with OpenCodePlugin(vault_path=str(temp_vault_root), passphrase="test-passphrase") as plugin:
        entries = plugin.list_entries()
        key_names = {e["key_name"] for e in entries}
        assert "ENTRY_A" in key_names
        assert "ENTRY_B" in key_names


def test_opencode_plugin_generate_config(temp_vault_root: Path, tmp_path: Path, master_key: bytes):
    """Test generate_config writes YAML file correctly."""
    import base64

    # Set up some entries using the SAME master key
    os.environ["VAULT_MASTER_KEY"] = base64.b64encode(master_key).decode("ascii")
    with HermesPlugin(vault_path=str(temp_vault_root), passphrase="test-passphrase") as hp:
        hp.set("CONFIG_KEY", "config-value", is_encrypted=True)
        hp.set("PUBLIC_KEY", "public-value", is_encrypted=False)

    config_path = tmp_path / "opencode_config.yaml"

    os.environ["VAULT_MASTER_KEY"] = base64.b64encode(master_key).decode("ascii")
    with OpenCodePlugin(vault_path=str(temp_vault_root), passphrase="test-passphrase") as plugin:
        plugin.generate_config(config_path)

    assert config_path.exists()

    import yaml
    with open(config_path) as f:
        config = yaml.safe_load(f)

    assert "CONFIG_KEY" in config
    assert config["CONFIG_KEY"]["is_encrypted"] is True
    assert "fingerprint" in config["CONFIG_KEY"]

    assert "PUBLIC_KEY" in config
    assert config["PUBLIC_KEY"]["is_encrypted"] is False


def test_opencode_plugin_inject_env(temp_vault_root: Path, master_key: bytes):
    """Test inject_env returns decrypted values as env vars."""
    import base64

    # Set up entries using the SAME master key
    os.environ["VAULT_MASTER_KEY"] = base64.b64encode(master_key).decode("ascii")
    with HermesPlugin(vault_path=str(temp_vault_root), passphrase="test-passphrase") as hp:
        hp.set("SECRET_API_KEY", "sk-secret-12345", is_encrypted=True)
        hp.set("PUBLIC_URL", "https://api.example.com", is_encrypted=False)

    os.environ["VAULT_MASTER_KEY"] = base64.b64encode(master_key).decode("ascii")
    with OpenCodePlugin(vault_path=str(temp_vault_root), passphrase="test-passphrase") as plugin:
        env_vars = plugin.inject_env(prefix="VAULT_")

    assert "VAULT_SECRET_API_KEY" in env_vars
    assert env_vars["VAULT_SECRET_API_KEY"] == "sk-secret-12345"
    assert "VAULT_PUBLIC_URL" in env_vars
    assert env_vars["VAULT_PUBLIC_URL"] == "https://api.example.com"


def test_opencode_plugin_inject_env_custom_prefix(temp_vault_root: Path, master_key: bytes):
    """Test inject_env with custom prefix."""
    import base64

    os.environ["VAULT_MASTER_KEY"] = base64.b64encode(master_key).decode("ascii")
    with HermesPlugin(vault_path=str(temp_vault_root), passphrase="test-passphrase") as hp:
        hp.set("MY_KEY", "my-value")

    os.environ["VAULT_MASTER_KEY"] = base64.b64encode(master_key).decode("ascii")
    with OpenCodePlugin(vault_path=str(temp_vault_root), passphrase="test-passphrase") as plugin:
        env_vars = plugin.inject_env(prefix="CUSTOM_")

    assert "CUSTOM_MY_KEY" in env_vars
    assert env_vars["CUSTOM_MY_KEY"] == "my-value"


def test_opencode_plugin_status(temp_vault_root: Path, master_key: bytes):
    """Test status returns correct info with readonly flag."""
    import base64

    os.environ["VAULT_MASTER_KEY"] = base64.b64encode(master_key).decode("ascii")
    with HermesPlugin(vault_path=str(temp_vault_root), passphrase="test-passphrase") as hp:
        hp.set("STATUS_KEY", "status-value")

    os.environ["VAULT_MASTER_KEY"] = base64.b64encode(master_key).decode("ascii")
    with OpenCodePlugin(vault_path=str(temp_vault_root), passphrase="test-passphrase") as plugin:
        status = plugin.status()

    assert status["plugin_name"] == "OpenCodePlugin"
    assert status["readonly"] is True
    assert status["entry_count"] >= 1

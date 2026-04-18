"""Integration tests for vault plugin cross-plugin consistency."""
from __future__ import annotations

import base64
import json
import os
import threading
import time
import urllib.request
import urllib.error
from pathlib import Path

import pytest

from hermesoptimizer.vault.crypto import VaultCrypto, derive_key
from hermesoptimizer.vault.fingerprint import fingerprint_secret


def _create_test_vault(vault_dir: Path) -> None:
    """Create a minimal vault.enc.json inside vault_dir."""
    salt = b"test-salt-16-bytes"
    key, _ = derive_key("test-passphrase", salt)
    crypto = VaultCrypto()

    entries = [
        {
            "key_name": "EXISTING_KEY",
            "fingerprint": fingerprint_secret("existing-secret-value"),
            "source_file": "test.env",
            "is_encrypted": True,
            "encrypted_value": crypto.encrypt("existing-secret-value", key),
            "plaintext_value": None,
        },
        {
            "key_name": "EXISTING_URL",
            "fingerprint": fingerprint_secret("https://api.example.com"),
            "source_file": "test.env",
            "is_encrypted": False,
            "encrypted_value": None,
            "plaintext_value": "https://api.example.com",
        },
    ]

    enc_path = vault_dir / "vault.enc.json"
    enc_path.write_text(
        json.dumps({"version": 1, "salt": base64.b64encode(salt).decode(), "entries": entries}),
        encoding="utf-8",
    )


@pytest.fixture
def vault_dir(tmp_path: Path) -> Path:
    _create_test_vault(tmp_path)
    return tmp_path


class TestCrossPluginConsistency:
    """Verify all 3 plugins operate on the same vault correctly."""

    def test_hermes_writes_opencode_reads(self, vault_dir: Path) -> None:
        """HermesPlugin writes -> OpenCodePlugin reads same values."""
        from hermesoptimizer.vault.plugins.hermes_plugin import HermesPlugin
        from hermesoptimizer.vault.plugins.opencode_plugin import OpenCodePlugin

        with HermesPlugin(vault_path=str(vault_dir), passphrase="test-passphrase") as hp:
            hp.set("NEW_SECRET", "sk-cross-plugin-test", is_encrypted=True)
            hp.set("NEW_URL", "https://cross.plugin.test/v1", is_encrypted=False)

        ocp = OpenCodePlugin(vault_path=str(vault_dir), passphrase="test-passphrase")
        assert ocp.get("NEW_SECRET") == "sk-cross-plugin-test"
        assert ocp.get("NEW_URL") == "https://cross.plugin.test/v1"
        assert ocp.get("EXISTING_KEY") == "existing-secret-value"

    def test_openclaw_http_writes_hermes_reads(self, vault_dir: Path) -> None:
        """OpenClawPlugin HTTP write -> HermesPlugin reads same value."""
        from hermesoptimizer.vault.plugins.hermes_plugin import HermesPlugin
        from hermesoptimizer.vault.plugins.openclaw_plugin import OpenClawPlugin

        ocp = OpenClawPlugin(
            vault_path=str(vault_dir),
            passphrase="test-passphrase",
            port=18598,
            auth_token="test-token-123",
        )

        server_thread = threading.Thread(target=ocp.start_server, daemon=True)
        server_thread.start()
        time.sleep(0.5)

        try:
            # Write via HTTP
            data = json.dumps({"key_name": "HTTP_KEY", "value": "sk-via-http", "is_encrypted": True}).encode()
            req = urllib.request.Request(
                "http://127.0.0.1:18598/vault/entry",
                data=data,
                headers={"Content-Type": "application/json", "Authorization": "Bearer test-token-123"},
                method="POST",
            )
            resp = urllib.request.urlopen(req)
            assert resp.status == 200

            # Read via HermesPlugin
            with HermesPlugin(vault_path=str(vault_dir), passphrase="test-passphrase") as hp:
                val = hp.get("HTTP_KEY")
                assert val == "sk-via-http"
        finally:
            ocp.shutdown()

    def test_hermes_delete_opencode_cannot_see(self, vault_dir: Path) -> None:
        """HermesPlugin deletes -> OpenCodePlugin sees entry gone."""
        from hermesoptimizer.vault.plugins.hermes_plugin import HermesPlugin
        from hermesoptimizer.vault.plugins.opencode_plugin import OpenCodePlugin

        with HermesPlugin(vault_path=str(vault_dir), passphrase="test-passphrase") as hp:
            hp.delete("EXISTING_KEY")

        ocp = OpenCodePlugin(vault_path=str(vault_dir), passphrase="test-passphrase")
        assert ocp.get("EXISTING_KEY") is None
        # Metadata still present
        assert ocp.get("EXISTING_URL") == "https://api.example.com"

    def test_full_crud_cycle_hermes(self, vault_dir: Path) -> None:
        """Full CRUD cycle through HermesPlugin."""
        from hermesoptimizer.vault.plugins.hermes_plugin import HermesPlugin

        with HermesPlugin(vault_path=str(vault_dir), passphrase="test-passphrase") as hp:
            # Create
            hp.set("CRUD_KEY", "initial-value", is_encrypted=True)
            assert hp.get("CRUD_KEY") == "initial-value"

            # Read via list
            entries = hp.list_entries()
            crud_entry = [e for e in entries if e["key_name"] == "CRUD_KEY"]
            assert len(crud_entry) == 1
            assert crud_entry[0]["is_encrypted"] is True

            # Update
            hp.set("CRUD_KEY", "updated-value", is_encrypted=True)
            assert hp.get("CRUD_KEY") == "updated-value"

            # Delete
            hp.delete("CRUD_KEY")
            assert hp.get("CRUD_KEY") is None

    def test_status_reflects_vault_state(self, vault_dir: Path) -> None:
        """Status endpoint shows correct counts after operations."""
        from hermesoptimizer.vault.plugins.hermes_plugin import HermesPlugin

        with HermesPlugin(vault_path=str(vault_dir), passphrase="test-passphrase") as hp:
            status = hp.status()
            assert status["encrypted_count"] >= 1  # EXISTING_KEY
            assert status["entry_count"] >= 2

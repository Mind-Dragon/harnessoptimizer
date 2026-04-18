"""OpenClawPlugin - HTTP bridge sidecar for VaultSession."""
from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from hermesoptimizer.vault.plugins.base import VaultPlugin
from hermesoptimizer.vault.session import VaultSession

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8599


class _VaultHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for vault sidecar API."""

    def _send_json(self, status: int, data: Any) -> None:
        """Send JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def _read_json(self) -> dict[str, Any]:
        """Read JSON body from request."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        body = self.rfile.read(content_length)
        return json.loads(body.decode("utf-8"))

    def _check_auth(self) -> bool:
        """Check bearer token auth against VAULT_API_TOKEN env var or configured token."""
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return False
        token = auth_header[7:]  # Strip "Bearer "
        # Check configured token first, then VAULT_API_TOKEN env var
        expected = (
            getattr(self.server, "_auth_token", None)
            or os.environ.get("VAULT_API_TOKEN")
        )
        return token == expected

    def do_GET(self) -> None:
        """Handle GET requests."""
        if not self._check_auth():
            self._send_json(401, {"error": "Unauthorized"})
            return

        path = self.path.rstrip("/")

        # GET /vault/status
        if path == "/vault/status":
            status = self.server._plugin.status()
            self._send_json(200, status)
            return

        # GET /vault/entries
        if path == "/vault/entries":
            entries = self.server._plugin.list_entries()
            self._send_json(200, {"entries": entries})
            return

        # GET /vault/entry/<key_name>
        if path.startswith("/vault/entry/"):
            key_name = path[12:]  # Strip "/vault/entry/"
            value = self.server._plugin.get(key_name)
            if value is None:
                self._send_json(404, {"error": f"Entry '{key_name}' not found"})
            else:
                self._send_json(200, {"key_name": key_name, "value": value})
            return

        self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        """Handle POST requests."""
        if not self._check_auth():
            self._send_json(401, {"error": "Unauthorized"})
            return

        path = self.path.rstrip("/")

        # POST /vault/entry
        if path == "/vault/entry":
            data = self._read_json()
            key_name = data.get("key_name")
            value = data.get("value", "")
            is_encrypted = data.get("is_encrypted", True)

            if not key_name:
                self._send_json(400, {"error": "key_name is required"})
                return

            self.server._plugin.set(key_name, value, is_encrypted=is_encrypted)
            self._send_json(200, {"status": "ok"})
            return

        self._send_json(404, {"error": "Not found"})

    def do_DELETE(self) -> None:
        """Handle DELETE requests."""
        if not self._check_auth():
            self._send_json(401, {"error": "Unauthorized"})
            return

        path = self.path.rstrip("/")

        # DELETE /vault/entry/<key_name>
        if path.startswith("/vault/entry/"):
            key_name = path[12:]  # Strip "/vault/entry/"
            self.server._plugin.delete(key_name)
            self._send_json(200, {"status": "ok"})
            return

        self._send_json(404, {"error": "Not found"})

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default logging."""
        pass


class _VaultHTTPServer(HTTPServer):
    """HTTP server with plugin reference."""

    def __init__(self, server_address: tuple[str, int], plugin: VaultPlugin, auth_token: str | None) -> None:
        super().__init__(server_address, _VaultHTTPHandler)
        self._plugin = plugin
        self._auth_token = auth_token


class OpenClawPlugin(VaultPlugin):
    """
    HTTP bridge sidecar plugin for VaultSession.

    This plugin wraps VaultSession behind a Flask/FastAPI-style HTTP API
    using Python's built-in http.server module. All CRUD operations are
    delegated to an internal VaultSession instance.

    Args:
        host: Host to bind to (default 127.0.0.1)
        port: Port to listen on (default 8599)
        vault_path: Path to vault root (default ~/.vault/)
        passphrase: Passphrase for vault encryption (default 'hermes-vault-default')
        auth_token: Optional bearer token for authentication. If None, uses VAULT_API_TOKEN env var.

    Example:
        plugin = OpenClawPlugin(port=8599)
        plugin.start_server()  # Blocks, run in thread for non-blocking
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        vault_path: str | Path | None = None,
        passphrase: str = "hermes-vault-default",
        auth_token: str | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._vault_path = vault_path or os.path.expanduser("~/.vault/")
        self._passphrase = passphrase
        self._auth_token = auth_token

        # Create the underlying session
        from hermesoptimizer.vault.crypto import derive_key
        vault_root = Path(self._vault_path)
        if not vault_root.exists():
            vault_root.mkdir(parents=True, exist_ok=True)

        # Check VAULT_MASTER_KEY env var first (like VaultSession does)
        import base64
        env_key = os.environ.get("VAULT_MASTER_KEY")
        if env_key:
            try:
                master_key = base64.b64decode(env_key)
            except Exception:
                master_key, _ = derive_key(passphrase)
        else:
            # Try to load salt from existing vault.enc.json to derive consistent key
            enc_path = vault_root / "vault.enc.json"
            stored_salt = self._load_salt_from_vault(enc_path)
            if stored_salt:
                master_key, _ = derive_key(passphrase, stored_salt)
            else:
                master_key, _ = derive_key(passphrase)

        self._session = VaultSession(vault_root=vault_root, master_key=master_key)

        self._server: _VaultHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._session_entered = False

    def _load_salt_from_vault(self, enc_path: Path) -> bytes | None:
        """Load salt from vault.enc.json if it exists."""
        import base64
        import json

        if not enc_path.exists():
            return None

        try:
            content = enc_path.read_text(encoding="utf-8")
            data = json.loads(content)
            salt_b64 = data.get("salt")
            if salt_b64:
                return base64.b64decode(salt_b64)
        except Exception:
            pass
        return None

    def get(self, key_name: str) -> str | None:
        """Get value from vault via internal session."""
        return self._session.get(key_name)

    def set(self, key_name: str, value: str, is_encrypted: bool = True) -> None:
        """Set value in vault via internal session."""
        self._session.set(key_name, value, encrypted=is_encrypted)
        # Persist immediately for HTTP server use case
        self._session._save_vault()

    def delete(self, key_name: str) -> None:
        """Delete entry from vault via internal session."""
        self._session.delete(key_name)
        # Persist immediately for HTTP server use case
        self._session._save_vault()

    def list_entries(self) -> list[dict[str, Any]]:
        """List entries from vault via internal session."""
        entries = self._session.list_entries()
        return [
            {
                "key_name": entry.key_name,
                "fingerprint": entry.fingerprint,
                "is_encrypted": entry.is_encrypted,
                "source_file": str(entry.source_path),
            }
            for entry in entries
        ]

    def status(self) -> dict[str, Any]:
        """Return plugin status."""
        entries = self.list_entries()
        encrypted_count = sum(1 for e in entries if e.get("is_encrypted", False))
        return {
            "plugin_name": self.__class__.__name__,
            "vault_path": self._vault_path,
            "entry_count": len(entries),
            "encrypted_count": encrypted_count,
        }

    def start_server(self) -> None:
        """
        Start the HTTP server (blocking).

        This method blocks indefinitely. For non-blocking operation,
        call this in a separate thread.

        Note: The session is entered automatically when the server starts.
        """
        # Enter the session context
        self._session.__enter__()
        self._session_entered = True

        self._server = _VaultHTTPServer(
            (self._host, self._port),
            self,
            self._auth_token,
        )
        self._server.serve_forever()

    def stop_server(self) -> None:
        """Stop the HTTP server."""
        if self._server:
            self._server.shutdown()
            self._server = None
        # Exit the session if it was entered
        if self._session_entered:
            self._session.__exit__(None, None, None)
            self._session_entered = False

    def shutdown(self) -> None:
        """Shutdown the HTTP server (alias for stop_server)."""
        self.stop_server()

    def __enter__(self) -> OpenClawPlugin:
        """Enter context manager - open vault session."""
        self._session.__enter__()
        self._session_entered = True
        return self

    def __exit__(self, *args: Any) -> None:
        """Exit context manager - close vault session and stop server."""
        if self._session_entered:
            self._session.__exit__(*args)
            self._session_entered = False
        self.stop_server()

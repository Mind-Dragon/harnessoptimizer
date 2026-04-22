"""TDD tests for HTTP vault status providers: AWS/Azure NotImplementedError, Hermes and OpenClaw providers.

These tests prove the HTTP-based status provider backends work with mocked
HTTP responses - no real API keys or network calls are made.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from hermesoptimizer.vault import (
    ValidationResult,
    VaultEntry,
)
from hermesoptimizer.vault.providers.http import (
    AWSProvider,
    AzureProvider,
    HermesProvider,
    OpenClawProvider,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_entry(tmp_path: Path) -> VaultEntry:
    """A minimal VaultEntry for testing."""
    p = tmp_path / "test.env"
    p.write_text("KEY=value\n", encoding="utf-8")
    return VaultEntry(
        source_path=p,
        source_kind="env",
        key_name="KEY",
        fingerprint="abc123",
    )


# ---------------------------------------------------------------------------
# AWSProvider NotImplementedError tests
# ---------------------------------------------------------------------------

class TestAWSProviderNotImplemented:
    """Tests for AWSProvider NotImplementedError."""

    def test_aws_provider_raises_not_implemented(self, sample_entry: VaultEntry) -> None:
        """AWS STS requires SigV4 signing which is not yet implemented."""
        provider = AWSProvider()

        with pytest.raises(NotImplementedError) as exc_info:
            provider(sample_entry)

        assert "SigV4" in str(exc_info.value)
        assert "not yet implemented" in str(exc_info.value)


# ---------------------------------------------------------------------------
# AzureProvider NotImplementedError tests
# ---------------------------------------------------------------------------

class TestAzureProviderNotImplemented:
    """Tests for AzureProvider NotImplementedError."""

    def test_azure_provider_raises_not_implemented(self, sample_entry: VaultEntry) -> None:
        """Azure AD token validation requires JWKS-based JWT verification which is not yet implemented."""
        provider = AzureProvider()

        with pytest.raises(NotImplementedError) as exc_info:
            provider(sample_entry)

        assert "JWKS" in str(exc_info.value)
        assert "not yet implemented" in str(exc_info.value)


# ---------------------------------------------------------------------------
# HermesProvider tests
# ---------------------------------------------------------------------------

class TestHermesProvider:
    """Tests for the Hermes-specific status provider."""

    def test_hermes_provider_active_on_200(self, sample_entry: VaultEntry) -> None:
        """HTTP 200 response returns ok=True with 'active' status."""
        provider = HermesProvider()

        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            result = provider(sample_entry)

        assert result is not None
        assert result.ok is True
        assert result.status == "active"
        assert "127.0.0.1:18080" in result.message

    def test_hermes_provider_degraded_on_non_200(self, sample_entry: VaultEntry) -> None:
        """HTTP non-200 response returns ok=False with 'degraded' status."""
        provider = HermesProvider()

        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 503
            mock_get.return_value = mock_response

            result = provider(sample_entry)

        assert result is not None
        assert result.ok is False
        assert result.status == "degraded"

    def test_hermes_provider_unavailable_on_connection_error(
        self, sample_entry: VaultEntry
    ) -> None:
        """Connection error returns ok=False with 'unavailable' status."""
        provider = HermesProvider()

        with patch("requests.get") as mock_get:
            mock_get.side_effect = requests.RequestException("Connection refused")

            result = provider(sample_entry)

        assert result is not None
        assert result.ok is False
        assert result.status == "unavailable"

    def test_hermes_provider_uses_custom_host_port(self, sample_entry: VaultEntry) -> None:
        """Provider respects custom host/port settings."""
        provider = HermesProvider(host="192.168.1.100", port=9000)

        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            result = provider(sample_entry)

        assert result is not None
        assert result.ok is True
        assert "192.168.1.100:9000" in result.message


# ---------------------------------------------------------------------------
# OpenClawProvider tests
# ---------------------------------------------------------------------------

class TestOpenClawProvider:
    """Tests for the OpenClaw-specific status provider."""

    def test_openclaw_provider_active_on_ok_live_json(self, sample_entry: VaultEntry) -> None:
        """JSON response with ok=true, status=live returns ok=True with 'active' status."""
        provider = OpenClawProvider()

        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"ok": True, "status": "live"}
            mock_get.return_value = mock_response

            result = provider(sample_entry)

        assert result is not None
        assert result.ok is True
        assert result.status == "active"
        assert "127.0.0.1:18789" in result.message

    def test_openclaw_provider_degraded_on_wrong_response(
        self, sample_entry: VaultEntry
    ) -> None:
        """Wrong JSON response returns ok=False with 'degraded' status."""
        provider = OpenClawProvider()

        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"ok": False, "status": "dead"}
            mock_get.return_value = mock_response

            result = provider(sample_entry)

        assert result is not None
        assert result.ok is False
        assert result.status == "degraded"

    def test_openclaw_provider_degraded_on_non_200(self, sample_entry: VaultEntry) -> None:
        """HTTP non-200 response returns ok=False with 'degraded' status."""
        provider = OpenClawProvider()

        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_get.return_value = mock_response

            result = provider(sample_entry)

        assert result is not None
        assert result.ok is False
        assert result.status == "degraded"

    def test_openclaw_provider_unavailable_on_connection_error(
        self, sample_entry: VaultEntry
    ) -> None:
        """Connection error returns ok=False with 'unavailable' status."""
        provider = OpenClawProvider()

        with patch("requests.get") as mock_get:
            mock_get.side_effect = requests.RequestException("Connection refused")

            result = provider(sample_entry)

        assert result is not None
        assert result.ok is False
        assert result.status == "unavailable"

    def test_openclaw_provider_uses_custom_host_port(self, sample_entry: VaultEntry) -> None:
        """Provider respects custom host/port settings."""
        provider = OpenClawProvider(host="192.168.1.100", port=9999)

        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"ok": True, "status": "live"}
            mock_get.return_value = mock_response

            result = provider(sample_entry)

        assert result is not None
        assert result.ok is True
        assert "192.168.1.100:9999" in result.message


# --------------------------------------------------------------------------
# Realistic HTTP Response Tests
# --------------------------------------------------------------------------


class TestHermesProviderRealisticResponses:
    """Tests for HermesProvider with realistic HTTP response structures."""

    def _make_response(self, status_code: int, json_data: dict | None = None, headers: dict | None = None, text: str = "") -> MagicMock:
        """Create a realistic HTTP response mock with proper attribute structure."""
        response = MagicMock()
        response.status_code = status_code
        response.headers = headers or {"Content-Type": "application/json"}
        response.text = text
        if json_data is not None:
            response.json.return_value = json_data
        else:
            response.json.side_effect = ValueError("No JSON body")
        return response

    def test_hermes_provider_handles_response_headers(self, sample_entry: VaultEntry) -> None:
        """Hermes health endpoint with realistic response including headers."""
        provider = HermesProvider(host="192.168.1.50", port=18080)

        with patch("requests.get") as mock_get:
            mock_response = self._make_response(
                status_code=200,
                headers={
                    "Content-Type": "application/json",
                    "Server": "Hermes/1.0",
                    "X-Health-Check": "ok",
                },
            )
            mock_get.return_value = mock_response

            result = provider(sample_entry)

        assert result.ok is True
        assert result.status == "active"
        # Verify the response has the expected server header
        assert mock_response.headers["Server"] == "Hermes/1.0"

    def test_hermes_provider_handles_502_bad_gateway(self, sample_entry: VaultEntry) -> None:
        """Hermes returning 502 Bad Gateway is degraded."""
        provider = HermesProvider(host="192.168.1.50", port=18080)

        with patch("requests.get") as mock_get:
            mock_response = self._make_response(
                status_code=502,
                headers={"Content-Type": "text/html"},
                text="Bad Gateway",
            )
            mock_get.return_value = mock_response

            result = provider(sample_entry)

        assert result.ok is False
        assert result.status == "degraded"
        assert "502" in result.message


class TestOpenClawProviderRealisticResponses:
    """Tests for OpenClawProvider with realistic HTTP response structures."""

    def _make_response(self, status_code: int, json_data: dict | None = None, headers: dict | None = None, text: str = "") -> MagicMock:
        """Create a realistic HTTP response mock."""
        response = MagicMock()
        response.status_code = status_code
        response.headers = headers or {"Content-Type": "application/json"}
        response.text = text
        if json_data is not None:
            response.json.return_value = json_data
        else:
            response.json.side_effect = ValueError("No JSON body")
        return response

    def test_openclaw_provider_parses_realistic_live_response(self, sample_entry: VaultEntry) -> None:
        """OpenClaw with realistic live status JSON response."""
        provider = OpenClawProvider(host="192.168.1.100", port=18789)

        with patch("requests.get") as mock_get:
            mock_response = self._make_response(
                status_code=200,
                json_data={
                    "ok": True,
                    "status": "live",
                    "version": "2.1.0",
                    "uptime_seconds": 86400,
                    "services": {
                        "gateway": "healthy",
                        "worker": "healthy",
                    },
                },
                headers={
                    "Content-Type": "application/json",
                    "X-Gateway-Id": "oc-12345",
                },
            )
            mock_get.return_value = mock_response

            result = provider(sample_entry)

        assert result.ok is True
        assert result.status == "active"
        assert "192.168.1.100:18789" in result.message

    def test_openclaw_provider_handles_degraded_status_in_json(self, sample_entry: VaultEntry) -> None:
        """OpenClaw returning 200 but with degraded status in JSON body."""
        provider = OpenClawProvider(host="192.168.1.100", port=18789)

        with patch("requests.get") as mock_get:
            mock_response = self._make_response(
                status_code=200,
                json_data={
                    "ok": False,
                    "status": "degraded",
                    "issue": "Worker pool at capacity",
                },
            )
            mock_get.return_value = mock_response

            result = provider(sample_entry)

        assert result.ok is False
        assert result.status == "degraded"
        # Message should include the JSON data
        assert "degraded" in result.message.lower() or "unexpected" in result.message.lower()

    def test_openclaw_provider_handles_malformed_json_response(self, sample_entry: VaultEntry) -> None:
        """OpenClaw returning 200 but malformed JSON body is degraded."""
        provider = OpenClawProvider(host="192.168.1.100", port=18789)

        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"Content-Type": "application/json"}
            mock_response.text = "{ invalid json }"
            # Simulate JSON parse error
            mock_response.json.side_effect = ValueError("Expecting property name")

            mock_get.return_value = mock_response

            result = provider(sample_entry)

        assert result.ok is False
        assert result.status == "degraded"
        assert "invalid JSON" in result.message

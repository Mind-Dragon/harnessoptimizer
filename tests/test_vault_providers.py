"""Tests for vault provider validation backends (v052-live-validation).

These tests prove the HTTP-based status provider backends work with mocked
HTTP responses - no real API keys or network calls are made.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from hermesoptimizer.vault import (
    StatusProvider,
    ValidationResult,
    VaultEntry,
    VaultInventory,
    build_vault_inventory,
    validate_inventory,
)
from hermesoptimizer.vault.providers.http import (
    HTTPStatusProvider,
    AWSProvider,
    GCPProvider,
    AzureProvider,
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


@pytest.fixture
def sample_inventory(tmp_path: Path) -> VaultInventory:
    """A minimal VaultInventory for testing."""
    vault = tmp_path / ".vault"
    vault.mkdir()
    f1 = vault / "a.env"
    f1.write_text("AWS_KEY=foo\n", encoding="utf-8")
    f2 = vault / "b.env"
    f2.write_text("GCP_KEY=bar\n", encoding="utf-8")
    return VaultInventory(roots=[vault], files=[f1, f2], entries=[])


# ---------------------------------------------------------------------------
# HTTPStatusProvider tests
# ---------------------------------------------------------------------------

class TestHTTPStatusProvider:
    """Tests for the generic HTTP status provider."""

    def test_http_provider_returns_validation_result_on_200(
        self,
        sample_entry: VaultEntry,
    ) -> None:
        """HTTP 200 response returns ok=True with 'active' status."""
        provider = HTTPStatusProvider(endpoint="https://api.example.com/health")

        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            result = provider(sample_entry)

        assert result is not None
        assert result.ok is True
        assert result.status == "active"
        assert "api.example.com" in result.message

    def test_http_provider_returns_degraded_on_non_200(
        self,
        sample_entry: VaultEntry,
    ) -> None:
        """HTTP non-200 response returns ok=False with 'degraded' status."""
        provider = HTTPStatusProvider(endpoint="https://api.example.com/health")

        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 503
            mock_get.return_value = mock_response

            result = provider(sample_entry)

        assert result is not None
        assert result.ok is False
        assert result.status == "degraded"

    def test_http_provider_returns_error_on_request_exception(
        self,
        sample_entry: VaultEntry,
    ) -> None:
        """Request exception returns ok=False with 'unavailable' status."""
        provider = HTTPStatusProvider(endpoint="https://api.example.com/health")

        with patch("requests.get") as mock_get:
            mock_get.side_effect = requests.RequestException("Connection refused")

            result = provider(sample_entry)

        assert result is not None
        assert result.ok is False
        assert result.status == "unavailable"

    def test_http_provider_uses_custom_timeout(
        self,
        sample_entry: VaultEntry,
    ) -> None:
        """Provider respects custom timeout setting."""
        provider = HTTPStatusProvider(
            endpoint="https://api.example.com/health",
            timeout=10.0,
        )

        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            provider(sample_entry)

        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs.get("timeout") == 10.0

    def test_http_provider_injects_auth_header(
        self,
        sample_entry: VaultEntry,
    ) -> None:
        """Provider injects Authorization header when token is set."""
        provider = HTTPStatusProvider(
            endpoint="https://api.example.com/health",
            token="Bearer secret123",
        )

        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            provider(sample_entry)

        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs.get("headers", {}).get("Authorization") == "Bearer secret123"

    def test_http_provider_can_act_as_status_provider_for_validate_inventory(
        self,
        tmp_path: Path,
    ) -> None:
        """HTTP provider can be passed directly to validate_inventory."""
        vault = tmp_path / ".vault"
        vault.mkdir()
        f = vault / "test.env"
        f.write_text("KEY=value\n", encoding="utf-8")
        inventory = build_vault_inventory([vault])

        provider = HTTPStatusProvider(endpoint="https://api.example.com/health")

        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            results = validate_inventory(inventory, status_provider=provider)

        assert len(results) == 1
        assert results[0].ok is True


# ---------------------------------------------------------------------------
# AWSProvider tests
# ---------------------------------------------------------------------------

class TestAWSProvider:
    """Tests for the AWS-specific status provider."""

    def test_aws_provider_returns_active_on_valid_credentials(
        self,
        sample_entry: VaultEntry,
    ) -> None:
        """Valid AWS credentials return ok=True."""
        provider = AWSProvider(
            endpoint="https://sts.amazonaws.com",
            token="AKIAEXAMPLE123456789",
        )

        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = """<?xml version="1.0" encoding="UTF-8"?>
            <GetCallerIdentityResponse>
                <Arn>arn:aws:iam::123456789012:user/test</Arn>
                <UserId>AKIAEXAMPLE123456789</UserId>
                <Account>123456789012</Account>
            </GetCallerIdentityResponse>"""
            mock_post.return_value = mock_response

            result = provider(sample_entry)

        assert result is not None
        assert result.ok is True
        assert result.status == "active"

    def test_aws_provider_returns_degraded_on_invalid_credentials(
        self,
        sample_entry: VaultEntry,
    ) -> None:
        """Invalid AWS credentials return ok=False."""
        provider = AWSProvider(
            endpoint="https://sts.amazonaws.com",
            token="AKIAINVALID",
        )

        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 403
            mock_post.return_value = mock_response

            result = provider(sample_entry)

        assert result is not None
        assert result.ok is False
        assert result.status == "degraded"

    def test_aws_provider_returns_unavailable_on_connection_error(
        self,
        sample_entry: VaultEntry,
    ) -> None:
        """Connection error returns ok=False with unavailable status."""
        provider = AWSProvider(
            endpoint="https://sts.amazonaws.com",
            token="AKIAEXAMPLE123456789",
        )

        with patch("requests.post") as mock_post:
            mock_post.side_effect = requests.RequestException("Connection refused")

            result = provider(sample_entry)

        assert result is not None
        assert result.ok is False
        assert result.status == "unavailable"

    def test_aws_provider_injects_aws_headers(
        self,
        sample_entry: VaultEntry,
    ) -> None:
        """Provider injects AWS-specific headers including Authorization."""
        provider = AWSProvider(
            endpoint="https://sts.amazonaws.com",
            token="AKIAEXAMPLE123456789",
        )

        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = """<?xml version="1.0" encoding="UTF-8"?>
            <GetCallerIdentityResponse>
                <Arn>arn:aws:iam::123456789012:user/test</Arn>
                <UserId>AKIAEXAMPLE123456789</UserId>
                <Account>123456789012</Account>
            </GetCallerIdentityResponse>"""
            mock_post.return_value = mock_response

            provider(sample_entry)

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args.kwargs
        assert "headers" in call_kwargs
        assert "Authorization" in call_kwargs["headers"]


# ---------------------------------------------------------------------------
# GCPProvider tests
# ---------------------------------------------------------------------------

class TestGCPProvider:
    """Tests for the GCP-specific status provider."""

    def test_gcp_provider_returns_active_on_valid_token(
        self,
        sample_entry: VaultEntry,
    ) -> None:
        """Valid GCP token returns ok=True."""
        provider = GCPProvider(
            endpoint="https://oauth2.googleapis.com/token_info",
            token="ya29.valid_token",
        )

        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"email": "test@example.com"}
            mock_get.return_value = mock_response

            result = provider(sample_entry)

        assert result is not None
        assert result.ok is True
        assert result.status == "active"

    def test_gcp_provider_returns_degraded_on_invalid_token(
        self,
        sample_entry: VaultEntry,
    ) -> None:
        """Invalid GCP token returns ok=False."""
        provider = GCPProvider(
            endpoint="https://oauth2.googleapis.com/token_info",
            token="invalid_token",
        )

        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_get.return_value = mock_response

            result = provider(sample_entry)

        assert result is not None
        assert result.ok is False
        assert result.status == "degraded"


# ---------------------------------------------------------------------------
# AzureProvider tests
# ---------------------------------------------------------------------------

class TestAzureProvider:
    """Tests for the Azure-specific status provider."""

    def test_azure_provider_returns_active_on_valid_token(
        self,
        sample_entry: VaultEntry,
    ) -> None:
        """Valid Azure token returns ok=True."""
        provider = AzureProvider(
            endpoint="https://login.microsoftonline.com/common/discovery/v2.0/keys",
            token="eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.valid",
        )

        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"keys": []}
            mock_get.return_value = mock_response

            result = provider(sample_entry)

        assert result is not None
        assert result.ok is True
        assert result.status == "active"

    def test_azure_provider_returns_degraded_on_invalid_token(
        self,
        sample_entry: VaultEntry,
    ) -> None:
        """Invalid Azure token returns ok=False."""
        provider = AzureProvider(
            endpoint="https://login.microsoftonline.com/common/discovery/v2.0/keys",
            token="invalid_token",
        )

        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_get.return_value = mock_response

            result = provider(sample_entry)

        assert result is not None
        assert result.ok is False
        assert result.status == "degraded"


# ---------------------------------------------------------------------------
# Provider integration tests
# ---------------------------------------------------------------------------

class TestProviderIntegration:
    """Integration tests proving providers work with validate_inventory."""

    def test_multiple_providers_can_be_chained(
        self,
        tmp_path: Path,
    ) -> None:
        """Multiple providers can be composed together."""
        vault = tmp_path / ".vault"
        vault.mkdir()
        f1 = vault / "aws.env"
        f1.write_text("AWS_KEY=foo\n", encoding="utf-8")
        f2 = vault / "gcp.env"
        f2.write_text("GCP_KEY=bar\n", encoding="utf-8")
        inventory = build_vault_inventory([vault])

        # Create a chain that routes to different providers based on entry
        def chained_provider(entry: VaultEntry) -> ValidationResult | None:
            if "aws" in str(entry.source_path):
                aws_provider = AWSProvider(
                    endpoint="https://sts.amazonaws.com",
                    token="AKIAEXAMPLE123456789",
                )
                with patch("requests.post") as mock_post:
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    mock_response.text = """<?xml version="1.0" encoding="UTF-8"?>
                    <GetCallerIdentityResponse>
                        <Arn>arn:aws:iam::123456789012:user/test</Arn>
                        <UserId>AKIAEXAMPLE123456789</UserId>
                        <Account>123456789012</Account>
                    </GetCallerIdentityResponse>"""
                    mock_post.return_value = mock_response
                    return aws_provider(entry)
            elif "gcp" in str(entry.source_path):
                gcp_provider = GCPProvider(
                    endpoint="https://oauth2.googleapis.com/token_info",
                    token="ya29.valid_token",
                )
                with patch("requests.get") as mock_get:
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    mock_response.json.return_value = {"email": "test@example.com"}
                    mock_get.return_value = mock_response
                    return gcp_provider(entry)
            return None

        results = validate_inventory(inventory, status_provider=chained_provider)

        assert len(results) == 2
        # Both should be active since our mocks return success
        assert all(r.ok for r in results)

"""HTTP-based status provider backends for vault validation.

These providers perform live HTTP checks against cloud provider endpoints
or generic HTTP health endpoints. They implement the StatusProvider hook
and return ValidationResult objects.

All network operations are designed to be mocked in tests - no real API
calls are made during test execution.
"""
from __future__ import annotations

from typing import Any

import requests

from hermesoptimizer.vault import StatusProvider, ValidationResult, VaultEntry


# ---------------------------------------------------------------------------
# Generic HTTP Status Provider
# ---------------------------------------------------------------------------


class HTTPStatusProvider:
    """Generic HTTP-based status provider.

    Performs an HTTP GET request to a specified endpoint and translates
    the response into a ValidationResult.

    Args:
        endpoint: The URL to check (e.g., https://api.example.com/health).
        token: Optional Bearer token to include in the Authorization header.
        timeout: Request timeout in seconds (default 5.0).
    """

    def __init__(
        self,
        endpoint: str,
        token: str | None = None,
        timeout: float = 5.0,
    ) -> None:
        self.endpoint = endpoint
        self.token = token
        self.timeout = timeout

    def __call__(self, entry: VaultEntry) -> ValidationResult:
        """Check the HTTP endpoint and return a ValidationResult.

        Returns:
            ValidationResult with:
            - ok=True, status="active" if HTTP 200
            - ok=False, status="degraded" if HTTP non-200
            - ok=False, status="unavailable" if request fails
        """
        headers: dict[str, str] = {}
        if self.token:
            headers["Authorization"] = self.token

        try:
            response = requests.get(
                self.endpoint,
                headers=headers if headers else None,
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return ValidationResult(
                    source_path=str(entry.source_path),
                    ok=True,
                    status="active",
                    message=f"HTTP check passed for {self.endpoint}",
                )
            return ValidationResult(
                source_path=str(entry.source_path),
                ok=False,
                status="degraded",
                message=f"HTTP check returned {response.status_code} for {self.endpoint}",
            )
        except requests.RequestException as exc:
            return ValidationResult(
                source_path=str(entry.source_path),
                ok=False,
                status="unavailable",
                message=f"HTTP check failed for {self.endpoint}: {exc}",
            )


# ---------------------------------------------------------------------------
# AWS Status Provider (NotImplementedError)
# ---------------------------------------------------------------------------


class AWSProvider:
    """AWS-specific status provider using STS GetCallerIdentity.

    Raises NotImplementedError because AWS STS requires SigV4 signing
    which is not yet implemented.

    Use the generic HTTPStatusProvider with an AWS health endpoint instead.
    """

    def __init__(
        self,
        endpoint: str = "https://sts.amazonaws.com",
        token: str | None = None,
        timeout: float = 5.0,
    ) -> None:
        pass

    def __call__(self, entry: VaultEntry) -> ValidationResult:
        """Raise NotImplementedError.

        AWS STS requires SigV4 signing which is not yet implemented.
        Use the generic HTTPStatusProvider with an AWS health endpoint instead.
        """
        raise NotImplementedError(
            "AWS STS requires SigV4 signing which is not yet implemented. "
            "Use the generic HTTPStatusProvider with an AWS health endpoint instead."
        )


# ---------------------------------------------------------------------------
# GCP Status Provider
# ---------------------------------------------------------------------------


class GCPProvider:
    """GCP-specific status provider using OAuth token info endpoint.

    Performs an HTTP GET to the Google OAuth2 token_info endpoint to
    validate if a GCP access token is valid.

    Args:
        endpoint: GCP token info endpoint (default: https://oauth2.googleapis.com/token_info).
        token: GCP OAuth2 access token to validate.
        timeout: Request timeout in seconds (default 5.0).
    """

    def __init__(
        self,
        endpoint: str = "https://oauth2.googleapis.com/token_info",
        token: str | None = None,
        timeout: float = 5.0,
    ) -> None:
        self.endpoint = endpoint
        self.token = token
        self.timeout = timeout

    def __call__(self, entry: VaultEntry) -> ValidationResult:
        """Validate GCP OAuth2 token via token_info endpoint.

        Returns:
            ValidationResult with:
            - ok=True, status="active" if token is valid (HTTP 200)
            - ok=False, status="degraded" if token is invalid (HTTP 401)
            - ok=False, status="unavailable" if request fails
        """
        if not self.token:
            return ValidationResult(
                source_path=str(entry.source_path),
                ok=False,
                status="degraded",
                message="GCP token not provided",
            )

        headers = {
            "Authorization": f"Bearer {self.token}"
        } if self.token else {}
        try:
            response = requests.get(
                self.endpoint,
                headers=headers,
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return ValidationResult(
                    source_path=str(entry.source_path),
                    ok=True,
                    status="active",
                    message=f"GCP token valid (oauth2 check passed)",
                )
            return ValidationResult(
                source_path=str(entry.source_path),
                ok=False,
                status="degraded",
                message=f"GCP token invalid (oauth2 returned {response.status_code})",
            )
        except requests.RequestException as exc:
            return ValidationResult(
                source_path=str(entry.source_path),
                ok=False,
                status="unavailable",
                message=f"GCP oauth2 check failed: {exc}",
            )


# ---------------------------------------------------------------------------
# Azure Status Provider (NotImplementedError)
# ---------------------------------------------------------------------------


class AzureProvider:
    """Azure-specific status provider using Microsoft identity validation.

    Raises NotImplementedError because Azure AD token validation requires
    JWKS-based JWT verification which is not yet implemented.

    Use the generic HTTPStatusProvider with an Azure health endpoint instead.
    """

    def __init__(
        self,
        endpoint: str = "https://login.microsoftonline.com/common/discovery/v2.0/keys",
        token: str | None = None,
        timeout: float = 5.0,
    ) -> None:
        pass

    def __call__(self, entry: VaultEntry) -> ValidationResult:
        """Raise NotImplementedError.

        Azure AD token validation requires JWKS-based JWT verification
        which is not yet implemented.
        Use the generic HTTPStatusProvider with an Azure health endpoint instead.
        """
        raise NotImplementedError(
            "Azure AD token validation requires JWKS-based JWT verification "
            "which is not yet implemented. "
            "Use the generic HTTPStatusProvider with an Azure health endpoint instead."
        )


# ---------------------------------------------------------------------------
# Hermes Status Provider
# ---------------------------------------------------------------------------


class HermesProvider:
    """Hermes-specific status provider using main thread health endpoint.

    Performs an HTTP GET to the Hermes main thread health endpoint
    to check if the service is running.

    Args:
        host: Hermes host (default: 127.0.0.1).
        port: Hermes port (default: 18080).
        timeout: Request timeout in seconds (default 5.0).
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 18080,
        timeout: float = 5.0,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.endpoint = f"http://{host}:{port}"

    def __call__(self, entry: VaultEntry) -> ValidationResult:
        """Check the Hermes health endpoint and return a ValidationResult.

        Returns:
            ValidationResult with:
            - ok=True, status="active" if HTTP 200
            - ok=False, status="degraded" if HTTP non-200
            - ok=False, status="unavailable" if request fails
        """
        try:
            response = requests.get(
                self.endpoint,
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return ValidationResult(
                    source_path=str(entry.source_path),
                    ok=True,
                    status="active",
                    message=f"Hermes health check passed for {self.endpoint}",
                )
            return ValidationResult(
                source_path=str(entry.source_path),
                ok=False,
                status="degraded",
                message=f"Hermes health check returned {response.status_code} for {self.endpoint}",
            )
        except requests.RequestException as exc:
            return ValidationResult(
                source_path=str(entry.source_path),
                ok=False,
                status="unavailable",
                message=f"Hermes health check failed for {self.endpoint}: {exc}",
            )


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------


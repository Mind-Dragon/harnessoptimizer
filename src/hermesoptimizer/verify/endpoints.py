"""
Phase 2 endpoint verification helpers for Hermes.

Provides deterministic, testable endpoint verification that does NOT
require live network access in tests. All HTTP operations go through
a swappable _http_get helper so tests can inject mocked responses.

Detects:
- Right-key-wrong-endpoint (RKWE): correct API key but wrong base URL
- Stale model names: model name not in provider's known list
- Endpoint drift: configured endpoint differs from canonical
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable
import urllib.request
import urllib.error

from hermesoptimizer.sources.provider_truth import (
    ProviderTruthRecord,
    ProviderTruthStore,
)


# ---------------------------------------------------------------------------
# HTTP abstraction (swappable for tests)
# ---------------------------------------------------------------------------

# Default HTTP getter; replace with a mock in tests
_http_get: Callable[[str], tuple[int, str]] | None = None


def _default_http_get(url: str) -> tuple[int, str]:
    """
    Default HTTP GET. Returns (status_code, body).
    Raises on network error.
    """
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        raise


def _get_http_getter() -> Callable[[str], tuple[int, str]]:
    return _http_get or _default_http_get


def set_http_get(getter: Callable[[str], tuple[int, str]]) -> None:
    """Replace the HTTP getter (used in tests to inject mocks)."""
    global _http_get
    _http_get = getter


def reset_http_get() -> None:
    """Restore the default HTTP getter."""
    global _http_get
    _http_get = None


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

class EndpointCheckStatus(Enum):
    OK = "ok"
    RKWE = "rkwe"          # right-key-wrong-endpoint
    STALE_MODEL = "stale_model"
    ENDPOINT_DRIFT = "endpoint_drift"
    UNKNOWN_PROVIDER = "unknown_provider"
    NETWORK_ERROR = "network_error"
    FAILED = "failed"


@dataclass
class EndpointCheckResult:
    provider: str
    model: str | None
    configured_endpoint: str | None
    status: EndpointCheckStatus
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def is_ok(self) -> bool:
        return self.status == EndpointCheckStatus.OK

    def is_issue(self) -> bool:
        return self.status not in (EndpointCheckStatus.OK, EndpointCheckStatus.UNKNOWN_PROVIDER)


# ---------------------------------------------------------------------------
# Core verification functions
# ---------------------------------------------------------------------------

def verify_endpoint(
    provider: str,
    endpoint: str,
    model: str | None,
    truth_store: ProviderTruthStore,
) -> EndpointCheckResult:
    """
    Verify a provider/endpoint/model configuration against provider truth.

    Performs the following checks in order:
    1. If provider is unknown in truth store -> UNKNOWN_PROVIDER
    2. RKWE check: endpoint vs canonical endpoint
    3. Stale model check: model vs known model list
    4. If all pass -> OK

    Parameters:
        provider: Provider name (e.g. "openai")
        endpoint: Configured base URL
        model: Configured model name (may be None)
        truth_store: ProviderTruthStore with canonical truth

    Returns:
        EndpointCheckResult with status and message
    """
    rec = truth_store.get(provider)

    if rec is None:
        return EndpointCheckResult(
            provider=provider,
            model=model,
            configured_endpoint=endpoint,
            status=EndpointCheckStatus.UNKNOWN_PROVIDER,
            message=f"Provider '{provider}' not found in truth store",
        )

    # Check 1: right-key-wrong-endpoint
    is_rkwe, rkwe_msg = truth_store.check_right_key_wrong_endpoint(provider, endpoint)
    if is_rkwe:
        return EndpointCheckResult(
            provider=provider,
            model=model,
            configured_endpoint=endpoint,
            status=EndpointCheckStatus.RKWE,
            message=rkwe_msg,
            details={"canonical_endpoint": rec.canonical_endpoint},
        )

    # Check 2: stale model
    if model:
        is_stale, stale_msg = truth_store.check_stale_model(provider, model)
        if is_stale:
            return EndpointCheckResult(
                provider=provider,
                model=model,
                configured_endpoint=endpoint,
                status=EndpointCheckStatus.STALE_MODEL,
                message=stale_msg,
                details={
                    "known_models": rec.known_models,
                    "deprecated_models": rec.deprecated_models,
                },
            )

    return EndpointCheckResult(
        provider=provider,
        model=model,
        configured_endpoint=endpoint,
        status=EndpointCheckStatus.OK,
        message=f"Provider '{provider}' endpoint and model verified OK",
        details={"canonical_endpoint": rec.canonical_endpoint},
    )


def verify_provider_truth(
    configured_providers: list[dict[str, Any]],
    truth_store: ProviderTruthStore,
) -> list[EndpointCheckResult]:
    """
    Verify a list of configured providers against the truth store.

    Parameters:
        configured_providers: List of dicts with keys "provider", "base_url", "model"
        truth_store: ProviderTruthStore

    Returns:
        List of EndpointCheckResult, one per configured provider
    """
    results: list[EndpointCheckResult] = []
    for cfg in configured_providers:
        result = verify_endpoint(
            provider=cfg.get("provider", ""),
            endpoint=cfg.get("base_url", ""),
            model=cfg.get("model"),
            truth_store=truth_store,
        )
        results.append(result)
    return results


def check_endpoint_live(endpoint: str) -> tuple[bool, str]:
    """
    Perform a live HTTP GET on an endpoint's health or root URL.

    Returns (is_reachable, message).
    Uses the swappable _http_get helper so tests can inject mocks.
    """
    try:
        status, body = _get_http_getter()(endpoint)
        if status == 200:
            return True, f"Endpoint reachable (HTTP {status})"
        return False, f"Endpoint returned HTTP {status}"
    except Exception as e:
        return False, f"Network error: {e}"

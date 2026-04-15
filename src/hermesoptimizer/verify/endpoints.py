"""
Phase 2 endpoint verification helpers for Hermes.

Provides deterministic, testable endpoint verification that does NOT
require live network access in tests. All HTTP operations go through
a swappable _http_get helper so tests can inject mocked responses.

Detects:
- Right-key-wrong-endpoint (RKWE): correct API key but wrong base URL
- Stale model names: model name not in provider's known list
- Endpoint drift: configured endpoint differs from canonical
- Auth failures when a live endpoint returns 401/403
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable
import urllib.error
import urllib.request

import yaml

from hermesoptimizer.sources.provider_truth import (
    ProviderTruthRecord,
    ProviderTruthStore,
)


# ---------------------------------------------------------------------------
# HTTP abstraction (swappable for tests)
# ---------------------------------------------------------------------------

# Default HTTP getter; replace with a mock in tests.
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
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return e.code, body
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
# Live truth gating
# ---------------------------------------------------------------------------


def is_live_truth_enabled() -> bool:
    """Return True when live truth lookups are explicitly enabled."""
    value = os.getenv("HERMES_LIVE_TRUTH_ENABLED", "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


class EndpointCheckStatus(Enum):
    OK = "ok"
    RKWE = "rkwe"  # right-key-wrong-endpoint
    STALE_MODEL = "stale_model"
    ENDPOINT_DRIFT = "endpoint_drift"
    UNKNOWN_PROVIDER = "unknown_provider"
    NETWORK_ERROR = "network_error"
    AUTH_FAILURE = "auth_failure"
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


def probe_endpoint_live(endpoint: str) -> tuple[int | None, str, str]:
    """Probe an endpoint and return (status_code, body, message)."""
    try:
        status, body = _get_http_getter()(endpoint)
        return status, body, f"Endpoint returned HTTP {status}"
    except Exception as e:
        return None, "", f"Network error: {e}"


def check_endpoint_live(endpoint: str) -> tuple[bool, str]:
    """
    Perform a live HTTP GET on an endpoint's health or root URL.

    Returns (is_reachable, message).
    Uses the swappable _http_get helper so tests can inject mocks.
    """
    status, _, message = probe_endpoint_live(endpoint)
    return status == 200, message


@dataclass(slots=True)
class LiveTruthAdapter:
    """Fetch provider truth records from a live source URL."""

    def fetch_record(self, provider: str, source_url: str) -> ProviderTruthRecord | None:
        status, body, _ = probe_endpoint_live(source_url)
        if status != 200 or not body:
            return None

        payload: Any
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            try:
                payload = yaml.safe_load(body)
            except Exception:
                return None

        if not isinstance(payload, dict):
            return None

        canonical_endpoint = payload.get("canonical_endpoint") or payload.get("endpoint") or payload.get("base_url") or ""
        if not canonical_endpoint:
            servers = payload.get("servers")
            if isinstance(servers, list) and servers:
                first = servers[0]
                if isinstance(first, dict):
                    canonical_endpoint = first.get("url") or ""
        paths = payload.get("paths")
        if canonical_endpoint and isinstance(paths, dict) and "/models" in paths and not canonical_endpoint.rstrip("/").endswith("/models"):
            canonical_endpoint = canonical_endpoint.rstrip("/") + "/models"
        known_models = payload.get("known_models") or payload.get("models") or []
        deprecated_models = payload.get("deprecated_models") or []
        capabilities = payload.get("capabilities") or []
        context_window = int(payload.get("context_window") or payload.get("contextWindow") or 0)
        confidence = payload.get("confidence", "medium")
        source_url_value = payload.get("source_url") or source_url
        provider_name = payload.get("provider") or provider

        if not canonical_endpoint:
            return None

        return ProviderTruthRecord(
            provider=provider_name,
            canonical_endpoint=canonical_endpoint,
            known_models=list(known_models),
            deprecated_models=list(deprecated_models),
            capabilities=list(capabilities),
            context_window=context_window,
            source_url=source_url_value,
            confidence=confidence,
            auth_type=payload.get("auth_type"),
        )


def _merge_truth_records(base: ProviderTruthRecord, live: ProviderTruthRecord) -> ProviderTruthRecord:
    """Overlay live truth onto local truth, preserving local model metadata when the live source omits it."""
    return ProviderTruthRecord(
        provider=live.provider or base.provider,
        canonical_endpoint=live.canonical_endpoint or base.canonical_endpoint,
        known_models=live.known_models or base.known_models,
        deprecated_models=live.deprecated_models or base.deprecated_models,
        capabilities=live.capabilities or base.capabilities,
        context_window=live.context_window or base.context_window,
        source_url=live.source_url or base.source_url,
        confidence=live.confidence or base.confidence,
        auth_type=live.auth_type or base.auth_type,
    )


def _effective_truth_record(
    provider: str,
    truth_store: ProviderTruthStore,
    *,
    use_live_truth: bool | None = None,
) -> ProviderTruthRecord | None:
    rec = truth_store.get(provider)
    if rec is None:
        return None
    if use_live_truth is None:
        use_live_truth = is_live_truth_enabled()
    if use_live_truth and rec.source_url:
        live_rec = LiveTruthAdapter().fetch_record(provider, rec.source_url)
        if live_rec is not None:
            return _merge_truth_records(rec, live_rec)
    return rec


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


def verify_endpoint_with_live(
    provider: str,
    endpoint: str,
    model: str | None,
    truth_store: ProviderTruthStore,
    *,
    use_live_truth: bool | None = None,
) -> EndpointCheckResult:
    """
    Verify a provider configuration, refreshing truth from live docs/endpoints
    when the live-truth gate is enabled.
    """
    rec = _effective_truth_record(provider, truth_store, use_live_truth=use_live_truth)
    if rec is None:
        return EndpointCheckResult(
            provider=provider,
            model=model,
            configured_endpoint=endpoint,
            status=EndpointCheckStatus.UNKNOWN_PROVIDER,
            message=f"Provider '{provider}' not found in truth store",
        )

    if rec.canonical_endpoint and not rec.is_endpoint_canonical(endpoint):
        return EndpointCheckResult(
            provider=provider,
            model=model,
            configured_endpoint=endpoint,
            status=EndpointCheckStatus.RKWE,
            message=(
                f"Endpoint mismatch for provider '{provider}': expected '{rec.canonical_endpoint}' "
                f"but got '{endpoint}'"
            ),
            details={"canonical_endpoint": rec.canonical_endpoint, "source_url": rec.source_url},
        )

    if model and not rec.is_model_known(model):
        status = EndpointCheckStatus.STALE_MODEL if rec.is_model_deprecated(model) else EndpointCheckStatus.STALE_MODEL
        msg = (
            f"Model '{model}' for provider '{provider}' is deprecated"
            if rec.is_model_deprecated(model)
            else f"Model '{model}' for provider '{provider}' is not in known model list"
        )
        return EndpointCheckResult(
            provider=provider,
            model=model,
            configured_endpoint=endpoint,
            status=status,
            message=msg,
            details={
                "known_models": rec.known_models,
                "deprecated_models": rec.deprecated_models,
                "source_url": rec.source_url,
            },
        )

    status_code, _, probe_msg = probe_endpoint_live(endpoint)
    if status_code in {401, 403}:
        details = {"source_url": rec.source_url}
        message = probe_msg
        if rec.requires_human_auth():
            details["escalation"] = "human"
            message = (
                f"OAuth-only provider '{provider}' requires human sign-off. "
                f"{probe_msg}"
            )
        return EndpointCheckResult(
            provider=provider,
            model=model,
            configured_endpoint=endpoint,
            status=EndpointCheckStatus.AUTH_FAILURE,
            message=message,
            details=details,
        )
    if status_code is not None and status_code != 200:
        return EndpointCheckResult(
            provider=provider,
            model=model,
            configured_endpoint=endpoint,
            status=EndpointCheckStatus.NETWORK_ERROR,
            message=probe_msg,
            details={"source_url": rec.source_url, "status_code": status_code},
        )
    if status_code is None:
        return EndpointCheckResult(
            provider=provider,
            model=model,
            configured_endpoint=endpoint,
            status=EndpointCheckStatus.NETWORK_ERROR,
            message=probe_msg,
            details={"source_url": rec.source_url},
        )

    return EndpointCheckResult(
        provider=provider,
        model=model,
        configured_endpoint=endpoint,
        status=EndpointCheckStatus.OK,
        message=f"Provider '{provider}' endpoint and model verified OK",
        details={"canonical_endpoint": rec.canonical_endpoint, "source_url": rec.source_url},
    )


def verify_provider_truth(
    configured_providers: list[dict[str, Any]],
    truth_store: ProviderTruthStore,
    *,
    use_live_truth: bool | None = None,
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
    if use_live_truth is None:
        use_live_truth = is_live_truth_enabled()
    for cfg in configured_providers:
        if use_live_truth:
            result = verify_endpoint_with_live(
                provider=cfg.get("provider", ""),
                endpoint=cfg.get("base_url", ""),
                model=cfg.get("model"),
                truth_store=truth_store,
                use_live_truth=use_live_truth,
            )
        else:
            result = verify_endpoint(
                provider=cfg.get("provider", ""),
                endpoint=cfg.get("base_url", ""),
                model=cfg.get("model"),
                truth_store=truth_store,
            )
        results.append(result)
    return results


def categorize_verification_results(results: list[EndpointCheckResult]) -> dict[str, list[EndpointCheckResult]]:
    """Bucket verification results by their status value."""
    buckets: dict[str, list[EndpointCheckResult]] = {}
    for result in results:
        buckets.setdefault(result.status.value, []).append(result)
    return buckets

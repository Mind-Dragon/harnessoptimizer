from __future__ import annotations

from pathlib import Path

import pytest

from hermesoptimizer.sources.provider_truth import (
    ProviderTruthRecord,
    ProviderTruthStore,
    canonical_provider_name,
    dump_provider_truth,
    load_provider_truth,
)
from hermesoptimizer.verify.endpoints import (
    EndpointCheckStatus,
    categorize_verification_results,
    reset_http_get,
    set_http_get,
    verify_endpoint,
    verify_endpoint_with_live,
    verify_provider_truth,
    is_live_truth_enabled,
)


def test_provider_truth_roundtrip(tmp_path: Path) -> None:
    store = ProviderTruthStore()
    store.add(
        ProviderTruthRecord(
            provider="openai",
            canonical_endpoint="https://api.openai.com/v1",
            known_models=["gpt-5"],
            deprecated_models=["gpt-4"],
            capabilities=["text"],
            context_window=128000,
            source_url="https://platform.openai.com/docs",
            confidence="high",
            auth_type="oauth",
        )
    )
    path = tmp_path / "truth.yaml"
    dump_provider_truth(store, path)
    loaded = load_provider_truth(path)
    assert loaded.get("openai") is not None
    assert loaded.get("openai").canonical_endpoint == "https://api.openai.com/v1"
    assert loaded.get("openai").auth_type == "oauth"


def test_provider_truth_rejects_duplicate_canonical_family() -> None:
    store = ProviderTruthStore()
    store.add(
        ProviderTruthRecord(
            provider="kimi",
            canonical_endpoint="https://api.example.com/v1",
            known_models=["kimi-k2"],
        )
    )

    with pytest.raises(ValueError):
        store.add(
            ProviderTruthRecord(
                provider="kimi-for-coding",
                canonical_endpoint="https://api.example.com/v1",
                known_models=["kimi-k2"],
            )
        )


def test_provider_truth_accepts_qwen_alias_lookup() -> None:
    store = ProviderTruthStore()
    store.add(
        ProviderTruthRecord(
            provider="bailian",
            canonical_endpoint="https://coding.dashscope.aliyuncs.com/v1",
            known_models=["qwen3.6-plus"],
        )
    )
    assert store.get("qwen") is not None
    assert store.get("bailian").canonical_endpoint == "https://coding.dashscope.aliyuncs.com/v1"


def test_canonical_provider_name_normalizes_common_aliases() -> None:
    assert canonical_provider_name("openai-codex") == "openai"
    assert canonical_provider_name("alibaba-coding-plan") == "qwen"
    assert canonical_provider_name("z.ai") == "zai"
    assert canonical_provider_name("zai-chat") == "zai"
    assert canonical_provider_name("x.ai") == "xai"





def test_verify_endpoint_detects_rkwe_and_stale_model() -> None:
    store = ProviderTruthStore()
    store.add(
        ProviderTruthRecord(
            provider="openai",
            canonical_endpoint="https://api.openai.com/v1",
            known_models=["gpt-5"],
            deprecated_models=["gpt-4"],
            confidence="high",
        )
    )
    ok = verify_endpoint("openai", "https://api.openai.com/v1", "gpt-5", store)
    rkwe = verify_endpoint("openai", "https://wrong.example/v1", "gpt-5", store)
    deprecated = verify_endpoint("openai", "https://api.openai.com/v1", "gpt-4", store)
    unknown_stale = verify_endpoint("openai", "https://api.openai.com/v1", "completely-unknown", store)
    assert ok.status == EndpointCheckStatus.OK
    assert rkwe.status == EndpointCheckStatus.RKWE
    # gpt-4 is in deprecated_models, so it should get DEPRECATED_MODEL status
    assert deprecated.status == EndpointCheckStatus.DEPRECATED_MODEL
    assert deprecated.details.get("is_deprecated") is True
    # completely-unknown is not in known or deprecated lists, so it gets STALE_MODEL
    assert unknown_stale.status == EndpointCheckStatus.STALE_MODEL
    assert unknown_stale.details.get("is_deprecated") is not True


def test_verify_provider_truth_handles_multiple_configs() -> None:
    store = ProviderTruthStore()
    store.add(
        ProviderTruthRecord(
            provider="openai",
            canonical_endpoint="https://api.openai.com/v1",
            known_models=["gpt-5"],
            confidence="high",
        )
    )
    results = verify_provider_truth(
        [
            {"provider": "openai", "base_url": "https://api.openai.com/v1", "model": "gpt-5"},
            {"provider": "missing", "base_url": "https://example.invalid", "model": "x"},
        ],
        store,
    )
    assert len(results) == 2
    assert results[0].status == EndpointCheckStatus.OK
    assert results[1].status == EndpointCheckStatus.UNKNOWN_PROVIDER


def test_verify_endpoint_live_helper_uses_mock_http_get() -> None:
    try:
        set_http_get(lambda url: (200, "ok"))
        assert verify_endpoint("openai", "https://api.openai.com/v1", "gpt-5", ProviderTruthStore()).status == EndpointCheckStatus.UNKNOWN_PROVIDER
    finally:
        reset_http_get()


def test_live_truth_gate_defaults_off(monkeypatch) -> None:
    monkeypatch.delenv("HERMES_LIVE_TRUTH_ENABLED", raising=False)
    assert is_live_truth_enabled() is False


def test_verify_endpoint_with_live_truth_distinguishes_auth_failure(monkeypatch) -> None:
    monkeypatch.setenv("HERMES_LIVE_TRUTH_ENABLED", "1")
    store = ProviderTruthStore()
    store.add(
        ProviderTruthRecord(
            provider="openai",
            canonical_endpoint="https://api.openai.com/v1",
            known_models=["gpt-5"],
            deprecated_models=["gpt-4"],
            source_url="https://truth.local/openai.json",
            confidence="high",
        )
    )

    def fake_http_get(url: str):
        if url == "https://truth.local/openai.json":
            return 200, '{"provider":"openai","canonical_endpoint":"https://api.openai.com/v1","known_models":["gpt-5"],"deprecated_models":["gpt-4"],"source_url":"https://truth.local/openai.json"}'
        if url == "https://api.openai.com/v1":
            return 401, "unauthorized"
        return 404, "not found"

    try:
        set_http_get(fake_http_get)
        result = verify_endpoint_with_live("openai", "https://api.openai.com/v1", "gpt-5", store)
        assert result.status == EndpointCheckStatus.AUTH_FAILURE
        assert "401" in result.message or "unauthorized" in result.message.lower()
    finally:
        reset_http_get()


def test_verify_endpoint_with_live_truth_escalates_oauth_to_human(monkeypatch) -> None:
    monkeypatch.setenv("HERMES_LIVE_TRUTH_ENABLED", "1")
    store = ProviderTruthStore()
    store.add(
        ProviderTruthRecord(
            provider="openai",
            canonical_endpoint="https://api.openai.com/v1",
            known_models=["gpt-5"],
            deprecated_models=["gpt-4"],
            auth_type="oauth",
            source_url="https://truth.local/openai.json",
            confidence="high",
        )
    )

    def fake_http_get(url: str):
        if url == "https://truth.local/openai.json":
            return 200, '{"provider":"openai","canonical_endpoint":"https://api.openai.com/v1","known_models":["gpt-5"],"deprecated_models":["gpt-4"],"auth_type":"oauth","source_url":"https://truth.local/openai.json"}'
        if url == "https://api.openai.com/v1":
            return 401, "unauthorized"
        return 404, "not found"

    try:
        set_http_get(fake_http_get)
        result = verify_endpoint_with_live("openai", "https://api.openai.com/v1", "gpt-5", store)
        assert result.status == EndpointCheckStatus.AUTH_FAILURE
        assert result.details.get("escalation") == "human"
        assert "oauth" in result.message.lower()
    finally:
        reset_http_get()


def test_verify_provider_truth_categorizes_results_with_live_truth(monkeypatch) -> None:
    monkeypatch.setenv("HERMES_LIVE_TRUTH_ENABLED", "1")
    store = ProviderTruthStore()
    store.add(
        ProviderTruthRecord(
            provider="openai",
            canonical_endpoint="https://api.openai.com/v1",
            known_models=["gpt-5"],
            deprecated_models=["gpt-4"],
            source_url="https://truth.local/openai.json",
            confidence="high",
        )
    )

    def fake_http_get(url: str):
        if url == "https://truth.local/openai.json":
            return 200, '{"provider":"openai","canonical_endpoint":"https://api.openai.com/v1","known_models":["gpt-5"],"deprecated_models":["gpt-4"],"source_url":"https://truth.local/openai.json"}'
        if url == "https://api.openai.com/v1":
            return 200, "ok"
        return 404, "not found"

    try:
        set_http_get(fake_http_get)
        results = verify_provider_truth(
            [{"provider": "openai", "base_url": "https://api.openai.com/v1", "model": "gpt-5"}],
            store,
            use_live_truth=True,
        )
        buckets = categorize_verification_results(results)
        assert results[0].status == EndpointCheckStatus.OK
        assert "ok" in buckets
    finally:
        reset_http_get()


def test_live_truth_uses_openapi_models_path_for_auth_failure(monkeypatch) -> None:
    monkeypatch.setenv("HERMES_LIVE_TRUTH_ENABLED", "1")
    store = ProviderTruthStore()
    store.add(
        ProviderTruthRecord(
            provider="openai",
            canonical_endpoint="https://api.openai.com/v1",
            known_models=["gpt-4o"],
            deprecated_models=["gpt-4"],
            source_url="https://raw.githubusercontent.com/openai/openai-openapi/manual_spec/openapi.yaml",
            confidence="high",
        )
    )

    result = verify_endpoint_with_live(
        "openai",
        "https://api.openai.com/v1/models",
        "gpt-4o",
        store,
        use_live_truth=True,
    )
    assert result.status == EndpointCheckStatus.AUTH_FAILURE
    assert result.details.get("source_url") == "https://raw.githubusercontent.com/openai/openai-openapi/manual_spec/openapi.yaml"

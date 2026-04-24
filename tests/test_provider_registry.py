"""Tests for provider registry foundation."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
import yaml

from hermesoptimizer.sources.lane_state import LaneState
from hermesoptimizer.sources.provider_registry import (
    ProviderRegistry,
    RegistryIntegrityError,
    fetch_remote_registry,
)


def _payload_bytes(*, provenance: bool = True) -> bytes:
    registry = {"name": "Liminal-Registry", "owner": "Mind-Dragon", "repo": "Liminal-Registry", "source": "unit"}
    data = {
        "version": "remote-test",
        "providers": [
            {
                "id": "remote",
                "name": "Remote",
                "endpoint": "https://remote.invalid/v1",
                "api_style": "openai-compatible",
                "status": "active",
                "models": [{"id": "remote-model", "status": "active"}],
            }
        ],
    }
    if provenance:
        data["registry"] = registry
    return json.dumps(data, sort_keys=True).encode("utf-8")


def _registry_doc(provider_id: str, endpoint: str, model_id: str) -> dict:
    return {
        "version": "test",
        "registry": {"name": "test", "owner": "unit", "repo": "unit", "source": "test"},
        "providers": [
            {
                "id": provider_id,
                "name": provider_id.title(),
                "endpoint": endpoint,
                "api_style": "openai-compatible",
                "status": "active",
                "models": [{"id": model_id, "status": "active"}],
            }
        ],
    }


def _patch_urlopen(monkeypatch, payload: bytes):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def read(self):
            return payload

    def fake_urlopen(request, timeout):
        assert timeout == 1.0
        assert "Liminal-Registry" in request.full_url
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)


def _make_provider_db(home: Path, providers: dict[str, tuple[str, list[str]]]) -> None:
    db = home / "provider-db" / "provider_model.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE providers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            source TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active'
        );
        CREATE TABLE models (
            id INTEGER PRIMARY KEY,
            provider_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            source TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            UNIQUE(provider_id, name)
        );
        CREATE TABLE provider_endpoints (
            id INTEGER PRIMARY KEY,
            provider_id INTEGER NOT NULL,
            endpoint_url TEXT NOT NULL,
            source TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            is_primary INTEGER NOT NULL DEFAULT 0,
            UNIQUE(provider_id, endpoint_url)
        );
        """
    )
    for name, (endpoint, models) in providers.items():
        conn.execute("INSERT INTO providers (name, source) VALUES (?, 'unit-db')", (name,))
        provider_id = conn.execute("SELECT id FROM providers WHERE name=?", (name,)).fetchone()[0]
        conn.execute(
            "INSERT INTO provider_endpoints (provider_id, endpoint_url, source, is_primary) VALUES (?, ?, 'unit-db', 1)",
            (provider_id, endpoint),
        )
        for model in models:
            conn.execute("INSERT INTO models (provider_id, name, source) VALUES (?, ?, 'unit-db')", (provider_id, model))
    conn.commit()
    conn.close()


class TestProviderRegistry:
    def test_empty_registry(self) -> None:
        registry = ProviderRegistry.empty()
        assert registry.providers() == []

    def test_seed_registry_loads_public_first_pass_models(self) -> None:
        registry = ProviderRegistry.from_seed()
        assert registry.source == "package-seed"
        assert "openai-codex" in registry.providers()
        assert registry.model_ids("openai-codex") == ["gpt-5.5", "gpt-5.4-mini"]
        assert registry.contains_model("gpt-5.5") is True
        assert registry.contains_model("gpt-5.4-mini") is True
        assert registry.contains_model("moonshotai/kimi-k2.6") is True
        assert registry.contains_model("inclusionai/ling-2.6-flash:free") is True

    def test_registry_to_truth_store_preserves_known_models(self) -> None:
        registry = ProviderRegistry.from_seed()
        store = registry.to_truth_store()
        openai = store.get("openai-codex")
        assert openai is not None
        assert openai.provider == "openai"
        assert "gpt-5.5" in openai.known_models
        assert "gpt-5.4-mini" in openai.known_models
        assert openai.canonical_endpoint == "https://api.openai.com/v1"

    def test_registry_from_cache_or_seed_uses_cache_when_present(self, tmp_path: Path) -> None:
        cache = tmp_path / "provider_registry.cache.json"
        cache.write_text(_payload_bytes().decode("utf-8"), encoding="utf-8")
        registry = ProviderRegistry.from_cache_or_seed(cache)
        assert registry.providers() == ["remote"]
        assert registry.model_ids("remote") == ["remote-model"]

    def test_full_merge_policy_applies_declared_priority_order(self, tmp_path: Path) -> None:
        local = tmp_path / "local.json"
        cache = tmp_path / "cache.json"
        config = tmp_path / "config.yaml"
        home = tmp_path / "home"

        local.write_text(json.dumps(_registry_doc("shared", "https://local.invalid/v1", "local-model")), encoding="utf-8")
        cache_data = _registry_doc("shared", "https://cache.invalid/v1", "cache-model")
        cache_data["providers"].append(_registry_doc("cacheonly", "https://cache-only.invalid/v1", "cache-only-model")["providers"][0])
        cache.write_text(json.dumps(cache_data), encoding="utf-8")
        _make_provider_db(home, {
            "shared": ("https://db.invalid/v1", ["db-model"]),
            "dbonly": ("https://db-only.invalid/v1", ["db-only-model"]),
        })
        config.write_text(
            yaml.safe_dump(
                {
                    "providers": {
                        "shared": {"api": "https://config.invalid/v1", "default_model": "config-model"},
                        "configonly": {"api": "https://config-only.invalid/v1", "default_model": "config-only-model"},
                    }
                }
            ),
            encoding="utf-8",
        )

        registry = ProviderRegistry.from_merged_sources(
            local_override_path=local,
            cache_path=cache,
            hermes_home=home,
            hermes_config_path=config,
        )

        assert registry.source == "merged"
        assert registry.providers_by_id["shared"].endpoint == "https://local.invalid/v1"
        assert registry.model_ids("shared") == ["local-model"]
        assert registry.model_ids("cacheonly") == ["cache-only-model"]
        assert registry.model_ids("dbonly") == ["db-only-model"]
        assert registry.model_ids("configonly") == ["config-only-model"]
        assert registry.model_ids("openai-codex") == ["gpt-5.5", "gpt-5.4-mini"]

    def test_merged_registry_ignores_missing_optional_sources(self, tmp_path: Path) -> None:
        registry = ProviderRegistry.from_merged_sources(
            local_override_path=tmp_path / "missing-local.json",
            cache_path=tmp_path / "missing-cache.json",
            hermes_home=tmp_path / "missing-home",
            hermes_config_path=tmp_path / "missing-config.yaml",
        )
        assert registry.source == "merged"
        assert registry.model_ids("openai-codex") == ["gpt-5.5", "gpt-5.4-mini"]

    def test_registry_can_mark_quarantined_providers_without_losing_models(self) -> None:
        registry = ProviderRegistry.from_seed().with_quarantined_providers({"openrouter"})
        assert "openrouter" not in registry.providers()
        assert "openrouter" in registry.providers(include_quarantined=True)
        assert registry.quarantined_providers() == ["openrouter"]
        assert registry.model_ids("openrouter") == ["inclusionai/ling-2.6-flash:free"]
        assert registry.model_ids("openrouter", include_quarantined=False) == []

    def test_registry_preserves_existing_quarantine_status_from_data(self) -> None:
        registry = ProviderRegistry.from_data(
            _registry_doc("bad", "https://bad.invalid/v1", "bad-model"),
            source="unit",
        ).with_quarantined_providers({"bad"})
        assert registry.providers() == []
        assert registry.providers(include_quarantined=True) == ["bad"]

    def test_fetch_remote_registry_caches_payload_with_hash_and_provenance(self, monkeypatch, tmp_path: Path) -> None:
        payload = _payload_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        _patch_urlopen(monkeypatch, payload)
        cache = tmp_path / "cache.json"
        registry = fetch_remote_registry(
            timeout=1.0,
            cache_path=cache,
            expected_sha256=digest,
            expected_signature=f"sha256:{digest}",
        )
        assert registry.providers() == ["remote"]
        assert cache.exists()
        cached = json.loads(cache.read_text(encoding="utf-8"))
        assert cached["version"] == "remote-test"
        assert cached["registry"]["owner"] == "Mind-Dragon"

    def test_fetch_remote_registry_rejects_wrong_hash_and_does_not_cache(self, monkeypatch, tmp_path: Path) -> None:
        payload = _payload_bytes()
        _patch_urlopen(monkeypatch, payload)
        cache = tmp_path / "cache.json"
        with pytest.raises(RegistryIntegrityError, match="sha256 mismatch"):
            fetch_remote_registry(
                timeout=1.0,
                cache_path=cache,
                expected_sha256="0" * 64,
                expected_signature="sha256:" + "0" * 64,
            )
        assert not cache.exists()

    def test_fetch_remote_registry_rejects_missing_provenance_and_does_not_cache(self, monkeypatch, tmp_path: Path) -> None:
        payload = _payload_bytes(provenance=False)
        digest = hashlib.sha256(payload).hexdigest()
        _patch_urlopen(monkeypatch, payload)
        cache = tmp_path / "cache.json"
        with pytest.raises(RegistryIntegrityError, match="missing registry provenance"):
            fetch_remote_registry(
                timeout=1.0,
                cache_path=cache,
                expected_sha256=digest,
                expected_signature=f"sha256:{digest}",
            )
        assert not cache.exists()

    def test_fetch_remote_registry_rejects_wrong_signature_and_does_not_cache(self, monkeypatch, tmp_path: Path) -> None:
        payload = _payload_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        _patch_urlopen(monkeypatch, payload)
        cache = tmp_path / "cache.json"
        with pytest.raises(RegistryIntegrityError, match="signature mismatch"):
            fetch_remote_registry(
                timeout=1.0,
                cache_path=cache,
                expected_sha256=digest,
                expected_signature="sha256:" + "f" * 64,
            )
        assert not cache.exists()


class TestLaneState:
    def test_lane_state_from_string_direct_values(self) -> None:
        assert LaneState.from_string("green") is LaneState.GREEN
        assert LaneState.from_string("fallback_only") is LaneState.FALLBACK_ONLY
        assert LaneState.from_string("quota_blocked") is LaneState.QUOTA_BLOCKED
        assert LaneState.from_string("quarantined") is LaneState.QUARANTINED
        assert LaneState.from_string("unknown") is LaneState.UNKNOWN

    def test_lane_state_legacy_aliases(self) -> None:
        assert LaneState.from_string("active") is LaneState.GREEN
        assert LaneState.from_string("inactive") is LaneState.UNKNOWN

    def test_lane_state_case_insensitive(self) -> None:
        assert LaneState.from_string("GREEN") is LaneState.GREEN
        assert LaneState.from_string("Fallback_Only") is LaneState.FALLBACK_ONLY
        assert LaneState.from_string("Active") is LaneState.GREEN

    def test_lane_state_unknown_for_unrecognized(self) -> None:
        assert LaneState.from_string("bogus") is LaneState.UNKNOWN
        assert LaneState.from_string("") is LaneState.UNKNOWN
        assert LaneState.from_string(None) is LaneState.UNKNOWN

    def test_lane_state_green_is_required_release_eligible(self) -> None:
        assert LaneState.GREEN.eligible_for_required_release() is True
        assert LaneState.FALLBACK_ONLY.eligible_for_required_release() is False
        assert LaneState.QUOTA_BLOCKED.eligible_for_required_release() is False
        assert LaneState.QUARANTINED.eligible_for_required_release() is False
        assert LaneState.UNKNOWN.eligible_for_required_release() is False


class TestProviderRegistryLaneState:
    def test_required_release_providers_returns_only_green(self) -> None:
        data = {
            "providers": [
                {"id": "a", "name": "A", "endpoint": "https://a.invalid/v1", "api_style": "openai-compatible", "status": "green", "models": []},
                {"id": "b", "name": "B", "endpoint": "https://b.invalid/v1", "api_style": "openai-compatible", "status": "fallback_only", "models": []},
                {"id": "c", "name": "C", "endpoint": "https://c.invalid/v1", "api_style": "openai-compatible", "status": "quota_blocked", "models": []},
                {"id": "d", "name": "D", "endpoint": "https://d.invalid/v1", "api_style": "openai-compatible", "status": "quarantined", "models": []},
                {"id": "e", "name": "E", "endpoint": "https://e.invalid/v1", "api_style": "openai-compatible", "status": "unknown", "models": []},
            ]
        }
        registry = ProviderRegistry.from_data(data, source="unit")
        required = registry.required_release_providers()
        assert required == ["a"]

    def test_required_release_providers_normalizes_legacy_active_alias(self) -> None:
        data = {
            "providers": [
                {"id": "legacy", "name": "Legacy", "endpoint": "https://legacy.invalid/v1", "api_style": "openai-compatible", "status": "active", "models": []},
            ]
        }
        registry = ProviderRegistry.from_data(data, source="unit")
        assert registry.required_release_providers() == ["legacy"]

    def test_required_release_providers_excludes_legacy_inactive_alias(self) -> None:
        data = {
            "providers": [
                {"id": "legacy", "name": "Legacy", "endpoint": "https://legacy.invalid/v1", "api_style": "openai-compatible", "status": "inactive", "models": []},
            ]
        }
        registry = ProviderRegistry.from_data(data, source="unit")
        assert registry.required_release_providers() == []

    def test_providers_behavior_unchanged_for_quarantined(self) -> None:
        data = {
            "providers": [
                {"id": "ok", "name": "OK", "endpoint": "https://ok.invalid/v1", "api_style": "openai-compatible", "status": "green", "models": []},
                {"id": "bad", "name": "Bad", "endpoint": "https://bad.invalid/v1", "api_style": "openai-compatible", "status": "quarantined", "models": []},
            ]
        }
        registry = ProviderRegistry.from_data(data, source="unit")
        assert registry.providers() == ["ok"]
        assert registry.providers(include_quarantined=True) == ["bad", "ok"]
        assert registry.quarantined_providers() == ["bad"]
        assert registry.required_release_providers() == ["ok"]

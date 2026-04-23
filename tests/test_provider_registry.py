"""Tests for provider registry foundation."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
import yaml

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
        assert registry.model_ids("openai-codex") == ["gpt-5.5"]
        assert registry.contains_model("gpt-5.5") is True
        assert registry.contains_model("moonshotai/kimi-k2.6") is True
        assert registry.contains_model("inclusionai/ling-2.6-flash:free") is True

    def test_registry_to_truth_store_preserves_known_models(self) -> None:
        registry = ProviderRegistry.from_seed()
        store = registry.to_truth_store()
        openai = store.get("openai-codex")
        assert openai is not None
        assert openai.provider == "openai"
        assert "gpt-5.5" in openai.known_models
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
        assert registry.model_ids("openai-codex") == ["gpt-5.5"]

    def test_merged_registry_ignores_missing_optional_sources(self, tmp_path: Path) -> None:
        registry = ProviderRegistry.from_merged_sources(
            local_override_path=tmp_path / "missing-local.json",
            cache_path=tmp_path / "missing-cache.json",
            hermes_home=tmp_path / "missing-home",
            hermes_config_path=tmp_path / "missing-config.yaml",
        )
        assert registry.source == "merged"
        assert registry.model_ids("openai-codex") == ["gpt-5.5"]

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

"""Tests for provider registry foundation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

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

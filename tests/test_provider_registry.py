"""Tests for provider registry foundation."""

from __future__ import annotations

import json
from pathlib import Path

from hermesoptimizer.sources.provider_registry import ProviderRegistry, fetch_remote_registry


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
        cache.write_text(
            json.dumps(
                {
                    "version": "test",
                    "registry": {"name": "test", "owner": "x", "repo": "y", "source": "local"},
                    "providers": [
                        {
                            "id": "localtest",
                            "name": "Local Test",
                            "endpoint": "https://example.invalid/v1",
                            "api_style": "openai-compatible",
                            "status": "active",
                            "models": [{"id": "local-model", "status": "active"}],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        registry = ProviderRegistry.from_cache_or_seed(cache)
        assert registry.providers() == ["localtest"]
        assert registry.model_ids("localtest") == ["local-model"]

    def test_fetch_remote_registry_caches_payload(self, monkeypatch, tmp_path: Path) -> None:
        payload = json.dumps(
            {
                "version": "remote-test",
                "registry": {"name": "Liminal-Registry", "owner": "Mind-Dragon", "repo": "Liminal-Registry", "source": "unit"},
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
        ).encode("utf-8")

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
        cache = tmp_path / "cache.json"
        registry = fetch_remote_registry(timeout=1.0, cache_path=cache)
        assert registry.providers() == ["remote"]
        assert cache.exists()
        assert json.loads(cache.read_text(encoding="utf-8"))["version"] == "remote-test"

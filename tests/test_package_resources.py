"""Tests for packaged provider-registry resource files."""

from __future__ import annotations

from hermesoptimizer.resources import read_package_json, read_provider_registry, read_schema


def _model_ids(registry: dict) -> set[str]:
    return {
        model["id"]
        for provider in registry["providers"]
        for model in provider.get("models", [])
    }


class TestPackageResources:
    def test_read_package_json_returns_dict(self):
        data = read_package_json("hermesoptimizer.data", "provider_registry.seed.json")
        assert data is not None
        assert isinstance(data, dict)

    def test_read_provider_registry(self):
        registry = read_provider_registry()
        assert registry is not None
        assert registry["registry"]["name"] == "Liminal-Registry"
        assert registry["registry"]["owner"] == "Mind-Dragon"
        assert isinstance(registry["providers"], list)

    def test_read_schema(self):
        schema = read_schema()
        assert schema is not None
        assert "$schema" in schema
        assert "properties" in schema
        assert "providers" in schema["properties"]

    def test_provider_registry_contains_openai_codex_gpt55(self):
        registry = read_provider_registry()
        providers = {p["id"]: p for p in registry["providers"]}
        assert "openai-codex" in providers
        assert "gpt-5.5" in _model_ids(registry)

    def test_provider_registry_contains_ling_lanes(self):
        registry = read_provider_registry()
        providers = {p["id"] for p in registry["providers"]}
        assert "kilocode" in providers
        assert "openrouter" in providers
        assert "inclusionai/ling-2.6-flash:free" in _model_ids(registry)

    def test_provider_registry_contains_nous_kimi(self):
        registry = read_provider_registry()
        providers = {p["id"] for p in registry["providers"]}
        assert "nous" in providers
        assert "moonshotai/kimi-k2.6" in _model_ids(registry)

    def test_registry_schema_validation_structure(self):
        registry = read_provider_registry()
        schema = read_schema()
        assert registry is not None
        assert schema is not None
        assert isinstance(registry["providers"], list)
        for provider in registry["providers"]:
            assert "id" in provider
            assert "name" in provider
            assert "endpoint" in provider
            assert "api_style" in provider
            assert "models" in provider
            assert "status" in provider
            for model in provider["models"]:
                assert "id" in model
                assert "status" in model

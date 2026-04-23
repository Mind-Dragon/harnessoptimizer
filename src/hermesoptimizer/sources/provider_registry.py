"""Provider registry foundation for HermesOptimizer.

The public registry is expected to live at Mind-Dragon/Liminal-Registry and be
consumed by both Hermes and HermesOptimizer. This module intentionally keeps the
first-pass contract small: load bundled seed data, optionally refresh/cache a
remote JSON registry, and expose provider/model rows for read-only tools.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hermesoptimizer.paths import get_data_dir
from hermesoptimizer.resources import read_provider_registry
from hermesoptimizer.sources.provider_truth import ProviderTruthRecord, ProviderTruthStore

DEFAULT_REGISTRY_URL = (
    "https://raw.githubusercontent.com/Mind-Dragon/"
    "Liminal-Registry/main/provider_registry.json"
)
CACHE_FILENAME = "provider_registry.cache.json"


@dataclass(frozen=True)
class RegistryModel:
    id: str
    status: str = "unknown"
    capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class RegistryProvider:
    id: str
    name: str
    endpoint: str
    api_style: str = "openai-compatible"
    status: str = "unknown"
    models: tuple[RegistryModel, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ProviderRegistry:
    """Small immutable provider registry view."""

    providers_by_id: dict[str, RegistryProvider]
    source: str = "unknown"

    @classmethod
    def empty(cls) -> "ProviderRegistry":
        return cls(providers_by_id={}, source="empty")

    @classmethod
    def from_data(cls, data: dict[str, Any], *, source: str = "memory") -> "ProviderRegistry":
        providers: dict[str, RegistryProvider] = {}
        for item in data.get("providers", []):
            provider_id = str(item.get("id", "")).strip()
            if not provider_id:
                continue
            models = tuple(
                RegistryModel(
                    id=str(model.get("id", "")).strip(),
                    status=str(model.get("status", "unknown")),
                    capabilities=tuple(str(c) for c in model.get("capabilities", [])),
                )
                for model in item.get("models", [])
                if str(model.get("id", "")).strip()
            )
            providers[provider_id] = RegistryProvider(
                id=provider_id,
                name=str(item.get("name", provider_id)),
                endpoint=str(item.get("endpoint", "")),
                api_style=str(item.get("api_style", "openai-compatible")),
                status=str(item.get("status", "unknown")),
                models=models,
            )
        return cls(providers_by_id=providers, source=source)

    @classmethod
    def from_seed(cls) -> "ProviderRegistry":
        data = read_provider_registry() or {"providers": []}
        return cls.from_data(data, source="package-seed")

    @classmethod
    def from_file(cls, path: str | Path) -> "ProviderRegistry":
        p = Path(path)
        return cls.from_data(json.loads(p.read_text(encoding="utf-8")), source=str(p))

    @classmethod
    def from_cache_or_seed(cls, cache_path: str | Path | None = None) -> "ProviderRegistry":
        path = Path(cache_path) if cache_path else get_data_dir() / CACHE_FILENAME
        if path.exists():
            return cls.from_file(path)
        return cls.from_seed()

    def providers(self) -> list[str]:
        return sorted(self.providers_by_id)

    def model_ids(self, provider_id: str) -> list[str]:
        provider = self.providers_by_id.get(provider_id)
        if provider is None:
            return []
        return [model.id for model in provider.models]

    def contains_model(self, model_id: str) -> bool:
        return any(model_id in self.model_ids(provider_id) for provider_id in self.providers())

    def to_truth_store(self) -> ProviderTruthStore:
        store = ProviderTruthStore()
        for provider in self.providers_by_id.values():
            store.add(
                ProviderTruthRecord(
                    provider=provider.id,
                    canonical_endpoint=provider.endpoint,
                    known_models=[model.id for model in provider.models],
                    capabilities=sorted({c for model in provider.models for c in model.capabilities}),
                    source_url=self.source,
                    confidence="medium",
                    auth_type="api_key",
                    transport="https" if provider.endpoint.startswith("https://") else "http",
                ),
                replace=True,
            )
        return store


def fetch_remote_registry(
    url: str = DEFAULT_REGISTRY_URL,
    *,
    timeout: float = 10.0,
    cache_path: str | Path | None = None,
) -> ProviderRegistry:
    """Fetch a public registry JSON file and cache it locally.

    This is explicit opt-in network I/O. Normal provider-list calls use cache or
    package seed and never block on the network.
    """
    request = urllib.request.Request(url, headers={"User-Agent": "hermesoptimizer/0.9.3"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read().decode("utf-8")
    data = json.loads(payload)
    path = Path(cache_path) if cache_path else get_data_dir() / CACHE_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return ProviderRegistry.from_data(data, source=url)

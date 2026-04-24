"""Provider registry foundation for HermesOptimizer.

The public registry is expected to live at Mind-Dragon/Liminal-Registry and be
consumed by both Hermes and HermesOptimizer. This module intentionally keeps the
first-pass contract small: load bundled seed data, optionally refresh/cache a
remote JSON registry, and expose provider/model rows for read-only tools.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from hermesoptimizer.paths import get_data_dir
from hermesoptimizer.resources import read_provider_registry
from hermesoptimizer.sources.lane_state import LaneState
from hermesoptimizer.sources.provider_truth import ProviderTruthRecord, ProviderTruthStore

DEFAULT_REGISTRY_URL = (
    "https://raw.githubusercontent.com/Mind-Dragon/"
    "Liminal-Registry/main/provider_registry.json"
)
CACHE_FILENAME = "provider_registry.cache.json"
LOCAL_OVERRIDE_FILENAME = "provider_registry.local.json"


class RegistryIntegrityError(ValueError):
    """Raised when remote registry integrity/provenance checks fail."""


@dataclass(frozen=True)
class RegistryIntegrityReport:
    sha256: str
    signature: str | None
    provenance_owner: str
    provenance_repo: str


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

    @classmethod
    def from_hermes_db(cls, hermes_home: str | Path) -> "ProviderRegistry":
        db_path = Path(hermes_home) / "provider-db" / "provider_model.sqlite"
        if not db_path.exists():
            return cls.empty()
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                """
                SELECT p.name, p.status, COALESCE(e.endpoint_url, ''), m.name, m.status
                FROM providers p
                LEFT JOIN provider_endpoints e ON e.provider_id = p.id AND e.is_primary = 1
                LEFT JOIN models m ON m.provider_id = p.id
                ORDER BY p.name, m.name
                """
            ).fetchall()
        finally:
            conn.close()
        grouped: dict[str, dict[str, Any]] = {}
        for provider_id, provider_status, endpoint, model_id, model_status in rows:
            item = grouped.setdefault(
                provider_id,
                {
                    "id": provider_id,
                    "name": provider_id,
                    "endpoint": endpoint or "",
                    "api_style": "openai-compatible",
                    "status": provider_status or "active",
                    "models": [],
                },
            )
            if endpoint and not item["endpoint"]:
                item["endpoint"] = endpoint
            if model_id:
                item["models"].append({"id": model_id, "status": model_status or "active"})
        return cls.from_data({"providers": list(grouped.values())}, source=str(db_path))

    @classmethod
    def from_hermes_config(cls, config_path: str | Path) -> "ProviderRegistry":
        path = Path(config_path)
        if not path.exists():
            return cls.empty()
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            return cls.empty()
        providers: list[dict[str, Any]] = []
        raw_providers = data.get("providers", {})
        if isinstance(raw_providers, dict):
            for provider_id, provider_data in raw_providers.items():
                if not isinstance(provider_data, dict):
                    continue
                model = provider_data.get("default_model") or provider_data.get("model") or ""
                providers.append(
                    {
                        "id": str(provider_id),
                        "name": str(provider_data.get("name") or provider_id),
                        "endpoint": str(provider_data.get("api") or provider_data.get("base_url") or ""),
                        "api_style": "openai-compatible",
                        "status": "active",
                        "models": [{"id": str(model), "status": "active"}] if model else [],
                    }
                )
        return cls.from_data({"providers": providers}, source=str(path))

    @classmethod
    def from_merged_sources(
        cls,
        *,
        local_override_path: str | Path | None = None,
        cache_path: str | Path | None = None,
        hermes_home: str | Path | None = None,
        hermes_config_path: str | Path | None = None,
    ) -> "ProviderRegistry":
        """Load registry sources in declared precedence order.

        Lower-priority sources are loaded first and then overwritten by higher
        priority providers with the same ID:
        Hermes config < Hermes provider DB < packaged fallback < public cache < local override.
        """
        merged: dict[str, RegistryProvider] = {}
        local_path = Path(local_override_path) if local_override_path is not None else get_data_dir() / LOCAL_OVERRIDE_FILENAME
        cache = Path(cache_path) if cache_path is not None else get_data_dir() / CACHE_FILENAME
        home = Path(hermes_home) if hermes_home is not None else Path.home() / ".hermes"
        config = Path(hermes_config_path) if hermes_config_path is not None else home / "config.yaml"

        def overlay(registry: "ProviderRegistry") -> None:
            merged.update(registry.providers_by_id)

        overlay(cls.from_hermes_config(config))
        overlay(cls.from_hermes_db(home))
        overlay(cls.from_seed())
        if cache.exists():
            overlay(cls.from_file(cache))
        if local_path.exists():
            overlay(cls.from_file(local_path))
        return cls(providers_by_id=merged, source="merged")

    def providers(self, *, include_quarantined: bool = False) -> list[str]:
        if include_quarantined:
            return sorted(self.providers_by_id)
        return sorted(
            provider_id
            for provider_id, provider in self.providers_by_id.items()
            if provider.status != "quarantined"
        )

    def required_release_providers(self) -> list[str]:
        """Return provider IDs whose lane state is green (or legacy active alias)."""
        return sorted(
            provider_id
            for provider_id, provider in self.providers_by_id.items()
            if LaneState.from_string(provider.status).is_green()
        )

    def quarantined_providers(self) -> list[str]:
        return sorted(
            provider_id
            for provider_id, provider in self.providers_by_id.items()
            if provider.status == "quarantined"
        )

    def with_quarantined_providers(self, providers: list[str] | tuple[str, ...] | set[str]) -> "ProviderRegistry":
        quarantined = {str(provider).strip().lower() for provider in providers if str(provider).strip()}
        updated: dict[str, RegistryProvider] = {}
        for provider_id, provider in self.providers_by_id.items():
            status = "quarantined" if provider_id.lower() in quarantined else provider.status
            updated[provider_id] = RegistryProvider(
                id=provider.id,
                name=provider.name,
                endpoint=provider.endpoint,
                api_style=provider.api_style,
                status=status,
                models=provider.models,
            )
        return ProviderRegistry(providers_by_id=updated, source=self.source)

    def model_ids(self, provider_id: str, *, include_quarantined: bool = True) -> list[str]:
        provider = self.providers_by_id.get(provider_id)
        if provider is None:
            return []
        if provider.status == "quarantined" and not include_quarantined:
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


def _normalize_sha256(value: str | None) -> str | None:
    if value is None:
        return None
    raw = value.strip().lower()
    if raw.startswith("sha256:"):
        raw = raw.split(":", 1)[1]
    if len(raw) != 64 or any(ch not in "0123456789abcdef" for ch in raw):
        raise RegistryIntegrityError("expected sha256 must be 64 lowercase hex chars or sha256:<hex>")
    return raw


def validate_registry_payload(
    payload: bytes,
    data: dict[str, Any],
    *,
    expected_sha256: str | None = None,
    expected_signature: str | None = None,
    require_provenance: bool = True,
) -> RegistryIntegrityReport:
    """Validate detached hash/signature and required registry provenance."""
    digest = hashlib.sha256(payload).hexdigest()
    expected_digest = _normalize_sha256(expected_sha256)
    if expected_digest is not None and digest != expected_digest:
        raise RegistryIntegrityError(f"sha256 mismatch: expected {expected_digest}, got {digest}")

    signature_digest = _normalize_sha256(expected_signature)
    if signature_digest is not None and digest != signature_digest:
        raise RegistryIntegrityError(f"signature mismatch: expected sha256:{signature_digest}, got sha256:{digest}")

    registry = data.get("registry")
    if require_provenance:
        if not isinstance(registry, dict):
            raise RegistryIntegrityError("missing registry provenance")
        missing = [key for key in ("name", "owner", "repo", "source") if not str(registry.get(key, "")).strip()]
        if missing:
            raise RegistryIntegrityError(f"missing registry provenance field(s): {', '.join(missing)}")
    registry = registry if isinstance(registry, dict) else {}
    return RegistryIntegrityReport(
        sha256=digest,
        signature=f"sha256:{signature_digest}" if signature_digest else None,
        provenance_owner=str(registry.get("owner", "")),
        provenance_repo=str(registry.get("repo", "")),
    )


def fetch_remote_registry(
    url: str = DEFAULT_REGISTRY_URL,
    *,
    timeout: float = 10.0,
    cache_path: str | Path | None = None,
    expected_sha256: str | None = None,
    expected_signature: str | None = None,
    require_provenance: bool = True,
) -> ProviderRegistry:
    """Fetch a public registry JSON file, validate integrity, and cache it locally.

    This is explicit opt-in network I/O. Normal provider-list calls use cache or
    package seed and never block on the network. The detached hash/signature
    arguments intentionally validate the raw payload before it is cached.
    """
    request = urllib.request.Request(url, headers={"User-Agent": "hermesoptimizer/0.9.4"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read()
    data = json.loads(payload.decode("utf-8"))
    validate_registry_payload(
        payload,
        data,
        expected_sha256=expected_sha256,
        expected_signature=expected_signature,
        require_provenance=require_provenance,
    )
    path = Path(cache_path) if cache_path else get_data_dir() / CACHE_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return ProviderRegistry.from_data(data, source=url)

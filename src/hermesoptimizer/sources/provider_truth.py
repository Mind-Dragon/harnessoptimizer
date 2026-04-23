from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_PROVIDER_ALIASES: dict[str, str] = {
    "kimi-for-coding": "kimi",
    "kimi-coding": "kimi",
    "kimi-coding-cn": "kimi",
    "bailian": "qwen",
    "bailian-coding": "qwen",
    "alibaba-bailian": "qwen",
    "alibaba-coding-plan": "qwen",
    "alibaba-coding": "qwen",
    "alibaba": "qwen",
    "tongyi": "qwen",
    "openai-codex": "openai",
    "zai-chat": "zai",
    "z.ai": "zai",
    "z-ai": "zai",
    "x.ai": "xai",
    "x-ai": "xai",
    "minimax-cn": "minimax",
}


def canonical_provider_name(provider: str) -> str:
    name = (provider or "").strip().lower()
    return _PROVIDER_ALIASES.get(name, name)


@dataclass(slots=True)
class EndpointCandidate:
    """
    Represents a known-good endpoint that can be used as a repair candidate
    when the primary endpoint is failing.

    Fields:
        endpoint: Base URL for this endpoint family
        api_style: API design style (e.g. "openai-compatible", "anthropic-compatible", "rest")
        auth_type: Authentication type (e.g. "bearer", "api_key", "oauth")
        region_scope: List of region codes this endpoint covers (e.g. ["us", "eu", "global"])
        is_stable: Whether this endpoint is considered stable/production-ready
    """

    endpoint: str
    api_style: str = "openai-compatible"
    auth_type: str = "bearer"
    region_scope: list[str] = field(default_factory=list)
    is_stable: bool = True

    def __repr__(self) -> str:
        return (
            f"EndpointCandidate(endpoint={self.endpoint!r}, "
            f"api_style={self.api_style!r}, auth_type={self.auth_type!r}, "
            f"region_scope={self.region_scope!r}, is_stable={self.is_stable!r})"
        )


@dataclass(slots=True)
class ProviderTruthRecord:
    """
    Canonical provider truth record.

    Fields:
        provider: Canonical provider name
        canonical_endpoint: Correct base URL for this provider
        known_models: Models confirmed to exist and be supported
        deprecated_models: Models confirmed to be deprecated or EOL
        stale_aliases: Mapping of known stale model name aliases to their correct names
            (e.g., {"gpt-5": "gpt-4o", "gpt-4.5": "gpt-4o"})
        model_endpoints: Mapping of model names to their specific endpoint URLs
            when a model requires a non-canonical endpoint
        capabilities: Capability tags (e.g. text, vision, embedding, rerank)
        context_window: Max context in tokens (0 if unknown)
        source_url: URL used to fetch live truth (optional)
        confidence: Confidence level ("high", "medium", "low")
        auth_type: Authentication type (e.g. "oauth", "api_key", "bearer")
        regions: Region codes where this provider operates (e.g. ["us", "eu", "cn", "global"])
        transport: Transport protocol ("https", "http", "wss", etc.)
        endpoint_candidates: Known-good alternative endpoints for repair probing
    """

    provider: str
    canonical_endpoint: str
    known_models: list[str] = field(default_factory=list)
    deprecated_models: list[str] = field(default_factory=list)
    stale_aliases: dict[str, str] = field(default_factory=dict)
    model_endpoints: dict[str, str] = field(default_factory=dict)
    capabilities: list[str] = field(default_factory=list)
    context_window: int = 0
    source_url: str | None = None
    confidence: str = "medium"
    auth_type: str | None = None
    regions: list[str] = field(default_factory=list)
    transport: str = ""
    endpoint_candidates: list[EndpointCandidate] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    # Model helpers
    # ------------------------------------------------------------------ #

    def is_model_known(self, model: str) -> bool:
        return model in self.known_models

    def is_model_deprecated(self, model: str) -> bool:
        return model in self.deprecated_models

    def get_stale_alias_correction(self, model: str) -> str | None:
        """Return the correct model name if the given model is a stale alias, else None."""
        return self.stale_aliases.get(model)

    def get_model_endpoint(self, model: str) -> str | None:
        """Return the model-specific endpoint if configured, else None."""
        return self.model_endpoints.get(model)

    # ------------------------------------------------------------------ #
    # Endpoint helpers
    # ------------------------------------------------------------------ #

    def is_endpoint_canonical(self, endpoint: str) -> bool:
        return self.canonical_endpoint.rstrip("/") == endpoint.rstrip("/")

    # ------------------------------------------------------------------ #
    # Auth helpers
    # ------------------------------------------------------------------ #

    def requires_human_auth(self) -> bool:
        return (self.auth_type or "").strip().lower() == "oauth"

    # ------------------------------------------------------------------ #
    # Region helpers
    # ------------------------------------------------------------------ #

    def is_available_in_region(self, region: str) -> bool:
        """Return True if this provider is available in the given region."""
        if not self.regions:
            return True  # Unknown means all regions possible
        return region in self.regions

    # ------------------------------------------------------------------ #
    # Transport helpers
    # ------------------------------------------------------------------ #

    def is_transport_secure(self) -> bool:
        """Return True if the transport is HTTPS or WSS (secure)."""
        return self.transport.lower() in {"https", "wss"}

    # ------------------------------------------------------------------ #
    # Endpoint candidate helpers
    # ------------------------------------------------------------------ #

    def get_stable_candidates(self) -> list[EndpointCandidate]:
        """Return only stable endpoint candidates."""
        return [c for c in self.endpoint_candidates if c.is_stable]

    def get_candidates_for_region(self, region: str) -> list[EndpointCandidate]:
        """Return endpoint candidates that cover the given region."""
        return [
            c
            for c in self.endpoint_candidates
            if not c.region_scope or region in c.region_scope
        ]


@dataclass
class ProviderTruthStore:
    records: dict[str, ProviderTruthRecord] = field(default_factory=dict)

    def add(self, record: ProviderTruthRecord, *, replace: bool = False) -> None:
        canonical = canonical_provider_name(record.provider)
        normalized = ProviderTruthRecord(
            provider=canonical,
            canonical_endpoint=record.canonical_endpoint,
            known_models=list(record.known_models),
            deprecated_models=list(record.deprecated_models),
            stale_aliases=dict(record.stale_aliases),
            model_endpoints=dict(record.model_endpoints),
            capabilities=list(record.capabilities),
            context_window=record.context_window,
            source_url=record.source_url,
            confidence=record.confidence,
            auth_type=record.auth_type,
            regions=list(record.regions),
            transport=record.transport,
            endpoint_candidates=list(record.endpoint_candidates),
        )
        existing = self.records.get(canonical)
        if existing is not None and not replace:
            raise ValueError(
                f"duplicate provider family '{canonical}' from '{record.provider}' conflicts with existing '{existing.provider}'"
            )
        self.records[canonical] = normalized

    def get(self, provider: str) -> ProviderTruthRecord | None:
        return self.records.get(canonical_provider_name(provider))

    def providers(self) -> list[str]:
        return list(self.records.keys())

    def check_right_key_wrong_endpoint(self, provider: str, endpoint: str) -> tuple[bool, str]:
        rec = self.get(provider)
        if rec is None or rec.is_endpoint_canonical(endpoint):
            return False, ""
        return True, f"Endpoint mismatch for provider '{rec.provider}': expected '{rec.canonical_endpoint}' but got '{endpoint}'"

    def check_stale_model(self, provider: str, model: str) -> tuple[bool, str]:
        rec = self.get(provider)
        if rec is None:
            return False, ""
        if rec.is_model_known(model):
            return False, ""
        if rec.is_model_deprecated(model):
            return True, f"Model '{model}' for provider '{rec.provider}' is deprecated"
        return True, f"Model '{model}' for provider '{rec.provider}' is not in known model list"

    def all_records(self) -> list[ProviderTruthRecord]:
        return list(self.records.values())

    # ------------------------------------------------------------------ #
    # Repair candidate helpers
    # ------------------------------------------------------------------ #

    def get_repair_candidates(
        self,
        provider: str,
        *,
        region: str | None = None,
        stable_only: bool = False,
    ) -> list[EndpointCandidate]:
        """
        Return known-good endpoint candidates for a provider that can be
        probed as repair candidates when the primary endpoint is failing.

        Parameters:
            provider: Provider name (alias resolves to canonical)
            region: Optional region code to filter candidates
            stable_only: If True, only return stable (is_stable=True) candidates

        Returns:
            List of EndpointCandidate objects, filtered by region and stability
        """
        rec = self.get(provider)
        if rec is None:
            return []

        candidates = rec.endpoint_candidates

        if stable_only:
            candidates = [c for c in candidates if c.is_stable]

        if region:
            candidates = [
                c
                for c in candidates
                if not c.region_scope or region in c.region_scope
            ]

        return candidates


def _dict_to_candidates(data: list[Any]) -> list[EndpointCandidate]:
    """Convert a list of dicts to EndpointCandidate objects."""
    result = []
    for item in data:
        if isinstance(item, dict):
            result.append(
                EndpointCandidate(
                    endpoint=item.get("endpoint", ""),
                    api_style=item.get("api_style", "openai-compatible"),
                    auth_type=item.get("auth_type", "bearer"),
                    region_scope=item.get("region_scope", []),
                    is_stable=item.get("is_stable", True),
                )
            )
    return result


def _dict_to_record(d: dict[str, Any]) -> ProviderTruthRecord:
    return ProviderTruthRecord(
        provider=d.get("provider", ""),
        canonical_endpoint=d.get("canonical_endpoint", ""),
        known_models=d.get("known_models", []),
        deprecated_models=d.get("deprecated_models", []),
        stale_aliases=d.get("stale_aliases", {}),
        model_endpoints=d.get("model_endpoints", {}),
        capabilities=d.get("capabilities", []),
        context_window=d.get("context_window", 0),
        source_url=d.get("source_url"),
        confidence=d.get("confidence", "medium"),
        auth_type=d.get("auth_type"),
        regions=d.get("regions", []),
        transport=d.get("transport", ""),
        endpoint_candidates=_dict_to_candidates(d.get("endpoint_candidates", [])),
    )


def _candidate_to_dict(c: EndpointCandidate) -> dict[str, Any]:
    return {
        "endpoint": c.endpoint,
        "api_style": c.api_style,
        "auth_type": c.auth_type,
        "region_scope": c.region_scope,
        "is_stable": c.is_stable,
    }


def seed_from_config(config_path: str | Path) -> ProviderTruthStore:
    """Build a ProviderTruthStore from a real config.yaml provider definitions.

    Reads providers.X.api, providers.X.default_model, providers.X.key_env
    and creates truth records so verify_endpoint works without an external YAML.
    Also seeds providers referenced in auxiliary roles but absent from the
    providers: section by resolving their env-var base_url.
    """
    import os

    from hermesoptimizer.sources.hermes_config import _PROVIDER_ENV_VARS

    p = Path(config_path)
    if not p.exists():
        return ProviderTruthStore()
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return ProviderTruthStore()

    store = ProviderTruthStore()
    providers = data.get("providers", {})
    if not isinstance(providers, dict):
        return store

    for name, prov in providers.items():
        if not isinstance(prov, dict):
            continue
        endpoint = prov.get("api") or prov.get("base_url", "")
        model = prov.get("default_model") or prov.get("model", "")
        known_models = [model] if model else []
        store.add(ProviderTruthRecord(
            provider=name,
            canonical_endpoint=endpoint,
            known_models=known_models,
            deprecated_models=[],
            stale_aliases={},
            model_endpoints={},
            capabilities=["text"],
            context_window=0,
            source_url=None,
            confidence="medium",
            auth_type="bearer",
            regions=["global"],
            transport="https",
            endpoint_candidates=[],
        ), replace=False)

    # Seed providers referenced via auxiliary roles but absent from the
    # providers: section.  Resolve endpoint from env vars or known defaults.
    auxiliary = data.get("auxiliary", {})
    if isinstance(auxiliary, dict):
        # Well-known default endpoints for providers commonly used in auxiliary.
        _KNOWN_ENDPOINTS: dict[str, str] = {
            "xai": "https://api.x.ai/v1",
            "openai": "https://api.openai.com/v1",
            "anthropic": "https://api.anthropic.com/v1",
            "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "kimi": "https://api.moonshot.cn/v1",
            "minimax": "https://api.minimax.chat/v1",
            "zai": "https://open.bigmodel.cn/api/paas/v4",
            "openrouter": "https://openrouter.ai/api/v1",
        }
        for _role, role_cfg in auxiliary.items():
            if not isinstance(role_cfg, dict):
                continue
            prov_name = canonical_provider_name(role_cfg.get("provider", ""))
            if not prov_name:
                continue
            if store.get(prov_name) is not None:
                continue  # already seeded from providers: section
            env_pair = _PROVIDER_ENV_VARS.get(prov_name)
            base_url = ""
            if env_pair:
                base_url = os.environ.get(env_pair[0], "")
            if not base_url:
                base_url = _KNOWN_ENDPOINTS.get(prov_name, "")
            model = role_cfg.get("model", "")
            if base_url:
                store.add(ProviderTruthRecord(
                    provider=prov_name,
                    canonical_endpoint=base_url,
                    known_models=[model] if model else [],
                    deprecated_models=[],
                    stale_aliases={},
                    model_endpoints={},
                    capabilities=["text"],
                    context_window=0,
                    source_url=None,
                    confidence="medium",
                    auth_type="bearer",
                    regions=["global"],
                    transport="https",
                    endpoint_candidates=[],
                ), replace=False)

    return store


def load_provider_truth(path: str | Path) -> ProviderTruthStore:
    p = Path(path)
    if not p.exists():
        return ProviderTruthStore()
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    store = ProviderTruthStore()
    for provider_name, rec_data in data.items():
        if isinstance(rec_data, dict):
            store.add(_dict_to_record({"provider": provider_name, **rec_data}), replace=False)
    return store


def dump_provider_truth(store: ProviderTruthStore, path: str | Path) -> None:
    data = {}
    for rec in store.all_records():
        record_dict: dict[str, Any] = {
            "provider": rec.provider,
            "canonical_endpoint": rec.canonical_endpoint,
            "known_models": rec.known_models,
            "deprecated_models": rec.deprecated_models,
            "stale_aliases": rec.stale_aliases,
            "model_endpoints": rec.model_endpoints,
            "capabilities": rec.capabilities,
            "context_window": rec.context_window,
            "source_url": rec.source_url,
            "confidence": rec.confidence,
            "auth_type": rec.auth_type,
            "regions": rec.regions,
            "transport": rec.transport,
            "endpoint_candidates": [_candidate_to_dict(c) for c in rec.endpoint_candidates],
        }
        data[rec.provider] = record_dict
    Path(path).write_text(yaml.dump(data, sort_keys=False), encoding="utf-8")

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class ProviderTruthRecord:
    provider: str
    canonical_endpoint: str
    known_models: list[str] = field(default_factory=list)
    deprecated_models: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    context_window: int = 0
    source_url: str | None = None
    confidence: str = "medium"

    def is_model_known(self, model: str) -> bool:
        return model in self.known_models

    def is_model_deprecated(self, model: str) -> bool:
        return model in self.deprecated_models

    def is_endpoint_canonical(self, endpoint: str) -> bool:
        return self.canonical_endpoint.rstrip("/") == endpoint.rstrip("/")


@dataclass
class ProviderTruthStore:
    records: dict[str, ProviderTruthRecord] = field(default_factory=dict)

    def add(self, record: ProviderTruthRecord) -> None:
        self.records[record.provider] = record

    def get(self, provider: str) -> ProviderTruthRecord | None:
        return self.records.get(provider)

    def providers(self) -> list[str]:
        return list(self.records.keys())

    def check_right_key_wrong_endpoint(self, provider: str, endpoint: str) -> tuple[bool, str]:
        rec = self.records.get(provider)
        if rec is None or rec.is_endpoint_canonical(endpoint):
            return False, ""
        return True, f"Endpoint mismatch for provider '{provider}': expected '{rec.canonical_endpoint}' but got '{endpoint}'"

    def check_stale_model(self, provider: str, model: str) -> tuple[bool, str]:
        rec = self.records.get(provider)
        if rec is None:
            return False, ""
        if rec.is_model_known(model):
            return False, ""
        if rec.is_model_deprecated(model):
            return True, f"Model '{model}' for provider '{provider}' is deprecated"
        return True, f"Model '{model}' for provider '{provider}' is not in known model list"

    def all_records(self) -> list[ProviderTruthRecord]:
        return list(self.records.values())


def _dict_to_record(d: dict[str, Any]) -> ProviderTruthRecord:
    return ProviderTruthRecord(
        provider=d.get("provider", ""),
        canonical_endpoint=d.get("canonical_endpoint", ""),
        known_models=d.get("known_models", []),
        deprecated_models=d.get("deprecated_models", []),
        capabilities=d.get("capabilities", []),
        context_window=d.get("context_window", 0),
        source_url=d.get("source_url"),
        confidence=d.get("confidence", "medium"),
    )


def load_provider_truth(path: str | Path) -> ProviderTruthStore:
    p = Path(path)
    if not p.exists():
        return ProviderTruthStore()
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    store = ProviderTruthStore()
    for provider_name, rec_data in data.items():
        if isinstance(rec_data, dict):
            store.add(_dict_to_record({"provider": provider_name, **rec_data}))
    return store


def dump_provider_truth(store: ProviderTruthStore, path: str | Path) -> None:
    data = {}
    for rec in store.all_records():
        data[rec.provider] = {
            "provider": rec.provider,
            "canonical_endpoint": rec.canonical_endpoint,
            "known_models": rec.known_models,
            "deprecated_models": rec.deprecated_models,
            "capabilities": rec.capabilities,
            "context_window": rec.context_window,
            "source_url": rec.source_url,
            "confidence": rec.confidence,
        }
    Path(path).write_text(yaml.dump(data, sort_keys=False), encoding="utf-8")

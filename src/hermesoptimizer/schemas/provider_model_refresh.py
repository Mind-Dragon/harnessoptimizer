"""
Provider Model Catalog Refresh Pipeline.

Refreshes the model catalog by:
1. Preferring live /models API when supported
2. Merging docs/manual metadata on top
3. Recording blocked source states explicitly
4. Maintaining source provenance

This module provides the refresh pipeline that keeps the checked-in model catalog
in sync with provider data.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any

import requests

from hermesoptimizer.schemas.exceptions import ProviderModelCatalogError
from hermesoptimizer.schemas.provider_endpoint import ProviderEndpointCatalog
from hermesoptimizer.schemas.provider_model import (
    ProviderModelCatalog,
    load_provider_models_catalog,
    validate_provider_models,
)


class RefreshStatus(str, Enum):
    """Status of a provider model refresh operation."""

    LIVE_API = "live_api"  # Successfully fetched from live API
    DOCS_ONLY = "docs_only"  # Only docs available, no live API used
    BLOCKED_API = "blocked_api"  # Live API blocked (anti-bot, auth, etc.)
    BLOCKED_DOC = "blocked_doc"  # Documentation blocked
    MANUAL_FALLBACK = "manual_fallback"  # Only manual/cached data available


class BlockedSourceReason(str, Enum):
    """Reason a source was blocked."""

    API_KEY_MISSING = "api_key_missing"
    API_KEY_INVALID = "api_key_invalid"
    ANTI_BOT_PROTECTION = "anti_bot_protection"
    RATE_LIMITED = "rate_limited"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    AUTH_REQUIRED = "auth_required"
    DOCS_BLOCKED = "docs_blocked"
    NOT_SUPPORTED = "not_supported"


@dataclass
class ManualMetadata:
    """Manual or documentation-derived metadata for a model.

    This metadata is merged with live API data when available.
    """

    display_name: str | None = None
    capabilities: list[str] | None = None
    context_window: int | None = None
    input_cost_per_mtok: float | None = None
    output_cost_per_mtok: float | None = None
    latency_tier: str | None = None
    region_availability: list[str] | None = None
    release_date: date | None = None
    is_deprecated: bool = False
    deprecation_notes: str | None = None
    notes: str | None = None


@dataclass
class ModelSourceProvenance:
    """Tracks the source of model data."""

    source: str  # live_api, official_docs, sdk_example, manual_fallback
    source_url: str | None = None


@dataclass
class BlockedSource:
    """Records a blocked source for a provider."""

    provider_slug: str
    source_type: str  # live_api, official_docs, sdk_example
    reason: BlockedSourceReason
    message: str


@dataclass
class ModelRefreshResult:
    """Result of refreshing models for a provider."""

    provider_slug: str
    status: RefreshStatus
    models: list[dict[str, Any]]
    blocked_sources: list[BlockedSource] = field(default_factory=list)
    error_message: str | None = None


def merge_with_manual_metadata(
    live_model: dict[str, Any],
    manual: ManualMetadata | None,
) -> dict[str, Any]:
    """
    Merge live API model data with manual/docs metadata.

    Live API data takes precedence for: provider_slug, model_name, capabilities,
    context_window, and cost fields. Manual metadata fills in: display_name,
    region_availability, deprecation info, latency_tier, and notes.

    Args:
        live_model: Model data from live API (must have provider_slug, model_name)
        manual: Manual metadata to merge on top

    Returns:
        Merged model dict with source_provenance set
    """
    if manual is None:
        # No manual metadata, return live model as-is with provenance
        result = dict(live_model)
        if "source_provenance" not in result:
            result["source_provenance"] = "live_api"
        return result

    result = dict(live_model)

    # Manual metadata fills in display_name if not present
    if manual.display_name is not None:
        result["display_name"] = manual.display_name

    # Capabilities from manual (live API may not expose all)
    if manual.capabilities is not None and manual.capabilities:
        # Merge with live capabilities, don't replace
        live_caps = set(result.get("capabilities", []))
        result["capabilities"] = sorted(live_caps | set(manual.capabilities))

    # Context window from live API takes precedence
    if result.get("context_window") is None and manual.context_window is not None:
        result["context_window"] = manual.context_window

    # Cost fields from live API take precedence (more accurate)
    if result.get("input_cost_per_mtok") is None and manual.input_cost_per_mtok is not None:
        result["input_cost_per_mtok"] = manual.input_cost_per_mtok
    if result.get("output_cost_per_mtok") is None and manual.output_cost_per_mtok is not None:
        result["output_cost_per_mtok"] = manual.output_cost_per_mtok

    # Latency tier from manual
    if manual.latency_tier is not None and "latency_tier" not in result:
        result["latency_tier"] = manual.latency_tier

    # Region availability from manual
    if manual.region_availability is not None and "region_availability" not in result:
        result["region_availability"] = manual.region_availability

    # Release date from manual
    if manual.release_date is not None and "release_date" not in result:
        result["release_date"] = manual.release_date.isoformat()

    # Deprecation from manual
    if manual.is_deprecated:
        result["is_deprecated"] = True
    if manual.deprecation_notes is not None:
        result["deprecation_notes"] = manual.deprecation_notes

    # Notes from manual
    if manual.notes is not None:
        result["notes"] = manual.notes

    # Set source provenance based on what data was used
    if result.get("source_provenance") is None:
        result["source_provenance"] = "official_docs"

    return result


class ProviderModelRefreshPipeline:
    """
    Pipeline for refreshing the provider model catalog.

    This pipeline:
    1. Loads existing model catalog and endpoint catalog
    2. For each provider, attempts to fetch models from live API
    3. Merges live data with manual/docs metadata
    4. Records blocked sources explicitly
    5. Persists updated catalog

    The pipeline prefers live API data when available and falls back to
    manual documentation metadata. Blocked sources are recorded explicitly
    rather than silently failing.
    """

    def __init__(
        self,
        model_catalog_path: str | Path,
        endpoint_catalog_path: str | Path,
        env_prefix: str = "",
    ) -> None:
        """
        Initialize the refresh pipeline.

        Args:
            model_catalog_path: Path to the provider models JSON catalog
            endpoint_catalog_path: Path to the provider endpoints JSON catalog
            env_prefix: Prefix for environment variables (e.g., "HERMES_")
        """
        self.model_catalog_path = Path(model_catalog_path)
        self.endpoint_catalog_path = Path(endpoint_catalog_path)
        self.env_prefix = env_prefix
        self._catalog: dict[str, Any] | None = None
        self._endpoint_catalog: ProviderEndpointCatalog | None = None

    def _load_catalog(self) -> dict[str, Any]:
        """Load the model catalog from disk."""
        try:
            return load_provider_models_catalog(self.model_catalog_path)
        except ProviderModelCatalogError:
            # Return empty catalog if file doesn't exist yet
            return {"version": "1.0.0", "provider_models": []}

    def _load_endpoint_catalog(self) -> ProviderEndpointCatalog:
        """Load the endpoint catalog from disk."""
        return ProviderEndpointCatalog.from_file(self.endpoint_catalog_path)

    def get_catalog(self) -> dict[str, Any]:
        """Get the current model catalog."""
        if self._catalog is None:
            self._catalog = self._load_catalog()
        return self._catalog

    def get_endpoint_catalog(self) -> ProviderEndpointCatalog:
        """Get the endpoint catalog."""
        if self._endpoint_catalog is None:
            self._endpoint_catalog = self._load_endpoint_catalog()
        return self._endpoint_catalog

    def get_provider_model_names(self, provider_slug: str) -> list[str]:
        """Get current model names for a provider from the catalog."""
        catalog = self.get_catalog()
        return [
            m["model_name"]
            for m in catalog.get("provider_models", [])
            if m.get("provider_slug") == provider_slug
        ]

    def get_manual_metadata_for_provider(
        self,
        provider_slug: str,
    ) -> dict[str, ManualMetadata]:
        """Get manual metadata for all models of a provider."""
        catalog = self.get_catalog()
        manual: dict[str, ManualMetadata] = {}

        for model in catalog.get("provider_models", []):
            if model.get("provider_slug") != provider_slug:
                continue

            model_name = model.get("model_name", "")
            if not model_name:
                continue

            # Build ManualMetadata from existing catalog entry
            manual[model_name] = ManualMetadata(
                display_name=model.get("display_name"),
                capabilities=model.get("capabilities"),
                context_window=model.get("context_window"),
                input_cost_per_mtok=model.get("input_cost_per_mtok"),
                output_cost_per_mtok=model.get("output_cost_per_mtok"),
                latency_tier=model.get("latency_tier"),
                region_availability=model.get("region_availability"),
                release_date=date.fromisoformat(model["release_date"])
                if model.get("release_date")
                else None,
                is_deprecated=model.get("is_deprecated", False),
                deprecation_notes=model.get("deprecation_notes"),
                notes=model.get("notes"),
            )

        return manual

    def get_providers_with_models_path(self) -> list[str]:
        """Get list of provider slugs that have a models_path endpoint."""
        endpoint_catalog = self.get_endpoint_catalog()
        providers = []

        for slug in endpoint_catalog.provider_slugs:
            families = endpoint_catalog.list_endpoint_families(slug)
            for family in families:
                if family.get("models_path"):
                    providers.append(slug)
                    break

        return providers

    def _get_api_key(self, provider_slug: str) -> str | None:
        """Get API key for a provider from environment."""
        endpoint_catalog = self.get_endpoint_catalog()
        provider = endpoint_catalog.get_provider(provider_slug)

        if provider is None:
            return None

        key_env = provider.get("default_auth_key_env")
        if key_env is None:
            return None

        # Try with prefix first, then without
        key = os.environ.get(f"{self.env_prefix}{key_env}")
        if key:
            return key
        return os.environ.get(key_env)

    def _fetch_live_models(
        self,
        provider_slug: str,
    ) -> tuple[list[dict[str, Any]], BlockedSource | None]:
        """
        Fetch models from live API for a provider.

        Args:
            provider_slug: Provider to fetch models for

        Returns:
            Tuple of (models list, blocked_source or None)
        """
        endpoint_catalog = self.get_endpoint_catalog()
        provider = endpoint_catalog.get_provider(provider_slug)

        if provider is None:
            blocked = BlockedSource(
                provider_slug=provider_slug,
                source_type="live_api",
                reason=BlockedSourceReason.NOT_SUPPORTED,
                message=f"Provider '{provider_slug}' not found in endpoint catalog",
            )
            return [], blocked

        default_endpoint = endpoint_catalog.get_default_endpoint(provider_slug)
        if default_endpoint is None:
            blocked = BlockedSource(
                provider_slug=provider_slug,
                source_type="live_api",
                reason=BlockedSourceReason.NOT_SUPPORTED,
                message=f"No default endpoint for provider '{provider_slug}'",
            )
            return [], blocked

        base_url = default_endpoint.get("base_url", "")
        models_path = default_endpoint.get("models_path", "/v1/models")

        if not models_path:
            blocked = BlockedSource(
                provider_slug=provider_slug,
                source_type="live_api",
                reason=BlockedSourceReason.NOT_SUPPORTED,
                message=f"No models_path configured for provider '{provider_slug}'",
            )
            return [], blocked

        api_key = self._get_api_key(provider_slug)
        if api_key is None:
            blocked = BlockedSource(
                provider_slug=provider_slug,
                source_type="live_api",
                reason=BlockedSourceReason.API_KEY_MISSING,
                message=f"No API key found for provider '{provider_slug}'",
            )
            return [], blocked

        url = f"{base_url.rstrip('/')}{models_path}"

        try:
            headers = {}
            auth_type = default_endpoint.get("auth_type", "bearer")
            if auth_type == "bearer":
                headers["Authorization"] = f"Bearer {api_key}"
            elif auth_type == "api_key":
                auth_header = default_endpoint.get("auth_header_shape", "")
                if "x-api-key" in auth_header.lower():
                    headers["x-api-key"] = api_key
                else:
                    headers["Authorization"] = f"Bearer {api_key}"

            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 401 or response.status_code == 403:
                blocked = BlockedSource(
                    provider_slug=provider_slug,
                    source_type="live_api",
                    reason=BlockedSourceReason.API_KEY_INVALID,
                    message=f"API key invalid (status {response.status_code})",
                )
                return [], blocked

            if response.status_code == 429:
                blocked = BlockedSource(
                    provider_slug=provider_slug,
                    source_type="live_api",
                    reason=BlockedSourceReason.RATE_LIMITED,
                    message=f"Rate limited (status {response.status_code})",
                )
                return [], blocked

            if response.status_code != 200:
                blocked = BlockedSource(
                    provider_slug=provider_slug,
                    source_type="live_api",
                    reason=BlockedSourceReason.NETWORK_ERROR,
                    message=f"Unexpected status {response.status_code}",
                )
                return [], blocked

            data = response.json()

            # Parse OpenAI-style response
            models = []
            for item in data.get("data", []):
                model_id = item.get("id", "")
                if not model_id:
                    continue

                model = {
                    "provider_slug": provider_slug,
                    "model_name": model_id,
                    "capabilities": item.get("capabilities", []),
                    "context_window": item.get("context_window") or item.get("max_tokens") or 0,
                }

                # Handle OpenAI-style owned_by field
                if item.get("owned_by"):
                    # Could set display_name from owned_by
                    pass

                models.append(model)

            return models, None

        except requests.exceptions.Timeout:
            blocked = BlockedSource(
                provider_slug=provider_slug,
                source_type="live_api",
                reason=BlockedSourceReason.TIMEOUT,
                message="Request timed out",
            )
            return [], blocked

        except requests.exceptions.RequestException as e:
            blocked = BlockedSource(
                provider_slug=provider_slug,
                source_type="live_api",
                reason=BlockedSourceReason.NETWORK_ERROR,
                message=f"Network error: {str(e)}",
            )
            return [], blocked

    def refresh_provider(self, provider_slug: str) -> ModelRefreshResult:
        """
        Refresh models for a single provider.

        Args:
            provider_slug: Provider to refresh

        Returns:
            ModelRefreshResult with models or blocked source info
        """
        blocked_sources: list[BlockedSource] = []

        # Try live API first
        live_models, blocked = self._fetch_live_models(provider_slug)

        if blocked:
            blocked_sources.append(blocked)

        if live_models:
            # Got live data, merge with manual metadata
            manual = self.get_manual_metadata_for_provider(provider_slug)
            merged_models = []

            for live_model in live_models:
                model_name = live_model.get("model_name", "")
                manual_meta = manual.get(model_name)
                merged = merge_with_manual_metadata(live_model, manual_meta)
                merged_models.append(merged)

            return ModelRefreshResult(
                provider_slug=provider_slug,
                status=RefreshStatus.LIVE_API,
                models=merged_models,
                blocked_sources=blocked_sources,
            )

        # No live data, use manual/cached metadata
        manual = self.get_manual_metadata_for_provider(provider_slug)
        manual_models = []

        for model_name, meta in manual.items():
            # Check if model already exists in catalog
            existing = None
            catalog = self.get_catalog()
            for m in catalog.get("provider_models", []):
                if m.get("provider_slug") == provider_slug and m.get("model_name") == model_name:
                    existing = m
                    break

            if existing:
                # Merge existing data
                merged = merge_with_manual_metadata(existing, meta)
                # Update source provenance
                merged["source_provenance"] = "manual_fallback"
                manual_models.append(merged)
            else:
                # Create new entry from manual metadata only
                model = {
                    "provider_slug": provider_slug,
                    "model_name": model_name,
                    "source_provenance": "manual_fallback",
                }
                merged = merge_with_manual_metadata(model, meta)
                manual_models.append(merged)

        if blocked_sources:
            # Had blocked API
            return ModelRefreshResult(
                provider_slug=provider_slug,
                status=RefreshStatus.BLOCKED_API,
                models=manual_models,
                blocked_sources=blocked_sources,
            )

        return ModelRefreshResult(
            provider_slug=provider_slug,
            status=RefreshStatus.MANUAL_FALLBACK,
            models=manual_models,
            blocked_sources=blocked_sources,
        )

    def refresh_all_providers(self) -> list[ModelRefreshResult]:
        """
        Refresh models for all providers in the endpoint catalog.

        Returns:
            List of ModelRefreshResult for each provider
        """
        endpoint_catalog = self.get_endpoint_catalog()
        results = []

        for provider_slug in endpoint_catalog.provider_slugs:
            result = self.refresh_provider(provider_slug)
            results.append(result)

        return results

    def update_catalog(
        self,
        results: list[ModelRefreshResult],
    ) -> dict[str, Any]:
        """
        Update the catalog with refresh results.

        Args:
            results: List of refresh results from refresh_all_providers

        Returns:
            Updated catalog dict
        """
        catalog = self.get_catalog()
        existing_models: dict[tuple[str, str], dict[str, Any]] = {}

        # Index existing models by (provider_slug, model_name)
        for model in catalog.get("provider_models", []):
            key = (model.get("provider_slug", ""), model.get("model_name", ""))
            existing_models[key] = model

        # Update with new models
        for result in results:
            for model in result.models:
                key = (model.get("provider_slug", ""), model.get("model_name", ""))
                # Preserve last_verified if not in new model
                if key in existing_models and "last_verified" in existing_models[key]:
                    if "last_verified" not in model:
                        model["last_verified"] = existing_models[key]["last_verified"]
                existing_models[key] = model

        # Convert back to list
        catalog["provider_models"] = list(existing_models.values())

        # Sort by provider_slug then model_name
        catalog["provider_models"].sort(
            key=lambda m: (m.get("provider_slug", ""), m.get("model_name", ""))
        )

        self._catalog = catalog
        return catalog

    def persist_catalog(self, catalog: dict[str, Any] | None = None) -> None:
        """
        Write the catalog to disk.

        Args:
            catalog: Catalog to write (uses internal if None)
        """
        if catalog is None:
            catalog = self.get_catalog()

        # Validate before writing
        errors = validate_provider_models(catalog)
        if errors:
            raise ProviderModelCatalogError(
                f"Catalog validation failed before persist: {'; '.join(errors)}"
            )

        with open(self.model_catalog_path, "w", encoding="utf-8") as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)

    def run(self) -> list[ModelRefreshResult]:
        """
        Run the full refresh pipeline.

        1. Refresh all providers
        2. Update catalog
        3. Persist to disk

        Returns:
            List of refresh results
        """
        results = self.refresh_all_providers()
        catalog = self.update_catalog(results)
        self.persist_catalog(catalog)
        return results

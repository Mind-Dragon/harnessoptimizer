"""
Provider Endpoint Catalog Loader and Validator.

Loads and validates provider endpoint JSON catalogs against the JSON schema.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

from hermesoptimizer.schemas.exceptions import ProviderModelCatalogError

# Schema path and URL constants
SCHEMA_PATH = Path(__file__).parent / "provider_endpoint.schema.json"
SCHEMA_URL = "https://hermesoptimizer.io/schemas/provider_endpoint.schema.json"

# Type alias for the validated catalog data structure
ProviderEndpointData = dict[str, Any]


def load_schema() -> dict[str, Any]:
    """Load and return the provider endpoint JSON schema."""
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_schema_path() -> Path:
    """Return the path to the provider endpoint JSON schema."""
    return SCHEMA_PATH


def get_schema_url() -> str:
    """Return the schema URL/id."""
    return SCHEMA_URL


def get_schema() -> dict[str, Any]:
    """Load and return the provider endpoint JSON schema."""
    return load_schema()


def validate_provider_endpoints(data: dict[str, Any]) -> list[str]:
    """
    Validate a provider endpoints catalog against the JSON schema.

    Returns a list of error messages (empty if valid).
    """
    errors: list[str] = []
    schema = get_schema()

    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as e:
        errors.append(f"Validation error: {e.message}")
        errors.append(f"  Path: {'.'.join(str(p) for p in e.path)}")
        errors.append(f"  Schema path: {'.'.join(str(p) for p in e.schema_path)}")
    except jsonschema.SchemaError as e:
        errors.append(f"Schema error: {e.message}")

    # Additional semantic validations
    if "provider_endpoints" in data:
        provider_slugs: set[str] = set()
        for idx, provider in enumerate(data["provider_endpoints"]):
            slug = provider.get("provider_slug", "")

            # Check for duplicate provider slugs
            if slug in provider_slugs:
                errors.append(
                    f"Duplicate provider slug '{slug}' at index {idx}"
                )
            provider_slugs.add(slug)

            # Validate endpoint families
            endpoints = provider.get("endpoints", [])
            default_count = sum(1 for e in endpoints if e.get("is_default", False))
            if default_count > 1:
                errors.append(
                    f"Provider '{slug}' has multiple default endpoint families"
                )

            # Validate base_url format
            for e_idx, endpoint in enumerate(endpoints):
                base_url = endpoint.get("base_url", "")
                if base_url and not base_url.startswith(("http://", "https://")):
                    errors.append(
                        f"Provider '{slug}' endpoint {e_idx} has invalid base_url "
                        f"'{base_url}' (must start with http:// or https://)"
                    )

    return errors


def load_provider_endpoints_catalog(path: str | Path) -> dict[str, Any]:
    """
    Load a provider endpoints JSON catalog from the given path.

    Returns the parsed JSON data.
    Raises ProviderModelCatalogError if the file cannot be read or parsed.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ProviderModelCatalogError(f"Invalid JSON in {path}: {e}")
    except OSError as e:
        raise ProviderModelCatalogError(f"Cannot read {path}: {e}")

    if not isinstance(data, dict):
        raise ProviderModelCatalogError(f"Expected JSON object in {path}, got {type(data).__name__}")

    return data


def validate_provider_endpoints_file(path: str | Path) -> list[str]:
    """
    Load and validate a provider endpoints JSON catalog file.

    Returns a list of error messages (empty if valid).
    """
    data = load_provider_endpoints_catalog(path)
    return validate_provider_endpoints(data)


class ProviderEndpointCatalog:
    """
    Represents a validated provider endpoint catalog.

    Provides convenient access to endpoint data.
    """

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data
        self._providers: dict[str, dict[str, Any]] = {}
        self._load_providers()

    def _load_providers(self) -> None:
        """Index providers by slug."""
        for provider in self._data.get("provider_endpoints", []):
            slug = provider.get("provider_slug", "")
            if slug:
                self._providers[slug] = provider

    @property
    def version(self) -> str | None:
        """Return the catalog version."""
        return self._data.get("version")

    @property
    def provider_slugs(self) -> list[str]:
        """Return sorted list of provider slugs."""
        return sorted(self._providers.keys())

    def get_provider(self, slug: str) -> dict[str, Any] | None:
        """Get provider data by slug."""
        return self._providers.get(slug.lower().strip())

    def list_endpoint_families(self, provider_slug: str) -> list[dict[str, Any]]:
        """List endpoint families for a provider."""
        provider = self.get_provider(provider_slug)
        if provider is None:
            return []
        return provider.get("endpoints", [])

    def get_default_endpoint(self, provider_slug: str) -> dict[str, Any] | None:
        """Get the default endpoint family for a provider."""
        families = self.list_endpoint_families(provider_slug)
        for family in families:
            if family.get("is_default", False):
                return family
        # If no explicit default, return first stable endpoint
        for family in families:
            if family.get("is_stable", True):
                return family
        return families[0] if families else None

    def validate(self) -> list[str]:
        """Validate the catalog and return error messages."""
        return validate_provider_endpoints(self._data)

    @classmethod
    def from_file(cls, path: str | Path) -> "ProviderEndpointCatalog":
        """Load a catalog from a JSON file."""
        data = load_provider_endpoints_catalog(path)
        errors = validate_provider_endpoints(data)
        if errors:
            raise ProviderModelCatalogError(
                f"Catalog validation failed: " + "; ".join(errors)
            )
        return cls(data)

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "ProviderEndpointCatalog":
        """Create a catalog from a dict, validating it."""
        errors = validate_provider_endpoints(data)
        if errors:
            raise ProviderModelCatalogError(
                f"Catalog validation failed: " + "; ".join(errors)
            )
        return cls(data)

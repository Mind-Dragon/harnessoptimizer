"""
Provider Model Catalog Loader and Validator.

Loads and validates provider model JSON catalogs against the JSON schema.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

from hermesoptimizer.schemas.exceptions import ProviderModelCatalogError

# Schema path and URL constants
SCHEMA_PATH = Path(__file__).parent / "provider_model.schema.json"
SCHEMA_URL = "https://hermesoptimizer.io/schemas/provider_model.schema.json"

# Type alias for the validated catalog data structure
ProviderModelData = dict[str, Any]


def load_schema() -> dict[str, Any]:
    """Load and return the provider model JSON schema."""
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_schema_path() -> Path:
    """Return the path to the provider model JSON schema."""
    return SCHEMA_PATH


def get_schema_url() -> str:
    """Return the schema URL/id."""
    return SCHEMA_URL


def get_schema() -> dict[str, Any]:
    """Load and return the provider model JSON schema."""
    return load_schema()


def validate_provider_models(data: dict[str, Any]) -> list[str]:
    """
    Validate a provider models catalog against the JSON schema.

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
    if "provider_models" in data:
        seen: dict[str, set[str]] = {}
        for idx, model in enumerate(data["provider_models"]):
            provider = model.get("provider_slug", "")
            model_name = model.get("model_name", "")

            # Check for duplicate (provider, model_name) pairs
            if provider not in seen:
                seen[provider] = set()
            if model_name in seen[provider]:
                errors.append(
                    f"Duplicate model '{model_name}' for provider '{provider}' at index {idx}"
                )
            seen[provider].add(model_name)

            # Validate context_window for text-capable models
            capabilities = model.get("capabilities", [])
            context_window = model.get("context_window", 0)
            if "text" in capabilities and context_window == 0:
                errors.append(
                    f"Model '{model_name}' has 'text' capability but context_window=0"
                )

            # Validate cost fields are non-negative
            input_cost = model.get("input_cost_per_mtok")
            if input_cost is not None and input_cost < 0:
                errors.append(
                    f"Model '{model_name}' has negative input_cost_per_mtok: {input_cost}"
                )

            output_cost = model.get("output_cost_per_mtok")
            if output_cost is not None and output_cost < 0:
                errors.append(
                    f"Model '{model_name}' has negative output_cost_per_mtok: {output_cost}"
                )

            # Validate endpoint_url format if present
            endpoint_url = model.get("endpoint_url")
            if endpoint_url and not endpoint_url.startswith(("http://", "https://")):
                errors.append(
                    f"Model '{model_name}' has invalid endpoint_url '{endpoint_url}'"
                )

            # Validate is_best_for references
            is_best_for = model.get("is_best_for")
            if is_best_for:
                provider_models = {m.get("model_name", "") for m in data["provider_models"]
                                   if m.get("provider_slug") == provider}
                for role, target_name in is_best_for.items():
                    if target_name not in provider_models:
                        errors.append(
                            f"Model '{model_name}' best_for['{role}']='{target_name}' "
                            f"does not exist in provider '{provider}'"
                        )

    return errors


def load_provider_models_catalog(path: str | Path) -> dict[str, Any]:
    """
    Load a provider models JSON catalog from the given path.

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


def validate_provider_models_file(path: str | Path) -> list[str]:
    """
    Load and validate a provider models JSON catalog file.

    Returns a list of error messages (empty if valid).
    """
    data = load_provider_models_catalog(path)
    return validate_provider_models(data)


class ProviderModelCatalog:
    """
    Represents a validated provider model catalog.

    Provides convenient access to model data.
    """

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data
        self._by_provider: dict[str, list[dict[str, Any]]] = {}
        self._all_models: list[dict[str, Any]] = []
        self._load_models()

    def _load_models(self) -> None:
        """Index models by provider."""
        for model in self._data.get("provider_models", []):
            provider = model.get("provider_slug", "")
            self._all_models.append(model)
            if provider:
                if provider not in self._by_provider:
                    self._by_provider[provider] = []
                self._by_provider[provider].append(model)

    @property
    def version(self) -> str | None:
        """Return the catalog version."""
        return self._data.get("version")

    @property
    def provider_slugs(self) -> list[str]:
        """Return sorted list of provider slugs."""
        return sorted(self._by_provider.keys())

    def get_models_by_provider(self, provider_slug: str) -> list[dict[str, Any]]:
        """Get all models for a provider."""
        return list(self._by_provider.get(provider_slug.lower().strip(), []))

    def get_model(self, provider_slug: str, model_name: str) -> dict[str, Any] | None:
        """Get a specific model by provider and model name."""
        models = self.get_models_by_provider(provider_slug)
        for model in models:
            if model.get("model_name") == model_name:
                return model
        return None

    def list_all_models(self) -> list[dict[str, Any]]:
        """List all models in the catalog."""
        return list(self._all_models)

    def get_models_by_capability(self, capability: str) -> list[dict[str, Any]]:
        """Get all models that have the given capability."""
        return [
            m for m in self._all_models
            if capability in m.get("capabilities", [])
        ]

    def get_models_by_region(self, region: str) -> list[dict[str, Any]]:
        """Get all models available in the given region."""
        return [
            m for m in self._all_models
            if m.get("region_availability") is None
            or region in m.get("region_availability", [])
        ]

    def get_deprecated_models(self) -> list[dict[str, Any]]:
        """Get all deprecated models."""
        return [m for m in self._all_models if m.get("is_deprecated", False)]

    def validate(self) -> list[str]:
        """Validate the catalog and return error messages."""
        return validate_provider_models(self._data)

    @classmethod
    def from_file(cls, path: str | Path) -> "ProviderModelCatalog":
        """Load a catalog from a JSON file."""
        data = load_provider_models_catalog(path)
        errors = validate_provider_models(data)
        if errors:
            raise ProviderModelCatalogError(
                f"Catalog validation failed: " + "; ".join(errors)
            )
        return cls(data)

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "ProviderModelCatalog":
        """Create a catalog from a dict, validating it."""
        errors = validate_provider_models(data)
        if errors:
            raise ProviderModelCatalogError(
                f"Catalog validation failed: " + "; ".join(errors)
            )
        return cls(data)

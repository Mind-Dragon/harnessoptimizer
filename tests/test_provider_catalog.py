"""
Tests for the provider endpoint and model catalog schemas and loaders.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermesoptimizer.schemas import (
    ProviderEndpointCatalog,
    ProviderModelCatalog,
    ProviderModelCatalogError,
    validate_provider_endpoints,
    validate_provider_models,
)
from hermesoptimizer.schemas.provider_endpoint import (
    SCHEMA_PATH as ENDPOINT_SCHEMA_PATH,
    SCHEMA_URL as ENDPOINT_SCHEMA_URL,
    get_schema as get_endpoint_schema,
    get_schema_path as get_endpoint_schema_path,
    get_schema_url as get_endpoint_schema_url,
    load_provider_endpoints_catalog,
    validate_provider_endpoints_file,
)
from hermesoptimizer.schemas.provider_model import (
    SCHEMA_PATH as MODEL_SCHEMA_PATH,
    SCHEMA_URL as MODEL_SCHEMA_URL,
    get_schema as get_model_schema,
    get_schema_path as get_model_schema_path,
    get_schema_url as get_model_schema_url,
    load_provider_models_catalog,
    validate_provider_models_file,
)


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------

@pytest.fixture
def fixtures_dir() -> Path:
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def provider_endpoints_fixture(fixtures_dir: Path) -> Path:
    """Return path to provider endpoints fixture."""
    return fixtures_dir / "provider_endpoints.json"


@pytest.fixture
def provider_models_fixture(fixtures_dir: Path) -> Path:
    """Return path to provider models fixture."""
    return fixtures_dir / "provider_models.json"


@pytest.fixture
def data_dir() -> Path:
    """Return path to data directory."""
    return Path(__file__).parent.parent / "data"


# -----------------------------------------------------------------------
# Schema Files Exist
# -----------------------------------------------------------------------

def test_endpoint_schema_file_exists() -> None:
    """Provider endpoint schema file should exist."""
    assert ENDPOINT_SCHEMA_PATH.is_file(), f"Schema not found at {ENDPOINT_SCHEMA_PATH}"


def test_model_schema_file_exists() -> None:
    """Provider model schema file should exist."""
    assert MODEL_SCHEMA_PATH.is_file(), f"Schema not found at {MODEL_SCHEMA_PATH}"


def test_endpoint_schema_loads() -> None:
    """Provider endpoint schema should load without error."""
    schema = get_endpoint_schema()
    assert isinstance(schema, dict)
    assert "$schema" in schema
    assert schema["title"] == "Provider Endpoint Catalog"


def test_model_schema_loads() -> None:
    """Provider model schema should load without error."""
    schema = get_model_schema()
    assert isinstance(schema, dict)
    assert "$schema" in schema
    assert schema["title"] == "Provider Model Catalog"


# -----------------------------------------------------------------------
# Schema Path and URL
# -----------------------------------------------------------------------

def test_endpoint_schema_path() -> None:
    """Endpoint schema path should be correct."""
    assert str(ENDPOINT_SCHEMA_PATH).endswith("provider_endpoint.schema.json")


def test_model_schema_path() -> None:
    """Model schema path should be correct."""
    assert str(MODEL_SCHEMA_PATH).endswith("provider_model.schema.json")


def test_endpoint_schema_url() -> None:
    """Endpoint schema URL should be set."""
    assert ENDPOINT_SCHEMA_URL.startswith("https://")


def test_model_schema_url() -> None:
    """Model schema URL should be set."""
    assert MODEL_SCHEMA_URL.startswith("https://")


# -----------------------------------------------------------------------
# Fixture Files Exist and Are Valid JSON
# -----------------------------------------------------------------------

def test_provider_endpoints_fixture_exists(provider_endpoints_fixture: Path) -> None:
    """Provider endpoints fixture should exist."""
    assert provider_endpoints_fixture.is_file(), f"Fixture not found at {provider_endpoints_fixture}"


def test_provider_models_fixture_exists(provider_models_fixture: Path) -> None:
    """Provider models fixture should exist."""
    assert provider_models_fixture.is_file(), f"Fixture not found at {provider_models_fixture}"


def test_provider_endpoints_fixture_valid_json(provider_endpoints_fixture: Path) -> None:
    """Provider endpoints fixture should be valid JSON."""
    with open(provider_endpoints_fixture, "r") as f:
        data = json.load(f)
    assert isinstance(data, dict)


def test_provider_models_fixture_valid_json(provider_models_fixture: Path) -> None:
    """Provider models fixture should be valid JSON."""
    with open(provider_models_fixture, "r") as f:
        data = json.load(f)
    assert isinstance(data, dict)


# -----------------------------------------------------------------------
# Schema Validation - Provider Endpoints
# -----------------------------------------------------------------------

def test_validate_valid_provider_endpoints(provider_endpoints_fixture: Path) -> None:
    """Valid provider endpoints should pass validation."""
    data = load_provider_endpoints_catalog(provider_endpoints_fixture)
    errors = validate_provider_endpoints(data)
    assert errors == [], f"Expected no errors, got: {errors}"


def test_validate_valid_provider_endpoints_file(provider_endpoints_fixture: Path) -> None:
    """validate_provider_endpoints_file should return empty list for valid file."""
    errors = validate_provider_endpoints_file(provider_endpoints_fixture)
    assert errors == [], f"Expected no errors, got: {errors}"


def test_provider_endpoints_schema_requires_version() -> None:
    """Schema should require version field."""
    data = {"provider_endpoints": []}
    errors = validate_provider_endpoints(data)
    assert len(errors) > 0, "Expected validation error for missing version"


def test_provider_endpoints_schema_requires_provider_endpoints() -> None:
    """Schema should require provider_endpoints field."""
    data = {"version": "1.0.0"}
    errors = validate_provider_endpoints(data)
    assert len(errors) > 0, "Expected validation error for missing provider_endpoints"


def test_provider_endpoints_requires_valid_slug() -> None:
    """Provider slug should match pattern [a-z][a-z0-9_-]*."""
    data = {
        "version": "1.0.0",
        "provider_endpoints": [
            {
                "provider_slug": "InvalidSlug",  # uppercase not allowed
                "provider_name": "Test",
                "endpoints": []
            }
        ]
    }
    errors = validate_provider_endpoints(data)
    assert len(errors) > 0, "Expected validation error for invalid slug"


# -----------------------------------------------------------------------
# Schema Validation - Provider Models
# -----------------------------------------------------------------------

def test_validate_valid_provider_models(provider_models_fixture: Path) -> None:
    """Valid provider models should pass validation."""
    data = load_provider_models_catalog(provider_models_fixture)
    errors = validate_provider_models(data)
    assert errors == [], f"Expected no errors, got: {errors}"


def test_validate_valid_provider_models_file(provider_models_fixture: Path) -> None:
    """validate_provider_models_file should return empty list for valid file."""
    errors = validate_provider_models_file(provider_models_fixture)
    assert errors == [], f"Expected no errors, got: {errors}"


def test_provider_models_schema_requires_version() -> None:
    """Schema should require version field."""
    data = {"provider_models": []}
    errors = validate_provider_models(data)
    assert len(errors) > 0, "Expected validation error for missing version"


def test_provider_models_schema_requires_provider_models() -> None:
    """Schema should require provider_models field."""
    data = {"version": "1.0.0"}
    errors = validate_provider_models(data)
    assert len(errors) > 0, "Expected validation error for missing provider_models"


def test_provider_models_requires_capabilities() -> None:
    """Model entry should require capabilities array."""
    data = {
        "version": "1.0.0",
        "provider_models": [
            {
                "provider_slug": "test",
                "model_name": "test-model",
                "display_name": "Test",
                "capabilities": [],  # empty not allowed
                "context_window": 8000
            }
        ]
    }
    errors = validate_provider_models(data)
    assert len(errors) > 0, "Expected validation error for empty capabilities"


# -----------------------------------------------------------------------
# ProviderEndpointCatalog Class
# -----------------------------------------------------------------------

def test_provider_endpoint_catalog_from_file(provider_endpoints_fixture: Path) -> None:
    """ProviderEndpointCatalog should load from file."""
    catalog = ProviderEndpointCatalog.from_file(provider_endpoints_fixture)
    assert catalog.version == "1.0.0"
    assert "testprovider" in catalog.provider_slugs
    assert "anotherprovider" in catalog.provider_slugs


def test_provider_endpoint_catalog_get_provider(provider_endpoints_fixture: Path) -> None:
    """Catalog should get provider by slug."""
    catalog = ProviderEndpointCatalog.from_file(provider_endpoints_fixture)
    provider = catalog.get_provider("testprovider")
    assert provider is not None
    assert provider["provider_name"] == "Test Provider"


def test_provider_endpoint_catalog_list_endpoints(provider_endpoints_fixture: Path) -> None:
    """Catalog should list endpoint families for a provider."""
    catalog = ProviderEndpointCatalog.from_file(provider_endpoints_fixture)
    families = catalog.list_endpoint_families("testprovider")
    assert len(families) == 1
    assert families[0]["family_name"] == "Test API"


def test_provider_endpoint_catalog_get_default_endpoint(provider_endpoints_fixture: Path) -> None:
    """Catalog should get default endpoint family."""
    catalog = ProviderEndpointCatalog.from_file(provider_endpoints_fixture)
    endpoint = catalog.get_default_endpoint("testprovider")
    assert endpoint is not None
    assert endpoint["is_default"] is True


def test_provider_endpoint_catalog_validate(provider_endpoints_fixture: Path) -> None:
    """Catalog validate() should return errors."""
    catalog = ProviderEndpointCatalog.from_file(provider_endpoints_fixture)
    errors = catalog.validate()
    assert errors == []


# -----------------------------------------------------------------------
# ProviderModelCatalog Class
# -----------------------------------------------------------------------

def test_provider_model_catalog_from_file(provider_models_fixture: Path) -> None:
    """ProviderModelCatalog should load from file."""
    catalog = ProviderModelCatalog.from_file(provider_models_fixture)
    assert catalog.version == "1.0.0"
    assert "testprovider" in catalog.provider_slugs
    assert "anotherprovider" in catalog.provider_slugs


def test_provider_model_catalog_get_models_by_provider(provider_models_fixture: Path) -> None:
    """Catalog should get models by provider."""
    catalog = ProviderModelCatalog.from_file(provider_models_fixture)
    models = catalog.get_models_by_provider("testprovider")
    assert len(models) == 2
    names = [m["model_name"] for m in models]
    assert "test-model-1" in names
    assert "test-model-deprecated" in names


def test_provider_model_catalog_get_model(provider_models_fixture: Path) -> None:
    """Catalog should get specific model."""
    catalog = ProviderModelCatalog.from_file(provider_models_fixture)
    model = catalog.get_model("testprovider", "test-model-1")
    assert model is not None
    assert model["display_name"] == "Test Model 1"


def test_provider_model_catalog_get_models_by_capability(provider_models_fixture: Path) -> None:
    """Catalog should filter models by capability."""
    catalog = ProviderModelCatalog.from_file(provider_models_fixture)
    vision_models = catalog.get_models_by_capability("vision")
    assert len(vision_models) >= 1
    assert all("vision" in m.get("capabilities", []) for m in vision_models)


def test_provider_model_catalog_get_deprecated_models(provider_models_fixture: Path) -> None:
    """Catalog should return deprecated models."""
    catalog = ProviderModelCatalog.from_file(provider_models_fixture)
    deprecated = catalog.get_deprecated_models()
    assert len(deprecated) >= 1
    assert all(m.get("is_deprecated", False) for m in deprecated)


def test_provider_model_catalog_validate(provider_models_fixture: Path) -> None:
    """Catalog validate() should return errors."""
    catalog = ProviderModelCatalog.from_file(provider_models_fixture)
    errors = catalog.validate()
    assert errors == []


# -----------------------------------------------------------------------
# Catalog Validation Errors
# -----------------------------------------------------------------------

def test_duplicate_provider_slug_raises() -> None:
    """Duplicate provider slugs should be caught."""
    data = {
        "version": "1.0.0",
        "provider_endpoints": [
            {
                "provider_slug": "same",
                "provider_name": "First",
                "endpoints": []
            },
            {
                "provider_slug": "same",
                "provider_name": "Second",
                "endpoints": []
            }
        ]
    }
    errors = validate_provider_endpoints(data)
    assert any("Duplicate" in e for e in errors), f"Expected duplicate error, got: {errors}"


def test_multiple_default_endpoints_raises() -> None:
    """Multiple default endpoint families should be caught."""
    data = {
        "version": "1.0.0",
        "provider_endpoints": [
            {
                "provider_slug": "test",
                "provider_name": "Test",
                "endpoints": [
                    {"base_url": "https://a.example.com", "api_style": "rest",
                     "auth_header_shape": "Bearer <token>", "models_path": "/models",
                     "is_default": True},
                    {"base_url": "https://b.example.com", "api_style": "rest",
                     "auth_header_shape": "Bearer <token>", "models_path": "/models",
                     "is_default": True}
                ]
            }
        ]
    }
    errors = validate_provider_endpoints(data)
    assert any("multiple default" in e for e in errors), f"Expected multiple default error, got: {errors}"


def test_invalid_base_url_raises() -> None:
    """Invalid base_url should be caught."""
    data = {
        "version": "1.0.0",
        "provider_endpoints": [
            {
                "provider_slug": "test",
                "provider_name": "Test",
                "endpoints": [
                    {"base_url": "ftp://invalid.example.com", "api_style": "rest",
                     "auth_header_shape": "Bearer <token>", "models_path": "/models"}
                ]
            }
        ]
    }
    errors = validate_provider_endpoints(data)
    assert len(errors) > 0, f"Expected error for invalid base_url, got: {errors}"


def test_duplicate_model_name_raises() -> None:
    """Duplicate model names for same provider should be caught."""
    data = {
        "version": "1.0.0",
        "provider_models": [
            {
                "provider_slug": "test",
                "model_name": "dup-model",
                "display_name": "Dup",
                "capabilities": ["text"],
                "context_window": 8000
            },
            {
                "provider_slug": "test",
                "model_name": "dup-model",
                "display_name": "Dup 2",
                "capabilities": ["text"],
                "context_window": 8000
            }
        ]
    }
    errors = validate_provider_models(data)
    assert any("Duplicate" in e for e in errors), f"Expected duplicate error, got: {errors}"


def test_text_capable_model_zero_context_raises() -> None:
    """Text-capable model with context_window=0 should be caught."""
    data = {
        "version": "1.0.0",
        "provider_models": [
            {
                "provider_slug": "test",
                "model_name": "bad-model",
                "display_name": "Bad",
                "capabilities": ["text"],
                "context_window": 0
            }
        ]
    }
    errors = validate_provider_models(data)
    assert any("context_window" in e.lower() for e in errors), f"Expected context_window error, got: {errors}"


# -----------------------------------------------------------------------
# Load Errors
# -----------------------------------------------------------------------

def test_load_invalid_json_raises() -> None:
    """Loading invalid JSON should raise ProviderModelCatalogError."""
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("{ invalid json }")
        path = f.name

    try:
        with pytest.raises(ProviderModelCatalogError) as exc_info:
            load_provider_endpoints_catalog(path)
        assert "Invalid JSON" in str(exc_info.value)
    finally:
        Path(path).unlink(missing_ok=True)


def test_load_nonexistent_file_raises() -> None:
    """Loading nonexistent file should raise ProviderModelCatalogError."""
    with pytest.raises(ProviderModelCatalogError) as exc_info:
        load_provider_endpoints_catalog("/nonexistent/path/to/file.json")
    assert "Cannot read" in str(exc_info.value)


# -----------------------------------------------------------------------
# Data Catalog Files
# -----------------------------------------------------------------------

def test_data_provider_endpoints_exists(data_dir: Path) -> None:
    """Data provider_endpoints.json should exist."""
    path = data_dir / "provider_endpoints.json"
    assert path.is_file(), f"Data file not found at {path}"


def test_data_provider_models_exists(data_dir: Path) -> None:
    """Data provider_models.json should exist."""
    path = data_dir / "provider_models.json"
    assert path.is_file(), f"Data file not found at {path}"


def test_data_provider_endpoints_valid(data_dir: Path) -> None:
    """Data provider_endpoints.json should be valid."""
    path = data_dir / "provider_endpoints.json"
    errors = validate_provider_endpoints_file(path)
    assert errors == [], f"Data catalog has errors: {errors}"


def test_data_provider_models_valid(data_dir: Path) -> None:
    """Data provider_models.json should be valid."""
    path = data_dir / "provider_models.json"
    errors = validate_provider_models_file(path)
    assert errors == [], f"Data catalog has errors: {errors}"

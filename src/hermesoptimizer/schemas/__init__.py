"""
Hermes Optimizer Schemas Package.

Provides JSON schemas and loaders for provider endpoint and model catalogs.
"""
from __future__ import annotations

from hermesoptimizer.schemas.exceptions import ProviderModelCatalogError, SchemaError
from hermesoptimizer.schemas.provider_endpoint import (
    ProviderEndpointCatalog,
    get_schema as get_endpoint_schema,
    get_schema_path as get_endpoint_schema_path,
    get_schema_url as get_endpoint_schema_url,
    load_schema as load_endpoint_schema,
    validate_provider_endpoints,
    validate_provider_endpoints_file,
)
from hermesoptimizer.schemas.provider_model import (
    ProviderModelCatalog,
    get_schema as get_model_schema,
    get_schema_path as get_model_schema_path,
    get_schema_url as get_model_schema_url,
    load_schema as load_model_schema,
    validate_provider_models,
    validate_provider_models_file,
)
from hermesoptimizer.schemas.provider_model_refresh import (
    BlockedSource,
    BlockedSourceReason,
    ManualMetadata,
    ModelRefreshResult,
    ModelSourceProvenance,
    ProviderModelRefreshPipeline,
    RefreshStatus,
    merge_with_manual_metadata,
)

__all__ = [
    # Exceptions
    "ProviderModelCatalogError",
    "SchemaError",
    # Provider Endpoint
    "ProviderEndpointCatalog",
    "get_endpoint_schema",
    "get_endpoint_schema_path",
    "get_endpoint_schema_url",
    "load_endpoint_schema",
    "validate_provider_endpoints",
    "validate_provider_endpoints_file",
    # Provider Model
    "ProviderModelCatalog",
    "get_model_schema",
    "get_model_schema_path",
    "get_model_schema_url",
    "load_model_schema",
    "validate_provider_models",
    "validate_provider_models_file",
    # Provider Model Refresh
    "BlockedSource",
    "BlockedSourceReason",
    "ManualMetadata",
    "ModelRefreshResult",
    "ModelSourceProvenance",
    "ProviderModelRefreshPipeline",
    "RefreshStatus",
    "merge_with_manual_metadata",
]

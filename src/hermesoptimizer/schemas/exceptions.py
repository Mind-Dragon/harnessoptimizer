"""
Shared exceptions for Hermes Optimizer schemas package.
"""
from __future__ import annotations


class ProviderModelCatalogError(ValueError):
    """Raised when a provider catalog operation fails validation or loading."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class SchemaError(ValueError):
    """Raised when a schema operation fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

"""Vault provider backends for live status checks and rotation.

This module provides two types of providers:

StatusProviders (validation):
- HTTPStatusProvider: Generic HTTP-based status checks
- AWSProvider: AWS STS-based credential validation
- GCPProvider: GCP OAuth token validation
- AzureProvider: Azure AD token validation

RotationAdapters (rotation execution):
- StubRotationAdapter: Minimal adapter for testing and demonstration
- EnvFileRotationAdapter: Adapter for .env file credential rotation

All network operations are designed to be mocked in tests - no real API
calls are made during test execution.
"""
from __future__ import annotations

from .http import (
    AWSProvider,
    AzureProvider,
    GCPProvider,
    HTTPStatusProvider,
)
from .rotation import (
    EnvFileRotationAdapter,
    NoOpRotationAdapter,
    RotationAdapter,
    StubRotationAdapter,
)

__all__ = [
    "AWSProvider",
    "AzureProvider",
    "EnvFileRotationAdapter",
    "GCPProvider",
    "HTTPStatusProvider",
    "NoOpRotationAdapter",
    "RotationAdapter",
    "StubRotationAdapter",
]

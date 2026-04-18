"""Vault provider backends for live status checks and rotation.

This module provides two types of providers:

StatusProviders (validation):
- HTTPStatusProvider: Generic HTTP-based status checks
- AWSProvider: AWS STS-based credential validation
- GCPProvider: GCP OAuth token validation
- AzureProvider: Azure AD token validation

RotationAdapters (rotation execution):
- StubRotationAdapter: Minimal adapter for testing and demonstration
- EnvFileRotationAdapter: Adapter for .env file credential rotation with atomic writes
- VaultFileRotationAdapter: Adapter for vault-native encrypted storage

Backup management:
- clean_old_backups: Delete backup files older than max_age_days
- find_backup_files: Find all backup files in the vault root

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
    VaultFileRotationAdapter,
    clean_old_backups,
    find_backup_files,
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
    "VaultFileRotationAdapter",
    "clean_old_backups",
    "find_backup_files",
]

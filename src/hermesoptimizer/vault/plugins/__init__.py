"""Vault plugin system for hermesoptimizer.

This module exports the VaultPlugin abstract base class and three concrete implementations:
- HermesPlugin: Direct Python import of VaultSession
- OpenClawPlugin: HTTP bridge sidecar wrapping VaultSession
- OpenCodePlugin: Read-only plugin for OpenCode-compatible config generation
"""
from hermesoptimizer.vault.plugins.base import VaultPlugin
from hermesoptimizer.vault.plugins.hermes_plugin import HermesPlugin
from hermesoptimizer.vault.plugins.openclaw_plugin import OpenClawPlugin
from hermesoptimizer.vault.plugins.opencode_plugin import OpenCodePlugin

__all__ = [
    "VaultPlugin",
    "HermesPlugin",
    "OpenClawPlugin",
    "OpenCodePlugin",
]

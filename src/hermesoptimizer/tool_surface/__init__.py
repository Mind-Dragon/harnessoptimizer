"""HermesOptimizer Tool Surface IR package (v0.8.0).

This package implements the Tool Surface IR layer for describing agent-facing
tool and command surfaces. It provides the foundational schema types for:

- SurfaceKind: typed, textual, or hybrid surface classification
- RiskLevel: risk classification for execution
- HelpContract: help/usage contract description
- OutputContract: output format and overflow handling
- ToolSurface: typed tool surface description
- CommandSurface: textual/CLI command surface description

The schema layer is intentionally minimal and focused on representing
the surface characteristics needed for tool selection and audit.

Task 5 adds a hybrid read-only command layer:
- commands: Lightweight textual command interpreter for read-only inspection
- chain: Composition operators (|, &&, ||, ;) for command chaining
"""

from __future__ import annotations

from .audit import (
    BUCKET_COMPOSABILITY,
    BUCKET_DISCOVERABILITY,
    BUCKET_OBSERVABILITY,
    BUCKET_RECOVERY_QUALITY,
    BUCKET_SAFETY,
    BUCKET_TOKEN_EFFICIENCY,
    audit_surfaces,
)
from .chain import (
    AND,
    ChainResult,
    OR,
    PIPE,
    SEMICOLON,
    chain_execute,
)
from .commands import (
    CommandResult,
    execute_command,
    get_help,
    list_commands,
)
from .findings import FindingKind, ToolSurfaceFinding
from .schema import (
    CommandSurface,
    HelpContract,
    OutputContract,
    RiskLevel,
    SurfaceKind,
    ToolSurface,
)

__all__ = [
    # Schema types
    "SurfaceKind",
    "RiskLevel",
    "HelpContract",
    "OutputContract",
    "ToolSurface",
    "CommandSurface",
    # Findings
    "FindingKind",
    "ToolSurfaceFinding",
    # Audit
    "audit_surfaces",
    "BUCKET_DISCOVERABILITY",
    "BUCKET_COMPOSABILITY",
    "BUCKET_SAFETY",
    "BUCKET_OBSERVABILITY",
    "BUCKET_TOKEN_EFFICIENCY",
    "BUCKET_RECOVERY_QUALITY",
    # Commands (Task 5)
    "CommandResult",
    "execute_command",
    "get_help",
    "list_commands",
    # Chain (Task 5)
    "ChainResult",
    "chain_execute",
    "PIPE",
    "AND",
    "OR",
    "SEMICOLON",
]

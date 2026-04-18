"""Tool Surface IR schema (v0.8.0 Task 1).

This module defines the minimal shared types for describing agent-facing
tool and command surfaces:

- SurfaceKind: typed, textual, or hybrid
- RiskLevel: critical, high, medium, low
- HelpContract: describes how to get help for a surface
- OutputContract: describes output format and overflow handling
- ToolSurface: describes a typed tool surface
- CommandSurface: describes a textual/shell command surface

These types form the foundation for the Tool Surface IR layer and are
kept intentionally simple (dataclasses/enums) per the architecture guidelines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# SurfaceKind — describes the type of tool/command surface
# ---------------------------------------------------------------------------


class SurfaceKind(Enum):
    """Classification of tool/command surface types.

    - TYPED: Structured, type-safe tool with typed inputs/outputs
    - TEXTUAL: Shell/CLI-style textual interface
    - HYBRID: Mixed-mode with both typed and textual characteristics
    """

    TYPED = "typed"
    TEXTUAL = "textual"
    HYBRID = "hybrid"


# ---------------------------------------------------------------------------
# RiskLevel — describes the risk level of executing a surface
# ---------------------------------------------------------------------------


class RiskLevel(Enum):
    """Risk classification for tool/command execution.

    - CRITICAL: Destructive operations, credential mutations
    - HIGH: Significant operations with meaningful side effects
    - MEDIUM: Moderate operations with limited risk
    - LOW: Read-only or minimal-risk operations
    """

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ---------------------------------------------------------------------------
# HelpContract — describes how to get help for a surface
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HelpContract:
    """Describes the help contract for a tool or command surface.

    Attributes:
        usage: How to invoke help (e.g., "--help", "-h", "help <cmd>")
        examples: List of example invocations showing common usage patterns (None if not provided)
    """

    usage: str
    examples: Optional[list[str]] = None


# ---------------------------------------------------------------------------
# OutputContract — describes output format and overflow handling
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OutputContract:
    """Describes the output contract for a tool or command surface.

    Attributes:
        format: Output format (e.g., "json", "text", "table")
        truncated_field: Field name used to signal output truncation/overflow
    """

    format: str
    truncated_field: str = "truncated"


# ---------------------------------------------------------------------------
# ToolSurface — describes a typed tool surface
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolSurface:
    """Describes a typed tool surface in the Tool Surface IR.

    A ToolSurface represents a structured, type-safe tool that agents
    can invoke with typed inputs and receive typed outputs.

    Required fields:
        surface_name: Unique name for this surface
        command_name: Command or tool invocation name
        kind: SurfaceKind classification
        risk_level: RiskLevel for execution
        supports_help: Whether help is available
        supports_partial_discovery: Whether partial name matching works
        supports_overflow_handle: Whether overflow/truncation is signaled
        supports_binary_guard: Whether binary content is detected/guarded
        read_only: Whether this surface only reads data
        recommended_for_agent: Whether agents should use this surface

    Optional fields:
        notes: Human-readable notes about this surface (defaults to empty string)
        help_contract: Detailed help contract if supports_help is True
        output_contract: Output format contract if relevant
    """

    surface_name: str
    command_name: str
    kind: SurfaceKind
    risk_level: RiskLevel
    supports_help: bool
    supports_partial_discovery: bool
    supports_overflow_handle: bool
    supports_binary_guard: bool
    read_only: bool
    recommended_for_agent: bool
    notes: str = ""
    help_contract: Optional[HelpContract] = None
    output_contract: Optional[OutputContract] = None


# ---------------------------------------------------------------------------
# CommandSurface — describes a textual/CLI command surface
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CommandSurface:
    """Describes a textual/CLI command surface in the Tool Surface IR.

    A CommandSurface represents a shell-style command that agents invoke
    through a textual interface (e.g., bash commands, CLI tools).

    Required fields:
        surface_name: Unique name for this surface
        command_name: Command or tool invocation name
        kind: SurfaceKind classification
        risk_level: RiskLevel for execution
        supports_help: Whether help is available
        supports_partial_discovery: Whether partial name matching works
        supports_overflow_handle: Whether overflow/truncation is signaled
        supports_binary_guard: Whether binary content is detected/guarded
        read_only: Whether this surface only reads data
        recommended_for_agent: Whether agents should use this surface

    Optional fields:
        notes: Human-readable notes about this surface (defaults to empty string)
        help_contract: Detailed help contract if supports_help is True
        output_contract: Output format contract if relevant
        subcommands: List of available subcommands if applicable (None if not provided)
    """

    surface_name: str
    command_name: str
    kind: SurfaceKind
    risk_level: RiskLevel
    supports_help: bool
    supports_partial_discovery: bool
    supports_overflow_handle: bool
    supports_binary_guard: bool
    read_only: bool
    recommended_for_agent: bool
    notes: str = ""
    help_contract: Optional[HelpContract] = None
    output_contract: Optional[OutputContract] = None
    subcommands: Optional[list[str]] = None

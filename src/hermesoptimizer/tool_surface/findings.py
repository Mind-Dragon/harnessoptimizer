"""Tool Surface findings (v0.8.0 Task 3).

This module defines the structured finding types for the audit engine.
Findings are machine-usable, not prose-only judgments.

FindingKind: enum of concrete finding types
ToolSurfaceFinding: dataclass representing a single audit finding
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FindingKind(Enum):
    """Concrete finding kinds for tool surface audit.

    Each kind is a machine-usable slug, not a prose judgment.
    Format: tool-<aspect>-<specific-issue>
    """

    # Discoverability: help/subcommand usage
    TOOL_HELP_MISSING_SUBCOMMAND_USAGE = "tool-help-missing-subcommand-usage"

    # Recovery quality: error handling and next steps
    TOOL_ERROR_MISSING_NEXT_STEP = "tool-error-missing-next-step"

    # Observability: output overflow handling
    TOOL_OUTPUT_NO_OVERFLOW_PATH = "tool-output-no-overflow-path"

    # Safety: binary content routing
    TOOL_BINARY_ROUTING_WEAK = "tool-binary-routing-weak"

    # Safety: high-risk untyped mutation
    TOOL_SURFACE_HIGH_RISK_UNTYPED_MUTATION = "tool-surface-high-risk-untyped-mutation"


@dataclass(frozen=True)
class ToolSurfaceFinding:
    """A structured audit finding for a tool or command surface.

    Findings are deterministic, machine-usable representations of
    issues detected during surface audit.

    Attributes:
        surface_name: Name of the surface that generated this finding
        kind: Specific FindingKind enum variant
        bucket: Scoring bucket this finding belongs to
        message: Human-readable description of the finding

    Machine-usable: kind.value is a slug, all fields are structured.
    """

    surface_name: str
    kind: FindingKind
    bucket: str
    message: str
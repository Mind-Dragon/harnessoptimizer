"""Tool Surface audit engine (v0.8.0 Task 3).

This module provides the audit/scoring layer for tool surfaces.
It evaluates surfaces against deterministic rules and emits structured findings.

Scoring buckets:
- discoverability: How well the surface can be found and used correctly
- composability: How well the surface composes with other surfaces
- safety: How safely the surface operates
- observability: How observable the surface's output and state are
- token_efficiency: How efficiently the surface uses tokens
- recovery_quality: How well the surface supports error recovery

Design principles:
- Deterministic audit rules only (no network, no runtime probing)
- Fixture-driven and reproducible
- Machine-usable structured findings (not prose)
"""

from __future__ import annotations

from hermesoptimizer.tool_surface.findings import FindingKind, ToolSurfaceFinding
from hermesoptimizer.tool_surface.schema import CommandSurface, HelpContract, ToolSurface

# ---------------------------------------------------------------------------
# Scoring bucket constants
# ---------------------------------------------------------------------------

BUCKET_DISCOVERABILITY = "discoverability"
BUCKET_COMPOSABILITY = "composability"
BUCKET_SAFETY = "safety"
BUCKET_OBSERVABILITY = "observability"
BUCKET_TOKEN_EFFICIENCY = "token_efficiency"
BUCKET_RECOVERY_QUALITY = "recovery_quality"


# ---------------------------------------------------------------------------
# Audit rules
# ---------------------------------------------------------------------------


def _check_help_missing_subcommand_usage(
    surface: ToolSurface | CommandSurface,
) -> list[ToolSurfaceFinding]:
    """Check for tool-help-missing-subcommand-usage.

    CommandSurface with subcommands but HelpContract.examples is None
    or does not include any subcommand usage patterns.
    """
    findings = []

    # Only applies to CommandSurface with subcommands
    if not isinstance(surface, CommandSurface):
        return findings

    if surface.subcommands is None or len(surface.subcommands) == 0:
        return findings

    # Check if help contract has examples showing subcommand usage
    if surface.help_contract is None:
        findings.append(
            ToolSurfaceFinding(
                surface_name=surface.surface_name,
                kind=FindingKind.TOOL_HELP_MISSING_SUBCOMMAND_USAGE,
                bucket=BUCKET_DISCOVERABILITY,
                message="Command has subcommands but no help examples showing their usage",
            )
        )
        return findings

    examples = surface.help_contract.examples
    if examples is None or len(examples) == 0:
        findings.append(
            ToolSurfaceFinding(
                surface_name=surface.surface_name,
                kind=FindingKind.TOOL_HELP_MISSING_SUBCOMMAND_USAGE,
                bucket=BUCKET_DISCOVERABILITY,
                message="Command has subcommands but help examples are missing or empty",
            )
        )
        return findings

    # Check if any example contains a subcommand reference
    subcommand_mentioned = False
    for example in examples:
        for subcmd in surface.subcommands:
            if subcmd in example:
                subcommand_mentioned = True
                break
        if subcommand_mentioned:
            break

    if not subcommand_mentioned:
        findings.append(
            ToolSurfaceFinding(
                surface_name=surface.surface_name,
                kind=FindingKind.TOOL_HELP_MISSING_SUBCOMMAND_USAGE,
                bucket=BUCKET_DISCOVERABILITY,
                message="Command has subcommands but help examples do not show subcommand usage",
            )
        )

    return findings


def _check_error_missing_next_step(
    surface: ToolSurface | CommandSurface,
) -> list[ToolSurfaceFinding]:
    """Check for tool-error-missing-next-step.

    Surface that has supports_help but no guidance on interpreting
    error output or recovering from failures. Checks both notes and
    HelpContract.examples for recovery-related guidance.
    """
    findings = []

    # Only check if surface claims to support help
    if not surface.supports_help:
        return findings

    # Check notes for recovery keywords
    notes_lower = (surface.notes or "").lower()
    has_recovery_in_notes = any(
        keyword in notes_lower
        for keyword in [
            "error",
            "recovery",
            "fallback",
            "retry",
            "next step",
            "on failure",
        ]
    )

    # Also check help_contract.examples for recovery guidance
    has_recovery_in_examples = False
    if surface.help_contract is not None and surface.help_contract.examples:
        for example in surface.help_contract.examples:
            example_lower = example.lower()
            if any(
                keyword in example_lower
                for keyword in [
                    "error",
                    "recovery",
                    "fallback",
                    "retry",
                    "next step",
                    "on failure",
                ]
            ):
                has_recovery_in_examples = True
                break

    has_recovery_keywords = has_recovery_in_notes or has_recovery_in_examples

    if not has_recovery_keywords and surface.risk_level.value in ("high", "critical"):
        findings.append(
            ToolSurfaceFinding(
                surface_name=surface.surface_name,
                kind=FindingKind.TOOL_ERROR_MISSING_NEXT_STEP,
                bucket=BUCKET_RECOVERY_QUALITY,
                message="High-risk surface has no error recovery guidance",
            )
        )

    return findings


def _check_output_no_overflow_path(
    surface: ToolSurface | CommandSurface,
) -> list[ToolSurfaceFinding]:
    """Check for tool-output-no-overflow-path.

    Surface that produces structured output but does not signal
    when output is truncated or provide an overflow path.
    """
    findings = []

    # Check if surface has output but no overflow handling
    if isinstance(surface, ToolSurface) and surface.output_contract is not None:
        if not surface.supports_overflow_handle:
            findings.append(
                ToolSurfaceFinding(
                    surface_name=surface.surface_name,
                    kind=FindingKind.TOOL_OUTPUT_NO_OVERFLOW_PATH,
                    bucket=BUCKET_OBSERVABILITY,
                    message="Surface has structured output but no overflow/truncation handling",
                )
            )
    elif isinstance(surface, CommandSurface):
        # Command surfaces that plausibly produce large/paginated output
        # should have overflow handling
        if not surface.supports_overflow_handle:
            # Check if surface plausibly produces output
            # Either has output_contract or surface_name suggests output production
            has_output_contract = surface.output_contract is not None
            name_suggests_output = any(
                keyword in surface.surface_name.lower()
                for keyword in ["log", "output", "view", "display", "print",
                               "list", "show", "get", "query", "cat", "fetch"]
            )
            if has_output_contract or name_suggests_output:
                findings.append(
                    ToolSurfaceFinding(
                        surface_name=surface.surface_name,
                        kind=FindingKind.TOOL_OUTPUT_NO_OVERFLOW_PATH,
                        bucket=BUCKET_OBSERVABILITY,
                        message="Command surface has no overflow handling for output",
                    )
                )

    return findings


def _check_binary_routing_weak(
    surface: ToolSurface | CommandSurface,
) -> list[ToolSurfaceFinding]:
    """Check for tool-binary-routing-weak.

    Surface that likely handles binary data but does not have
    binary content detection/guarding.
    """
    findings = []

    # Surfaces with binary-related keywords in notes that indicate actual handling
    # Exclude "no file" or "no binary" patterns (negative references)
    notes_lower = (surface.notes or "").lower()

    # Skip if notes explicitly deny binary handling
    if "no file" in notes_lower or "no binary" in notes_lower:
        return findings

    binary_keywords = [
        "binary",
        "file",
        "image",
        "audio",
        "video",
        "document",
        "pdf",
        "archive",
        "download",
        "upload",
        "export",
        "write",
    ]

    has_binary_context = any(keyword in notes_lower for keyword in binary_keywords)

    # Only flag if surface has meaningful risk (not read-only low-risk)
    # and lacks binary guard
    if has_binary_context and not surface.supports_binary_guard:
        # Low-risk read-only surfaces are less concerning
        if surface.read_only and surface.risk_level.value == "low":
            return findings

        findings.append(
            ToolSurfaceFinding(
                surface_name=surface.surface_name,
                kind=FindingKind.TOOL_BINARY_ROUTING_WEAK,
                bucket=BUCKET_SAFETY,
                message="Surface handles binary data but lacks binary content guard",
            )
        )

    return findings


def _check_high_risk_untyped_mutation(
    surface: ToolSurface | CommandSurface,
) -> list[ToolSurfaceFinding]:
    """Check for tool-surface-high-risk-untyped-mutation.

    Surface that is HIGH/CRITICAL risk, not read-only, but uses
    TEXTUAL/HYBRID kind (untyped mutation) - dangerous combination.
    """
    findings = []

    # Only applies to non-read-only surfaces
    if surface.read_only:
        return findings

    # Only applies to high/critical risk
    if surface.risk_level.value not in ("high", "critical"):
        return findings

    # TEXTUAL/HYBRID is untyped - dangerous for high-risk mutations
    if surface.kind.value in ("textual", "hybrid"):
        findings.append(
            ToolSurfaceFinding(
                surface_name=surface.surface_name,
                kind=FindingKind.TOOL_SURFACE_HIGH_RISK_UNTYPED_MUTATION,
                bucket=BUCKET_SAFETY,
                message="High-risk surface uses untyped interface for mutation",
            )
        )

    return findings


# ---------------------------------------------------------------------------
# Main audit function
# ---------------------------------------------------------------------------


def audit_surfaces(
    surfaces: list[ToolSurface | CommandSurface],
) -> list[ToolSurfaceFinding]:
    """Audit a list of tool/command surfaces and return structured findings.

    This function applies all deterministic audit rules to each surface
    and returns a list of findings. The results are completely deterministic
    based on the input surfaces.

    Args:
        surfaces: List of ToolSurface or CommandSurface instances to audit

    Returns:
        List of ToolSurfaceFinding instances, one per issue detected.
        Empty list if no issues found.
    """
    all_findings: list[ToolSurfaceFinding] = []

    for surface in surfaces:
        # Check each audit rule
        all_findings.extend(_check_help_missing_subcommand_usage(surface))
        all_findings.extend(_check_error_missing_next_step(surface))
        all_findings.extend(_check_output_no_overflow_path(surface))
        all_findings.extend(_check_binary_routing_weak(surface))
        all_findings.extend(_check_high_risk_untyped_mutation(surface))

    return all_findings
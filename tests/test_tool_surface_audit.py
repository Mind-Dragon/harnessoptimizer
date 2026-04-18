"""Tests for Tool Surface audit engine (v0.8.0 Task 3).

This module tests the audit/scoring layer built on top of the Tool Surface IR.
The audit engine evaluates surfaces for:
- Scoring buckets: discoverability, composability, safety, observability,
  token_efficiency, recovery_quality
- Concrete finding kinds (machine-usable, not prose-only):
  - tool-help-missing-subcommand-usage
  - tool-error-missing-next-step
  - tool-output-no-overflow-path
  - tool-binary-routing-weak
  - tool-surface-high-risk-untyped-mutation

Design principles:
- Deterministic audit rules only
- No network access, no runtime probing
- Machine-usable structured findings
"""

from __future__ import annotations

import pytest

from hermesoptimizer.tool_surface.schema import (
    CommandSurface,
    HelpContract,
    OutputContract,
    RiskLevel,
    SurfaceKind,
    ToolSurface,
)


class TestFindingKindExists:
    """FindingKind enum must exist with all required finding kinds."""

    def test_finding_kind_enum_exists(self) -> None:
        """FindingKind must be importable from tool_surface.findings."""
        from hermesoptimizer.tool_surface.findings import FindingKind

        assert FindingKind is not None

    def test_finding_kind_has_tool_help_missing_subcommand_usage(self) -> None:
        """FindingKind must have tool-help-missing-subcommand-usage variant."""
        from hermesoptimizer.tool_surface.findings import FindingKind

        assert hasattr(FindingKind, "TOOL_HELP_MISSING_SUBCOMMAND_USAGE")
        assert FindingKind.TOOL_HELP_MISSING_SUBCOMMAND_USAGE.value == "tool-help-missing-subcommand-usage"

    def test_finding_kind_has_tool_error_missing_next_step(self) -> None:
        """FindingKind must have tool-error-missing-next-step variant."""
        from hermesoptimizer.tool_surface.findings import FindingKind

        assert hasattr(FindingKind, "TOOL_ERROR_MISSING_NEXT_STEP")
        assert FindingKind.TOOL_ERROR_MISSING_NEXT_STEP.value == "tool-error-missing-next-step"

    def test_finding_kind_has_tool_output_no_overflow_path(self) -> None:
        """FindingKind must have tool-output-no-overflow-path variant."""
        from hermesoptimizer.tool_surface.findings import FindingKind

        assert hasattr(FindingKind, "TOOL_OUTPUT_NO_OVERFLOW_PATH")
        assert FindingKind.TOOL_OUTPUT_NO_OVERFLOW_PATH.value == "tool-output-no-overflow-path"

    def test_finding_kind_has_tool_binary_routing_weak(self) -> None:
        """FindingKind must have tool-binary-routing-weak variant."""
        from hermesoptimizer.tool_surface.findings import FindingKind

        assert hasattr(FindingKind, "TOOL_BINARY_ROUTING_WEAK")
        assert FindingKind.TOOL_BINARY_ROUTING_WEAK.value == "tool-binary-routing-weak"

    def test_finding_kind_has_tool_surface_high_risk_untyped_mutation(self) -> None:
        """FindingKind must have tool-surface-high-risk-untyped-mutation variant."""
        from hermesoptimizer.tool_surface.findings import FindingKind

        assert hasattr(FindingKind, "TOOL_SURFACE_HIGH_RISK_UNTYPED_MUTATION")
        assert (
            FindingKind.TOOL_SURFACE_HIGH_RISK_UNTYPED_MUTATION.value
            == "tool-surface-high-risk-untyped-mutation"
        )


class TestToolSurfaceFinding:
    """ToolSurfaceFinding dataclass must be structured and machine-usable."""

    def test_finding_dataclass_exists(self) -> None:
        """ToolSurfaceFinding must be importable from tool_surface.findings."""
        from hermesoptimizer.tool_surface.findings import ToolSurfaceFinding

        assert ToolSurfaceFinding is not None

    def test_finding_has_surface_name(self) -> None:
        """Finding must reference the surface that generated it."""
        from hermesoptimizer.tool_surface.findings import ToolSurfaceFinding

        finding = ToolSurfaceFinding(
            surface_name="test_surface",
            kind=None,  # type: ignore[arg-type]
            bucket="test",
            message="test",
        )
        assert finding.surface_name == "test_surface"

    def test_finding_has_kind(self) -> None:
        """Finding must have a FindingKind."""
        from hermesoptimizer.tool_surface.findings import FindingKind, ToolSurfaceFinding

        finding = ToolSurfaceFinding(
            surface_name="test_surface",
            kind=FindingKind.TOOL_HELP_MISSING_SUBCOMMAND_USAGE,
            bucket="discoverability",
            message="Help is missing subcommand usage examples",
        )
        assert finding.kind == FindingKind.TOOL_HELP_MISSING_SUBCOMMAND_USAGE

    def test_finding_has_bucket(self) -> None:
        """Finding must have a scoring bucket name."""
        from hermesoptimizer.tool_surface.findings import FindingKind, ToolSurfaceFinding

        finding = ToolSurfaceFinding(
            surface_name="test_surface",
            kind=FindingKind.TOOL_HELP_MISSING_SUBCOMMAND_USAGE,
            bucket="discoverability",
            message="test",
        )
        assert finding.bucket == "discoverability"

    def test_finding_has_message(self) -> None:
        """Finding must have a human-readable message."""
        from hermesoptimizer.tool_surface.findings import FindingKind, ToolSurfaceFinding

        finding = ToolSurfaceFinding(
            surface_name="test_surface",
            kind=FindingKind.TOOL_ERROR_MISSING_NEXT_STEP,
            bucket="recovery_quality",
            message="Error output does not suggest next steps",
        )
        assert finding.message == "Error output does not suggest next steps"

    def test_finding_is_frozen(self) -> None:
        """ToolSurfaceFinding must be immutable (frozen=True) for IR stability."""
        from dataclasses import FrozenInstanceError

        from hermesoptimizer.tool_surface.findings import ToolSurfaceFinding

        finding = ToolSurfaceFinding(
            surface_name="test_surface",
            kind=None,  # type: ignore[arg-type]
            bucket="test",
            message="test",
        )
        with pytest.raises(FrozenInstanceError):
            finding.surface_name = "renamed"


class TestScoringBuckets:
    """Audit engine must define and use scoring buckets."""

    def test_discoverability_bucket_exists(self) -> None:
        """discoverability bucket must be defined in audit module."""
        from hermesoptimizer.tool_surface import audit

        assert hasattr(audit, "BUCKET_DISCOVERABILITY")
        assert audit.BUCKET_DISCOVERABILITY == "discoverability"

    def test_composability_bucket_exists(self) -> None:
        """composability bucket must be defined in audit module."""
        from hermesoptimizer.tool_surface import audit

        assert hasattr(audit, "BUCKET_COMPOSABILITY")
        assert audit.BUCKET_COMPOSABILITY == "composability"

    def test_safety_bucket_exists(self) -> None:
        """safety bucket must be defined in audit module."""
        from hermesoptimizer.tool_surface import audit

        assert hasattr(audit, "BUCKET_SAFETY")
        assert audit.BUCKET_SAFETY == "safety"

    def test_observability_bucket_exists(self) -> None:
        """observability bucket must be defined in audit module."""
        from hermesoptimizer.tool_surface import audit

        assert hasattr(audit, "BUCKET_OBSERVABILITY")
        assert audit.BUCKET_OBSERVABILITY == "observability"

    def test_token_efficiency_bucket_exists(self) -> None:
        """token_efficiency bucket must be defined in audit module."""
        from hermesoptimizer.tool_surface import audit

        assert hasattr(audit, "BUCKET_TOKEN_EFFICIENCY")
        assert audit.BUCKET_TOKEN_EFFICIENCY == "token_efficiency"

    def test_recovery_quality_bucket_exists(self) -> None:
        """recovery_quality bucket must be defined in audit module."""
        from hermesoptimizer.tool_surface import audit

        assert hasattr(audit, "BUCKET_RECOVERY_QUALITY")
        assert audit.BUCKET_RECOVERY_QUALITY == "recovery_quality"

    def test_all_buckets_defined(self) -> None:
        """All 6 scoring buckets must be defined."""
        from hermesoptimizer.tool_surface import audit

        expected_buckets = [
            "discoverability",
            "composability",
            "safety",
            "observability",
            "token_efficiency",
            "recovery_quality",
        ]
        for bucket in expected_buckets:
            assert hasattr(audit, f"BUCKET_{bucket.upper()}")


class TestAuditEngineExists:
    """Audit engine must exist and be callable."""

    def test_audit_function_exists(self) -> None:
        """audit_surfaces() function must exist in audit module."""
        from hermesoptimizer.tool_surface import audit

        assert hasattr(audit, "audit_surfaces")
        assert callable(audit.audit_surfaces)

    def test_audit_accepts_surfaces_parameter(self) -> None:
        """audit_surfaces() must accept a list of ToolSurface/CommandSurface."""
        from hermesoptimizer.tool_surface import audit

        # Should accept empty list without error
        result = audit.audit_surfaces([])
        assert isinstance(result, list)


class TestAuditResultsDeterministic:
    """Audit results must be deterministic (fixture-driven)."""

    def test_same_input_produces_same_output(self) -> None:
        """Running audit on same surfaces twice must produce identical results."""
        from hermesoptimizer.tool_surface import audit
        from hermesoptimizer.tool_surface.schema import (
            RiskLevel,
            SurfaceKind,
            ToolSurface,
        )

        surface = ToolSurface(
            surface_name="test_surface",
            command_name="test_cmd",
            kind=SurfaceKind.TYPED,
            risk_level=RiskLevel.LOW,
            supports_help=True,
            supports_partial_discovery=False,
            supports_overflow_handle=False,
            supports_binary_guard=False,
            read_only=True,
            recommended_for_agent=True,
        )

        result1 = audit.audit_surfaces([surface])
        result2 = audit.audit_surfaces([surface])

        assert result1 == result2

    def test_audit_results_are_hashable_comparable(self) -> None:
        """Audit results (findings) must be comparable for test stability."""
        from hermesoptimizer.tool_surface import audit
        from hermesoptimizer.tool_surface.schema import (
            RiskLevel,
            SurfaceKind,
            ToolSurface,
        )

        surface = ToolSurface(
            surface_name="test_surface",
            command_name="test_cmd",
            kind=SurfaceKind.TYPED,
            risk_level=RiskLevel.LOW,
            supports_help=True,
            supports_partial_discovery=False,
            supports_overflow_handle=False,
            supports_binary_guard=False,
            read_only=True,
            recommended_for_agent=True,
        )

        result = audit.audit_surfaces([surface])
        # Results should be a list of ToolSurfaceFinding
        assert isinstance(result, list)
        for finding in result:
            assert finding.surface_name is not None
            assert finding.kind is not None
            assert finding.bucket is not None
            assert finding.message is not None


class TestAuditToolHelpMissingSubcommandUsage:
    """Audit rule: tool-help-missing-subcommand-usage.

    CommandSurface with subcommands but HelpContract.examples is None
    or does not include any subcommand usage patterns.
    """

    def test_command_with_subcommands_but_no_help_examples_generates_finding(
        self,
    ) -> None:
        """CommandSurface with subcommands but no help examples triggers finding."""
        from hermesoptimizer.tool_surface import audit
        from hermesoptimizer.tool_surface.findings import FindingKind

        surface = CommandSurface(
            surface_name="test_cmd",
            command_name="test",
            kind=SurfaceKind.TEXTUAL,
            risk_level=RiskLevel.MEDIUM,
            supports_help=True,
            supports_partial_discovery=True,
            supports_overflow_handle=True,
            supports_binary_guard=False,
            read_only=False,
            recommended_for_agent=True,
            # Has subcommands but no examples in help
            help_contract=HelpContract(usage="test --help"),
            subcommands=["start", "stop", "restart"],
        )

        findings = audit.audit_surfaces([surface])

        subcommand_findings = [
            f for f in findings if f.kind == FindingKind.TOOL_HELP_MISSING_SUBCOMMAND_USAGE
        ]
        assert len(subcommand_findings) >= 1
        assert subcommand_findings[0].surface_name == "test_cmd"
        assert subcommand_findings[0].bucket == "discoverability"

    def test_command_with_subcommands_and_help_examples_no_finding(self) -> None:
        """CommandSurface with subcommands and proper help examples does not trigger."""
        from hermesoptimizer.tool_surface import audit
        from hermesoptimizer.tool_surface.findings import FindingKind

        surface = CommandSurface(
            surface_name="test_cmd",
            command_name="test",
            kind=SurfaceKind.TEXTUAL,
            risk_level=RiskLevel.MEDIUM,
            supports_help=True,
            supports_partial_discovery=True,
            supports_overflow_handle=True,
            supports_binary_guard=False,
            read_only=False,
            recommended_for_agent=True,
            # Has subcommands AND examples showing subcommand usage
            help_contract=HelpContract(
                usage="test --help",
                examples=["test start", "test stop", "test restart"],
            ),
            subcommands=["start", "stop", "restart"],
        )

        findings = audit.audit_surfaces([surface])

        subcommand_findings = [
            f for f in findings if f.kind == FindingKind.TOOL_HELP_MISSING_SUBCOMMAND_USAGE
        ]
        assert len(subcommand_findings) == 0

    def test_tool_surface_no_subcommand_finding(self) -> None:
        """ToolSurface (not CommandSurface) does not trigger subcommand finding."""
        from hermesoptimizer.tool_surface import audit
        from hermesoptimizer.tool_surface.findings import FindingKind

        surface = ToolSurface(
            surface_name="test_tool",
            command_name="test",
            kind=SurfaceKind.TYPED,
            risk_level=RiskLevel.LOW,
            supports_help=True,
            supports_partial_discovery=False,
            supports_overflow_handle=False,
            supports_binary_guard=False,
            read_only=True,
            recommended_for_agent=True,
            help_contract=HelpContract(usage="help test"),
        )

        findings = audit.audit_surfaces([surface])

        subcommand_findings = [
            f for f in findings if f.kind == FindingKind.TOOL_HELP_MISSING_SUBCOMMAND_USAGE
        ]
        assert len(subcommand_findings) == 0


class TestAuditToolErrorMissingNextStep:
    """Audit rule: tool-error-missing-next-step.

    Surface that has supports_help but the HelpContract does not include
    guidance on interpreting error output or recovering from failures.
    """

    def test_surface_without_error_recovery_guidance_generates_finding(self) -> None:
        """Surface with help but no error recovery guidance triggers finding."""
        from hermesoptimizer.tool_surface import audit
        from hermesoptimizer.tool_surface.findings import FindingKind

        surface = ToolSurface(
            surface_name="risky_tool",
            command_name="risky",
            kind=SurfaceKind.TYPED,
            risk_level=RiskLevel.HIGH,
            supports_help=True,
            supports_partial_discovery=False,
            supports_overflow_handle=False,
            supports_binary_guard=False,
            read_only=False,
            recommended_for_agent=True,
            # Has basic help but no error recovery guidance
            help_contract=HelpContract(usage="help risky_tool"),
        )

        findings = audit.audit_surfaces([surface])

        error_findings = [
            f for f in findings if f.kind == FindingKind.TOOL_ERROR_MISSING_NEXT_STEP
        ]
        assert len(error_findings) >= 1
        assert error_findings[0].surface_name == "risky_tool"
        assert error_findings[0].bucket == "recovery_quality"

    def test_surface_with_error_recovery_keyword_no_finding(self) -> None:
        """Surface with error recovery keywords in notes does not trigger."""
        from hermesoptimizer.tool_surface import audit
        from hermesoptimizer.tool_surface.findings import FindingKind

        surface = ToolSurface(
            surface_name="robust_tool",
            command_name="robust",
            kind=SurfaceKind.TYPED,
            risk_level=RiskLevel.HIGH,
            supports_help=True,
            supports_partial_discovery=False,
            supports_overflow_handle=False,
            supports_binary_guard=False,
            read_only=False,
            recommended_for_agent=True,
            # Notes mention error handling/recovery
            notes="Provides error recovery guidance and next-step suggestions on failure.",
            help_contract=HelpContract(usage="help robust_tool"),
        )

        findings = audit.audit_surfaces([surface])

        error_findings = [
            f for f in findings if f.kind == FindingKind.TOOL_ERROR_MISSING_NEXT_STEP
        ]
        assert len(error_findings) == 0


class TestAuditToolOutputNoOverflowPath:
    """Audit rule: tool-output-no-overflow-path.

    Surface that produces structured output but does not signal
    when output is truncated or provide an overflow path.
    """

    def test_surface_with_output_but_no_overflow_handle_generates_finding(
        self,
    ) -> None:
        """Surface with output but no overflow handling triggers finding."""
        from hermesoptimizer.tool_surface import audit
        from hermesoptimizer.tool_surface.findings import FindingKind

        surface = ToolSurface(
            surface_name="data_query",
            command_name="query_data",
            kind=SurfaceKind.TYPED,
            risk_level=RiskLevel.LOW,
            supports_help=True,
            supports_partial_discovery=False,
            # Output but no overflow handling
            supports_overflow_handle=False,
            supports_binary_guard=False,
            read_only=True,
            recommended_for_agent=True,
            output_contract=OutputContract(format="json"),
        )

        findings = audit.audit_surfaces([surface])

        overflow_findings = [
            f for f in findings if f.kind == FindingKind.TOOL_OUTPUT_NO_OVERFLOW_PATH
        ]
        assert len(overflow_findings) >= 1
        assert overflow_findings[0].surface_name == "data_query"
        assert overflow_findings[0].bucket == "observability"

    def test_surface_with_overflow_handle_no_finding(self) -> None:
        """Surface with overflow handling does not trigger finding."""
        from hermesoptimizer.tool_surface import audit
        from hermesoptimizer.tool_surface.findings import FindingKind

        surface = ToolSurface(
            surface_name="safe_query",
            command_name="safe_query",
            kind=SurfaceKind.TYPED,
            risk_level=RiskLevel.LOW,
            supports_help=True,
            supports_partial_discovery=False,
            # Has overflow handling
            supports_overflow_handle=True,
            supports_binary_guard=False,
            read_only=True,
            recommended_for_agent=True,
            output_contract=OutputContract(format="json", truncated_field="truncated"),
        )

        findings = audit.audit_surfaces([surface])

        overflow_findings = [
            f for f in findings if f.kind == FindingKind.TOOL_OUTPUT_NO_OVERFLOW_PATH
        ]
        assert len(overflow_findings) == 0

    def test_textual_surface_without_overflow_handle_still_finds(self) -> None:
        """CommandSurface without overflow handle also triggers finding."""
        from hermesoptimizer.tool_surface import audit
        from hermesoptimizer.tool_surface.findings import FindingKind

        surface = CommandSurface(
            surface_name="log_viewer",
            command_name="view_logs",
            kind=SurfaceKind.TEXTUAL,
            risk_level=RiskLevel.LOW,
            supports_help=True,
            supports_partial_discovery=False,
            # No overflow handling
            supports_overflow_handle=False,
            supports_binary_guard=False,
            read_only=True,
            recommended_for_agent=True,
        )

        findings = audit.audit_surfaces([surface])

        overflow_findings = [
            f for f in findings if f.kind == FindingKind.TOOL_OUTPUT_NO_OVERFLOW_PATH
        ]
        assert len(overflow_findings) >= 1


class TestAuditToolBinaryRoutingWeak:
    """Audit rule: tool-binary-routing-weak.

    Surface that handles binary data (file operations, downloads, etc.)
    but does not have binary content detection/guarding.
    """

    def test_binary_surface_without_guard_generates_finding(self) -> None:
        """Surface likely handling binary data without guard triggers finding."""
        from hermesoptimizer.tool_surface import audit
        from hermesoptimizer.tool_surface.findings import FindingKind

        # A surface that likely handles binary data (file write, report export)
        # but has no binary guard
        surface = ToolSurface(
            surface_name="file_writer",
            command_name="write_file",
            kind=SurfaceKind.TYPED,
            risk_level=RiskLevel.MEDIUM,
            supports_help=True,
            supports_partial_discovery=False,
            supports_overflow_handle=False,
            # No binary guard for a file operation
            supports_binary_guard=False,
            read_only=False,
            recommended_for_agent=True,
            notes="Writes binary file content to filesystem.",
        )

        findings = audit.audit_surfaces([surface])

        binary_findings = [
            f for f in findings if f.kind == FindingKind.TOOL_BINARY_ROUTING_WEAK
        ]
        assert len(binary_findings) >= 1
        assert binary_findings[0].surface_name == "file_writer"
        assert binary_findings[0].bucket == "safety"

    def test_binary_surface_with_guard_no_finding(self) -> None:
        """Surface with binary guard does not trigger finding."""
        from hermesoptimizer.tool_surface import audit
        from hermesoptimizer.tool_surface.findings import FindingKind

        surface = ToolSurface(
            surface_name="safe_file_writer",
            command_name="safe_write",
            kind=SurfaceKind.TYPED,
            risk_level=RiskLevel.MEDIUM,
            supports_help=True,
            supports_partial_discovery=False,
            supports_overflow_handle=False,
            # Has binary guard
            supports_binary_guard=True,
            read_only=False,
            recommended_for_agent=True,
            notes="Writes binary file content with MIME-type detection.",
        )

        findings = audit.audit_surfaces([surface])

        binary_findings = [
            f for f in findings if f.kind == FindingKind.TOOL_BINARY_ROUTING_WEAK
        ]
        assert len(binary_findings) == 0

    def test_safe_surface_without_guard_no_finding(self) -> None:
        """Safe read-only surface without binary guard does not trigger finding."""
        from hermesoptimizer.tool_surface import audit
        from hermesoptimizer.tool_surface.findings import FindingKind

        surface = ToolSurface(
            surface_name="safe_query",
            command_name="query",
            kind=SurfaceKind.TYPED,
            risk_level=RiskLevel.LOW,
            supports_help=True,
            supports_partial_discovery=False,
            supports_overflow_handle=False,
            supports_binary_guard=False,  # No guard but also no binary risk
            read_only=True,
            recommended_for_agent=True,
            notes="Read-only JSON query with no file or binary operations.",
        )

        findings = audit.audit_surfaces([surface])

        binary_findings = [
            f for f in findings if f.kind == FindingKind.TOOL_BINARY_ROUTING_WEAK
        ]
        assert len(binary_findings) == 0


class TestAuditToolSurfaceHighRiskUntypedMutation:
    """Audit rule: tool-surface-high-risk-untyped-mutation.

    Surface that is HIGH/CRITICAL risk, not read-only, but uses
    TEXTUAL/HYBRID kind (untyped mutation) - dangerous combination.
    """

    def test_high_risk_textual_mutation_generates_finding(self) -> None:
        """HIGH risk textual surface that mutates triggers finding."""
        from hermesoptimizer.tool_surface import audit
        from hermesoptimizer.tool_surface.findings import FindingKind

        surface = CommandSurface(
            surface_name="dangerous_cmd",
            command_name="dangerous",
            kind=SurfaceKind.TEXTUAL,
            risk_level=RiskLevel.HIGH,
            supports_help=True,
            supports_partial_discovery=True,
            supports_overflow_handle=False,
            supports_binary_guard=False,
            read_only=False,  # Mutating!
            recommended_for_agent=True,
        )

        findings = audit.audit_surfaces([surface])

        mutation_findings = [
            f
            for f in findings
            if f.kind == FindingKind.TOOL_SURFACE_HIGH_RISK_UNTYPED_MUTATION
        ]
        assert len(mutation_findings) >= 1
        assert mutation_findings[0].surface_name == "dangerous_cmd"
        assert mutation_findings[0].bucket == "safety"

    def test_high_risk_typed_mutation_no_finding(self) -> None:
        """HIGH risk but TYPED surface does not trigger (typed is safer)."""
        from hermesoptimizer.tool_surface import audit
        from hermesoptimizer.tool_surface.findings import FindingKind

        surface = ToolSurface(
            surface_name="typed_dangerous",
            command_name="typed_dangerous",
            kind=SurfaceKind.TYPED,  # Typed is safer
            risk_level=RiskLevel.HIGH,
            supports_help=True,
            supports_partial_discovery=False,
            supports_overflow_handle=False,
            supports_binary_guard=False,
            read_only=False,  # Mutating
            recommended_for_agent=True,
        )

        findings = audit.audit_surfaces([surface])

        mutation_findings = [
            f
            for f in findings
            if f.kind == FindingKind.TOOL_SURFACE_HIGH_RISK_UNTYPED_MUTATION
        ]
        assert len(mutation_findings) == 0

    def test_low_risk_textual_mutation_no_finding(self) -> None:
        """LOW risk textual surface does not trigger (not high risk enough)."""
        from hermesoptimizer.tool_surface import audit
        from hermesoptimizer.tool_surface.findings import FindingKind

        surface = CommandSurface(
            surface_name="safe_cmd",
            command_name="safe",
            kind=SurfaceKind.TEXTUAL,
            risk_level=RiskLevel.LOW,  # Not high risk
            supports_help=True,
            supports_partial_discovery=True,
            supports_overflow_handle=False,
            supports_binary_guard=False,
            read_only=False,
            recommended_for_agent=True,
        )

        findings = audit.audit_surfaces([surface])

        mutation_findings = [
            f
            for f in findings
            if f.kind == FindingKind.TOOL_SURFACE_HIGH_RISK_UNTYPED_MUTATION
        ]
        assert len(mutation_findings) == 0

    def test_read_only_textual_no_finding(self) -> None:
        """Read-only textual surface does not trigger (no mutation)."""
        from hermesoptimizer.tool_surface import audit
        from hermesoptimizer.tool_surface.findings import FindingKind

        surface = CommandSurface(
            surface_name="read_only_cmd",
            command_name="readonly",
            kind=SurfaceKind.TEXTUAL,
            risk_level=RiskLevel.HIGH,
            supports_help=True,
            supports_partial_discovery=True,
            supports_overflow_handle=False,
            supports_binary_guard=False,
            read_only=True,  # Read-only!
            recommended_for_agent=True,
        )

        findings = audit.audit_surfaces([surface])

        mutation_findings = [
            f
            for f in findings
            if f.kind == FindingKind.TOOL_SURFACE_HIGH_RISK_UNTYPED_MUTATION
        ]
        assert len(mutation_findings) == 0


class TestAuditOnRealRegistry:
    """Audit engine should work with real registry surfaces."""

    def test_audit_runs_on_default_registry(self) -> None:
        """audit_surfaces() should run on default registry without errors."""
        from hermesoptimizer.tool_surface import audit, registry

        surfaces_fn = getattr(
            registry, "default_surfaces", None
        ) or getattr(registry, "build_default_registry", None)
        surfaces = surfaces_fn()

        findings = audit.audit_surfaces(surfaces)

        assert isinstance(findings, list)
        # Findings should be ToolSurfaceFinding instances
        for f in findings:
            assert hasattr(f, "surface_name")
            assert hasattr(f, "kind")
            assert hasattr(f, "bucket")
            assert hasattr(f, "message")

    def test_audit_findings_have_valid_buckets(self) -> None:
        """All findings from real registry should have valid bucket names."""
        from hermesoptimizer.tool_surface import audit, registry

        surfaces_fn = getattr(
            registry, "default_surfaces", None
        ) or getattr(registry, "build_default_registry", None)
        surfaces = surfaces_fn()

        findings = audit.audit_surfaces(surfaces)

        valid_buckets = {
            "discoverability",
            "composability",
            "safety",
            "observability",
            "token_efficiency",
            "recovery_quality",
        }
        for f in findings:
            assert f.bucket in valid_buckets, (
                f"Finding on {f.surface_name} has invalid bucket: {f.bucket}"
            )

    def test_audit_findings_have_valid_kinds(self) -> None:
        """All findings from real registry should have valid FindingKind values."""
        from hermesoptimizer.tool_surface import audit, registry
        from hermesoptimizer.tool_surface.findings import FindingKind

        surfaces_fn = getattr(
            registry, "default_surfaces", None
        ) or getattr(registry, "build_default_registry", None)
        surfaces = surfaces_fn()

        findings = audit.audit_surfaces(surfaces)

        valid_kinds = {kind.value for kind in FindingKind}
        for f in findings:
            assert f.kind.value in valid_kinds, (
                f"Finding on {f.surface_name} has invalid kind: {f.kind}"
            )


class TestAuditMachineUsable:
    """Audit output must be machine-usable (structured, not prose)."""

    def test_findings_are_dataclasses(self) -> None:
        """Findings must be dataclass instances for easy field access."""
        from dataclasses import is_dataclass

        from hermesoptimizer.tool_surface import audit
        from hermesoptimizer.tool_surface.schema import (
            RiskLevel,
            SurfaceKind,
            ToolSurface,
        )

        surface = ToolSurface(
            surface_name="test",
            command_name="test",
            kind=SurfaceKind.TYPED,
            risk_level=RiskLevel.LOW,
            supports_help=False,
            supports_partial_discovery=False,
            supports_overflow_handle=False,
            supports_binary_guard=False,
            read_only=True,
            recommended_for_agent=True,
        )

        findings = audit.audit_surfaces([surface])

        for f in findings:
            assert is_dataclass(f)

    def test_findings_are_serializable(self) -> None:
        """Findings should be serializable to basic Python types."""
        import json

        from hermesoptimizer.tool_surface import audit
        from hermesoptimizer.tool_surface.schema import (
            RiskLevel,
            SurfaceKind,
            ToolSurface,
        )

        surface = ToolSurface(
            surface_name="test",
            command_name="test",
            kind=SurfaceKind.TYPED,
            risk_level=RiskLevel.LOW,
            supports_help=False,
            supports_partial_discovery=False,
            supports_overflow_handle=False,
            supports_binary_guard=False,
            read_only=True,
            recommended_for_agent=True,
        )

        findings = audit.audit_surfaces([surface])

        # Should not raise - findings should be JSON serializable
        for f in findings:
            json.dumps(
                {
                    "surface_name": f.surface_name,
                    "kind": f.kind.value,
                    "bucket": f.bucket,
                    "message": f.message,
                }
            )

    def test_no_prose_only_judgments(self) -> None:
        """Findings must have structured kinds, not prose-only judgments."""
        from hermesoptimizer.tool_surface import audit
        from hermesoptimizer.tool_surface.findings import FindingKind

        surface = CommandSurface(
            surface_name="test_cmd",
            command_name="test",
            kind=SurfaceKind.TEXTUAL,
            risk_level=RiskLevel.MEDIUM,
            supports_help=True,
            supports_partial_discovery=True,
            supports_overflow_handle=True,
            supports_binary_guard=False,
            read_only=False,
            recommended_for_agent=True,
            subcommands=["start", "stop"],
            # No examples in help - triggers finding
            help_contract=HelpContract(usage="test --help"),
        )

        findings = audit.audit_surfaces([surface])

        # All findings should have a proper FindingKind value
        for f in findings:
            assert isinstance(f.kind, FindingKind)
            # kind.value should be a slug like "tool-help-missing-subcommand-usage"
            # NOT a prose description like "This tool is hard to discover"
            assert "-" in f.kind.value or "_" in f.kind.value
            assert len(f.kind.value) < 60  # Slugs are short
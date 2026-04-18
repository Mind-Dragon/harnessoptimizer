"""Tests for Tool Surface registry (v0.8.0 Task 2).

These tests verify the tool surface registry that maps real HermesOptimizer
surfaces into the Tool Surface IR.

Target surfaces (per Task 2 spec):
1. provider/config surfaces: provider_truth, config_fix, provider_management, endpoints
2. workflow inspection surfaces: workflow/schema, workflow/store, todo_cmd, devdo_cmd
3. dreams/memory surfaces: memory_meta, decay, sweep, recall
4. report surfaces: markdown, json_export, health, issues

Success condition: registry emits 8-12 normalized entries from real HermesOptimizer surfaces.
"""

from __future__ import annotations

import pytest


class TestRegistryExists:
    """Registry module must exist and be importable."""

    def test_registry_module_importable(self) -> None:
        """Registry module must be importable from tool_surface package."""
        from hermesoptimizer.tool_surface import registry

        assert registry is not None

    def test_default_surfaces_function_exists(self) -> None:
        """default_surfaces() or build_default_registry() function must exist."""
        from hermesoptimizer.tool_surface import registry

        # Either default_surfaces or build_default_registry should exist
        has_default_surfaces = hasattr(registry, "default_surfaces")
        has_build_default = hasattr(registry, "build_default_registry")
        assert has_default_surfaces or has_build_default, (
            "registry must have default_surfaces() or build_default_registry()"
        )


class TestRegistrySurfacesCount:
    """Registry must emit 8-12 real entries per success condition."""

    def test_registry_has_8_to_12_entries(self) -> None:
        """Registry must emit between 8 and 12 normalized entries."""
        from hermesoptimizer.tool_surface import registry

        surfaces_fn = getattr(registry, "default_surfaces", None) or getattr(registry, "build_default_registry", None)
        assert surfaces_fn is not None, "No surfaces function found"

        surfaces = surfaces_fn()
        count = len(surfaces)

        assert 8 <= count <= 12, (
            f"Registry must emit 8-12 entries but got {count}. "
            f"Each family should contribute 2-3 entries."
        )


class TestRegistryFamilies:
    """Registry must cover all 4 target families."""

    def test_provider_config_family_present(self) -> None:
        """Provider/config family surfaces must be present."""
        from hermesoptimizer.tool_surface import registry

        surfaces_fn = getattr(registry, "default_surfaces", None) or getattr(registry, "build_default_registry", None)
        surfaces = surfaces_fn()

        # At least one surface should reference provider_truth, config_fix, provider_management, or endpoints
        provider_keywords = {"provider", "config", "endpoint", "truth"}
        provider_surfaces = [
            s for s in surfaces
            if any(kw in s.surface_name.lower() or kw in s.notes.lower() for kw in provider_keywords)
        ]

        assert len(provider_surfaces) >= 1, (
            f"Provider/config family must have at least 1 surface, got {len(provider_surfaces)}"
        )

    def test_provider_management_backing_source_explicitly_covered(self) -> None:
        """Provider/config family must explicitly cover verify/provider_management.py."""
        from hermesoptimizer.tool_surface import registry

        surfaces_fn = getattr(registry, "default_surfaces", None) or getattr(registry, "build_default_registry", None)
        surfaces = surfaces_fn()

        # At least one surface must explicitly reference provider_management.py as backing source
        provider_mgmt_surfaces = [
            s for s in surfaces
            if "provider_management" in s.notes.lower() and "provider_management.py" in s.notes.lower()
        ]

        assert len(provider_mgmt_surfaces) >= 1, (
            f"Provider/config family must explicitly cover verify/provider_management.py backing source. "
            f"No surface found with 'provider_management.py' in notes. "
            f"Available surfaces: {[s.surface_name for s in surfaces]}"
        )

    def test_workflow_family_present(self) -> None:
        """Workflow inspection family surfaces must be present."""
        from hermesoptimizer.tool_surface import registry

        surfaces_fn = getattr(registry, "default_surfaces", None) or getattr(registry, "build_default_registry", None)
        surfaces = surfaces_fn()

        # At least one surface should reference workflow, plan, task, or run
        workflow_keywords = {"workflow", "plan", "task", "run", "checkpoint", "blocker"}
        workflow_surfaces = [
            s for s in surfaces
            if any(kw in s.surface_name.lower() or kw in s.notes.lower() for kw in workflow_keywords)
        ]

        assert len(workflow_surfaces) >= 1, (
            f"Workflow family must have at least 1 surface, got {len(workflow_surfaces)}"
        )

    def test_dreams_memory_family_present(self) -> None:
        """Dreams/memory family surfaces must be present."""
        from hermesoptimizer.tool_surface import registry

        surfaces_fn = getattr(registry, "default_surfaces", None) or getattr(registry, "build_default_registry", None)
        surfaces = surfaces_fn()

        # At least one surface should reference memory, dream, recall, sweep, or decay
        memory_keywords = {"memory", "dream", "recall", "sweep", "decay", "reheat", "fidelity"}
        memory_surfaces = [
            s for s in surfaces
            if any(kw in s.surface_name.lower() or kw in s.notes.lower() for kw in memory_keywords)
        ]

        assert len(memory_surfaces) >= 1, (
            f"Dreams/memory family must have at least 1 surface, got {len(memory_surfaces)}"
        )

    def test_report_family_present(self) -> None:
        """Report family surfaces must be present."""
        from hermesoptimizer.tool_surface import registry

        surfaces_fn = getattr(registry, "default_surfaces", None) or getattr(registry, "build_default_registry", None)
        surfaces = surfaces_fn()

        # At least one surface should reference report, markdown, json, health, or issues
        report_keywords = {"report", "markdown", "json", "health", "issue", "finding"}
        report_surfaces = [
            s for s in surfaces
            if any(kw in s.surface_name.lower() or kw in s.notes.lower() for kw in report_keywords)
        ]

        assert len(report_surfaces) >= 1, (
            f"Report family must have at least 1 surface, got {len(report_surfaces)}"
        )

    def test_report_issues_backing_source_explicitly_covered(self) -> None:
        """Report family must explicitly cover report/issues.py."""
        from hermesoptimizer.tool_surface import registry

        surfaces_fn = getattr(registry, "default_surfaces", None) or getattr(registry, "build_default_registry", None)
        surfaces = surfaces_fn()

        # At least one surface must explicitly reference report/issues.py as backing source
        issues_surfaces = [
            s for s in surfaces
            if "issues.py" in s.notes.lower() or "report/issues" in s.notes.lower()
        ]

        assert len(issues_surfaces) >= 1, (
            f"Report family must explicitly cover report/issues.py backing source. "
            f"No surface found with 'issues.py' or 'report/issues' in notes. "
            f"Available surfaces: {[s.surface_name for s in surfaces]}"
        )


class TestSurfaceSchemaCompliance:
    """All registry entries must comply with ToolSurface or CommandSurface schema."""

    def test_all_entries_are_tool_or_command_surfaces(self) -> None:
        """Every registry entry must be a ToolSurface or CommandSurface instance."""
        from hermesoptimizer.tool_surface import registry
        from hermesoptimizer.tool_surface.schema import ToolSurface, CommandSurface

        surfaces_fn = getattr(registry, "default_surfaces", None) or getattr(registry, "build_default_registry", None)
        surfaces = surfaces_fn()

        for entry in surfaces:
            is_tool = isinstance(entry, ToolSurface)
            is_command = isinstance(entry, CommandSurface)
            assert is_tool or is_command, (
                f"Entry '{entry.surface_name}' is neither ToolSurface nor CommandSurface, "
                f"got {type(entry).__name__}"
            )

    def test_all_entries_have_unique_names(self) -> None:
        """Each registry entry must have a unique surface_name."""
        from hermesoptimizer.tool_surface import registry

        surfaces_fn = getattr(registry, "default_surfaces", None) or getattr(registry, "build_default_registry", None)
        surfaces = surfaces_fn()

        names = [s.surface_name for s in surfaces]
        unique_names = set(names)

        assert len(names) == len(unique_names), (
            f"Duplicate surface names found: {[n for n in names if names.count(n) > 1]}"
        )


class TestSurfaceRiskClassification:
    """Registry entries must have appropriate risk levels."""

    def test_read_only_surfaces_marked_read_only(self) -> None:
        """Surfaces that only read data should be marked read_only=True."""
        from hermesoptimizer.tool_surface import registry
        from hermesoptimizer.tool_surface.schema import RiskLevel

        surfaces_fn = getattr(registry, "default_surfaces", None) or getattr(registry, "build_default_registry", None)
        surfaces = surfaces_fn()

        # Query-type surfaces should be read-only
        read_only_surfaces = [s for s in surfaces if s.read_only]
        write_surfaces = [s for s in surfaces if not s.read_only]

        # We should have both types in a healthy registry
        assert len(read_only_surfaces) >= 1, "Registry should have at least 1 read-only surface"
        assert len(write_surfaces) >= 1, "Registry should have at least 1 mutating surface"

    def test_critical_surfaces_have_high_risk(self) -> None:
        """Surfaces that mutate config or credentials should have HIGH or CRITICAL risk."""
        from hermesoptimizer.tool_surface import registry
        from hermesoptimizer.tool_surface.schema import RiskLevel

        surfaces_fn = getattr(registry, "default_surfaces", None) or getattr(registry, "build_default_registry", None)
        surfaces = surfaces_fn()

        # Mutating surfaces should not be LOW risk
        mutating_low = [
            s for s in surfaces
            if not s.read_only and s.risk_level == RiskLevel.LOW
        ]

        assert len(mutating_low) == 0, (
            f"Mutating surfaces should not be LOW risk: "
            f"{[s.surface_name for s in mutating_low]}"
        )


class TestRegistryReturnsList:
    """Registry function must return a list of surfaces."""

    def test_returns_list(self) -> None:
        """default_surfaces() or build_default_registry() must return a list."""
        from hermesoptimizer.tool_surface import registry

        surfaces_fn = getattr(registry, "default_surfaces", None) or getattr(registry, "build_default_registry", None)
        result = surfaces_fn()

        assert isinstance(result, list), f"Expected list, got {type(result).__name__}"

    def test_returns_non_empty_list(self) -> None:
        """Registry must return a non-empty list."""
        from hermesoptimizer.tool_surface import registry

        surfaces_fn = getattr(registry, "default_surfaces", None) or getattr(registry, "build_default_registry", None)
        result = surfaces_fn()

        assert len(result) > 0, "Registry returned empty list"

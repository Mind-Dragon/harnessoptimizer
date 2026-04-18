"""Tests for Tool Surface IR schema (v0.8.0 Task 1).

These tests verify the minimal shared types for agent-facing tool surfaces:
- SurfaceKind (typed, textual, hybrid)
- RiskLevel
- HelpContract
- OutputContract
- ToolSurface
- CommandSurface

Required fields:
- surface_name, command_name, kind, risk_level, supports_help,
  supports_partial_discovery, supports_overflow_handle, supports_binary_guard,
  read_only, recommended_for_agent, notes
"""

from __future__ import annotations

import pytest


class TestSurfaceKind:
    """Tests for the SurfaceKind enum."""

    def test_surface_kind_has_typed_variant(self) -> None:
        """SurfaceKind must have a 'typed' variant for structured/typed tools."""
        from hermesoptimizer.tool_surface.schema import SurfaceKind

        assert SurfaceKind.TYPED is not None
        assert SurfaceKind.TYPED.value == "typed"

    def test_surface_kind_has_textual_variant(self) -> None:
        """SurfaceKind must have a 'textual' variant for shell/CLI tools."""
        from hermesoptimizer.tool_surface.schema import SurfaceKind

        assert SurfaceKind.TEXTUAL is not None
        assert SurfaceKind.TEXTUAL.value == "textual"

    def test_surface_kind_has_hybrid_variant(self) -> None:
        """SurfaceKind must have a 'hybrid' variant for mixed-mode tools."""
        from hermesoptimizer.tool_surface.schema import SurfaceKind

        assert SurfaceKind.HYBRID is not None
        assert SurfaceKind.HYBRID.value == "hybrid"


class TestRiskLevel:
    """Tests for the RiskLevel enum."""

    def test_risk_level_critical_exists(self) -> None:
        """RiskLevel must have a CRITICAL variant for destructive/riskful operations."""
        from hermesoptimizer.tool_surface.schema import RiskLevel

        assert RiskLevel.CRITICAL is not None
        assert RiskLevel.CRITICAL.value == "critical"

    def test_risk_level_high_exists(self) -> None:
        """RiskLevel must have a HIGH variant for significant operations."""
        from hermesoptimizer.tool_surface.schema import RiskLevel

        assert RiskLevel.HIGH is not None
        assert RiskLevel.HIGH.value == "high"

    def test_risk_level_medium_exists(self) -> None:
        """RiskLevel must have a MEDIUM variant for moderate-risk operations."""
        from hermesoptimizer.tool_surface.schema import RiskLevel

        assert RiskLevel.MEDIUM is not None
        assert RiskLevel.MEDIUM.value == "medium"

    def test_risk_level_low_exists(self) -> None:
        """RiskLevel must have a LOW variant for low-risk operations."""
        from hermesoptimizer.tool_surface.schema import RiskLevel

        assert RiskLevel.LOW is not None
        assert RiskLevel.LOW.value == "low"


class TestHelpContract:
    """Tests for the HelpContract dataclass."""

    def test_help_contract_has_usage(self) -> None:
        """HelpContract must have a usage field describing how to get help."""
        from hermesoptimizer.tool_surface.schema import HelpContract

        contract = HelpContract(usage="--help", examples=["--help", "-h"])
        assert contract.usage == "--help"
        assert "--help" in contract.examples

    def test_help_contract_has_examples(self) -> None:
        """HelpContract must have an examples field listing usage examples."""
        from hermesoptimizer.tool_surface.schema import HelpContract

        contract = HelpContract(usage="--help", examples=["--help", "-h", "--usage"])
        assert len(contract.examples) == 3

    def test_help_contract_is_dataclass(self) -> None:
        """HelpContract must be a dataclass for simplicity."""
        from dataclasses import is_dataclass

        from hermesoptimizer.tool_surface.schema import HelpContract

        assert is_dataclass(HelpContract)

    def test_help_contract_examples_is_optional_with_none_default(self) -> None:
        """HelpContract.examples must be Optional with None default for consistency.

        This matches CommandSurface.subcommands which is Optional with None default.
        The contract is: examples=None means not provided, examples=[] means provided but empty.
        """
        from hermesoptimizer.tool_surface.schema import HelpContract

        # When not provided, examples should be None
        contract = HelpContract(usage="--help")
        assert contract.examples is None

        # When explicitly set to None, should be None
        contract_none = HelpContract(usage="--help", examples=None)
        assert contract_none.examples is None

        # When set to empty list, should be empty list
        contract_empty = HelpContract(usage="--help", examples=[])
        assert contract_empty.examples == []

        # When set to non-empty list, should have values
        contract_with_values = HelpContract(usage="--help", examples=["-h", "--help"])
        assert len(contract_with_values.examples) == 2

    def test_help_contract_is_frozen(self) -> None:
        """HelpContract must be immutable (frozen=True) for IR stability."""
        from dataclasses import FrozenInstanceError

        from hermesoptimizer.tool_surface.schema import HelpContract

        contract = HelpContract(usage="--help")
        with pytest.raises(FrozenInstanceError):
            contract.usage = "--usage"


class TestOutputContract:
    """Tests for the OutputContract dataclass."""

    def test_output_contract_has_format(self) -> None:
        """OutputContract must have a format field."""
        from hermesoptimizer.tool_surface.schema import OutputContract

        contract = OutputContract(format="json", truncated_field="truncated")
        assert contract.format == "json"

    def test_output_contract_has_truncated_field(self) -> None:
        """OutputContract must have a truncated_field for overflow signaling."""
        from hermesoptimizer.tool_surface.schema import OutputContract

        contract = OutputContract(format="json", truncated_field="truncated")
        assert contract.truncated_field == "truncated"

    def test_output_contract_is_dataclass(self) -> None:
        """OutputContract must be a dataclass for simplicity."""
        from dataclasses import is_dataclass

        from hermesoptimizer.tool_surface.schema import OutputContract

        assert is_dataclass(OutputContract)

    def test_output_contract_is_frozen(self) -> None:
        """OutputContract must be immutable (frozen=True) for IR stability."""
        from dataclasses import FrozenInstanceError

        from hermesoptimizer.tool_surface.schema import OutputContract

        contract = OutputContract(format="json")
        with pytest.raises(FrozenInstanceError):
            contract.format = "text"


class TestToolSurface:
    """Tests for the ToolSurface dataclass."""

    def test_tool_surface_has_required_fields(self) -> None:
        """ToolSurface must have all required fields per spec."""
        from hermesoptimizer.tool_surface.schema import (
            RiskLevel,
            SurfaceKind,
            ToolSurface,
        )

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
            notes="A test tool surface.",
        )

        assert surface.surface_name == "test_tool"
        assert surface.command_name == "test"
        assert surface.kind == SurfaceKind.TYPED
        assert surface.risk_level == RiskLevel.LOW
        assert surface.supports_help is True
        assert surface.supports_partial_discovery is False
        assert surface.supports_overflow_handle is False
        assert surface.supports_binary_guard is False
        assert surface.read_only is True
        assert surface.recommended_for_agent is True
        assert surface.notes == "A test tool surface."

    def test_tool_surface_has_optional_help_contract(self) -> None:
        """ToolSurface may have an optional help_contract field."""
        from hermesoptimizer.tool_surface.schema import (
            HelpContract,
            RiskLevel,
            SurfaceKind,
            ToolSurface,
        )

        help_c = HelpContract(usage="--help", examples=["--help"])
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
            notes="",
            help_contract=help_c,
        )

        assert surface.help_contract is not None
        assert surface.help_contract.usage == "--help"

    def test_tool_surface_has_optional_output_contract(self) -> None:
        """ToolSurface may have an optional output_contract field."""
        from hermesoptimizer.tool_surface.schema import (
            OutputContract,
            RiskLevel,
            SurfaceKind,
            ToolSurface,
        )

        out_c = OutputContract(format="json", truncated_field="truncated")
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
            notes="",
            output_contract=out_c,
        )

        assert surface.output_contract is not None
        assert surface.output_contract.format == "json"

    def test_tool_surface_is_dataclass(self) -> None:
        """ToolSurface must be a dataclass for simplicity."""
        from dataclasses import is_dataclass

        from hermesoptimizer.tool_surface.schema import ToolSurface

        assert is_dataclass(ToolSurface)

    def test_tool_surface_notes_has_default_empty_string(self) -> None:
        """ToolSurface.notes must default to empty string for constructor ease."""
        from hermesoptimizer.tool_surface.schema import (
            RiskLevel,
            SurfaceKind,
            ToolSurface,
        )

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
        )

        assert surface.notes == ""

    def test_tool_surface_is_frozen(self) -> None:
        """ToolSurface must be immutable (frozen=True) for IR stability."""
        from dataclasses import FrozenInstanceError

        from hermesoptimizer.tool_surface.schema import (
            RiskLevel,
            SurfaceKind,
            ToolSurface,
        )

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
            notes="test",
        )
        with pytest.raises(FrozenInstanceError):
            surface.surface_name = "renamed"


class TestCommandSurface:
    """Tests for the CommandSurface dataclass."""

    def test_command_surface_has_required_fields(self) -> None:
        """CommandSurface must have all required fields per spec."""
        from hermesoptimizer.tool_surface.schema import (
            RiskLevel,
            SurfaceKind,
            CommandSurface,
        )

        surface = CommandSurface(
            surface_name="test_cmd",
            command_name="test",
            kind=SurfaceKind.TEXTUAL,
            risk_level=RiskLevel.LOW,
            supports_help=True,
            supports_partial_discovery=True,
            supports_overflow_handle=True,
            supports_binary_guard=True,
            read_only=True,
            recommended_for_agent=True,
            notes="A test command surface.",
        )

        assert surface.surface_name == "test_cmd"
        assert surface.command_name == "test"
        assert surface.kind == SurfaceKind.TEXTUAL
        assert surface.risk_level == RiskLevel.LOW
        assert surface.supports_help is True
        assert surface.supports_partial_discovery is True
        assert surface.supports_overflow_handle is True
        assert surface.supports_binary_guard is True
        assert surface.read_only is True
        assert surface.recommended_for_agent is True
        assert surface.notes == "A test command surface."

    def test_command_surface_has_optional_subcommands(self) -> None:
        """CommandSurface may have an optional subcommands list."""
        from hermesoptimizer.tool_surface.schema import (
            RiskLevel,
            SurfaceKind,
            CommandSurface,
        )

        surface = CommandSurface(
            surface_name="test_cmd",
            command_name="test",
            kind=SurfaceKind.TEXTUAL,
            risk_level=RiskLevel.LOW,
            supports_help=True,
            supports_partial_discovery=False,
            supports_overflow_handle=False,
            supports_binary_guard=False,
            read_only=True,
            recommended_for_agent=True,
            notes="",
            subcommands=["list", "get", "inspect"],
        )

        assert surface.subcommands is not None
        assert len(surface.subcommands) == 3
        assert "list" in surface.subcommands

    def test_command_surface_is_dataclass(self) -> None:
        """CommandSurface must be a dataclass for simplicity."""
        from dataclasses import is_dataclass

        from hermesoptimizer.tool_surface.schema import CommandSurface

        assert is_dataclass(CommandSurface)

    def test_command_surface_subcommands_is_optional_with_none_default(self) -> None:
        """CommandSurface.subcommands must be Optional with None default for consistency.

        This matches HelpContract.examples which should also be Optional with None default.
        The contract is: subcommands=None means not provided, subcommands=[] means provided but empty.
        """
        from hermesoptimizer.tool_surface.schema import (
            RiskLevel,
            SurfaceKind,
            CommandSurface,
        )

        # When not provided, subcommands should be None
        surface = CommandSurface(
            surface_name="test_cmd",
            command_name="test",
            kind=SurfaceKind.TEXTUAL,
            risk_level=RiskLevel.LOW,
            supports_help=True,
            supports_partial_discovery=False,
            supports_overflow_handle=False,
            supports_binary_guard=False,
            read_only=True,
            recommended_for_agent=True,
        )
        assert surface.subcommands is None

        # When explicitly set to None, should be None
        surface_none = CommandSurface(
            surface_name="test_cmd",
            command_name="test",
            kind=SurfaceKind.TEXTUAL,
            risk_level=RiskLevel.LOW,
            supports_help=True,
            supports_partial_discovery=False,
            supports_overflow_handle=False,
            supports_binary_guard=False,
            read_only=True,
            recommended_for_agent=True,
            subcommands=None,
        )
        assert surface_none.subcommands is None

        # When set to empty list, should be empty list
        surface_empty = CommandSurface(
            surface_name="test_cmd",
            command_name="test",
            kind=SurfaceKind.TEXTUAL,
            risk_level=RiskLevel.LOW,
            supports_help=True,
            supports_partial_discovery=False,
            supports_overflow_handle=False,
            supports_binary_guard=False,
            read_only=True,
            recommended_for_agent=True,
            subcommands=[],
        )
        assert surface_empty.subcommands == []

    def test_command_surface_notes_has_default_empty_string(self) -> None:
        """CommandSurface.notes must default to empty string for constructor ease."""
        from hermesoptimizer.tool_surface.schema import (
            RiskLevel,
            SurfaceKind,
            CommandSurface,
        )

        surface = CommandSurface(
            surface_name="test_cmd",
            command_name="test",
            kind=SurfaceKind.TEXTUAL,
            risk_level=RiskLevel.LOW,
            supports_help=True,
            supports_partial_discovery=False,
            supports_overflow_handle=False,
            supports_binary_guard=False,
            read_only=True,
            recommended_for_agent=True,
        )

        assert surface.notes == ""

    def test_command_surface_is_frozen(self) -> None:
        """CommandSurface must be immutable (frozen=True) for IR stability."""
        from dataclasses import FrozenInstanceError

        from hermesoptimizer.tool_surface.schema import (
            RiskLevel,
            SurfaceKind,
            CommandSurface,
        )

        surface = CommandSurface(
            surface_name="test_cmd",
            command_name="test",
            kind=SurfaceKind.TEXTUAL,
            risk_level=RiskLevel.LOW,
            supports_help=True,
            supports_partial_discovery=False,
            supports_overflow_handle=False,
            supports_binary_guard=False,
            read_only=True,
            recommended_for_agent=True,
            notes="test",
        )
        with pytest.raises(FrozenInstanceError):
            surface.surface_name = "renamed"


class TestSchemaExports:
    """Tests that the schema module exports all required types."""

    def test_tool_surface_importable(self) -> None:
        """ToolSurface must be importable from the schema module."""
        from hermesoptimizer.tool_surface.schema import ToolSurface

        assert ToolSurface is not None

    def test_command_surface_importable(self) -> None:
        """CommandSurface must be importable from the schema module."""
        from hermesoptimizer.tool_surface.schema import CommandSurface

        assert CommandSurface is not None

    def test_surface_kind_importable(self) -> None:
        """SurfaceKind must be importable from the schema module."""
        from hermesoptimizer.tool_surface.schema import SurfaceKind

        assert SurfaceKind is not None

    def test_risk_level_importable(self) -> None:
        """RiskLevel must be importable from the schema module."""
        from hermesoptimizer.tool_surface.schema import RiskLevel

        assert RiskLevel is not None

    def test_help_contract_importable(self) -> None:
        """HelpContract must be importable from the schema module."""
        from hermesoptimizer.tool_surface.schema import HelpContract

        assert HelpContract is not None

    def test_output_contract_importable(self) -> None:
        """OutputContract must be importable from the schema module."""
        from hermesoptimizer.tool_surface.schema import OutputContract

        assert OutputContract is not None


class TestToolSurfacePackageInit:
    """Tests that the tool_surface package __init__ exports correctly."""

    def test_tool_surface_exported_from_package(self) -> None:
        """ToolSurface must be exported from the tool_surface package."""
        from hermesoptimizer.tool_surface import ToolSurface

        assert ToolSurface is not None

    def test_command_surface_exported_from_package(self) -> None:
        """CommandSurface must be exported from the tool_surface package."""
        from hermesoptimizer.tool_surface import CommandSurface

        assert CommandSurface is not None

    def test_surface_kind_exported_from_package(self) -> None:
        """SurfaceKind must be exported from the tool_surface package."""
        from hermesoptimizer.tool_surface import SurfaceKind

        assert SurfaceKind is not None

    def test_risk_level_exported_from_package(self) -> None:
        """RiskLevel must be exported from the tool_surface package."""
        from hermesoptimizer.tool_surface import RiskLevel

        assert RiskLevel is not None

    def test_help_contract_exported_from_package(self) -> None:
        """HelpContract must be exported from the tool_surface package."""
        from hermesoptimizer.tool_surface import HelpContract

        assert HelpContract is not None

    def test_output_contract_exported_from_package(self) -> None:
        """OutputContract must be exported from the tool_surface package."""
        from hermesoptimizer.tool_surface import OutputContract

        assert OutputContract is not None

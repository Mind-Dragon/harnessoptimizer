"""Tests for Tool Surface commands (v0.8.0 Task 5).

These tests verify the hybrid read-only command layer that provides
a narrow command namespace for inspection flows.

Command namespace:
- provider list
- provider recommend (placeholder stub for Task 6)
- workflow list
- dreams inspect
- report latest

All commands are read-only and do not route destructive or credential-mutating
actions.

Design principles:
- Narrow and deterministic
- Reuses schema types from tool_surface.schema
- No shell runtime; lightweight in-process textual command interpreter
- Progressive help behavior at top-level, command usage, and subcommand levels
"""

from __future__ import annotations

from pathlib import Path

import pytest


class TestCommandsModuleImport:
    """Commands module must exist and be importable."""

    def test_commands_module_importable(self) -> None:
        """Commands module must be importable from tool_surface package."""
        from hermesoptimizer.tool_surface import commands

        assert commands is not None

    def test_execute_command_function_exists(self) -> None:
        """execute_command() function must exist."""
        from hermesoptimizer.tool_surface import commands

        assert hasattr(commands, "execute_command")
        assert callable(commands.execute_command)

    def test_get_help_function_exists(self) -> None:
        """get_help() function must exist for progressive help."""
        from hermesoptimizer.tool_surface import commands

        assert hasattr(commands, "get_help")
        assert callable(commands.get_help)

    def test_list_commands_function_exists(self) -> None:
        """list_commands() function must exist for top-level listing."""
        from hermesoptimizer.tool_surface import commands

        assert hasattr(commands, "list_commands")
        assert callable(commands.list_commands)


class TestCommandNamespace:
    """Command namespace must cover all required command families."""

    def test_provider_list_command_exists(self) -> None:
        """provider list command must be supported."""
        from hermesoptimizer.tool_surface import commands

        result = commands.execute_command("provider list")
        assert result is not None
        assert hasattr(result, "success")

    def test_provider_recommend_command_exists(self) -> None:
        """provider recommend command must be supported (placeholder for Task 6)."""
        from hermesoptimizer.tool_surface import commands

        result = commands.execute_command("provider recommend")
        assert result is not None
        assert hasattr(result, "success")
        # Should succeed but indicate it's a placeholder
        assert result.read_only is True

    def test_workflow_list_command_exists(self) -> None:
        """workflow list command must be supported."""
        from hermesoptimizer.tool_surface import commands

        result = commands.execute_command("workflow list")
        assert result is not None
        assert hasattr(result, "success")

    def test_dreams_inspect_command_exists(self) -> None:
        """dreams inspect command must be supported."""
        from hermesoptimizer.tool_surface import commands

        result = commands.execute_command("dreams inspect")
        assert result is not None
        assert hasattr(result, "success")

    def test_report_latest_command_exists(self) -> None:
        """report latest command must be supported."""
        from hermesoptimizer.tool_surface import commands

        result = commands.execute_command("report latest")
        assert result is not None
        assert hasattr(result, "success")


class TestCommandReadOnlyConstraint:
    """All commands must be read-only; no destructive or credential-mutating actions."""

    def test_provider_list_is_read_only(self) -> None:
        """provider list must be read-only."""
        from hermesoptimizer.tool_surface import commands

        result = commands.execute_command("provider list")
        assert result.read_only is True

    def test_provider_recommend_is_read_only(self) -> None:
        """provider recommend must be read-only."""
        from hermesoptimizer.tool_surface import commands

        result = commands.execute_command("provider recommend")
        assert result.read_only is True

    def test_workflow_list_is_read_only(self) -> None:
        """workflow list must be read-only."""
        from hermesoptimizer.tool_surface import commands

        result = commands.execute_command("workflow list")
        assert result.read_only is True

    def test_dreams_inspect_is_read_only(self) -> None:
        """dreams inspect must be read-only."""
        from hermesoptimizer.tool_surface import commands

        result = commands.execute_command("dreams inspect")
        assert result.read_only is True

    def test_report_latest_is_read_only(self) -> None:
        """report latest must be read-only."""
        from hermesoptimizer.tool_surface import commands

        result = commands.execute_command("report latest")
        assert result.read_only is True


class TestCommandResultStructure:
    """Command results must have a consistent structure."""

    def test_result_has_success_field(self) -> None:
        """Command result must have a success field."""
        from hermesoptimizer.tool_surface import commands

        result = commands.execute_command("provider list")
        assert hasattr(result, "success")
        assert isinstance(result.success, bool)

    def test_result_has_read_only_field(self) -> None:
        """Command result must have a read_only field."""
        from hermesoptimizer.tool_surface import commands

        result = commands.execute_command("provider list")
        assert hasattr(result, "read_only")
        assert isinstance(result.read_only, bool)

    def test_result_has_output_field(self) -> None:
        """Command result must have an output field."""
        from hermesoptimizer.tool_surface import commands

        result = commands.execute_command("provider list")
        assert hasattr(result, "output")

    def test_result_has_stdout_field(self) -> None:
        """Command result must have a stdout field."""
        from hermesoptimizer.tool_surface import commands

        result = commands.execute_command("provider list")
        assert hasattr(result, "stdout")
        assert isinstance(result.stdout, str)

    def test_result_has_stderr_field(self) -> None:
        """Command result must have a stderr field."""
        from hermesoptimizer.tool_surface import commands

        result = commands.execute_command("provider list")
        assert hasattr(result, "stderr")
        assert isinstance(result.stderr, str)


class TestProgressiveHelp:
    """Progressive help behavior at top-level, command, and subcommand levels."""

    def test_help_with_no_args_shows_top_level_list(self) -> None:
        """get_help() with no args shows top-level command list."""
        from hermesoptimizer.tool_surface import commands

        help_text = commands.get_help()
        assert isinstance(help_text, str)
        assert len(help_text) > 0
        # Should mention command families
        assert "provider" in help_text.lower() or "command" in help_text.lower()

    def test_help_for_command_shows_usage(self) -> None:
        """get_help('provider') shows command usage."""
        from hermesoptimizer.tool_surface import commands

        help_text = commands.get_help("provider")
        assert isinstance(help_text, str)
        assert len(help_text) > 0
        # Should mention subcommands like list, recommend
        assert "list" in help_text.lower() or "recommend" in help_text.lower()

    def test_help_for_subcommand_shows_specific_usage(self) -> None:
        """get_help('provider list') shows subcommand-specific usage."""
        from hermesoptimizer.tool_surface import commands

        help_text = commands.get_help("provider list")
        assert isinstance(help_text, str)
        assert len(help_text) > 0
        # Should describe what provider list does
        assert "provider" in help_text.lower()

    def test_list_commands_returns_command_names(self) -> None:
        """list_commands() returns the available command names."""
        from hermesoptimizer.tool_surface import commands

        commands_list = commands.list_commands()
        assert isinstance(commands_list, list)
        assert len(commands_list) > 0
        # Should include the required commands
        assert any("provider" in c for c in commands_list)
        assert any("workflow" in c for c in commands_list)
        assert any("dreams" in c for c in commands_list)
        assert any("report" in c for c in commands_list)


class TestUnknownCommandHandling:
    """Unknown commands should be handled gracefully."""

    def test_unknown_command_returns_failure_result(self) -> None:
        """Unknown command should return a result with success=False."""
        from hermesoptimizer.tool_surface import commands

        result = commands.execute_command("unknown command")
        assert result.success is False

    def test_unknown_command_returns_helpful_message(self) -> None:
        """Unknown command should include a helpful error message."""
        from hermesoptimizer.tool_surface import commands

        result = commands.execute_command("unknown command")
        assert len(result.stdout) > 0 or len(result.stderr) > 0


class TestCommandIntegrationWithBackingSources:
    """Commands should integrate with real backing sources."""

    def test_provider_list_returns_provider_info(self) -> None:
        """provider list should return provider information from truth store."""
        from hermesoptimizer.tool_surface import commands

        result = commands.execute_command("provider list")
        # Must succeed
        assert result.success is True, f"provider list failed: {result.stderr}"
        # Must be read-only
        assert result.read_only is True
        # Should have meaningful output about providers or empty store
        output = result.stdout
        assert len(output) > 0, "provider list should produce output"
        # Output should mention "provider" or "truth store" or be empty list message
        assert ("provider" in output.lower() or
                "truth store" in output.lower() or
                "no providers" in output.lower()), \
            f"provider list output should mention providers or empty store: {output!r}"

    def test_workflow_list_returns_workflow_info(self) -> None:
        """workflow list should return workflow information from store."""
        from hermesoptimizer.tool_surface import commands

        result = commands.execute_command("workflow list")
        # Must succeed
        assert result.success is True, f"workflow list failed: {result.stderr}"
        # Must be read-only
        assert result.read_only is True
        # Should have meaningful output about workflows or empty store
        output = result.stdout
        assert len(output) > 0, "workflow list should produce output"
        # Output should mention "workflow", "plan", or empty message
        assert ("workflow" in output.lower() or
                "plan" in output.lower() or
                "no workflow" in output.lower()), \
            f"workflow list output should mention workflows or empty store: {output!r}"

    def test_workflow_list_handles_dataclass_plans(self) -> None:
        """workflow list must handle WorkflowPlan dataclass instances, not dicts.

        This test exposes a latent bug where the handler assumed list_plans()
        returns dicts with .get() method, but it actually returns WorkflowPlan
        dataclass instances with attribute access.
        """
        from unittest.mock import patch
        from hermesoptimizer.tool_surface import commands
        from hermesoptimizer.workflow.schema import WorkflowPlan

        # Create real WorkflowPlan dataclass instances (what list_plans actually returns)
        mock_plans = [
            WorkflowPlan(
                workflow_id="test-id-1",
                objective="Test objective 1",
                status="draft",
            ),
            WorkflowPlan(
                workflow_id="test-id-2",
                objective="Test objective 2",
                status="frozen",
            ),
        ]

        with patch("hermesoptimizer.commands.todo_cmd.list_plans", return_value=mock_plans):
            result = commands.execute_command("workflow list")
            # Must succeed - if bug exists, this will raise AttributeError
            assert result.success is True, f"workflow list failed: {result.stderr}"
            assert result.read_only is True
            # Output should contain both workflow names
            output = result.stdout
            assert "Test objective 1" in output, f"Missing first plan in output: {output!r}"
            assert "Test objective 2" in output, f"Missing second plan in output: {output!r}"

    def test_dreams_inspect_uses_real_memory_meta_api(self) -> None:
        """dreams inspect should use the actual memory_meta module functions."""
        from hermesoptimizer.tool_surface import commands

        result = commands.execute_command("dreams inspect")
        # Must succeed
        assert result.success is True, f"dreams inspect failed: {result.stderr}"
        # Must be read-only
        assert result.read_only is True
        # Should have meaningful output about dreams database
        output = result.stdout
        assert len(output) > 0, "dreams inspect should produce output"
        # Output should mention database path or entries
        assert ("dreams" in output.lower() or
                "memory" in output.lower() or
                "database" in output.lower() or
                "entries" in output.lower()), \
            f"dreams inspect output should mention database or entries: {output!r}"

    def test_report_latest_handles_missing_reports_dir(self, tmp_path: Path, monkeypatch) -> None:
        """report latest should handle missing runtime reports directory gracefully."""
        from hermesoptimizer.tool_surface import commands

        hoptimizer_home = tmp_path / "hopt-home"
        monkeypatch.setenv("HOPTIMIZER_HOME", str(hoptimizer_home))

        result = commands.execute_command("report latest")
        assert result.success is True, f"report latest failed: {result.stderr}"
        assert result.read_only is True
        output = result.stdout.lower()
        assert "no report" in output or "not found" in output, \
            f"report latest should indicate no reports found: {result.stdout!r}"

    def test_provider_recommend_returns_ranked_output(self) -> None:
        """provider recommend should return real ranked recommendations."""
        from hermesoptimizer.tool_surface import commands

        result = commands.execute_command("provider recommend")
        assert result.success is True, f"provider recommend failed: {result.stderr}"
        assert result.read_only is True
        output = result.stdout.lower()
        assert "recommendations:" in output, \
            f"provider recommend should emit ranked output: {result.stdout!r}"
        assert "provider=" in output, \
            f"provider recommend should include provider rows: {result.stdout!r}"

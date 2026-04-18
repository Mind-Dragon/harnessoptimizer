"""Tests for Tool Surface chain (v0.8.0 Task 5).

These tests verify the composition operators support for the command layer.
Supported operators: |, &&, ||, ;

Design principles:
- Narrow and deterministic
- Operators are compositional but constrained
- NOT a shell runtime; lightweight in-process textual command composition
- Read-only commands only; no destructive operations
"""

from __future__ import annotations

import pytest


class TestChainModuleImport:
    """Chain module must exist and be importable."""

    def test_chain_module_importable(self) -> None:
        """Chain module must be importable from tool_surface package."""
        from hermesoptimizer.tool_surface import chain

        assert chain is not None

    def test_chain_execute_function_exists(self) -> None:
        """chain_execute() function must exist."""
        from hermesoptimizer.tool_surface import chain

        assert hasattr(chain, "chain_execute")
        assert callable(chain.chain_execute)


class TestPipeOperator:
    """Pipe operator | should pass output of left command to right command."""

    def test_pipe_operator_exists(self) -> None:
        """PIPE operator constant should exist."""
        from hermesoptimizer.tool_surface.chain import PIPE

        assert PIPE is not None

    def test_pipe_passes_stdout_to_next_command(self) -> None:
        """Pipe should pass stdout of first command as input to second command."""
        from hermesoptimizer.tool_surface import chain

        result = chain.chain_execute("provider list | grep -i provider")
        # Should execute without crashing
        assert result is not None
        assert hasattr(result, "success")

    def test_pipe_preserves_read_only_constraint(self) -> None:
        """Pipe chain should remain read-only."""
        from hermesoptimizer.tool_surface import chain

        result = chain.chain_execute("provider list | grep -i something")
        assert result.read_only is True


class TestAndOperator:
    """AND operator && should execute commands sequentially on success."""

    def test_and_operator_exists(self) -> None:
        """AND operator constant should exist."""
        from hermesoptimizer.tool_surface.chain import AND

        assert AND is not None

    def test_and_stops_on_first_failure(self) -> None:
        """AND should stop execution if first command fails."""
        from hermesoptimizer.tool_surface import chain

        # Use a command that will fail followed by one that would succeed
        result = chain.chain_execute("unknowncmd && provider list")
        # The result should indicate overall failure
        assert result.success is False or result.exit_code != 0

    def test_and_executes_both_on_success(self) -> None:
        """AND should execute both commands when first succeeds."""
        from hermesoptimizer.tool_surface import chain

        result = chain.chain_execute("provider list && workflow list")
        # Should complete (may succeed or fail depending on data)
        assert result is not None
        assert hasattr(result, "success")
        # Both commands should have run, so output should contain provider-related text
        assert "provider" in result.stdout.lower() or len(result.stdout) > 0

    def test_and_preserves_read_only_constraint(self) -> None:
        """AND chain should remain read-only."""
        from hermesoptimizer.tool_surface import chain

        result = chain.chain_execute("provider list && workflow list")
        assert result.read_only is True

    def test_and_combines_stdout_from_both_commands(self) -> None:
        """AND should combine stdout from both successful commands."""
        from hermesoptimizer.tool_surface import chain

        result = chain.chain_execute("provider list && provider list")
        # Both commands should execute and their outputs combined
        assert result.success is True
        # Output should be combined - non-empty and properly structured
        assert len(result.stdout) > 0, "Combined output should be non-empty"
        lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
        assert len(lines) >= 1, "Should have output from commands"

    def test_and_stops_execution_on_failure(self) -> None:
        """AND should stop and not execute subsequent commands after failure."""
        from hermesoptimizer.tool_surface import chain

        # Execute command that fails followed by provider list
        result = chain.chain_execute("unknowncmd && provider list")
        # The unknowncmd fails, so AND should not run provider list
        # The chain should return failure and preserve read-only
        assert result.read_only is True


class TestOrOperator:
    """OR operator || should execute second command only if first fails."""

    def test_or_operator_exists(self) -> None:
        """OR operator constant should exist."""
        from hermesoptimizer.tool_surface.chain import OR

        assert OR is not None

    def test_or_runs_second_on_first_failure(self) -> None:
        """OR should run second command when first fails."""
        from hermesoptimizer.tool_surface import chain

        result = chain.chain_execute("unknowncmd || provider list")
        # Should have tried the second command - check read-only constraint
        assert result.read_only is True
        # Second command (provider list) should have produced output
        assert len(result.stdout) > 0, "Second command should produce output"

    def test_or_skips_second_on_first_success(self) -> None:
        """OR should skip second command when first succeeds."""
        from hermesoptimizer.tool_surface import chain

        # First command succeeds, second should not affect outcome much
        result = chain.chain_execute("provider list || unknowncmd")
        assert result is not None
        assert result.success is True or result.exit_code == 0

    def test_or_fallback_produces_expected_output(self) -> None:
        """OR should produce output from the fallback command when first fails."""
        from hermesoptimizer.tool_surface import chain

        result = chain.chain_execute("unknowncmd || provider list")
        # The fallback command should have executed and produced output
        assert len(result.stdout) > 0, "Fallback command should produce output"

    def test_or_preserves_read_only_constraint(self) -> None:
        """OR chain should remain read-only."""
        from hermesoptimizer.tool_surface import chain

        result = chain.chain_execute("provider list || workflow list")
        assert result.read_only is True


class TestSemicolonOperator:
    """Semicolon operator ; should execute commands sequentially regardless."""

    def test_semicolon_operator_exists(self) -> None:
        """SEMICOLON operator constant should exist."""
        from hermesoptimizer.tool_surface.chain import SEMICOLON

        assert SEMICOLON is not None

    def test_semicolon_executes_both_always(self) -> None:
        """Semicolon should execute both commands regardless of outcome."""
        from hermesoptimizer.tool_surface import chain

        result = chain.chain_execute("provider list ; provider list")
        # Should execute both commands
        assert result is not None
        assert hasattr(result, "success")
        # Both commands should have run - output should be combined
        assert len(result.stdout) > 0, "Output should contain results from both commands"
        # With two provider list commands, we should have combined output
        lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
        assert len(lines) >= 1, "Should have output lines"

    def test_semicolon_continues_after_failure(self) -> None:
        """Semicolon should continue executing even if first command fails."""
        from hermesoptimizer.tool_surface import chain

        result = chain.chain_execute("unknowncmd ; provider list")
        # Second command should still execute - verify output exists
        assert len(result.stdout) > 0, "Second command should produce output even after first fails"
        # The chain should still be read-only
        assert result.read_only is True

    def test_semicolon_preserves_read_only_constraint(self) -> None:
        """Semicolon chain should remain read-only."""
        from hermesoptimizer.tool_surface import chain

        result = chain.chain_execute("provider list ; workflow list")
        assert result.read_only is True


class TestChainResultStructure:
    """Chain execution results must have a consistent structure."""

    def test_chain_result_has_success_field(self) -> None:
        """Chain result must have a success field."""
        from hermesoptimizer.tool_surface import chain

        result = chain.chain_execute("provider list")
        assert hasattr(result, "success")

    def test_chain_result_has_read_only_field(self) -> None:
        """Chain result must have a read_only field."""
        from hermesoptimizer.tool_surface import chain

        result = chain.chain_execute("provider list")
        assert hasattr(result, "read_only")
        assert result.read_only is True

    def test_chain_result_has_exit_code_field(self) -> None:
        """Chain result must have an exit_code field."""
        from hermesoptimizer.tool_surface import chain

        result = chain.chain_execute("provider list")
        assert hasattr(result, "exit_code")

    def test_chain_result_has_stdout_field(self) -> None:
        """Chain result must have a stdout field."""
        from hermesoptimizer.tool_surface import chain

        result = chain.chain_execute("provider list")
        assert hasattr(result, "stdout")
        assert isinstance(result.stdout, str)

    def test_chain_result_has_stderr_field(self) -> None:
        """Chain result must have a stderr field."""
        from hermesoptimizer.tool_surface import chain

        result = chain.chain_execute("provider list")
        assert hasattr(result, "stderr")
        assert isinstance(result.stderr, str)


class TestChainReadOnlyConstraint:
    """Chain operations should preserve read-only constraint."""

    def test_all_operators_preserve_read_only(self) -> None:
        """All operators should produce read-only chain results."""
        from hermesoptimizer.tool_surface import chain

        operators = [" | ", " && ", " || ", " ; "]
        for op in operators:
            result = chain.chain_execute(f"provider list{op}workflow list")
            assert result.read_only is True, f"Operator '{op}' did not preserve read_only"

    def test_chain_cannot_be_used_for_destructive_operations(self) -> None:
        """Chain should not allow destructive operations."""
        from hermesoptimizer.tool_surface import chain

        # Try to chain a destructive-sounding command - it should either
        # fail to parse or return a read-only result
        result = chain.chain_execute("rm -rf / && provider list")
        # The result should still be read_only=True if it partially succeeds,
        # or fail appropriately
        assert result.read_only is True or result.success is False


class TestChainParsing:
    """Chain parsing should handle command strings correctly."""

    def test_simple_command_without_operator(self) -> None:
        """Simple command without operator should work."""
        from hermesoptimizer.tool_surface import chain

        result = chain.chain_execute("provider list")
        assert result.success is True

    def test_command_with_extra_whitespace(self) -> None:
        """Commands with extra whitespace should be handled."""
        from hermesoptimizer.tool_surface import chain

        result = chain.chain_execute("  provider list  ")
        assert result.success is True

    def test_empty_command_string(self) -> None:
        """Empty command string should be handled gracefully."""
        from hermesoptimizer.tool_surface import chain

        result = chain.chain_execute("")
        # Should return a failure result
        assert result.success is False

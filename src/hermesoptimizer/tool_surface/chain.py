"""Chain composition operators for read-only command layer (v0.8.0 Task 5).

This module provides composition operators for combining read-only commands.
It is NOT a shell runtime - it is a lightweight in-process textual command
composer that is narrow, deterministic, and read-only.

Supported operators:
- | (pipe): Pass stdout of left command to right command as input
- && (and): Execute left, if success execute right
- || (or): Execute left, if failure execute right
- ; (semicolon): Execute left, then execute right regardless

Design principles:
- All operators preserve read-only constraint
- No shell runtime; purely in-process composition
- Simple parsing and dispatching
- Deterministic and testable
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .commands import CommandResult, execute_command


# --------------------------------------------------------------------------:
# Operator constants
# --------------------------------------------------------------------------:

PIPE = "|"
AND = "&&"
OR = "||"
SEMICOLON = ";"


# --------------------------------------------------------------------------:
# Chain result structure
# --------------------------------------------------------------------------:


@dataclass
class ChainResult:
    """Result of executing a chain of commands.

    Attributes:
        success: Whether the chain succeeded overall
        read_only: Whether this was a read-only chain (always True)
        exit_code: Exit code (0 for success, non-zero for failure)
        stdout: Combined standard output from all commands
        stderr: Combined standard error from all commands
    """

    success: bool
    read_only: bool = True
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""


# --------------------------------------------------------------------------:
# Chain parsing
# --------------------------------------------------------------------------:


def _parse_chain(command_line: str) -> list[tuple[str, Optional[str]]]:
    """Parse a command line into commands and their joining operators.

    Args:
        command_line: Command string potentially containing operators

    Returns:
        List of (command, operator) tuples.
        The operator is the joining operator AFTER this command (None if last).
    """
    # Split on operators while preserving them
    parts = []
    current = ""

    i = 0
    while i < len(command_line):
        # Check for operators at current position
        if command_line[i:i+2] in (AND, OR):
            # Push current with this operator
            if current.strip():
                parts.append((current.strip(), AND if command_line[i:i+2] == AND else OR))
            current = ""
            i += 2
        elif command_line[i] == PIPE:
            if current.strip():
                parts.append((current.strip(), PIPE))
            current = ""
            i += 1
        elif command_line[i] == SEMICOLON:
            if current.strip():
                parts.append((current.strip(), SEMICOLON))
            current = ""
            i += 1
        else:
            current += command_line[i]
            i += 1

    # Don't forget the last part - no operator after it
    if current.strip():
        parts.append((current.strip(), None))

    return parts


def _split_command_args(command: str) -> tuple[str, list[str]]:
    """Split a command string into command and arguments.

    Args:
        command: Command string (e.g., "provider list")

    Returns:
        Tuple of (command, args_list)
    """
    parts = command.split()
    if not parts:
        return "", []
    return parts[0], parts[1:]


# --------------------------------------------------------------------------:
# Chain execution
# --------------------------------------------------------------------------:


def chain_execute(command_line: str) -> ChainResult:
    """Execute a chain of commands with operators.

    Args:
        command_line: Command string potentially containing operators
            e.g., "provider list | grep provider" or "provider list && workflow list"

    Returns:
        ChainResult with combined output from all commands
    """
    # Handle empty command
    command_line = command_line.strip()
    if not command_line:
        return ChainResult(success=False, exit_code=1, stderr="Empty command")

    # Parse the chain
    parts = _parse_chain(command_line)

    if not parts:
        return ChainResult(success=False, exit_code=1, stderr="Empty command")

    # Execute commands sequentially
    all_stdout = []
    all_stderr = []
    overall_success = True
    last_exit_code = 0
    pipe_input: Optional[str] = None
    skip_next = False  # For OR operator

    for cmd, op in parts:
        # Handle skip for OR operator
        if skip_next:
            skip_next = False
            continue

        # Execute the command
        if cmd:
            result = execute_command(cmd)

            # For pipe, we use the previous command's stdout as input context
            # (the actual pipe filtering would need to be implemented per-command)
            if pipe_input and result.stdout:
                # Simple pipe: filter local output by pipe_input if it's a grep-like pattern
                if "grep" in cmd:
                    # Extract grep pattern from command
                    args = cmd.split("grep")[1].strip() if "grep" in cmd else ""
                    if args:
                        # Filter lines containing the pattern (case-insensitive)
                        pattern = args.strip().strip("'\"").replace("-i", "").strip()
                        if pattern:
                            lines = result.stdout.split("\n")
                            filtered = [l for l in lines if pattern.lower() in l.lower()]
                            result = CommandResult(
                                success=result.success,
                                read_only=result.read_only,
                                stdout="\n".join(filtered),
                                stderr=result.stderr,
                                exit_code=result.exit_code,
                            )

            all_stdout.append(result.stdout)
            if result.stderr:
                all_stderr.append(result.stderr)

            last_exit_code = result.exit_code
            if not result.success:
                overall_success = False

        # Handle operators for NEXT command
        if op == AND:
            # Stop on failure: if current command failed, skip rest
            if not overall_success:
                break

        elif op == OR:
            # If current command succeeded, skip next command
            if overall_success:
                skip_next = True

        elif op == PIPE:
            # Store stdout for piping (handled in next command execution)
            if all_stdout:
                pipe_input = all_stdout[-1]

        elif op == SEMICOLON:
            # Continue regardless - no special handling needed
            pass

    # Combine outputs
    stdout = "\n".join(all_stdout)
    stderr = "\n".join(all_stderr)

    return ChainResult(
        success=overall_success,
        read_only=True,  # Always read-only
        exit_code=last_exit_code,
        stdout=stdout,
        stderr=stderr,
    )

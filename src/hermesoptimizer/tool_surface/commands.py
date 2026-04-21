"""Hybrid read-only command layer (v0.8.0 Task 5).

This module provides a lightweight in-process textual command interpreter
over existing local tool surfaces. It is NOT a shell runtime - it is
narrow, deterministic, and read-only.

Command namespace (deliberately narrow and read-only):
- provider list: List available providers from provider truth
- provider recommend: Placeholder for Task 6 recommender (read-only stub)
- workflow list: List workflow plans and runs
- dreams inspect: Inspect memory/dream state
- report latest: Get the latest report

Design principles:
- Progressive help: top-level list, command usage, subcommand-specific usage
- All commands are read-only; no destructive or credential-mutating actions
- Simple parser/dispatcher functions, not heavyweight command frameworks
- Reusable by later evaluation/proof work

Composition operators (where deterministic and testable):
- | (pipe): Pass output of left to right
- && (and): Execute sequentially on success
- || (or): Execute second only if first fails
- ; (semicolon): Execute sequentially regardless
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from hermesoptimizer.paths import get_report_dir

# --------------------------------------------------------------------------:
# Command result structure
# --------------------------------------------------------------------------:


@dataclass
class CommandResult:
    """Result of executing a command.

    Attributes:
        success: Whether the command succeeded
        read_only: Whether this was a read-only command (always True for this layer)
        stdout: Standard output from the command
        stderr: Standard error from the command
        exit_code: Exit code (0 for success, non-zero for failure)
        output: Alias/shortcut for stdout for compatibility
    """

    success: bool
    read_only: bool = True
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    output: str = ""

    def __post_init__(self) -> None:
        """Set output alias for stdout."""
        if not self.output:
            self.output = self.stdout


# --------------------------------------------------------------------------:
# Command handlers
# --------------------------------------------------------------------------:


def _handle_provider_list(_args: Optional[list[str]] = None) -> CommandResult:
    """Handle 'provider list' command.

    Lists available providers from the provider truth source.
    This is a read-only operation.
    """
    try:
        # Import the provider truth module to get provider information
        from hermesoptimizer.sources.provider_truth import ProviderTruthStore

        store = ProviderTruthStore()
        providers = store.providers()

        if providers:
            output_lines = [f"Provider: {p}" for p in providers]
            stdout = "\n".join(output_lines)
        else:
            stdout = "No providers found in truth store"

        return CommandResult(success=True, read_only=True, stdout=stdout, exit_code=0)
    except Exception as e:
        return CommandResult(
            success=False,
            read_only=True,
            stdout="",
            stderr=f"Error listing providers: {e}",
            exit_code=1,
        )


def _handle_provider_recommend(_args: Optional[list[str]] = None) -> CommandResult:
    """Handle 'provider recommend' command with real recommendation output."""
    try:
        from hermesoptimizer.schemas.provider_endpoint import ProviderEndpointCatalog
        from hermesoptimizer.schemas.provider_model import ProviderModelCatalog
        from hermesoptimizer.sources.provider_truth import ProviderTruthStore, seed_from_config
        from hermesoptimizer.tool_surface.provider_recommend import (
            ProviderRecommendInput,
            ProviderRecommender,
            SafetyLane,
        )

        repo_root = Path(__file__).resolve().parents[3]
        endpoint_catalog = ProviderEndpointCatalog.from_file(repo_root / "data" / "provider_endpoints.json")
        model_catalog = ProviderModelCatalog.from_file(repo_root / "data" / "provider_models.json")
        config_path = Path.home() / ".hermes" / "config.yaml"
        truth_store = seed_from_config(config_path) if config_path.exists() else ProviderTruthStore()

        recommender = ProviderRecommender(
            truth_store=truth_store,
            endpoint_catalog=endpoint_catalog,
            model_catalog=model_catalog,
        )
        result = recommender.recommend(
            ProviderRecommendInput(
                desired_capabilities=["text"],
                desired_lane=SafetyLane.GENERAL,
            )
        )

        recommendations = result.recommendations[:5]
        if not recommendations:
            stdout = "No provider recommendations matched the requested filters."
        else:
            lines = [
                f"Recommendations: {len(recommendations)} shown / {result.total_candidates} candidates considered",
                f"Validation passed: {result.validation_passed}",
                "",
            ]
            for idx, rec in enumerate(recommendations, start=1):
                lines.extend(
                    [
                        f"{idx}. provider={rec.provider} model={rec.model or '-'} lane={rec.lane.value} score={rec.rank_score:.2f}",
                        f"   endpoint: {rec.endpoint}",
                        f"   reason: {rec.reason}",
                        f"   provenance: {rec.provenance}",
                    ]
                )
            stdout = "\n".join(lines)

        return CommandResult(success=True, read_only=True, stdout=stdout, exit_code=0)
    except Exception as e:
        return CommandResult(
            success=False,
            read_only=True,
            stdout="",
            stderr=f"Error recommending providers: {e}",
            exit_code=1,
        )


def _handle_workflow_list(_args: Optional[list[str]] = None) -> CommandResult:
    """Handle 'workflow list' command.

    Lists workflow plans and runs from the workflow store.
    This is a read-only operation.
    """
    try:
        from hermesoptimizer.commands.todo_cmd import list_plans

        plans = list_plans()

        if plans:
            # Handle both dataclass (WorkflowPlan) and dict-like access
            output_lines = []
            for p in plans:
                if hasattr(p, 'objective') and p.objective:
                    output_lines.append(f"Plan: {p.objective}")
                elif hasattr(p, 'get'):
                    output_lines.append(f"Plan: {p.get('name', 'unnamed')}")
                else:
                    output_lines.append("Plan: unnamed")
            stdout = "\n".join(output_lines)
        else:
            stdout = "No workflow plans found"

        return CommandResult(success=True, read_only=True, stdout=stdout, exit_code=0)
    except Exception as e:
        return CommandResult(
            success=False,
            read_only=True,
            stdout="",
            stderr=f"Error listing workflows: {e}",
            exit_code=1,
        )


def _handle_dreams_inspect(_args: Optional[list[str]] = None) -> CommandResult:
    """Handle 'dreams inspect' command.

    Inspects memory/dream state from the dreams module.
    This is a read-only operation.
    """
    try:
        from hermesoptimizer.dreams.memory_meta import init_db, query_by_score
        from pathlib import Path

        db_path = Path("~/.hermes/dreams/memory_meta.db").expanduser()

        # Initialize DB if needed (idempotent)
        init_db(db_path)

        # Get entries ordered by importance
        entries = query_by_score(db_path, threshold=0.0)

        if entries:
            stdout = f"Dreams memory database at {db_path}\n"
            stdout += f"Total entries: {len(entries)}\n"
            for entry in entries[:5]:
                content_hash = entry.get("content_hash", "unknown")
                importance = entry.get("importance", 0)
                supermemory_id = entry.get("supermemory_id", "unknown")
                stdout += f"  - {content_hash[:8]}... (score: {importance}, id: {supermemory_id[:8]}...)\n"
        else:
            stdout = f"Dreams memory database at {db_path}\nNo entries found"

        return CommandResult(success=True, read_only=True, stdout=stdout, exit_code=0)
    except FileNotFoundError:
        return CommandResult(
            success=True,
            read_only=True,
            stdout="Dreams memory database not initialized. Run dreaming_pre_sweep.py first.",
            exit_code=0,
        )
    except Exception as e:
        return CommandResult(
            success=False,
            read_only=True,
            stdout="",
            stderr=f"Error inspecting dreams: {e}",
            exit_code=1,
        )


def _handle_report_latest(_args: Optional[list[str]] = None) -> CommandResult:
    """Handle 'report latest' command.

    Gets the latest report from the runtime reports directory.
    This is a read-only operation.
    """
    try:
        import os

        reports_dir = get_report_dir()
        if not reports_dir.exists():
            return CommandResult(
                success=True,
                read_only=True,
                stdout="No reports directory found",
                exit_code=0,
            )

        report_files: list[tuple[Path, float]] = []
        for path in reports_dir.iterdir():
            if path.is_file() and path.suffix in {".md", ".json"}:
                report_files.append((path, path.stat().st_mtime))

        if not report_files:
            return CommandResult(
                success=True,
                read_only=True,
                stdout="No reports found",
                exit_code=0,
            )

        report_files.sort(key=lambda item: item[1], reverse=True)
        latest_path = report_files[0][0]
        content = latest_path.read_text(encoding="utf-8")

        max_len = 2000
        if len(content) > max_len:
            content = content[:max_len] + f"\n... [truncated, full report: {latest_path.name}]"

        stdout = f"Latest report: {latest_path.name}\n\n{content}"
        return CommandResult(success=True, read_only=True, stdout=stdout, exit_code=0)
    except Exception as e:
        return CommandResult(
            success=False,
            read_only=True,
            stdout="",
            stderr=f"Error getting latest report: {e}",
            exit_code=1,
        )


# --------------------------------------------------------------------------:
# Command registry
# --------------------------------------------------------------------------:


# Command handlers mapping: command string -> handler function
_COMMAND_HANDLERS: dict[str, tuple[str, callable]] = {
    "provider list": ("provider", _handle_provider_list),
    "provider recommend": ("provider", _handle_provider_recommend),
    "workflow list": ("workflow", _handle_workflow_list),
    "dreams inspect": ("dreams", _handle_dreams_inspect),
    "report latest": ("report", _handle_report_latest),
}

# All available commands
AVAILABLE_COMMANDS = list(_COMMAND_HANDLERS.keys())

# Command families for help grouping
_COMMAND_FAMILIES: dict[str, list[str]] = {
    "provider": ["list", "recommend"],
    "workflow": ["list"],
    "dreams": ["inspect"],
    "report": ["latest"],
}


# --------------------------------------------------------------------------:
# Public API
# --------------------------------------------------------------------------:


def execute_command(command_line: str) -> CommandResult:
    """Execute a command string and return the result.

    Args:
        command_line: Command string to execute (e.g., "provider list")

    Returns:
        CommandResult with success status, output, and metadata
    """
    # Normalize command string
    command_line = command_line.strip()

    if not command_line:
        return CommandResult(
            success=False,
            read_only=True,
            stdout="",
            stderr="Empty command",
            exit_code=1,
        )

    # Look up the command handler
    if command_line in _COMMAND_HANDLERS:
        _family, handler = _COMMAND_HANDLERS[command_line]
        return handler()

    # Unknown command
    return CommandResult(
        success=False,
        read_only=True,
        stdout="",
        stderr=f"Unknown command: {command_line}\nUse 'help' to see available commands",
        exit_code=1,
    )


def get_help(topic: Optional[str] = None) -> str:
    """Get help text with progressive disclosure.

    Args:
        topic: Optional topic to get help for.
           - None: Returns top-level command list
           - "provider", "workflow", "dreams", "report": Returns command family help
           - "provider list", "provider recommend", etc.: Returns subcommand-specific help

    Returns:
        Help text string
    """
    if topic is None:
        # Top-level help: list all commands
        lines = [
            "Available commands (read-only):",
            "",
        ]
        for family, subcommands in _COMMAND_FAMILIES.items():
            lines.append(f"  {family}:")
            for sub in subcommands:
                lines.append(f"    {family} {sub}")
        lines.append("")
        lines.append("Use 'help <command>' for more information.")
        return "\n".join(lines)

    # Normalize topic
    topic = topic.strip().lower()

    # Top-level command family help
    if topic in _COMMAND_FAMILIES:
        family = topic
        lines = [
            f"Command family: {family}",
            "",
            f"Available subcommands for '{family}':",
        ]
        for sub in _COMMAND_FAMILIES[family]:
            lines.append(f"  {family} {sub}")
        lines.append("")
        lines.append(f"Use 'help {family} <subcommand>' for subcommand-specific help.")
        return "\n".join(lines)

    # Specific subcommand help
    # Check if it's a full command like "provider list"
    if topic in _COMMAND_HANDLERS:
        family, handler = _COMMAND_HANDLERS[topic]
        lines = [
            f"Command: {topic}",
            "",
            f"Family: {family}",
            "Read-only: Yes",
            "",
        ]
        # Add specific help based on command
        if topic == "provider list":
            lines.extend([
                "Lists available providers from the provider truth store.",
                "",
                "Usage: provider list",
                "",
                "This command queries the provider truth store and returns",
                "a list of all known providers.",
            ])
        elif topic == "provider recommend":
            lines.extend([
                "Produces ranked provider/model recommendations.",
                "",
                "Usage: provider recommend",
                "",
                "This command ranks provider/model candidates using checked-in",
                "endpoint/model catalogs plus any locally seeded provider truth.",
            ])
        elif topic == "workflow list":
            lines.extend([
                "Lists workflow plans and runs.",
                "",
                "Usage: workflow list",
                "",
                "This command queries the workflow store and returns",
                "a list of all workflow plans.",
            ])
        elif topic == "dreams inspect":
            lines.extend([
                "Inspects memory/dream state.",
                "",
                "Usage: dreams inspect",
                "",
                "This command inspects the dreams memory database and returns",
                "information about recent memory entries.",
            ])
        elif topic == "report latest":
            lines.extend([
                "Gets the latest report.",
                "",
                "Usage: report latest",
                "",
                "This command finds and displays the most recent report",
                "from the runtime report directory.",
            ])

        return "\n".join(lines)

    # Unknown topic
    return f"Unknown help topic: {topic}\nUse 'help' to see available commands."


def list_commands() -> list[str]:
    """List all available command strings.

    Returns:
        List of command strings (e.g., ["provider list", "provider recommend", ...])
    """
    return AVAILABLE_COMMANDS.copy()

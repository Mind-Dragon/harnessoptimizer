"""QUAL-3: Verify no print() calls in partition 3 production code.

Also verifies that logging is properly configured with module-level loggers.
CLI modules (budget/commands, extensions/verify_contracts) are allowed
print() for user-facing stdout/stderr output.
"""
from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "hermesoptimizer"

# CLI modules that legitimately need print() for user-facing output
CLI_MODULES = {
    "brain_doctor.py",
    "budget/commands.py",
    "extensions/verify_contracts.py",
}

PARTITION_FILES = [
    "__init__.py",
    "brain_doctor.py",
    "budget/__init__.py",
    "budget/commands.py",
    "budget/profile.py",
    "budget/recommender.py",
    "budget/tuner.py",
    "caveman/__init__.py",
    "config_watcher.py",
    "dreams/decay.py",
    "dreams/fidelity.py",
    "extensions/__init__.py",
    "extensions/loader.py",
    "extensions/resolver.py",
    "extensions/verify_contracts.py",
    "network/scanner.py",
    "paths.py",
    "route/diagnosis.py",
    "schemas/__init__.py",
    "schemas/exceptions.py",
    "scrape/exa_scraper.py",
    "sources/hermes_config.py",
    "sources/hermes_discover.py",
    "sources/hermes_inventory.py",
    "sources/hermes_sessions.py",
    "sources/model_catalog.py",
    "sources/model_plan_truth.py",
    "sources/modelscope_catalog.py",
    "sources/provider_registry.py",
    "tool_surface/provider_recommend.py",
    "tools/__init__.py",
    "tools/analyzer.py",
    "vault/providers/__init__.py",
    "vault/rotation.py",
    "vault/session.py",
    "verify/hot_reload.py",
    "workflow/executor.py",
    "workflow/schema.py",
]

NON_CLI_FILES = [f for f in PARTITION_FILES if f not in CLI_MODULES]


class _PrintCallFinder(ast.NodeVisitor):
    """AST visitor to find bare print() calls in production code."""

    def __init__(self) -> None:
        self.print_calls: list[tuple[int, str]] = []

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id == "print":
            line = node.lineno
            args = []
            for arg in node.args[:2]:
                if isinstance(arg, ast.Constant):
                    args.append(str(arg.value)[:40])
                else:
                    args.append("<expr>")
            context = f"print({', '.join(args)})"
            self.print_calls.append((line, context))
        self.generic_visit(node)


@pytest.fixture(params=NON_CLI_FILES, ids=lambda x: x.split("/")[-1])
def source_file(request) -> Path:
    return SRC_ROOT / request.param


class TestNoPrintInProduction:
    """Non-CLI production code must use logging, not print()."""

    def test_no_print_calls(self, source_file: Path) -> None:
        if not source_file.exists():
            pytest.skip(f"File not found: {source_file}")

        source = source_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(source_file))

        finder = _PrintCallFinder()
        finder.visit(tree)

        assert not finder.print_calls, (
            f"{source_file.relative_to(SRC_ROOT)} has print() calls on lines: "
            f"{finder.print_calls}"
        )


class TestLoggingConfigured:
    """Files that previously had print() should have logger = logging.getLogger(__name__)."""

    PRINT_PRONE_FILES = [
        "brain_doctor.py",
        "budget/commands.py",
        "extensions/verify_contracts.py",
        "vault/session.py",
    ]

    @pytest.fixture(params=PRINT_PRONE_FILES, ids=lambda x: x)
    def logging_file(self, request) -> Path:
        return SRC_ROOT / request.param

    def test_has_module_logger(self, logging_file: Path) -> None:
        source = logging_file.read_text(encoding="utf-8")
        assert "logging.getLogger(__name__)" in source, (
            f"{logging_file.name} missing 'logger = logging.getLogger(__name__)'"
        )
        assert "import logging" in source, (
            f"{logging_file.name} missing 'import logging'"
        )

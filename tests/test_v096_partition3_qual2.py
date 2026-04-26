"""QUAL-2: Verify module-level docstrings exist for all partition 3 files.

Every Python module should have a docstring describing its purpose,
key exports, and usage notes (Google/NumPy style).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "hermesoptimizer"

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


def _get_module_docstring(source: str) -> str | None:
    """Extract the module-level docstring from Python source."""
    tree = ast.parse(source)
    return ast.get_docstring(tree)


@pytest.fixture(params=PARTITION_FILES, ids=lambda x: x.split("/")[-1])
def source_file(request) -> Path:
    return SRC_ROOT / request.param


class TestModuleDocstrings:
    """Every module must have a docstring."""

    def test_module_has_docstring(self, source_file: Path) -> None:
        if not source_file.exists():
            pytest.skip(f"File not found: {source_file}")

        source = source_file.read_text(encoding="utf-8")
        docstring = _get_module_docstring(source)

        assert docstring is not None, (
            f"{source_file.relative_to(SRC_ROOT)} is missing a module-level docstring"
        )
        assert len(docstring.strip()) >= 10, (
            f"{source_file.relative_to(SRC_ROOT)} has a trivially short docstring: "
            f"'{docstring.strip()[:50]}'"
        )

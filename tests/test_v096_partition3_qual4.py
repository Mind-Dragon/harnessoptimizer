"""QUAL-4: Verify type hint coverage for partition 3 files.

Checks that all public functions/methods in partition 3 source files
have complete type annotations on their signatures.
"""
from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path
from typing import Protocol

import pytest

# Partition 3 files under src/hermesoptimizer/
PARTITION_FILES = [
    "hermesoptimizer.__init__",
    "hermesoptimizer.brain_doctor",
    "hermesoptimizer.budget",
    "hermesoptimizer.budget.commands",
    "hermesoptimizer.budget.profile",
    "hermesoptimizer.budget.recommender",
    "hermesoptimizer.budget.tuner",
    "hermesoptimizer.caveman",
    "hermesoptimizer.config_watcher",
    "hermesoptimizer.dreams.decay",
    "hermesoptimizer.dreams.fidelity",
    "hermesoptimizer.extensions",
    "hermesoptimizer.extensions.loader",
    "hermesoptimizer.extensions.resolver",
    "hermesoptimizer.extensions.verify_contracts",
    "hermesoptimizer.network.scanner",
    "hermesoptimizer.paths",
    "hermesoptimizer.route.diagnosis",
    "hermesoptimizer.schemas",
    "hermesoptimizer.schemas.exceptions",
    "hermesoptimizer.scrape.exa_scraper",
    "hermesoptimizer.sources.hermes_config",
    "hermesoptimizer.sources.hermes_discover",
    "hermesoptimizer.sources.hermes_inventory",
    "hermesoptimizer.sources.hermes_sessions",
    "hermesoptimizer.sources.model_catalog",
    "hermesoptimizer.sources.model_plan_truth",
    "hermesoptimizer.sources.modelscope_catalog",
    "hermesoptimizer.sources.provider_registry",
    "hermesoptimizer.tool_surface.provider_recommend",
    "hermesoptimizer.tools",
    "hermesoptimizer.tools.analyzer",
    "hermesoptimizer.vault.providers",
    "hermesoptimizer.vault.rotation",
    "hermesoptimizer.vault.session",
    "hermesoptimizer.verify.hot_reload",
    "hermesoptimizer.workflow.executor",
    "hermesoptimizer.workflow.schema",
]


def _is_public(name: str) -> bool:
    return not name.startswith("_")


def _has_type_hints(func) -> bool:
    """Check if a function has return annotation and parameter annotations."""
    sig = inspect.signature(func)
    params = sig.parameters

    # Skip 'self', 'cls', *args, **kwargs
    for pname, param in params.items():
        if pname in ("self", "cls"):
            continue
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        # Parameter must have annotation
        if param.annotation is inspect.Parameter.empty:
            return False

    # Return must be annotated
    if sig.return_annotation is inspect.Signature.empty:
        return False

    return True


@pytest.fixture(params=PARTITION_FILES, ids=lambda x: x.split(".")[-1])
def module(request):
    try:
        return importlib.import_module(request.param)
    except ImportError:
        pytest.skip(f"Cannot import {request.param}")


class TestTypeHints:
    """Verify public functions/methods have type annotations."""

    def test_public_functions_have_annotations(self, module):
        missing = []
        for name, obj in inspect.getmembers(module, inspect.isfunction):
            if not _is_public(name):
                continue
            # Only check functions defined in this module (not re-exports)
            if obj.__module__ != module.__name__:
                continue
            if not _has_type_hints(obj):
                missing.append(name)

        assert not missing, (
            f"Module {module.__name__}: functions missing type hints: {missing}"
        )

    def test_public_classes_have_annotated_methods(self, module):
        missing = []
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if not _is_public(name):
                continue
            if obj.__module__ != module.__name__:
                continue
            # Skip Protocol classes (their __init__ is synthetic)
            if issubclass(obj, Protocol):
                continue
            for mname, method in inspect.getmembers(obj, inspect.isfunction):
                if mname.startswith("_") and mname not in ("__init__",):
                    continue
                if not _has_type_hints(method):
                    missing.append(f"{name}.{mname}")

        assert not missing, (
            f"Module {module.__name__}: methods missing type hints: {missing}"
        )


class TestTypingImports:
    """Verify each module has from __future__ import annotations."""

    def test_future_annotations(self, module):
        # Skip pure re-export modules (no local source)
        source_file = getattr(module, "__file__", None)
        if source_file is None:
            pytest.skip("Compiled/builtin module")
        source = inspect.getsource(module)
        assert "from __future__ import annotations" in source, (
            f"Module {module.__name__} missing 'from __future__ import annotations'"
        )

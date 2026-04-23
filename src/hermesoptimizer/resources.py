"""Package resource helpers for HermesOptimizer data files."""

from __future__ import annotations

import importlib.resources
import json
from pathlib import Path
from typing import Any

from hermesoptimizer.paths import get_data_dir


def read_package_json(package_path: str, filename: str) -> dict[str, Any] | None:
    """Read JSON from package data with runtime-cache fallback.

    Lookup order:
    1. importlib.resources package data, works for wheel/editable installs.
    2. source-tree data beside this module, useful during local development.
    3. runtime data cache under HOPTIMIZER_HOME/`~/.hoptimizer`.
    """
    try:
        resource = importlib.resources.files(package_path).joinpath(filename)
        if resource.is_file():
            return json.loads(resource.read_text(encoding="utf-8"))
    except (FileNotFoundError, ModuleNotFoundError, json.JSONDecodeError, OSError):
        pass

    source_data = Path(__file__).resolve().parent / "data" / filename
    if source_data.exists():
        return json.loads(source_data.read_text(encoding="utf-8"))

    runtime_data = get_data_dir() / filename
    if runtime_data.exists():
        return json.loads(runtime_data.read_text(encoding="utf-8"))

    return None


def read_provider_registry() -> dict[str, Any] | None:
    """Load bundled provider registry seed data."""
    return read_package_json("hermesoptimizer.data", "provider_registry.seed.json")


def read_schema() -> dict[str, Any] | None:
    """Load bundled provider registry schema."""
    return read_package_json("hermesoptimizer.data", "provider_registry.schema.json")


def read_provider_endpoints() -> dict[str, Any] | None:
    """Load bundled provider endpoint catalog data."""
    return read_package_json("hermesoptimizer.data", "provider_endpoints.json")


def read_provider_models() -> dict[str, Any] | None:
    """Load bundled provider model catalog data."""
    return read_package_json("hermesoptimizer.data", "provider_models.json")

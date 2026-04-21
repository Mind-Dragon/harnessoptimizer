"""Load and validate extension registry from per-extension YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from hermesoptimizer.extensions.schema import ExtensionEntry, ExtensionType, Ownership


class RegistryValidationError(Exception):
    """Raised when registry validation fails."""


class DuplicateIdError(RegistryValidationError):
    """Raised when two extensions share the same id."""


class MissingFieldError(RegistryValidationError):
    """Raised when a required field is missing."""


def _coerce_extension_type(raw: str) -> ExtensionType:
    try:
        return ExtensionType(raw)
    except ValueError as exc:
        raise RegistryValidationError(f"Invalid extension type: {raw!r}") from exc


def _coerce_ownership(raw: str) -> Ownership:
    try:
        return Ownership(raw)
    except ValueError as exc:
        raise RegistryValidationError(f"Invalid ownership: {raw!r}") from exc


def load_extension_file(path: Path) -> ExtensionEntry:
    """Load a single extension definition from YAML."""
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise RegistryValidationError(f"Extension file {path} must contain a YAML mapping")

    required = {"id", "type", "description", "source_path"}
    missing = required - data.keys()
    if missing:
        raise MissingFieldError(
            f"Extension file {path} missing required fields: {sorted(missing)}"
        )

    return ExtensionEntry(
        id=data["id"],
        type=_coerce_extension_type(data["type"]),
        description=data["description"],
        source_path=data["source_path"],
        target_paths=data.get("target_paths", []),
        verify_command=data.get("verify_command"),
        ownership=_coerce_ownership(data.get("ownership", "repo_only")),
        metadata=data.get("metadata", {}),
    )


def load_registry(directory: Path) -> list[ExtensionEntry]:
    """Load all extension definitions from a directory of YAML files."""
    entries: list[ExtensionEntry] = []
    for path in sorted(directory.glob("*.yaml")):
        entries.append(load_extension_file(path))
    return entries


def validate_registry(entries: list[ExtensionEntry]) -> None:
    """Validate a list of extension entries."""
    seen: set[str] = set()
    for entry in entries:
        if entry.id in seen:
            raise DuplicateIdError(f"Duplicate extension id: {entry.id}")
        seen.add(entry.id)


def build_registry(directory: Path) -> list[ExtensionEntry]:
    """Load and validate all extensions from a directory."""
    entries = load_registry(directory)
    validate_registry(entries)
    return entries

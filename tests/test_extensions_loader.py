from __future__ import annotations

import pytest
from pathlib import Path

from hermesoptimizer.extensions.loader import (
    DuplicateIdError,
    MissingFieldError,
    RegistryValidationError,
    build_registry,
    load_extension_file,
    load_registry,
    validate_registry,
)
from hermesoptimizer.extensions.schema import ExtensionEntry, ExtensionType, Ownership


class TestLoadExtensionFile:
    def test_loads_valid_extension(self, tmp_path: Path) -> None:
        path = tmp_path / "caveman.yaml"
        path.write_text(
            """
id: caveman
type: config
description: Caveman output compression
source_path: src/hermesoptimizer/caveman/__init__.py
ownership: repo_only
"""
        )
        entry = load_extension_file(path)
        assert entry.id == "caveman"
        assert entry.type == ExtensionType.CONFIG
        assert entry.ownership == Ownership.REPO_ONLY

    def test_loads_full_extension(self, tmp_path: Path) -> None:
        path = tmp_path / "dreams.yaml"
        path.write_text(
            """
id: dreams
type: sidecar
description: Dreams memory sidecar
source_path: src/hermesoptimizer/dreams/
target_paths:
  - ~/.hermes/dreams/
  - scripts/dreaming_pre_sweep.py
verify_command: python -m hermesoptimizer dreams-sweep --help
ownership: repo_external
selected: false
metadata:
  cron: true
"""
        )
        entry = load_extension_file(path)
        assert entry.id == "dreams"
        assert entry.type == ExtensionType.SIDECAR
        assert entry.target_paths == ["~/.hermes/dreams/", "scripts/dreaming_pre_sweep.py"]
        assert entry.verify_command == "python -m hermesoptimizer dreams-sweep --help"
        assert entry.ownership == Ownership.REPO_EXTERNAL
        assert entry.selected is False
        assert entry.metadata == {"cron": True}

    def test_missing_required_field_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text(
            """
id: bad
type: config
"""
        )
        with pytest.raises(MissingFieldError, match="missing required fields"):
            load_extension_file(path)

    def test_invalid_type_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text(
            """
id: bad
type: not_a_type
description: bad
source_path: src/x.py
"""
        )
        with pytest.raises(RegistryValidationError, match="Invalid extension type"):
            load_extension_file(path)

    def test_invalid_ownership_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text(
            """
id: bad
type: config
description: bad
source_path: src/x.py
ownership: not_an_owner
"""
        )
        with pytest.raises(RegistryValidationError, match="Invalid ownership"):
            load_extension_file(path)


class TestLoadRegistry:
    def test_loads_directory(self, tmp_path: Path) -> None:
        (tmp_path / "a.yaml").write_text(
            "id: a\ntype: config\ndescription: a\nsource_path: src/a.py\n"
        )
        (tmp_path / "b.yaml").write_text(
            "id: b\ntype: skill\ndescription: b\nsource_path: src/b.py\n"
        )
        entries = load_registry(tmp_path)
        assert len(entries) == 2
        assert {e.id for e in entries} == {"a", "b"}

    def test_empty_directory(self, tmp_path: Path) -> None:
        entries = load_registry(tmp_path)
        assert entries == []


class TestValidateRegistry:
    def test_valid_registry(self) -> None:
        entries = [
            ExtensionEntry(id="a", type=ExtensionType.CONFIG, description="a", source_path="src/a.py"),
            ExtensionEntry(id="b", type=ExtensionType.CONFIG, description="b", source_path="src/b.py"),
        ]
        validate_registry(entries)  # does not raise

    def test_duplicate_id_raises(self) -> None:
        entries = [
            ExtensionEntry(id="a", type=ExtensionType.CONFIG, description="a", source_path="src/a.py"),
            ExtensionEntry(id="a", type=ExtensionType.SKILL, description="b", source_path="src/b.py"),
        ]
        with pytest.raises(DuplicateIdError, match="Duplicate extension id: a"):
            validate_registry(entries)


class TestBuildRegistry:
    def test_builds_and_validates(self, tmp_path: Path) -> None:
        (tmp_path / "a.yaml").write_text(
            "id: a\ntype: config\ndescription: a\nsource_path: src/a.py\n"
        )
        entries = build_registry(tmp_path)
        assert len(entries) == 1
        assert entries[0].id == "a"

    def test_builds_detects_duplicate(self, tmp_path: Path) -> None:
        (tmp_path / "a.yaml").write_text(
            "id: dup\ntype: config\ndescription: a\nsource_path: src/a.py\n"
        )
        (tmp_path / "b.yaml").write_text(
            "id: dup\ntype: skill\ndescription: b\nsource_path: src/b.py\n"
        )
        with pytest.raises(DuplicateIdError, match="Duplicate extension id: dup"):
            build_registry(tmp_path)

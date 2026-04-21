from __future__ import annotations

import pytest

from hermesoptimizer.extensions.schema import ExtensionEntry, ExtensionType, Ownership


class TestExtensionEntry:
    def test_minimal_entry(self) -> None:
        e = ExtensionEntry(
            id="caveman",
            type=ExtensionType.CONFIG,
            description="Caveman mode config",
            source_path="src/hermesoptimizer/caveman/__init__.py",
        )
        assert e.id == "caveman"
        assert e.type == ExtensionType.CONFIG
        assert e.ownership == Ownership.REPO_ONLY
        assert e.target_paths == []
        assert e.verify_command is None

    def test_full_entry(self) -> None:
        e = ExtensionEntry(
            id="dreams",
            type=ExtensionType.SIDECAR,
            description="Dreams sidecar",
            source_path="src/hermesoptimizer/dreams/",
            target_paths=["~/.hermes/dreams/"],
            verify_command="python -m hermesoptimizer dreams-sweep --help",
            ownership=Ownership.REPO_EXTERNAL,
            metadata={"cron": True},
        )
        assert e.target_paths == ["~/.hermes/dreams/"]
        assert e.verify_command == "python -m hermesoptimizer dreams-sweep --help"
        assert e.ownership == Ownership.REPO_EXTERNAL
        assert e.metadata == {"cron": True}

    def test_empty_id_raises(self) -> None:
        with pytest.raises(ValueError, match="id must be non-empty"):
            ExtensionEntry(
                id="",
                type=ExtensionType.CONFIG,
                description="bad",
                source_path="src/x.py",
            )

    def test_empty_source_path_raises(self) -> None:
        with pytest.raises(ValueError, match="source_path must be non-empty"):
            ExtensionEntry(
                id="x",
                type=ExtensionType.CONFIG,
                description="bad",
                source_path="",
            )

    def test_source_exists_true(self, tmp_path) -> None:
        (tmp_path / "exists.py").write_text("pass")
        e = ExtensionEntry(
            id="x",
            type=ExtensionType.CONFIG,
            description="x",
            source_path="exists.py",
        )
        assert e.source_exists(tmp_path) is True

    def test_source_exists_false(self, tmp_path) -> None:
        e = ExtensionEntry(
            id="x",
            type=ExtensionType.CONFIG,
            description="x",
            source_path="missing.py",
        )
        assert e.source_exists(tmp_path) is False


class TestExtensionType:
    def test_enum_values(self) -> None:
        assert ExtensionType.CONFIG.value == "config"
        assert ExtensionType.SKILL.value == "skill"
        assert ExtensionType.VAULT_PLUGIN.value == "vault_plugin"


class TestOwnership:
    def test_enum_values(self) -> None:
        assert Ownership.REPO_ONLY.value == "repo_only"
        assert Ownership.EXTERNAL_RUNTIME.value == "external_runtime"

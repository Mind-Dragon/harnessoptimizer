"""Installed-artifact smoke tests.

These tests verify that important scripts and skills installed under
~/.hermes/ are present and have the expected structure. They run in
an isolated HERMES_HOME sandbox and never touch the operator's real state.

Layer: L3 (plugin + installed-artifact smoke)
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest


@pytest.fixture()
def isolated_hermes_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temp HERMES_HOME and set env vars."""
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / "scripts").mkdir()
    (home / "skills").mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("HOME", str(tmp_path))
    return home


@pytest.fixture()
def seeded_hermes_home(isolated_hermes_home: Path) -> Path:
    """Seed the isolated HERMES_HOME with copies of installed artifacts."""
    real_scripts = Path.home() / ".hermes" / "scripts"
    real_skills = Path.home() / ".hermes" / "skills"

    # Copy dreaming reflection script if it exists
    dreaming_script = real_scripts / "dreaming_reflection_context.py"
    if dreaming_script.exists():
        shutil.copy2(dreaming_script, isolated_hermes_home / "scripts" / "dreaming_reflection_context.py")

    # Copy supermemory store if it exists
    supermemory_script = real_scripts / "supermemory_store.js"
    if supermemory_script.exists():
        shutil.copy2(supermemory_script, isolated_hermes_home / "scripts" / "supermemory_store.js")

    return isolated_hermes_home


class TestInstalledScriptArtifacts:
    """Smoke tests for scripts installed under ~/.hermes/scripts/."""

    def test_dreaming_reflection_script_exists_in_production(self) -> None:
        """The dreaming reflection context builder should exist in production."""
        real_path = Path.home() / ".hermes" / "scripts" / "dreaming_reflection_context.py"
        if not real_path.exists():
            pytest.skip("dreaming_reflection_context.py not installed in production HERMES_HOME")
        assert real_path.is_file()

    def test_dreaming_reflection_script_is_python(self) -> None:
        """The dreaming reflection script should be valid Python."""
        real_path = Path.home() / ".hermes" / "scripts" / "dreaming_reflection_context.py"
        if not real_path.exists():
            pytest.skip("dreaming_reflection_context.py not installed")
        content = real_path.read_text()
        # Should have Python shebang or imports
        assert "#!/" in content[:50] or "import " in content[:500] or "def " in content[:1000]

    def test_supermemory_store_script_exists_in_production(self) -> None:
        """The supermemory store integration script should exist in production."""
        real_path = Path.home() / ".hermes" / "scripts" / "supermemory_store.js"
        if not real_path.exists():
            pytest.skip("supermemory_store.js not installed in production HERMES_HOME")
        assert real_path.is_file()

    def test_seeded_dreaming_script_accessible_in_sandbox(
        self, seeded_hermes_home: Path
    ) -> None:
        """The seeded dreaming script should be accessible in the sandbox."""
        script = seeded_hermes_home / "scripts" / "dreaming_reflection_context.py"
        if not script.exists():
            pytest.skip("dreaming_reflection_context.py not available for seeding")
        assert script.is_file()
        assert len(script.read_text()) > 100

    def test_hermes_home_env_resolution(self, isolated_hermes_home: Path) -> None:
        """HERMES_HOME env var should resolve to the sandbox."""
        assert os.environ.get("HERMES_HOME") == str(isolated_hermes_home)

    def test_scripts_dir_created_in_sandbox(self, isolated_hermes_home: Path) -> None:
        """The scripts directory should exist in the sandbox."""
        assert (isolated_hermes_home / "scripts").is_dir()

    def test_skills_dir_created_in_sandbox(self, isolated_hermes_home: Path) -> None:
        """The skills directory should exist in the sandbox."""
        assert (isolated_hermes_home / "skills").is_dir()


class TestInstalledSkillArtifacts:
    """Smoke tests for skills installed under ~/.hermes/skills/."""

    def test_skills_directory_exists_in_production(self) -> None:
        """The production skills directory should exist."""
        real_path = Path.home() / ".hermes" / "skills"
        if not real_path.exists():
            pytest.skip("~/.hermes/skills/ not found")
        assert real_path.is_dir()

    def test_dreaming_skill_exists_in_production(self) -> None:
        """The dreaming skill directory should exist if installed."""
        real_path = Path.home() / ".hermes" / "skills" / "dogfood" / "dreaming"
        if not real_path.exists():
            # Try alternate paths
            alt = Path.home() / ".hermes" / "skills" / "dreaming"
            if not alt.exists():
                pytest.skip("dreaming skill not installed")
            assert alt.is_dir()
        else:
            assert real_path.is_dir()

    def test_dreaming_skill_has_content(self) -> None:
        """The dreaming skill should have SKILL.md or equivalent."""
        base = Path.home() / ".hermes" / "skills"
        candidates = [
            base / "dogfood" / "dreaming",
            base / "dreaming",
        ]
        skill_dir = None
        for c in candidates:
            if c.exists():
                skill_dir = c
                break
        if skill_dir is None:
            pytest.skip("dreaming skill not installed")
        
        files = list(skill_dir.iterdir())
        assert len(files) > 0, "dreaming skill directory is empty"
        # Should have at least a SKILL.md or .md file
        md_files = [f for f in files if f.suffix == ".md"]
        assert len(md_files) > 0, f"no .md files in {skill_dir}, found: {[f.name for f in files]}"


class TestPluginCrossCompatibility:
    """Verify plugin matrix works on shared temp vault fixtures."""

    def test_plugins_use_temp_vault_not_production(self) -> None:
        """Sanity check: plugin tests should reference tmp_path, not ~/.vault."""
        plugin_test = Path(__file__).parent / "test_vault_plugins.py"
        content = plugin_test.read_text()
        assert "tmp_path" in content or "temp_vault" in content, \
            "Plugin tests should use temp fixtures"
        assert "~/.vault" not in content, \
            "Plugin tests must not reference production ~/.vault"

    def test_integration_tests_use_temp_vault(self) -> None:
        """Sanity check: integration tests should use temp fixtures."""
        int_test = Path(__file__).parent / "test_vault_integration.py"
        content = int_test.read_text()
        assert "tmp_path" in content or "temp_vault" in content, \
            "Integration tests should use temp fixtures"
        assert "~/.vault" not in content, \
            "Integration tests must not reference production ~/.vault"

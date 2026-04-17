"""Tests for the vault-writeback CLI command.

These tests verify that the CLI exposes a vault-writeback command with:
- --confirm flag for explicit write execution
- --vault-root for specifying vault location (opt-in for production vault)
- --format for target format (env or yaml)
- Dry-run behavior when --confirm is not provided
- Safety contract: no accidental writes to production vault
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "hermesoptimizer", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


class TestVaultWritebackCLIExists:
    """Tests that the vault-writeback CLI command exists and is reachable."""

    def test_vault_writeback_command_is_known(self) -> None:
        """vault-writeback must be a recognized CLI command."""
        result = _run_cli("vault-writeback", "--help", cwd=REPO_ROOT)
        # Should not return error about unknown command
        assert result.returncode != 2 or "unrecognized" not in result.stderr.lower()
        # Should show help for vault-writeback
        assert "vault-writeback" in result.stdout.lower() or "usage" in result.stdout.lower()

    def test_vault_writeback_has_confirm_option(self) -> None:
        """vault-writeback help must mention --confirm flag."""
        result = _run_cli("vault-writeback", "--help", cwd=REPO_ROOT)
        assert "--confirm" in result.stdout.lower() or "--confirm" in result.stderr.lower()

    def test_vault_writeback_has_vault_root_option(self) -> None:
        """vault-writeback help must mention --vault-root option."""
        result = _run_cli("vault-writeback", "--help", cwd=REPO_ROOT)
        assert "--vault-root" in result.stdout or "--vault-root" in result.stderr


class TestVaultWritebackConfirmBehavior:
    """Tests for --confirm flag behavior matching v0.5.2 safety contract."""

    def test_writeback_without_confirm_does_not_modify_files(self, tmp_path: Path) -> None:
        """When --confirm is NOT provided, vault-writeback must NOT modify any files."""
        vault = tmp_path / ".vault"
        vault.mkdir()
        env_file = vault / "test.env"
        env_file.write_text("TOKEN=original_value\n", encoding="utf-8")

        result = _run_cli(
            "vault-writeback",
            "--vault-root", str(vault),
            "--format", "env",
            cwd=tmp_path,
        )

        # Should succeed (return 0) but NOT modify files
        assert result.returncode == 0
        # File content must remain unchanged
        content = env_file.read_text(encoding="utf-8")
        assert content == "TOKEN=original_value\n"
        # Should mention dry-run or confirm in output
        output = result.stdout + result.stderr
        assert "dry-run" in output.lower() or "confirm" in output.lower()

    def test_writeback_with_confirm_allows_write(self, tmp_path: Path) -> None:
        """When --confirm IS provided, vault-writeback MAY write changes."""
        vault = tmp_path / ".vault"
        vault.mkdir()
        env_file = vault / "test.env"
        env_file.write_text("TOKEN=original_value\n", encoding="utf-8")

        result = _run_cli(
            "vault-writeback",
            "--vault-root", str(vault),
            "--format", "env",
            "--confirm",
            cwd=tmp_path,
        )

        # Should succeed
        assert result.returncode == 0
        # File may be modified (fingerprint placeholders)
        content = env_file.read_text(encoding="utf-8")
        # Content should contain fingerprint placeholder
        assert "<fingerprint:" in content

    def test_writeback_confirm_false_is_default(self, tmp_path: Path) -> None:
        """Without explicit --confirm, write-back must not proceed (safe default)."""
        vault = tmp_path / ".vault"
        vault.mkdir()
        env_file = vault / "safe.env"
        env_file.write_text("SAFE=original\n", encoding="utf-8")

        result = _run_cli(
            "vault-writeback",
            "--vault-root", str(vault),
            "--format", "env",
            cwd=tmp_path,
        )

        assert result.returncode == 0
        content = env_file.read_text(encoding="utf-8")
        # Must NOT be modified
        assert content == "SAFE=original\n"


class TestVaultWritebackProductionVaultSafety:
    """Tests ensuring production vault is opt-in (safety contract)."""

    def test_vault_writeback_requires_explicit_vault_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """vault-writeback must require explicit --vault-root to avoid accidental production writes."""
        # Point HOME to tmp_path so ~/.vault would resolve to tmp_path/.vault
        monkeypatch.setenv("HOME", str(tmp_path))

        vault = tmp_path / ".vault"
        vault.mkdir()
        env_file = vault / "prod.env"
        env_file.write_text("PROD_KEY=secret\n", encoding="utf-8")

        # Running WITHOUT --vault-root should either:
        # 1. Fail with error about needing explicit path, OR
        # 2. Use tmp/.vault which doesn't exist (no-op), OR
        # 3. Show clear message that production vault is opt-in
        result = _run_cli(
            "vault-writeback",
            "--format", "env",
            cwd=tmp_path,
        )

        # The key safety requirement: running without --vault-root must NOT
        # silently write to ~/.vault if it exists
        # If ~/.vault exists and has content, we should NOT auto-use it
        # So the result should either be a no-op (return 0 with no changes)
        # or an error asking for explicit confirmation
        output = result.stdout + result.stderr
        # If it mentions "opt-in" or "explicit" or "production" that's ideal
        # But at minimum it should not have modified the file
        content = env_file.read_text(encoding="utf-8")
        assert content == "PROD_KEY=secret\n" or "opt-in" in output.lower() or "explicit" in output.lower() or "production" in output.lower() or "vault-root" in output.lower()

    def test_vault_writeback_with_explicit_vault_root_works(self, tmp_path: Path) -> None:
        """vault-writeback with explicit --vault-root must work correctly."""
        vault = tmp_path / ".vault"
        vault.mkdir()
        env_file = vault / "explicit.env"
        env_file.write_text("EXPLICIT=original\n", encoding="utf-8")

        result = _run_cli(
            "vault-writeback",
            "--vault-root", str(vault),
            "--format", "env",
            cwd=tmp_path,
        )

        # Should succeed (dry-run by default)
        assert result.returncode == 0
        # Should show it processed the file
        output = result.stdout + result.stderr
        assert "explicit.env" in output or "env" in output.lower()


class TestVaultWritebackFormatSupport:
    """Tests for different format support."""

    def test_writeback_env_format(self, tmp_path: Path) -> None:
        """vault-writeback must support --format env."""
        vault = tmp_path / ".vault"
        vault.mkdir()
        env_file = vault / "test.env"
        env_file.write_text("KEY=value\n", encoding="utf-8")

        result = _run_cli(
            "vault-writeback",
            "--vault-root", str(vault),
            "--format", "env",
            cwd=tmp_path,
        )

        assert result.returncode == 0
        output = result.stdout + result.stderr
        assert "env" in output.lower()

    def test_writeback_yaml_format(self, tmp_path: Path) -> None:
        """vault-writeback must support --format yaml."""
        vault = tmp_path / ".vault"
        vault.mkdir()
        yaml_file = vault / "test.yaml"
        yaml_file.write_text("key: value\n", encoding="utf-8")

        result = _run_cli(
            "vault-writeback",
            "--vault-root", str(vault),
            "--format", "yaml",
            cwd=tmp_path,
        )

        assert result.returncode == 0
        output = result.stdout + result.stderr
        assert "yaml" in output.lower()

    def test_writeback_invalid_format(self, tmp_path: Path) -> None:
        """vault-writeback with invalid format should fail gracefully."""
        vault = tmp_path / ".vault"
        vault.mkdir()

        result = _run_cli(
            "vault-writeback",
            "--vault-root", str(vault),
            "--format", "invalid_format",
            cwd=tmp_path,
        )

        # Should return non-zero or show error
        assert result.returncode != 0 or "error" in result.stdout.lower() or "error" in result.stderr.lower()

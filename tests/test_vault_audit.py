"""Tests for the vault-audit CLI command."""
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


def test_vault_audit_missing_root(capsys: pytest.CaptureFixture) -> None:
    """vault-audit with a non-existent root returns 0 with empty inventory."""
    result = _run_cli(
        "vault-audit",
        "--vault-root",
        "/nonexistent/vault/path",
        cwd=REPO_ROOT,
    )
    # Non-existent vault root is treated as empty vault (valid case)
    assert result.returncode == 0
    assert "total entries: 0" in result.stdout.lower()


def test_vault_audit_empty_vault(tmp_path: Path) -> None:
    """vault-audit on an empty vault root succeeds and reports zero entries."""
    vault = tmp_path / ".vault"
    vault.mkdir()

    result = _run_cli(
        "vault-audit",
        "--vault-root",
        str(vault),
        cwd=tmp_path,
    )
    assert result.returncode == 0
    assert "total entries: 0" in result.stdout.lower()


def test_vault_audit_single_entry(tmp_path: Path) -> None:
    """vault-audit on a vault with one entry reports it."""
    vault = tmp_path / ".vault"
    vault.mkdir()
    env_file = vault / "test.env"
    env_file.write_text("MY_KEY=my_value\n", encoding="utf-8")

    result = _run_cli(
        "vault-audit",
        "--vault-root",
        str(vault),
        cwd=tmp_path,
    )
    assert result.returncode == 0
    assert "total entries: 1" in result.stdout.lower()
    assert "my_key" in result.stdout.lower()


def test_vault_audit_dedup_summary(tmp_path: Path) -> None:
    """vault-audit shows dedup summary when duplicate fingerprints exist."""
    vault = tmp_path / ".vault"
    vault.mkdir()
    env1 = vault / "a.env"
    env2 = vault / "b.env"
    env1.write_text("TOKEN=abc123\n", encoding="utf-8")
    env2.write_text("TOKEN=abc123\n", encoding="utf-8")

    result = _run_cli(
        "vault-audit",
        "--vault-root",
        str(vault),
        cwd=tmp_path,
    )
    assert result.returncode == 0
    # Should show duplicate groups
    assert "dedup" in result.stdout.lower() or "duplicate" in result.stdout.lower()


def test_vault_audit_with_report(tmp_path: Path) -> None:
    """vault-audit --report writes a simple text report."""
    vault = tmp_path / ".vault"
    vault.mkdir()
    env_file = vault / "test.env"
    env_file.write_text("MY_KEY=my_value\n", encoding="utf-8")
    report_path = tmp_path / "audit_report.txt"

    result = _run_cli(
        "vault-audit",
        "--vault-root",
        str(vault),
        "--report",
        str(report_path),
        cwd=tmp_path,
    )
    assert result.returncode == 0
    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert "my_key" in content.lower()


def test_vault_audit_stale_entry(tmp_path: Path) -> None:
    """vault-audit marks stale entries in its validation output."""
    vault = tmp_path / ".vault"
    vault.mkdir()
    stale_file = vault / "stale.env"
    stale_file.write_text("OLD_KEY=old_value\n", encoding="utf-8")

    # Make file appear old
    import time
    old_time = time.time() - (90 * 24 * 60 * 60)
    os.utime(stale_file, (old_time, old_time))

    result = _run_cli(
        "vault-audit",
        "--vault-root",
        str(vault),
        cwd=tmp_path,
    )
    assert result.returncode == 0
    # Stale entries should be reported
    assert "stale" in result.stdout.lower() or "validation" in result.stdout.lower()


def test_vault_audit_default_vault_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """vault-audit uses default vault root (~/.vault) when no --vault-root given."""
    # Point HOME to tmp_path so ~/.vault resolves to tmp_path/.vault
    monkeypatch.setenv("HOME", str(tmp_path))

    vault = tmp_path / ".vault"
    vault.mkdir()
    env_file = vault / "default.env"
    env_file.write_text("DEFAULT_KEY=default_value\n", encoding="utf-8")

    # Run without --vault-root
    result = _run_cli(
        "vault-audit",
        cwd=tmp_path,
    )
    assert result.returncode == 0
    assert "default_key" in result.stdout.lower()

"""Tests for caveman CLI command."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the CLI with given args."""
    env = dict(**subprocess.os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "hermesoptimizer", *args],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_caveman_command_toggles_mode() -> None:
    """caveman command should toggle mode and report state."""
    # First call: should turn ON
    result = _run_cli("caveman")
    assert result.returncode == 0
    assert "caveman mode: ON" in result.stdout or "caveman mode: OFF" in result.stdout

    # Second call: should toggle to opposite state
    result = _run_cli("caveman")
    assert result.returncode == 0
    assert "caveman mode:" in result.stdout


def test_caveman_command_help_shows_caveman() -> None:
    """Help output should include caveman command."""
    result = _run_cli()
    assert result.returncode == 1
    assert "caveman" in result.stdout.lower()

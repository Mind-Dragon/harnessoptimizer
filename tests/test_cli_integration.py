from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args: str, cwd: Path, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-m", "hermesoptimizer", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_verify_endpoints_subprocess_smoke(tmp_path: Path) -> None:
    result = _run_cli(
        "verify-endpoints",
        "--provider",
        "openai",
        "--endpoint",
        "https://api.openai.com/v1",
        "--model",
        "gpt-5",
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    assert "not yet implemented" not in result.stdout.lower()
    assert "status:" in result.stdout.lower()


def test_dreams_sweep_subprocess_smoke(tmp_path: Path) -> None:
    output_path = tmp_path / "dreams-summary.json"
    result = _run_cli(
        "dreams-sweep",
        "--json-out",
        str(output_path),
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    assert "not yet implemented" not in result.stdout.lower()
    assert output_path.exists()
    assert "decisions" in output_path.read_text(encoding="utf-8")


def test_provider_recommend_subprocess_smoke(tmp_path: Path) -> None:
    result = _run_cli(
        "provider-recommend",
        "--capability",
        "text",
        "--lane",
        "general",
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    assert "placeholder" not in result.stdout.lower()
    assert "task 6" not in result.stdout.lower()
    assert "recommendation" in result.stdout.lower() or "provider" in result.stdout.lower()


def test_report_latest_uses_runtime_report_dir(tmp_path: Path) -> None:
    hoptimizer_home = tmp_path / "hopt-home"
    reports_dir = hoptimizer_home / "reports"
    reports_dir.mkdir(parents=True)
    (reports_dir / "sample.md").write_text("# Latest runtime report\n", encoding="utf-8")

    result = _run_cli(
        "report-latest",
        cwd=tmp_path,
        extra_env={"HOPTIMIZER_HOME": str(hoptimizer_home)},
    )

    assert result.returncode == 0, result.stderr
    assert "sample.md" in result.stdout
    assert "latest runtime report" in result.stdout.lower()

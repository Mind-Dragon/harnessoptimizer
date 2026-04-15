from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


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


def test_cli_init_add_export_smoke(tmp_path: Path) -> None:
    db = tmp_path / "catalog.db"
    out_dir = tmp_path / "reports"

    init = _run_cli("init-db", "--db", str(db), cwd=tmp_path)
    assert init.returncode == 0
    assert db.exists()
    assert "initialized" in init.stdout

    record = _run_cli(
        "add-record",
        "--db", str(db),
        "--provider", "openai",
        "--model", "gpt-5",
        "--base-url", "https://api.openai.com/v1",
        "--auth-type", "api_key",
        "--auth-key", "OPENAI_API_KEY",
        "--lane", "coding",
        "--capability", "text",
        cwd=tmp_path,
    )
    assert record.returncode == 0
    assert "record saved" in record.stdout

    finding = _run_cli(
        "add-finding",
        "--db", str(db),
        "--category", "log-signal",
        "--severity", "medium",
        "--file-path", "logs/app.log",
        "--line-num", "12",
        "--kind", "log-provider-failure",
        "--fingerprint", "logs/app.log:12",
        "--sample-text", "provider timeout",
        "--confidence", "high",
        "--router-note", "provider timeout observed",
        "--lane", "coding",
        cwd=tmp_path,
    )
    assert finding.returncode == 0
    assert "finding saved" in finding.stdout

    export = _run_cli(
        "export",
        "--db", str(db),
        "--out-dir", str(out_dir),
        "--title", "Smoke Test Report",
        cwd=tmp_path,
    )
    assert export.returncode == 0
    assert "wrote" in export.stdout
    assert (out_dir / "report.json").exists()
    assert (out_dir / "report.md").exists()

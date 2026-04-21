"""Extension verification: run verify_command for each extension."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from hermesoptimizer.extensions.schema import ExtensionEntry


@dataclass(frozen=True)
class VerifyResult:
    """Result of running an extension's verify_command."""

    id: str
    passed: bool
    exit_code: int
    stdout: str
    stderr: str
    command: str | None


def verify_extension(entry: ExtensionEntry, cwd: Path | None = None) -> VerifyResult:
    """Run the verify_command for one extension."""
    if not entry.verify_command:
        return VerifyResult(
            id=entry.id,
            passed=True,
            exit_code=0,
            stdout="",
            stderr="",
            command=None,
        )

    try:
        result = subprocess.run(
            entry.verify_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=cwd,
        )
        return VerifyResult(
            id=entry.id,
            passed=result.returncode == 0,
            exit_code=result.returncode,
            stdout=result.stdout.strip(),
            stderr=result.stderr.strip(),
            command=entry.verify_command,
        )
    except subprocess.TimeoutExpired:
        return VerifyResult(
            id=entry.id,
            passed=False,
            exit_code=-1,
            stdout="",
            stderr="verify_command timed out after 30s",
            command=entry.verify_command,
        )
    except Exception as exc:
        return VerifyResult(
            id=entry.id,
            passed=False,
            exit_code=-1,
            stdout="",
            stderr=str(exc),
            command=entry.verify_command,
        )


def verify_all(entries: list[ExtensionEntry], cwd: Path | None = None) -> list[VerifyResult]:
    """Run verification for all extensions."""
    return [verify_extension(e, cwd) for e in entries]

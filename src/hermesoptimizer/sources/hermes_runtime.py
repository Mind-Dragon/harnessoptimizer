"""
Phase 1 Hermes runtime and gateway health scanner.

Scans gateway health status by:
- Running the configured gateway status_command
- Parsing stdout/stderr for health indicators
- Surfacing findings for unhealthy/down gateway states

Also provides a runtime state scanner that checks for:
- Runtime lock files or PID files indicating a running process
- Runtime metadata files
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from hermesoptimizer.catalog import Finding

# Health indicators
_HEALTH_OK_PATTERNS = [
    "ok",
    "healthy",
    "status.*ok",
    "all.*systems.*go",
    "gateway.*up",
    "listening",
]
_UNHEALTHY_PATTERNS = [
    "down",
    "unhealthy",
    "failing",
    "error",
    "crash",
    "panic",
    "not.*responding",
    "connection.*refused",
    "refused",
]


def _matches_any(text: str, patterns: list[str]) -> bool:
    import re
    text_lower = text.lower()
    for p in patterns:
        if re.search(p, text_lower):
            return True
    return False


def _run_command(command: str) -> tuple[int, str, str]:
    """Run a shell command and return (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", "command timed out after 10s"
    except Exception as e:
        return -1, "", str(e)


def scan_gateway_health(commands: list[str]) -> list[Finding]:
    """
    Phase 1 scan of gateway health by running configured status commands.

    For each command in the list, runs it and produces findings based on output.
    """
    findings: list[Finding] = []
    for cmd in commands:
        returncode, stdout, stderr = _run_command(cmd)
        combined = f"{stdout}\n{stderr}".strip()

        if returncode != 0:
            findings.append(
                Finding(
                    file_path=cmd,
                    line_num=None,
                    category="gateway-signal",
                    severity="critical",
                    kind="gateway-down",
                    fingerprint=f"gateway:{cmd[:40]}",
                    sample_text=combined[:240] or f"exit code {returncode}",
                    count=1,
                    confidence="high",
                    router_note=f"gateway command failed: exit {returncode}",
                    lane=None,
                )
            )
            continue

        if _matches_any(combined, _UNHEALTHY_PATTERNS):
            findings.append(
                Finding(
                    file_path=cmd,
                    line_num=None,
                    category="gateway-signal",
                    severity="high",
                    kind="gateway-unhealthy",
                    fingerprint=f"gateway:{cmd[:40]}",
                    sample_text=combined[:240],
                    count=1,
                    confidence="medium",
                    router_note="gateway health check reports unhealthy state",
                    lane=None,
                )
            )
        elif _matches_any(combined, _HEALTH_OK_PATTERNS):
            # Health OK — no finding needed
            pass
        else:
            # Ambiguous — report at low confidence
            findings.append(
                Finding(
                    file_path=cmd,
                    line_num=None,
                    category="gateway-signal",
                    severity="low",
                    kind="gateway-unhealthy",
                    fingerprint=f"gateway:{cmd[:40]}",
                    sample_text=combined[:240],
                    count=1,
                    confidence="low",
                    router_note="gateway health output ambiguous",
                    lane=None,
                )
            )

    return findings


def scan_runtime_paths(paths: list[str | Path]) -> list[Finding]:
    """
    Phase 1 scan of runtime paths for evidence of running Hermes processes.

    Checks for:
    - Runtime lock/PID files
    - Runtime state files
    - Evidence of stale runtime (old timestamps)
    """
    findings: list[Finding] = []
    import time

    now = time.time()
    STALE_HOURS = 24 * 7  # 7 days

    for path in paths:
        p = Path(path) if isinstance(path, str) else path
        if not p.exists():
            continue

        # Check if directory or file
        if p.is_file():
            findings.append(
                Finding(
                    file_path=str(p),
                    line_num=None,
                    category="runtime-signal",
                    severity="info",
                    kind=None,
                    fingerprint=str(p),
                    sample_text=f"runtime file: {p.name}",
                    count=1,
                    confidence="low",
                    router_note=f"runtime file exists at {p}",
                    lane=None,
                )
            )
        elif p.is_dir():
            entries = list(p.iterdir())
            if not entries:
                findings.append(
                    Finding(
                        file_path=str(p),
                        line_num=None,
                        category="runtime-signal",
                        severity="low",
                        kind=None,
                        fingerprint=str(p),
                        sample_text="runtime directory is empty",
                        count=1,
                        confidence="medium",
                        router_note=f"runtime dir {p} has no contents",
                        lane=None,
                    )
                )
            for entry in entries:
                if entry.is_file() and entry.suffix in {".lock", ".pid", ".state"}:
                    age_seconds = now - entry.stat().st_mtime
                    if age_seconds > STALE_HOURS * 3600:
                        findings.append(
                            Finding(
                                file_path=str(entry),
                                line_num=None,
                                category="runtime-signal",
                                severity="low",
                                kind=None,
                                fingerprint=str(entry),
                                sample_text=f"stale runtime file: {entry.name}",
                                count=1,
                                confidence="medium",
                                router_note=f"runtime file {entry.name} is older than {STALE_HOURS}h",
                                lane=None,
                            )
                        )

    return findings

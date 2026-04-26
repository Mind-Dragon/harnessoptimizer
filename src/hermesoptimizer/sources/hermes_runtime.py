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
import shlex
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


def _run_command(command: str | list[str]) -> tuple[int, str, str]:
    """Run a command safely (no shell=True), return (rc, stdout, stderr).

    Accepts string (shlex.split) or list. shell=False prevents injection.
    """
    try:
        args = shlex.split(command) if isinstance(command, str) else command
        proc = subprocess.run(
            args,
            shell=False,
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


def scan_cli_status(commands: list[str]) -> list[Finding]:
    """
    Phase 1 scan of Hermes CLI health by running configured status commands.

    For each command in the list, runs it and produces findings based on output.
    """
    findings: list[Finding] = []
    unhealthy_markers = ["not logged in", "not configured", "error", "failed", "unauthorized", "denied"]
    healthy_markers = ["status", "healthy", "ok", "logged in", "running"]

    for cmd in commands:
        returncode, stdout, stderr = _run_command(cmd)
        combined = f"{stdout}\n{stderr}".strip()

        if returncode != 0:
            findings.append(
                Finding(
                    file_path=cmd,
                    line_num=None,
                    category="cli-signal",
                    severity="critical",
                    kind="cli-down",
                    fingerprint=f"cli:{cmd[:40]}",
                    sample_text=combined[:240] or f"exit code {returncode}",
                    count=1,
                    confidence="high",
                    router_note=f"CLI command failed: exit {returncode}",
                    lane=None,
                )
            )
            continue

        lowered = combined.lower()
        if any(marker in lowered for marker in unhealthy_markers):
            findings.append(
                Finding(
                    file_path=cmd,
                    line_num=None,
                    category="cli-signal",
                    severity="high",
                    kind="cli-unhealthy",
                    fingerprint=f"cli:{cmd[:40]}",
                    sample_text=combined[:240],
                    count=1,
                    confidence="medium",
                    router_note="CLI status reports unhealthy state",
                    lane=None,
                )
            )
        elif any(marker in lowered for marker in healthy_markers):
            pass
        else:
            findings.append(
                Finding(
                    file_path=cmd,
                    line_num=None,
                    category="cli-signal",
                    severity="low",
                    kind="cli-unhealthy",
                    fingerprint=f"cli:{cmd[:40]}",
                    sample_text=combined[:240],
                    count=1,
                    confidence="low",
                    router_note="CLI status output ambiguous",
                    lane=None,
                )
            )

    return findings


def scan_gateway_state_file(gateway_state_path: str | Path) -> list[Finding]:
    """
    Phase 1 scan of a gateway_state.json file as a first-class health source.

    Checks:
    - gateway_state field: running=good, stopped/error=finding
    - pid validity (process with that PID actually running)
    - restart_requested flag
    """
    findings: list[Finding] = []
    import os
    import json

    p = Path(gateway_state_path) if isinstance(gateway_state_path, str) else gateway_state_path
    if not p.exists():
        return findings

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return findings

    gateway_state = data.get("gateway_state", "")
    pid = data.get("pid")
    restart_requested = data.get("restart_requested", False)

    # Check gateway_state field
    if gateway_state == "running":
        pass  # healthy — no finding
    elif gateway_state in ("stopped", "error"):
        findings.append(
            Finding(
                file_path=str(p),
                line_num=None,
                category="gateway-signal",
                severity="critical",
                kind="gateway-down",
                fingerprint=f"gateway-state:{p}",
                sample_text=f"gateway_state={gateway_state}",
                count=1,
                confidence="high",
                router_note=f"gateway_state reports '{gateway_state}'",
                lane="A",
            )
        )

    # Check PID validity
    if pid is not None:
        try:
            pid_int = int(pid)
            if pid_int <= 0:
                raise ValueError("PID must be positive")
            # Send signal 0 to check if process exists (does not actually signal)
            os.kill(pid_int, 0)
        except (ValueError, OSError):
            findings.append(
                Finding(
                    file_path=str(p),
                    line_num=None,
                    category="gateway-signal",
                    severity="high",
                    kind="gateway-pid-invalid",
                    fingerprint=f"gateway-pid:{p}",
                    sample_text=f"pid={pid} is not a valid running process",
                    count=1,
                    confidence="high",
                    router_note=f"gateway PID {pid} is not valid or process is dead",
                    lane="A",
                )
            )

    # Check restart_requested flag
    if restart_requested:
        findings.append(
            Finding(
                file_path=str(p),
                line_num=None,
                category="gateway-signal",
                severity="medium",
                kind="gateway-restart-requested",
                fingerprint=f"gateway-restart:{p}",
                sample_text="restart_requested=true",
                count=1,
                confidence="high",
                router_note="gateway has restart_requested flag set",
                lane="A",
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

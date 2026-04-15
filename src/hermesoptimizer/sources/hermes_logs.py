"""
Phase 1 Hermes log scanner.

Parses Hermes log files and surfaces findings for:
- Auth failures (401, 403, unauthorized, auth failure)
- Provider failures (timeout, error, exception, retries)
- Runtime failures (worker crash, exception in thread, panic)
"""
from __future__ import annotations

import re
from pathlib import Path

from hermesoptimizer.catalog import Finding

# Regex patterns for each failure category
_AUTH_PATTERNS = [
    re.compile(r"401\s+Unauthorized", re.IGNORECASE),
    re.compile(r"403\s+Forbidden", re.IGNORECASE),
    re.compile(r"auth\s+(failure|error|denied)", re.IGNORECASE),
    re.compile(r"unauthorized", re.IGNORECASE),
    re.compile(r"invalid.*api.?key", re.IGNORECASE),
    re.compile(r"authentication.*failed", re.IGNORECASE),
    re.compile(r"bearer.*token.*invalid", re.IGNORECASE),
]

_PROVIDER_PATTERNS = [
    re.compile(r"provider.*timeout", re.IGNORECASE),
    re.compile(r"provider.*error", re.IGNORECASE),
    re.compile(r"retry\s+attempt\s+(\d+)/*\d*", re.IGNORECASE),
    re.compile(r"rate\s+limit", re.IGNORECASE),
    re.compile(r"quota\s+exceeded", re.IGNORECASE),
    re.compile(r"model.*not.*found", re.IGNORECASE),
    re.compile(r"model.*error", re.IGNORECASE),
    re.compile(r"upstream.*error", re.IGNORECASE),
    re.compile(r"connection.*reset", re.IGNORECASE),
    re.compile(r"connection.*timeout", re.IGNORECASE),
]

_RUNTIME_PATTERNS = [
    re.compile(r"exception\s+in\s+worker", re.IGNORECASE),
    re.compile(r"exception\s+in\s+thread", re.IGNORECASE),
    re.compile(r"crash(ed)?", re.IGNORECASE),
    re.compile(r"panicked", re.IGNORECASE),
    re.compile(r"segmentation\s+fault", re.IGNORECASE),
    re.compile(r"core\s+dumped", re.IGNORECASE),
    re.compile(r"abort(ed)?", re.IGNORECASE),
    re.compile(r"fatal\s+error", re.IGNORECASE),
    re.compile(r"internal\s+error", re.IGNORECASE),
    re.compile(r"nil\s+pointer", re.IGNORECASE),
    re.compile(r"stack\s+trace", re.IGNORECASE),
]

# Severity override per category
_CATEGORY_SEVERITY = {
    "log-auth-failure": "high",
    "log-provider-failure": "medium",
    "log-runtime-failure": "medium",
}


def _classify(line: str) -> tuple[str | None, str]:
    """
    Classify a log line into a failure category.
    Returns (kind, category) or (None, "") if no match.
    """
    for pat in _AUTH_PATTERNS:
        if pat.search(line):
            return ("log-auth-failure", "auth")
    for pat in _PROVIDER_PATTERNS:
        if pat.search(line):
            return ("log-provider-failure", "provider")
    for pat in _RUNTIME_PATTERNS:
        if pat.search(line):
            return ("log-runtime-failure", "runtime")
    return None, ""


def _count_retries(line: str) -> int:
    """Extract retry count from a log line if present."""
    m = re.search(r"retry\s+attempt\s+(\d+)", line, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s+retries?", line, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return 0


def scan_log(path: str | Path) -> list[Finding]:
    """
    Phase 1 scan of a single Hermes log file.

    Returns a list of Finding records, one per failure line.
    """
    findings: list[Finding] = []
    p = Path(path) if isinstance(path, str) else path
    if not p.exists():
        return findings

    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        findings.append(
            Finding(
                file_path=str(p),
                line_num=1,
                category="log-signal",
                severity="medium",
                kind="log-runtime-failure",
                fingerprint=f"{p}:1",
                sample_text="failed to read log file",
                count=1,
                confidence="low",
                router_note="log-read-error",
                lane=None,
            )
        )
        return findings

    for line_num, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        kind, cat = _classify(line)
        if kind is None:
            continue

        severity = _CATEGORY_SEVERITY.get(kind, "medium")
        retry_count = _count_retries(line)

        findings.append(
            Finding(
                file_path=str(p),
                line_num=line_num,
                category="log-signal",
                severity=severity,
                kind=kind,
                fingerprint=f"{p}:{line_num}",
                sample_text=line[:240],
                count=retry_count if retry_count > 0 else 1,
                confidence="high",
                router_note=f"{cat} failure detected at line {line_num}",
                lane=None,
            )
        )

    return findings


def scan_log_paths(paths: list[str | Path]) -> list[Finding]:
    """
    Scan a list of log file paths and return findings.
    Phase 1 implementation delegates to scan_log.
    """
    findings: list[Finding] = []
    for path in paths:
        findings.extend(scan_log(path))
    return findings

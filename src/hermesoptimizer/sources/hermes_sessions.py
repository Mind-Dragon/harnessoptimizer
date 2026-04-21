"""
Phase 1 Hermes session scanner.

Parses Hermes session JSON files and surfaces structured findings for:
- Error status entries
- Retry counts (threshold > 1)
- Crash indicators (keywords in error fields)
- Timeout indicators (duration_ms > threshold or keyword in error)
"""
from __future__ import annotations

import json
from pathlib import Path

from hermesoptimizer.catalog import Finding

# Thresholds
MAX_RETRIES_BEFORE_FLAG = 2
MAX_DURATION_MS = 30_000  # 30 seconds


def _error_to_str(error: str | dict | None) -> str:
    """Normalize error field to string. Real sessions have error as dict with type/message."""
    if isinstance(error, dict):
        parts = []
        if error.get("type"):
            parts.append(str(error["type"]))
        if error.get("message"):
            parts.append(str(error["message"]))
        return " ".join(parts)
    return str(error or "")


def _detect_timeout(session: dict) -> bool:
    """Return True if session shows timeout characteristics."""
    error = _error_to_str(session.get("error"))
    duration = session.get("duration_ms", 0) or 0
    return (
        "timeout" in error.lower()
        or duration > MAX_DURATION_MS
        or session.get("status") == "timeout"
    )


def _detect_crash(session: dict) -> bool:
    """Return True if session shows crash characteristics."""
    error = _error_to_str(session.get("error"))
    status = str(session.get("status", "") or "")
    crash_keywords = {"crash", "killed", "segmentation fault", "core dumped", "panicked", "abort"}
    error_lower = error.lower()
    status_lower = status.lower()
    return any(kw in error_lower or kw in status_lower for kw in crash_keywords)


def _severity_for_session(session: dict) -> str:
    """Determine severity based on session state."""
    if _detect_crash(session):
        return "critical"
    if _detect_timeout(session):
        return "high"
    if session.get("status") == "error":
        return "medium"
    return "low"


def scan_session(path: str | Path) -> list[Finding]:
    """
    Phase 1 scan of a single Hermes session JSON file.

    Returns a list of Finding records, one per notable event in the session.
    """
    findings: list[Finding] = []
    p = Path(path) if isinstance(path, str) else path
    if not p.exists():
        return findings

    try:
        session = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        findings.append(
            Finding(
                file_path=str(p),
                line_num=None,
                category="session-signal",
                severity="high",
                kind="session-error",
                fingerprint=str(p),
                sample_text="failed to parse session JSON",
                count=1,
                confidence="high",
                router_note="json-parse-error",
                lane=None,
            )
        )
        return findings

    if not isinstance(session, dict):
        return findings

    session_id = session.get("session_id", p.stem)
    status = session.get("status", "")
    error = _error_to_str(session.get("error"))
    retries = session.get("retries", 0) or 0
    provider = session.get("provider", "")
    model = session.get("model", "")
    lane = session.get("lane", "")
    duration_ms = session.get("duration_ms", 0) or 0
    created_at = session.get("created_at", "")

    # Base context for findings
    context = {
        "session_id": session_id,
        "provider": provider,
        "model": model,
        "lane": lane,
    }

    # Handle error status
    if status == "error" or error:
        if _detect_timeout(session):
            kind = "session-timeout"
        elif _detect_crash(session):
            kind = "session-crash"
        else:
            kind = "session-error"
        severity = _severity_for_session(session)
        sample = error if error else f"status={status}"
        findings.append(
            Finding(
                file_path=str(p),
                line_num=None,
                category="session-signal",
                severity=severity,
                kind=kind,
                fingerprint=f"{p}:{session_id}:error",
                sample_text=sample[:240],
                count=1,
                confidence="high",
                router_note=f"session {session_id} {kind}: {sample[:80]}",
                lane=lane or None,
            )
        )

    # Handle retries
    if retries > MAX_RETRIES_BEFORE_FLAG:
        findings.append(
            Finding(
                file_path=str(p),
                line_num=None,
                category="session-signal",
                severity="low",
                kind="session-retry",
                fingerprint=f"{p}:{session_id}:retries",
                sample_text=f"session {session_id} retried {retries} times",
                count=retries,
                confidence="high",
                router_note=f"session {session_id} had {retries} retries",
                lane=lane or None,
            )
        )

    # Handle crash
    if _detect_crash(session):
        findings.append(
            Finding(
                file_path=str(p),
                line_num=None,
                category="session-signal",
                severity="critical",
                kind="session-crash",
                fingerprint=f"{p}:{session_id}:crash",
                sample_text=error[:240] if error else f"session {session_id} crashed",
                count=1,
                confidence="high",
                router_note=f"session {session_id} crashed",
                lane=lane or None,
            )
        )

    return findings


def scan_session_files(paths: list[str | Path]) -> list[Finding]:
    """
    Scan a list of session file paths and return findings.
    Phase 1 implementation delegates to scan_session.
    """
    findings: list[Finding] = []
    for path in paths:
        findings.extend(scan_session(path))
    return findings

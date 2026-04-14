from __future__ import annotations

from pathlib import Path

from hermesoptimizer.catalog import Finding


def scan_session_files(paths: list[str | Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        p = Path(path)
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        if '"error"' in text.lower() or 'traceback' in text.lower():
            findings.append(
                Finding(
                    file_path=str(p),
                    line_num=None,
                    category="session-signal",
                    severity="medium",
                    kind="json",
                    fingerprint=str(p),
                    sample_text=text[:240],
                    count=1,
                    confidence="low",
                    router_note="heuristic session scan",
                    lane="auxiliary",
                )
            )
    return findings

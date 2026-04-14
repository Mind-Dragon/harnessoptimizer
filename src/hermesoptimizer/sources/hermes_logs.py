from __future__ import annotations

from pathlib import Path

from hermesoptimizer.catalog import Finding


def scan_log_paths(paths: list[str | Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        p = Path(path)
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for line_num, line in enumerate(text.splitlines(), start=1):
            lowered = line.lower()
            if any(token in lowered for token in ("error", "exception", "timeout", "auth")):
                findings.append(
                    Finding(
                        file_path=str(p),
                        line_num=line_num,
                        category="log-signal",
                        severity="medium",
                        kind="raw",
                        fingerprint=f"{p}:{line_num}",
                        sample_text=line[:240],
                        count=1,
                        confidence="medium",
                        router_note="heuristic log scan",
                        lane="auxiliary",
                    )
                )
    return findings

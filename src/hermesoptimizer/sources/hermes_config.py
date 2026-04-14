"""
Phase 0 Hermes config scanner stub.

Reads Hermes config files and returns structured findings.
This is a stub: it proves the scanner skeleton works before
deeper parsing logic exists.
"""
from __future__ import annotations

from pathlib import Path

from hermesoptimizer.catalog import Finding


def scan_config_paths(paths: list[str | Path]) -> list[Finding]:
    """
    Scan a list of config file paths and return findings.

    Phase 0 stub: reads the raw file and returns a finding
    if the file contains any suspicious patterns.
    """
    findings: list[Finding] = []
    for path in paths:
        p = Path(path) if isinstance(path, str) else path
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for line_num, line in enumerate(text.splitlines(), start=1):
            lowered = line.lower()
            # Phase 0: surface any line with a suspicious token
            if any(t in lowered for t in ("error", "exception", "timeout", "unauthorized", "auth")):
                findings.append(
                    Finding(
                        file_path=str(p),
                        line_num=line_num,
                        category="config-signal",
                        severity="medium",
                        kind="yaml",
                        fingerprint=f"{p}:{line_num}",
                        sample_text=line[:240],
                        count=1,
                        confidence="low",
                        router_note="stub config scan",
                        lane=None,
                    )
                )
    return findings

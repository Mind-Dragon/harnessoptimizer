from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from hermesoptimizer.catalog import Finding, Record


def write_json_report(path: str | Path, *, title: str, records: list[Record], findings: list[Finding]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "title": title,
        "records": [asdict(record) for record in records],
        "findings": [asdict(finding) for finding in findings],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

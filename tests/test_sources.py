from __future__ import annotations

from pathlib import Path

from hermesoptimizer.sources.hermes_logs import scan_log_paths
from hermesoptimizer.sources.hermes_sessions import scan_session_files


def test_scan_log_paths(tmp_path: Path) -> None:
    log = tmp_path / "app.log"
    log.write_text("ok\nERROR provider timeout\n", encoding="utf-8")

    findings = scan_log_paths([log])
    assert len(findings) == 1
    assert findings[0].category == "log-signal"


def test_scan_session_files(tmp_path: Path) -> None:
    session = tmp_path / "session.json"
    session.write_text('{"error":"boom"}', encoding="utf-8")

    findings = scan_session_files([session])
    assert len(findings) == 1
    assert findings[0].category == "session-signal"

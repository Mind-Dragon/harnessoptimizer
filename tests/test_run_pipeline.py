from __future__ import annotations

import argparse
import json
import sys
import types
from pathlib import Path

from hermesoptimizer.cli.run import handle_run


class _FakeTokenWaste:
    def __init__(self, waste_type: str, severity: str, description: str) -> None:
        self.waste_type = waste_type
        self.severity = severity
        self.description = description


class _FakeTokenAnalyzer:
    def __init__(self, files: list[Path]) -> None:
        self.files = files
        self.usages = [{"file": str(files[0])}] if files else []
        self.wastes = [_FakeTokenWaste("retry_loop", "WARNING", "retry loop detected")] if files else []

    def analyze(self) -> None:
        return None


class _FakeTokenOptimizer:
    def __init__(self, analyzer: _FakeTokenAnalyzer) -> None:
        self.analyzer = analyzer

    def generate_recommendations(self) -> list[dict[str, str]]:
        return [{"summary": "use a smaller prompt"}]


class _FakePerf:
    def __init__(self) -> None:
        self.provider = "openai"
        self.model = "gpt-5"
        self.error_rate = 0.25


class _FakeOutage:
    def __init__(self) -> None:
        self.provider = "anthropic"
        self.model = "claude-sonnet"
        self.error_reason = "timeout storm"


class _FakePerfAnalyzer:
    def __init__(self, files: list[Path]) -> None:
        self.files = files

    def analyze(self) -> None:
        return None

    def get_provider_perf(self) -> list[_FakePerf]:
        return [_FakePerf()]

    def get_outages(self) -> list[_FakeOutage]:
        return [_FakeOutage()]


class _FakeToolMiss:
    def __init__(self, miss_type: str, severity: str, description: str) -> None:
        self.miss_type = miss_type
        self.severity = severity
        self.description = description


class _FakeToolAnalyzer:
    def __init__(self, files: list[Path]) -> None:
        self.files = files
        self.usages = [{"tool": "read_file"}] if files else []
        self.misses = [_FakeToolMiss("manual_workaround", "INFO", "manual workaround detected")] if files else []

    def analyze(self) -> None:
        return None


class _FakeToolOptimizer:
    def __init__(self, analyzer: _FakeToolAnalyzer) -> None:
        self.analyzer = analyzer

    def generate_recommendations(self) -> list[dict[str, str]]:
        return [{"summary": "use tools directly"}]


def _install_fake_modules(monkeypatch) -> None:
    token_analyzer_mod = types.ModuleType("hermesoptimizer.tokens.analyzer")
    token_analyzer_mod.TokenAnalyzer = _FakeTokenAnalyzer
    token_optimizer_mod = types.ModuleType("hermesoptimizer.tokens.optimizer")
    token_optimizer_mod.TokenOptimizer = _FakeTokenOptimizer

    perf_analyzer_mod = types.ModuleType("hermesoptimizer.perf.analyzer")
    perf_analyzer_mod.PerfAnalyzer = _FakePerfAnalyzer

    tool_analyzer_mod = types.ModuleType("hermesoptimizer.tools.analyzer")
    tool_analyzer_mod.ToolAnalyzer = _FakeToolAnalyzer
    tool_optimizer_mod = types.ModuleType("hermesoptimizer.tools.optimizer")
    tool_optimizer_mod.ToolOptimizer = _FakeToolOptimizer

    monkeypatch.setitem(sys.modules, "hermesoptimizer.tokens.analyzer", token_analyzer_mod)
    monkeypatch.setitem(sys.modules, "hermesoptimizer.tokens.optimizer", token_optimizer_mod)
    monkeypatch.setitem(sys.modules, "hermesoptimizer.perf.analyzer", perf_analyzer_mod)
    monkeypatch.setitem(sys.modules, "hermesoptimizer.tools.analyzer", tool_analyzer_mod)
    monkeypatch.setitem(sys.modules, "hermesoptimizer.tools.optimizer", tool_optimizer_mod)


def test_run_pipeline_writes_reports_and_catalog(monkeypatch, tmp_path: Path) -> None:
    session_file = tmp_path / "session.json"
    config_file = tmp_path / "config.yaml"
    session_file.write_text('{"messages": []}', encoding="utf-8")
    config_file.write_text('port: 9201\nhost: 192.168.1.50\n', encoding="utf-8")

    monkeypatch.setattr(
        "hermesoptimizer.cli.run.discover_hermes_surfaces",
        lambda: [session_file, config_file],
    )
    _install_fake_modules(monkeypatch)

    db_path = tmp_path / "catalog.db"
    out_dir = tmp_path / "reports"
    args = argparse.Namespace(
        db=str(db_path),
        out_dir=str(out_dir),
        title="Pipeline Test Report",
    )

    rc = handle_run(args)

    assert rc == 0
    assert (out_dir / "report.json").exists()
    assert (out_dir / "report.md").exists()

    report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))
    assert report["title"] == "Pipeline Test Report"
    assert any(str(session_file) == item for item in report["inspected_inputs"])
    assert any(f["category"] == "token_waste" for f in report["findings"])
    assert any(f["category"] == "provider_outage" for f in report["findings"])
    assert any(f["category"] == "tool_miss" for f in report["findings"])

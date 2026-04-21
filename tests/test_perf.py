"""Tests for AI API performance monitoring."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermesoptimizer.perf.analyzer import PerfAnalyzer
from hermesoptimizer.perf.reporter import PerfReporter
from hermesoptimizer.perf.models import ProviderPerf, ProviderOutage


class TestPerfAnalyzer:
    def test_successful_session(self, tmp_path: Path) -> None:
        session = {
            "session_id": "s1",
            "provider": "openai",
            "model": "gpt-4o",
            "status": "completed",
            "duration_ms": 1200,
            "retries": 0,
            "messages": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi there"},
            ],
            "created_at": "2025-01-15T10:00:00Z",
        }
        p = tmp_path / "sess.json"
        p.write_text(json.dumps(session))

        analyzer = PerfAnalyzer([p])
        analyzer.analyze()
        perf = analyzer.get_provider_perf()

        assert len(perf) == 1
        assert perf[0].provider == "openai"
        assert perf[0].model == "gpt-4o"
        assert perf[0].total_requests == 1
        assert perf[0].success_count == 1
        assert perf[0].error_count == 0
        assert perf[0].avg_response_ms == 1200.0
        assert perf[0].error_rate == 0.0

    def test_failed_session(self, tmp_path: Path) -> None:
        session = {
            "session_id": "s1",
            "provider": "anthropic",
            "model": "claude-sonnet-4",
            "status": "failed",
            "duration_ms": 500,
            "retries": 2,
            "error": "Rate limit exceeded",
            "messages": [],
            "created_at": "2025-01-15T10:00:00Z",
        }
        p = tmp_path / "sess.json"
        p.write_text(json.dumps(session))

        analyzer = PerfAnalyzer([p])
        analyzer.analyze()
        perf = analyzer.get_provider_perf()

        assert perf[0].error_count == 1
        assert perf[0].error_rate == 1.0
        assert perf[0].retry_count == 2
        assert perf[0].retry_rate == 2.0

    def test_multiple_sessions_same_provider(self, tmp_path: Path) -> None:
        sessions = [
            {
                "session_id": "s1",
                "provider": "openai",
                "model": "gpt-4o",
                "status": "completed",
                "duration_ms": 1000,
                "retries": 0,
                "messages": [{"role": "user", "content": "test"}],
                "created_at": "2025-01-15T10:00:00Z",
            },
            {
                "session_id": "s2",
                "provider": "openai",
                "model": "gpt-4o",
                "status": "completed",
                "duration_ms": 2000,
                "retries": 1,
                "messages": [{"role": "user", "content": "test2"}],
                "created_at": "2025-01-15T10:01:00Z",
            },
        ]
        paths = []
        for i, s in enumerate(sessions):
            p = tmp_path / f"sess_{i}.json"
            p.write_text(json.dumps(s))
            paths.append(p)

        analyzer = PerfAnalyzer(paths)
        analyzer.analyze()
        perf = analyzer.get_provider_perf()

        assert len(perf) == 1
        assert perf[0].total_requests == 2
        assert perf[0].success_count == 2
        assert perf[0].avg_response_ms == 1500.0
        assert perf[0].retry_count == 1
        assert perf[0].retry_rate == 0.5

    def test_outage_detection(self, tmp_path: Path) -> None:
        sessions = [
            {
                "session_id": f"s{i}",
                "provider": "openai",
                "model": "gpt-4o",
                "status": "failed",
                "duration_ms": 100,
                "retries": 0,
                "messages": [],
                "created_at": f"2025-01-15T10:0{i}:00Z",
            }
            for i in range(5)
        ]
        # Add a success to end the outage
        sessions.append({
            "session_id": "s5",
            "provider": "openai",
            "model": "gpt-4o",
            "status": "completed",
            "duration_ms": 1000,
            "retries": 0,
            "messages": [],
            "created_at": "2025-01-15T10:06:00Z",
        })
        paths = []
        for i, s in enumerate(sessions):
            p = tmp_path / f"sess_{i}.json"
            p.write_text(json.dumps(s))
            paths.append(p)

        analyzer = PerfAnalyzer(paths)
        analyzer.analyze()
        outages = analyzer.get_outages()

        assert len(outages) == 1
        assert outages[0].provider == "openai"
        assert outages[0].affected_sessions == 5

    def test_failure_reasons(self, tmp_path: Path) -> None:
        sessions = [
            {
                "session_id": "s1",
                "provider": "openai",
                "model": "gpt-4o",
                "status": "failed",
                "error": "Connection timeout",
                "messages": [],
                "created_at": "2025-01-15T10:00:00Z",
            },
            {
                "session_id": "s2",
                "provider": "openai",
                "model": "gpt-4o",
                "status": "failed",
                "error": "Connection timeout",
                "messages": [],
                "created_at": "2025-01-15T10:01:00Z",
            },
        ]
        paths = []
        for i, s in enumerate(sessions):
            p = tmp_path / f"sess_{i}.json"
            p.write_text(json.dumps(s))
            paths.append(p)

        analyzer = PerfAnalyzer(paths)
        analyzer.analyze()
        reasons = analyzer.get_failure_reasons()

        assert "openai:gpt-4o" in reasons
        assert "Connection timeout" in reasons["openai:gpt-4o"]

    def test_tokens_per_second(self, tmp_path: Path) -> None:
        session = {
            "session_id": "s1",
            "provider": "openai",
            "model": "gpt-4o",
            "status": "completed",
            "duration_ms": 1000,
            "messages": [
                {"role": "user", "content": "a" * 400},  # ~100 tokens
                {"role": "assistant", "content": "b" * 400},  # ~100 tokens
            ],
            "created_at": "2025-01-15T10:00:00Z",
        }
        p = tmp_path / "sess.json"
        p.write_text(json.dumps(session))

        analyzer = PerfAnalyzer([p])
        analyzer.analyze()
        perf = analyzer.get_provider_perf()

        assert perf[0].tokens_per_second > 0


class TestPerfReporter:
    def test_generate_report(self, tmp_path: Path) -> None:
        session = {
            "session_id": "s1",
            "provider": "openai",
            "model": "gpt-4o",
            "status": "completed",
            "duration_ms": 1200,
            "messages": [{"role": "user", "content": "hello"}],
            "created_at": "2025-01-15T10:00:00Z",
        }
        p = tmp_path / "sess.json"
        p.write_text(json.dumps(session))

        analyzer = PerfAnalyzer([p])
        analyzer.analyze()
        reporter = PerfReporter(analyzer)
        report = reporter.generate_report()

        assert "openai" in report
        assert "gpt-4o" in report
        assert "AI API PERFORMANCE REPORT" in report

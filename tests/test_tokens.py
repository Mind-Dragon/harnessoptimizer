"""Tests for token usage analyzer and optimizer."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from hermesoptimizer.tokens.analyzer import estimate_tokens, parse_session_tokens, TokenAnalyzer
from hermesoptimizer.tokens.optimizer import TokenOptimizer


class TestEstimateTokens:
    def test_empty_string(self) -> None:
        assert estimate_tokens("") == 0

    def test_short_text(self) -> None:
        assert estimate_tokens("hello") == 1

    def test_long_text(self) -> None:
        text = "a" * 400
        assert estimate_tokens(text) == 100


class TestParseSessionTokens:
    def test_basic_session(self, tmp_path: Path) -> None:
        session = {
            "session_id": "sess-001",
            "provider": "openai",
            "model": "gpt-4o",
            "lane": "coding",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello there, how are you today?"},
                {"role": "assistant", "content": "I am doing well, thank you!"},
            ],
            "created_at": "2025-01-15T10:00:00Z",
        }
        path = tmp_path / "session.json"
        path.write_text(json.dumps(session))

        usages, wastes = parse_session_tokens(path)
        assert len(usages) == 3  # system, user, assistant
        assert sum(u.tokens_in for u in usages) > 0
        assert sum(u.tokens_out for u in usages) > 0
        assert len(wastes) == 0  # No waste in normal session

    def test_detects_prompt_bloat(self, tmp_path: Path) -> None:
        session = {
            "session_id": "sess-002",
            "provider": "openai",
            "model": "gpt-4o",
            "lane": "coding",
            "messages": [
                {"role": "user", "content": "x" * 20000},  # ~5000 tokens input
                {"role": "assistant", "content": "ok"},  # 1 token output
            ],
            "created_at": "2025-01-15T10:00:00Z",
        }
        path = tmp_path / "session.json"
        path.write_text(json.dumps(session))

        usages, wastes = parse_session_tokens(path)
        assert any(w.waste_type == "prompt_bloat" for w in wastes)

    def test_detects_retries(self, tmp_path: Path) -> None:
        session = {
            "session_id": "sess-003",
            "provider": "anthropic",
            "model": "claude-sonnet-4",
            "retries": 5,
            "messages": [
                {"role": "user", "content": "test"},
                {"role": "assistant", "content": "result"},
            ],
            "created_at": "2025-01-15T10:00:00Z",
        }
        path = tmp_path / "session.json"
        path.write_text(json.dumps(session))

        usages, wastes = parse_session_tokens(path)
        assert any(w.waste_type == "retries" for w in wastes)

    def test_detects_tool_loop(self, tmp_path: Path) -> None:
        session = {
            "session_id": "sess-004",
            "provider": "openai",
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"id": str(i)} for i in range(8)],
                },
            ],
            "created_at": "2025-01-15T10:00:00Z",
        }
        path = tmp_path / "session.json"
        path.write_text(json.dumps(session))

        usages, wastes = parse_session_tokens(path)
        assert any(w.waste_type == "tool_loop" for w in wastes)

    def test_detects_context_overflow(self, tmp_path: Path) -> None:
        session = {
            "session_id": "sess-005",
            "provider": "openai",
            "model": "gpt-4o",
            "messages": [
                {"role": "user", "content": "x" * 600000},  # ~150k tokens
            ],
            "created_at": "2025-01-15T10:00:00Z",
        }
        path = tmp_path / "session.json"
        path.write_text(json.dumps(session))

        usages, wastes = parse_session_tokens(path)
        assert any(w.waste_type == "context_overflow" for w in wastes)


class TestTokenAnalyzer:
    def test_skips_utf8_decode_failure_by_recovering_with_replacement(self, tmp_path: Path) -> None:
        raw = b'{"session_id":"s1","provider":"openai","model":"gpt-4o","lane":"coding","messages":[{"role":"user","content":"bad \xe6 byte"}],"created_at":"2025-01-15T10:00:00Z"}'
        p = tmp_path / "sess_bad.json"
        p.write_bytes(raw)

        usages, wastes = parse_session_tokens(p)

        assert len(usages) == 1
        assert usages[0].session_id == "s1"
        assert usages[0].provider == "openai"
        assert wastes == []

    def test_by_provider(self, tmp_path: Path) -> None:
        sessions = [
            {
                "session_id": "s1",
                "provider": "openai",
                "model": "gpt-4o",
                "lane": "coding",
                "messages": [
                    {"role": "user", "content": "hello"},
                    {"role": "assistant", "content": "hi"},
                ],
            },
            {
                "session_id": "s2",
                "provider": "anthropic",
                "model": "claude-sonnet-4",
                "lane": "coding",
                "messages": [
                    {"role": "user", "content": "world"},
                    {"role": "assistant", "content": "earth"},
                ],
            },
        ]
        paths = []
        for i, s in enumerate(sessions):
            p = tmp_path / f"sess_{i}.json"
            p.write_text(json.dumps(s))
            paths.append(p)

        analyzer = TokenAnalyzer(paths)
        analyzer.analyze()

        by_provider = analyzer.by_provider()
        assert "openai" in by_provider
        assert "anthropic" in by_provider
        assert by_provider["openai"]["sessions"] == 1
        assert by_provider["anthropic"]["sessions"] == 1

    def test_by_model(self, tmp_path: Path) -> None:
        session = {
            "session_id": "s1",
            "provider": "openai",
            "model": "gpt-4o",
            "lane": "coding",
            "messages": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi"},
            ],
        }
        p = tmp_path / "sess.json"
        p.write_text(json.dumps(session))

        analyzer = TokenAnalyzer([p])
        analyzer.analyze()

        by_model = analyzer.by_model()
        assert "gpt-4o" in by_model
        assert by_model["gpt-4o"]["sessions"] == 1

    def test_total_waste(self, tmp_path: Path) -> None:
        session = {
            "session_id": "s1",
            "provider": "openai",
            "model": "gpt-4o",
            "retries": 5,
            "messages": [
                {"role": "user", "content": "x" * 20000},
                {"role": "assistant", "content": "ok"},
            ],
        }
        p = tmp_path / "sess.json"
        p.write_text(json.dumps(session))

        analyzer = TokenAnalyzer([p])
        analyzer.analyze()
        assert analyzer.total_waste() > 0


class TestTokenOptimizer:
    def test_generates_recommendations(self, tmp_path: Path) -> None:
        session = {
            "session_id": "s1",
            "provider": "openai",
            "model": "gpt-4o",
            "lane": "coding",
            "retries": 5,
            "messages": [
                {"role": "user", "content": "x" * 20000},
                {"role": "assistant", "content": "ok"},
            ],
        }
        p = tmp_path / "sess.json"
        p.write_text(json.dumps(session))

        analyzer = TokenAnalyzer([p])
        analyzer.analyze()
        optimizer = TokenOptimizer(analyzer)
        recs = optimizer.generate_recommendations()

        assert len(recs) > 0
        # Should have retry mitigation rec
        assert any(r.target_id == "retries" for r in recs)

    def test_model_efficiency_rec(self, tmp_path: Path) -> None:
        session = {
            "session_id": "s1",
            "provider": "openai",
            "model": "gpt-4o",
            "lane": "coding",
            "messages": [
                {"role": "user", "content": "x" * 50000},  # High input
                {"role": "assistant", "content": "yes"},  # Very low output
            ],
        }
        p = tmp_path / "sess.json"
        p.write_text(json.dumps(session))

        analyzer = TokenAnalyzer([p])
        analyzer.analyze()
        optimizer = TokenOptimizer(analyzer)
        recs = optimizer.generate_recommendations()

        assert any(r.target_type == "model" for r in recs)

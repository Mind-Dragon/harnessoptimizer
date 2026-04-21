"""Tests for tool usage analyzer and optimizer."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermesoptimizer.tools.analyzer import (
    ToolAnalyzer,
    extract_tool_calls,
    detect_manual_workarounds,
    detect_tool_avoidance,
    detect_repeated_tool_failures,
)
from hermesoptimizer.tools.optimizer import ToolOptimizer


class TestExtractToolCalls:
    def test_basic_tool_call(self) -> None:
        messages = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"name": "web_search"}},
                    {"function": {"name": "web_search"}},
                ],
            },
        ]
        tools = extract_tool_calls(messages)
        assert "web_search" in tools
        assert tools["web_search"]["count"] == 2

    def test_tool_call_with_error(self) -> None:
        messages = [
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "browser_click"}}]},
            {"role": "tool", "content": "Error: element not found"},
        ]
        tools = extract_tool_calls(messages)
        assert tools["browser_click"]["failure"] == 1
        assert tools["browser_click"]["success"] == 0


class TestDetectManualWorkarounds:
    def test_detects_image_gen_manual(self) -> None:
        messages = [
            {"role": "assistant", "content": "I will create an image for you using Python."},
        ]
        misses = detect_manual_workarounds(messages)
        assert len(misses) == 1
        assert misses[0].miss_type == "image_gen_manual"
        assert misses[0].suggested_tool == "image_generate"

    def test_detects_script_manual(self) -> None:
        messages = [
            {"role": "assistant", "content": "I will write a script to process this data."},
        ]
        misses = detect_manual_workarounds(messages)
        assert len(misses) == 1
        assert misses[0].miss_type == "script_manual"

    def test_no_false_positives(self) -> None:
        messages = [
            {"role": "assistant", "content": "Here is the result you asked for."},
        ]
        misses = detect_manual_workarounds(messages)
        assert len(misses) == 0


class TestDetectToolAvoidance:
    def test_detects_avoidance(self) -> None:
        session = {
            "messages": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi"},
                {"role": "user", "content": "do this"},
                {"role": "assistant", "content": "sure"},
                {"role": "user", "content": "and this"},
                {"role": "assistant", "content": "ok"},
                {"role": "user", "content": "and that"},
                {"role": "assistant", "content": "done"},
            ]
        }
        misses = detect_tool_avoidance(session)
        assert len(misses) == 1
        assert misses[0].miss_type == "tool_avoidance"

    def test_no_avoidance_with_tools(self) -> None:
        session = {
            "messages": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "web_search"}}]},
                {"role": "user", "content": "do this"},
                {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "execute_code"}}]},
            ]
        }
        misses = detect_tool_avoidance(session)
        assert len(misses) == 0


class TestDetectRepeatedToolFailures:
    def test_detects_repeated_failures(self) -> None:
        messages = [
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "browser_click"}}]},
            {"role": "tool", "name": "browser_click", "content": "Error: timeout"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "browser_click"}}]},
            {"role": "tool", "name": "browser_click", "content": "Error: timeout"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "browser_click"}}]},
            {"role": "tool", "name": "browser_click", "content": "Error: timeout"},
        ]
        misses = detect_repeated_tool_failures(messages)
        assert len(misses) == 1
        assert misses[0].miss_type == "repeated_tool_failure"

    def test_no_false_positive_on_few_failures(self) -> None:
        messages = [
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "browser_click"}}]},
            {"role": "tool", "name": "browser_click", "content": "Error: timeout"},
        ]
        misses = detect_repeated_tool_failures(messages)
        assert len(misses) == 0


class TestToolAnalyzer:
    def test_by_tool(self, tmp_path: Path) -> None:
        session = {
            "session_id": "s1",
            "provider": "openai",
            "model": "gpt-4o",
            "lane": "coding",
            "messages": [
                {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "web_search"}}]},
                {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "execute_code"}}]},
            ],
        }
        p = tmp_path / "sess.json"
        p.write_text(json.dumps(session))

        analyzer = ToolAnalyzer([p])
        analyzer.analyze()
        by_tool = analyzer.by_tool()
        assert "web_search" in by_tool
        assert "execute_code" in by_tool
        assert by_tool["web_search"]["calls"] == 1

    def test_by_provider(self, tmp_path: Path) -> None:
        session = {
            "session_id": "s1",
            "provider": "openai",
            "model": "gpt-4o",
            "lane": "coding",
            "messages": [
                {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "web_search"}}]},
            ],
        }
        p = tmp_path / "sess.json"
        p.write_text(json.dumps(session))

        analyzer = ToolAnalyzer([p])
        analyzer.analyze()
        by_provider = analyzer.by_provider()
        assert "openai" in by_provider
        assert by_provider["openai"]["calls"] == 1

    def test_detects_manual_workaround(self, tmp_path: Path) -> None:
        session = {
            "session_id": "s1",
            "provider": "openai",
            "model": "gpt-4o",
            "lane": "coding",
            "messages": [
                {"role": "assistant", "content": "I will create an image for you using Python."},
            ],
        }
        p = tmp_path / "sess.json"
        p.write_text(json.dumps(session))

        analyzer = ToolAnalyzer([p])
        analyzer.analyze()
        assert any(m.miss_type == "image_gen_manual" for m in analyzer.misses)


class TestToolOptimizer:
    def test_generates_recommendations(self, tmp_path: Path) -> None:
        session = {
            "session_id": "s1",
            "provider": "openai",
            "model": "gpt-4o",
            "lane": "coding",
            "messages": [
                {"role": "assistant", "content": "I will create an image for you using Python."},
            ],
        }
        p = tmp_path / "sess.json"
        p.write_text(json.dumps(session))

        analyzer = ToolAnalyzer([p])
        analyzer.analyze()
        optimizer = ToolOptimizer(analyzer)
        recs = optimizer.generate_recommendations()

        assert len(recs) > 0
        assert any(r.target_type == "tool" for r in recs)

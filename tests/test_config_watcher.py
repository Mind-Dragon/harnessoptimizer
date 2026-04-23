"""Tests for config watcher and service lifecycle.

Phase I.1: Config file watcher with change classification.
Phase I.2: Service start/stop/status.
Phase I.3: Integration — flags, flush, self-change exclusion.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest
import yaml


# ---------------------------------------------------------------------------
# Config watcher tests
# ---------------------------------------------------------------------------


class TestClassifyChange:
    """Tests for config change classification."""

    def test_minor_single_key_change(self) -> None:
        from hermesoptimizer.config_watcher import classify_change, ChangeScope

        old = {"model": {"default": "gpt-5.4"}, "agent": {"max_turns": 100}}
        new = {"model": {"default": "gpt-5.4"}, "agent": {"max_turns": 200}}

        result = classify_change(old, new)
        assert result.scope == ChangeScope.MINOR

    def test_major_section_removed(self) -> None:
        from hermesoptimizer.config_watcher import classify_change, ChangeScope

        old = {"model": {"default": "gpt-5.4"}, "agent": {"max_turns": 100}, "yolo": {"enabled": True}}
        new = {"model": {"default": "gpt-5.4"}, "agent": {"max_turns": 100}}

        result = classify_change(old, new)
        assert result.scope == ChangeScope.MAJOR
        assert "yolo" in result.sections_removed

    def test_major_model_set_to_null(self) -> None:
        from hermesoptimizer.config_watcher import classify_change, ChangeScope

        old = {"model": {"default": "gpt-5.4", "provider": "openai"}}
        new = {"model": {"default": None, "provider": "openai"}}

        result = classify_change(old, new)
        assert result.scope == ChangeScope.MAJOR

    def test_major_provider_set_to_empty(self) -> None:
        from hermesoptimizer.config_watcher import classify_change, ChangeScope

        old = {"model": {"default": "gpt-5.4", "provider": "openai"}}
        new = {"model": {"default": "gpt-5.4", "provider": ""}}

        result = classify_change(old, new)
        assert result.scope == ChangeScope.MAJOR

    def test_major_many_keys_changed(self) -> None:
        from hermesoptimizer.config_watcher import classify_change, ChangeScope

        old = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5}
        new = {"a": 10, "b": 20, "c": 30, "d": 40, "e": 50}

        result = classify_change(old, new)
        assert result.scope == ChangeScope.MAJOR

    def test_major_truncation(self) -> None:
        from hermesoptimizer.config_watcher import classify_change, ChangeScope

        old = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6}
        new = {"a": 1, "b": 2}

        result = classify_change(old, new)
        assert result.scope == ChangeScope.MAJOR

    def test_minor_additive_key(self) -> None:
        from hermesoptimizer.config_watcher import classify_change, ChangeScope

        old = {"model": {"default": "gpt-5.4"}}
        new = {"model": {"default": "gpt-5.4"}, "yolo": {"enabled": True}}

        result = classify_change(old, new)
        assert result.scope == ChangeScope.MINOR


class TestConfigWatcher:
    """Tests for the watcher polling mechanism."""

    def test_create_watcher(self, tmp_path: Path) -> None:
        from hermesoptimizer.config_watcher import create_watcher

        cfg = tmp_path / "config.yaml"
        cfg.write_text("model:\n  default: test\n")

        watcher = create_watcher(config_dir=tmp_path)
        assert len(watcher.watched_files) >= 1

    def test_poll_detects_change(self, tmp_path: Path) -> None:
        from hermesoptimizer.config_watcher import create_watcher, poll_once

        cfg = tmp_path / "config.yaml"
        cfg.write_text("model:\n  default: gpt-5.4\n")
        auth = tmp_path / "auth.json"
        auth.write_text("{}")

        watcher = create_watcher(config_dir=tmp_path)
        assert len(watcher.watched_files) >= 1

        # Modify config
        cfg.write_text("model:\n  default: glm-5.1\n")

        changes = poll_once(watcher)
        assert len(changes) >= 1

    def test_poll_no_change(self, tmp_path: Path) -> None:
        from hermesoptimizer.config_watcher import create_watcher, poll_once

        cfg = tmp_path / "config.yaml"
        cfg.write_text("model:\n  default: gpt-5.4\n")
        auth = tmp_path / "auth.json"
        auth.write_text("{}")

        watcher = create_watcher(config_dir=tmp_path)
        changes = poll_once(watcher)
        assert len(changes) == 0

    def test_log_change(self, tmp_path: Path) -> None:
        from hermesoptimizer.config_watcher import (
            ChangeClassification,
            ChangeScope,
            log_change,
        )

        log_path = tmp_path / "watch.log"
        classification = ChangeClassification(
            scope=ChangeScope.MINOR,
            details="test change",
        )
        log_change(classification, tmp_path / "config.yaml", log_path)

        assert log_path.exists()
        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["scope"] == "minor"


# ---------------------------------------------------------------------------
# Service lifecycle tests
# ---------------------------------------------------------------------------


class TestServiceLifecycle:
    """Tests for service start/stop/status."""

    def test_status_when_not_running(self, tmp_path: Path, monkeypatch) -> None:
        from hermesoptimizer import service

        monkeypatch.setattr(service, "_pid_path", lambda: tmp_path / "optimizer.pid")
        monkeypatch.setattr(service, "_flags_path", lambda: tmp_path / "flags.json")

        status = service.service_status()
        assert status.running is False
        assert status.pid is None

    def test_stale_pid_cleaned(self, tmp_path: Path, monkeypatch) -> None:
        from hermesoptimizer import service

        pid_file = tmp_path / "optimizer.pid"
        pid_file.write_text("999999999")  # PID that doesn't exist
        monkeypatch.setattr(service, "_pid_path", lambda: pid_file)
        monkeypatch.setattr(service, "_flags_path", lambda: tmp_path / "flags.json")

        status = service.service_status()
        assert status.running is False
        assert not pid_file.exists()

    def test_add_flag(self, tmp_path: Path, monkeypatch) -> None:
        from hermesoptimizer import service

        monkeypatch.setattr(service, "_flags_path", lambda: tmp_path / "flags.json")

        service.add_flag("config changed: model.default")
        service.add_flag("auxiliary drift: compression")

        flags = service._load_flags()
        assert len(flags) == 2
        assert "config changed: model.default" in flags

    def test_flush_clears_flags(self, tmp_path: Path, monkeypatch) -> None:
        from hermesoptimizer import service

        monkeypatch.setattr(service, "_flags_path", lambda: tmp_path / "flags.json")

        service.add_flag("flag1")
        service.add_flag("flag2")

        result = service.service_flush()
        assert result["flags_processed"] == 2
        assert len(service._load_flags()) == 0

    def test_flush_empty(self, tmp_path: Path, monkeypatch) -> None:
        from hermesoptimizer import service

        monkeypatch.setattr(service, "_flags_path", lambda: tmp_path / "flags.json")

        result = service.service_flush()
        assert result["flags_processed"] == 0

    def test_stop_when_no_pid(self, tmp_path: Path, monkeypatch) -> None:
        from hermesoptimizer import service

        monkeypatch.setattr(service, "_pid_path", lambda: tmp_path / "optimizer.pid")

        result = service.service_stop()
        assert result is True

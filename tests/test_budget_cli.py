"""Tests for budget CLI subcommands: budget-review and budget-set."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from hermesoptimizer.budget.commands import (
    add_budget_review_subparser,
    add_budget_review_subparser,
    add_budget_set_subparser,
    handle_budget_review,
    handle_budget_set,
)
from hermesoptimizer.budget.profile import ProfileLevel
from hermesoptimizer.run_standalone import build_parser, main


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def session_dir(tmp_path: Path) -> Path:
    """Create a temporary session directory with sample session JSON files."""
    sessions = tmp_path / "sessions"
    sessions.mkdir()

    # Session with high utilization -> recommendation to step up
    session1 = {
        "tasks": [
            {
                "task_id": "task-001",
                "role": "implement",
                "turns_used": 80,
                "turns_budget": 100,
                "total_calls": 10,
                "productive_calls": 8,
                "retries": 1,
                "loops": False,
                "status": "completed",
                "fix_cycles": 2,
                "tokens_used": 150000,
                "duration_seconds": 120.0,
            },
            {
                "task_id": "task-002",
                "role": "test",
                "turns_used": 90,
                "turns_budget": 100,
                "total_calls": 8,
                "productive_calls": 6,
                "retries": 2,
                "loops": False,
                "status": "completed",
                "fix_cycles": 3,
                "tokens_used": 80000,
                "duration_seconds": 60.0,
            },
        ]
    }

    # Session with medium utilization and good completion
    session2 = {
        "tasks": [
            {
                "task_id": "task-003",
                "role": "research",
                "turns_used": 40,
                "turns_budget": 100,
                "total_calls": 5,
                "productive_calls": 4,
                "retries": 0,
                "loops": False,
                "status": "completed",
                "fix_cycles": 1,
                "tokens_used": 30000,
                "duration_seconds": 30.0,
            },
        ]
    }

    (sessions / "session_001.json").write_text(json.dumps(session1), encoding="utf-8")
    (sessions / "session_002.json").write_text(json.dumps(session2), encoding="utf-8")

    return sessions


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory."""
    config = tmp_path / "config"
    config.mkdir()
    return config


# ── budget-review handler tests ─────────────────────────────────────────────


class TestHandleBudgetReview:
    def test_review_with_valid_session_dir(self, session_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """budget-review prints recommendation for sessions in directory."""
        import argparse

        args = argparse.Namespace(
            sessions=10,
            profile="medium",
            session_dir=str(session_dir),
        )
        rc = handle_budget_review(args)
        assert rc == 0
        captured = capsys.readouterr()
        assert "Budget Review" in captured.out
        assert "Recommended profile:" in captured.out

    def test_review_with_sessions_limit(self, session_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """budget-review respects --sessions N limit."""
        import argparse

        args = argparse.Namespace(
            sessions=1,
            profile="medium",
            session_dir=str(session_dir),
        )
        rc = handle_budget_review(args)
        assert rc == 0
        captured = capsys.readouterr()
        assert "Signals analyzed:" in captured.out

    def test_review_invalid_profile(self, session_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """budget-review exits with error for invalid profile name."""
        import argparse

        args = argparse.Namespace(
            sessions=10,
            profile="invalid-profile",
            session_dir=str(session_dir),
        )
        rc = handle_budget_review(args)
        assert rc == 1
        captured = capsys.readouterr()
        assert "invalid profile" in captured.err

    def test_review_nonexistent_session_dir(self, capsys: pytest.CaptureFixture[str]) -> None:
        """budget-review exits with error when session dir doesn't exist."""
        import argparse

        args = argparse.Namespace(
            sessions=10,
            profile="medium",
            session_dir="/nonexistent/path/to/sessions",
        )
        rc = handle_budget_review(args)
        assert rc == 1
        captured = capsys.readouterr()
        assert "does not exist" in captured.err


# ── budget-set handler tests ─────────────────────────────────────────────────


class TestHandleBudgetSet:
    def test_set_profile_dry_run_does_not_write_file(self, config_dir: Path) -> None:
        """budget-set with --dry-run does not modify the config file."""
        import argparse

        config_file = config_dir / "config.yaml"
        args = argparse.Namespace(
            profile="medium",
            config=str(config_file),
            role=None,
            dry_run=True,
            confirm=False,
        )
        rc = handle_budget_set(args)
        assert rc == 0
        assert not config_file.exists()

    def test_set_profile_confirm_writes_file(self, config_dir: Path) -> None:
        """budget-set with --confirm writes the config file."""
        import argparse

        config_file = config_dir / "config.yaml"
        args = argparse.Namespace(
            profile="medium",
            config=str(config_file),
            role=None,
            dry_run=False,
            confirm=True,
        )
        rc = handle_budget_set(args)
        assert rc == 0
        assert config_file.exists()
        content = config_file.read_text()
        assert "medium" in content

    def test_set_profile_with_role_overrides(self, config_dir: Path) -> None:
        """budget-set with --role adds role_overrides to config."""
        import argparse

        config_file = config_dir / "config.yaml"
        args = argparse.Namespace(
            profile="high",
            config=str(config_file),
            role=[("implement", 150), ("review", 100)],
            dry_run=False,
            confirm=True,
        )
        rc = handle_budget_set(args)
        assert rc == 0
        assert config_file.exists()
        content = config_file.read_text()
        assert "role_overrides" in content
        assert "implement" in content

    def test_set_profile_invalid_profile(self, config_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """budget-set exits with error for invalid profile name."""
        import argparse

        config_file = config_dir / "config.yaml"
        args = argparse.Namespace(
            profile="not-a-profile",
            config=str(config_file),
            role=None,
            dry_run=True,
            confirm=False,
        )
        rc = handle_budget_set(args)
        assert rc == 1
        captured = capsys.readouterr()
        assert "invalid profile" in captured.err

    def test_set_profile_preserves_existing_content(self, config_dir: Path) -> None:
        """budget-set --confirm preserves existing config content."""
        import yaml

        config_file = config_dir / "config.yaml"
        existing = {"other_section": {"foo": 123}}
        config_file.write_text(yaml.dump(existing), encoding="utf-8")

        import argparse

        args = argparse.Namespace(
            profile="low",
            config=str(config_file),
            role=None,
            dry_run=False,
            confirm=True,
        )
        rc = handle_budget_set(args)
        assert rc == 0

        updated = yaml.safe_load(config_file.read_text())
        assert updated["other_section"] == {"foo": 123}
        assert updated["turn_budget"]["profile"] == "low"


# ── CLI parser integration tests ─────────────────────────────────────────────


class TestBudgetSubparsersRegistered:
    """Verify budget-review and budget-set are registered in the CLI parser."""

    def test_budget_review_subcommand_parses(self) -> None:
        """CLI parser accepts budget-review with its arguments."""
        parser = build_parser()
        args = parser.parse_args([
            "budget-review",
            "--sessions", "5",
            "--profile", "high",
            "--session-dir", "/tmp/sessions",
        ])
        assert args.command == "budget-review"
        assert args.sessions == 5
        assert args.profile == "high"
        assert args.session_dir == "/tmp/sessions"

    def test_budget_set_subcommand_parses(self) -> None:
        """CLI parser accepts budget-set with profile positional arg."""
        parser = build_parser()
        args = parser.parse_args([
            "budget-set",
            "medium",
            "--config", "/tmp/config.yaml",
        ])
        assert args.command == "budget-set"
        assert args.profile == "medium"
        assert args.config == "/tmp/config.yaml"

    def test_budget_set_with_role_overrides(self) -> None:
        """CLI parser accepts multiple --role arguments."""
        parser = build_parser()
        args = parser.parse_args([
            "budget-set",
            "high",
            "--role", "implement", "150",
            "--role", "test", "100",
        ])
        assert args.command == "budget-set"
        assert args.role == [["implement", "150"], ["test", "100"]]

    def test_budget_set_confirm_flag(self) -> None:
        """CLI parser accepts --confirm flag."""
        parser = build_parser()
        args = parser.parse_args([
            "budget-set",
            "low-medium",
            "--confirm",
        ])
        assert args.command == "budget-set"
        assert args.confirm is True
        assert args.dry_run is False

    def test_budget_set_default_dry_run(self) -> None:
        """budget-set defaults to dry-run mode (confirm=False)."""
        parser = build_parser()
        args = parser.parse_args([
            "budget-set",
            "medium",
        ])
        assert args.confirm is False
        # dry_run in handler is computed as `not args.confirm`, so False confirms dry-run behavior


# ── main() dispatch integration tests ───────────────────────────────────────


class TestMainBudgetReview:
    """Integration tests for budget-review via main()."""

    def test_budget_review_via_main(self, session_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """main() routes budget-review correctly and produces output."""
        rc = main([
            "budget-review",
            "--sessions", "10",
            "--profile", "medium",
            "--session-dir", str(session_dir),
        ])
        assert rc == 0
        captured = capsys.readouterr()
        assert "Budget Review" in captured.out
        assert "Recommended profile:" in captured.out

    def test_budget_review_invalid_profile_via_main(self, session_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """main() returns error exit code for invalid profile."""
        rc = main([
            "budget-review",
            "--profile", "bad-profile",
            "--session-dir", str(session_dir),
        ])
        assert rc == 1
        captured = capsys.readouterr()
        assert "invalid profile" in captured.err


class TestMainBudgetSet:
    """Integration tests for budget-set via main()."""

    def test_budget_set_dry_run_via_main(self, config_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """main() routes budget-set --dry-run and does not write file."""
        config_file = config_dir / "config.yaml"
        rc = main([
            "budget-set",
            "medium",
            "--config", str(config_file),
            "--dry-run",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        assert "Dry-run" in captured.out or "dry-run" in captured.out
        assert not config_file.exists()

    def test_budget_set_confirm_via_main(self, config_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """main() routes budget-set --confirm and writes file."""
        config_file = config_dir / "config.yaml"
        rc = main([
            "budget-set",
            "medium",
            "--config", str(config_file),
            "--confirm",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        assert "Wrote" in captured.out or "Written" in captured.out or "profile" in captured.out
        assert config_file.exists()

    def test_budget_set_with_role_overrides_via_main(self, config_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """main() routes budget-set with --role and writes role_overrides."""
        config_file = config_dir / "config.yaml"
        rc = main([
            "budget-set",
            "high",
            "--config", str(config_file),
            "--role", "implement", "150",
            "--confirm",
        ])
        assert rc == 0
        assert config_file.exists()
        content = config_file.read_text()
        assert "implement" in content

    def test_budget_set_invalid_profile_via_main(self, config_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """main() returns error exit code for invalid profile."""
        config_file = config_dir / "config.yaml"
        rc = main([
            "budget-set",
            "not-valid",
            "--config", str(config_file),
        ])
        assert rc == 1
        captured = capsys.readouterr()
        assert "invalid profile" in captured.err

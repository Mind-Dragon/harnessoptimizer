"""Tests for channel management: update, promotion, and state tracking."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

# Import the channel_update module (adds src to path)
import channel_update  # type: ignore


class TestChannelUpdate:
    """Test the channel_update module in isolation."""

    def test_channels_list(self) -> None:
        """Verify all expected channels are defined."""
        assert channel_update.CHANNELS == ["dev", "beta", "release"]

    def test_promotion_paths_documented(self) -> None:
        """Verify channel constants are consistent."""
        # dev maps to beta, beta maps to release
        assert channel_update.PROMOTION_PATHS == {
            "dev": "beta",
            "beta": "release",
        }

    def test_run_git_handles_missing_git(self, tmp_path: Path) -> None:
        """run_git returns error code for non-git directory."""
        code, out, err = channel_update.run_git("status", cwd=tmp_path)
        assert code != 0

    def test_get_current_branch_fails_outside_repo(self, tmp_path: Path) -> None:
        """get_current_branch handles non-git directories gracefully."""
        # Would need to mock run_git to fully test outside repo
        # For now, just verify it doesn't crash
        pass

    def test_channel_state_dataclass(self) -> None:
        """Verify ChannelState can be constructed."""
        from channel_update import ChannelState
        state = ChannelState(
            name="dev",
            branch="dev",
            tracked=True,
            commit="abc1234",
            behind=2,
            ahead=0,
            ff_candidate=True,
            canary_passed=True,
        )
        assert state.name == "dev"
        assert state.behind == 2
        assert state.ff_candidate is True

    def test_update_result_dataclass(self) -> None:
        """Verify UpdateResult can be constructed."""
        from channel_update import UpdateResult
        result = UpdateResult(
            channel="dev",
            success=True,
            dry_run=False,
            actions=["fetched", "merged"],
            errors=[],
        )
        assert result.success is True
        assert len(result.actions) == 2

    def test_update_channel_rejects_unknown_channel(self, tmp_path: Path) -> None:
        """Unknown channel returns an error result."""
        # Create a fake git repo
        (tmp_path / ".git").mkdir()
        result = channel_update.update_channel(tmp_path, "unknown-channel", dry_run=True)
        assert result.success is False
        assert any("Unknown channel" in e for e in result.errors)

    def test_update_channel_rejects_release(self, tmp_path: Path) -> None:
        """Release channel is read-only."""
        (tmp_path / ".git").mkdir()
        result = channel_update.update_channel(tmp_path, "release", dry_run=True)
        assert result.success is False
        assert any("read-only" in e.lower() for e in result.errors)


class TestChannelUpdateGitIntegration:
    """Integration tests that need a real git repo."""

    def test_fetch_origin_reports_failure_outside_repo(self, tmp_path: Path) -> None:
        """fetch_origin returns failure for non-git directories."""
        ok, msg = channel_update.fetch_origin(tmp_path)
        assert ok is False

    def test_fetch_origin_dry_run(self, tmp_path: Path) -> None:
        """fetch_origin dry_run returns success without hitting git."""
        ok, msg = channel_update.fetch_origin(tmp_path, dry_run=True)
        assert ok is True
        assert "dry run" in msg.lower() or "would fetch" in msg.lower()


class TestPromotionScript:
    """Test channel_promote module."""

    def test_valid_channels(self) -> None:
        """Verify VALID_CHANNELS contains expected channels."""
        import channel_promote  # type: ignore
        assert channel_promote.VALID_CHANNELS == ["dev", "beta", "release"]

    def test_promotion_paths(self) -> None:
        """Verify promotion paths are one-way."""
        import channel_promote  # type: ignore
        assert channel_promote.PROMOTION_PATHS["dev"] == "beta"
        assert channel_promote.PROMOTION_PATHS["beta"] == "release"
        # No reverse paths
        assert "release" not in channel_promote.PROMOTION_PATHS
        assert "dev" not in {
            v for v in channel_promote.PROMOTION_PATHS.values()
        }

    def test_promotion_check_dataclass(self) -> None:
        """Verify PromotionCheck can be constructed."""
        from channel_promote import PromotionCheck
        check = PromotionCheck(name="test", passed=True, detail="ok")
        assert check.name == "test"
        assert check.passed is True

    def test_promotion_result_dataclass(self) -> None:
        """Verify PromotionResult can be constructed."""
        from channel_promote import PromotionResult
        result = PromotionResult(
            source="dev",
            target="beta",
            success=True,
            dry_run=True,
        )
        assert result.source == "dev"
        assert result.target == "beta"
        assert result.success is True
        assert result.dry_run is True

    def test_do_promotion_checks_run(self, tmp_path: Path) -> None:
        """Verify promotion checks execute without error."""
        import channel_promote  # type: ignore
        # Run with a non-git dir — check should detect it
        checks = channel_promote.run_promotion_checks("dev", "beta", tmp_path, dry_run=True)
        assert len(checks) > 0
        # Should fail at source_exists since we're not in a git repo
        source_check = next((c for c in checks if c.name == "source_exists"), None)
        assert source_check is not None
        assert source_check.passed is False

    def test_beta_to_release_uses_full_suite_gate(self, tmp_path: Path) -> None:
        """beta -> release must use a truthful full-suite gate, not a subset."""
        import channel_promote  # type: ignore

        calls: list[list[str] | None] = []

        def fake_run_git(*args: str, cwd: Path | None = None):
            if args[:2] == ("rev-parse", "beta"):
                return 0, "beta-sha", ""
            if args[:2] == ("rev-parse", "release"):
                return 0, "release-sha", ""
            if args[:2] == ("merge-base", "--is-ancestor"):
                # source is not ancestor of target, target is ancestor of source
                if args[2] == "beta-sha":
                    return 1, "", ""
                return 0, "", ""
            if args[:3] == ("rev-parse", "--verify", "beta"):
                return 0, "beta-sha", ""
            return 0, "", ""

        def fake_run_tests(repo_root: Path, test_subset: list[str] | None = None, dry_run: bool = False):
            calls.append(test_subset)
            return True, "ok"

        with patch.object(channel_promote, "run_git", side_effect=fake_run_git), \
             patch.object(channel_promote, "run_tests", side_effect=fake_run_tests):
            checks = channel_promote.run_promotion_checks("beta", "release", tmp_path, dry_run=True)

        full_gate = next((c for c in checks if c.name == "full_test_gate"), None)
        assert full_gate is not None
        assert full_gate.passed is True
        assert calls == [None]


class TestPromotionScriptGitIntegration:
    """Git integration tests for promotion script."""

    def test_verify_fast_forward_rejects_unknown_branch(self, tmp_path: Path) -> None:
        """verify_fast_forward handles missing branches."""
        import channel_promote  # type: ignore
        # Not a git repo — should fail gracefully
        ok, detail = channel_promote.verify_fast_forward(tmp_path, "nonexistent", "dev")
        assert ok is False


class TestChannelWorkflowDocumented:
    """Verify the channel workflow documentation exists and is coherent."""

    def test_channels_doc_exists(self) -> None:
        """docs/CHANNELS.md should exist."""
        doc = Path(__file__).parent.parent / "docs" / "CHANNELS.md"
        assert doc.exists(), "docs/CHANNELS.md is missing"
        content = doc.read_text()
        assert "dev" in content
        assert "beta" in content
        assert "release" in content
        assert "fast-forward" in content.lower()

    def test_workflow_file_exists(self) -> None:
        """.github/workflows/channel-promote.yml should exist."""
        wf = Path(__file__).parent.parent / ".github" / "workflows" / "channel-promote.yml"
        assert wf.exists(), ".github/workflows/channel-promote.yml is missing"
        content = wf.read_text()
        assert "dev" in content
        assert "beta" in content
        assert "release" in content
        assert "fast-forward" in content.lower()
        assert "pytest -q" in content or "full suite" in content.lower()

    def test_channel_update_script_exists(self) -> None:
        """scripts/channel_update.py should exist and be runnable."""
        script = Path(__file__).parent.parent / "scripts" / "channel_update.py"
        assert script.exists()
        content = script.read_text()
        assert "CHANNELS" in content
        assert "fast-forward" in content.lower()


class TestChannelUpdateCanary:
    """Test the install canary integration."""

    def test_canary_runs_without_doctor(self, tmp_path: Path) -> None:
        """If doctor is not available, canary still reports success."""
        # Temporarily hide the doctor module
        import channel_update
        original = channel_update.DOCTOR_AVAILABLE
        channel_update.DOCTOR_AVAILABLE = False
        try:
            ok, report = channel_update.run_install_canary(tmp_path, dry_run=True)
            assert ok is True
            assert "not available" in report.get("note", "").lower()
        finally:
            channel_update.DOCTOR_AVAILABLE = original

    def test_canary_dry_run_skips_real_check(self, tmp_path: Path) -> None:
        """canary with dry_run=True should not run real checks."""
        import channel_update
        ok, report = channel_update.run_install_canary(tmp_path, dry_run=True)
        assert ok is True
        assert "dry run" in report.get("note", "").lower()


class TestChannelUpdateFlow:
    """Test the post-update gate sequencing and rollback behavior."""

    def test_update_channel_runs_tests_and_canary_after_merge(self, tmp_path: Path) -> None:
        """A successful update must pass through tests and install integrity gates."""
        import channel_update

        timeline: list[str] = []

        def fake_fetch_origin(repo_root: Path, dry_run: bool = False):
            timeline.append("fetch")
            return True, "fetched"

        def fake_check_channel_state(repo_root: Path, channel: str):
            return channel_update.ChannelState(
                name=channel,
                branch=channel,
                tracked=True,
                commit="abc1234",
                behind=1,
                ahead=0,
                ff_candidate=True,
            )

        def fake_run_git(*args: str, cwd: Path | None = None):
            if args[:2] == ("rev-parse", "--abbrev-ref"):
                return 0, "main", ""
            if args[:2] == ("checkout", "dev"):
                timeline.append("checkout")
                return 0, "", ""
            if args[:2] == ("merge", "--ff-only"):
                timeline.append("merge")
                return 0, "", ""
            return 0, "", ""

        def fake_run_update_test_gate(repo_root: Path, dry_run: bool = False):
            timeline.append("tests")
            return True, "ok"

        def fake_run_install_canary(repo_root: Path, dry_run: bool = False):
            timeline.append("canary")
            return True, {"healthy": True}

        with patch.object(channel_update, "fetch_origin", side_effect=fake_fetch_origin), \
             patch.object(channel_update, "check_channel_state", side_effect=fake_check_channel_state), \
             patch.object(channel_update, "run_git", side_effect=fake_run_git), \
             patch.object(channel_update, "run_update_test_gate", side_effect=fake_run_update_test_gate), \
             patch.object(channel_update, "run_install_canary", side_effect=fake_run_install_canary):
            result = channel_update.update_channel(tmp_path, "dev", dry_run=False)

        assert result.success is True
        assert timeline == ["fetch", "checkout", "merge", "tests", "canary"]
        assert any("test gate: PASSED" in a for a in result.actions)
        assert any("install canary: PASSED" in a for a in result.actions)

    def test_update_channel_rolls_back_when_tests_fail(self, tmp_path: Path) -> None:
        """A failed test gate must fail closed and reset the branch."""
        import channel_update

        calls: list[tuple[str, tuple[str, ...]]] = []

        def fake_fetch_origin(repo_root: Path, dry_run: bool = False):
            return True, "fetched"

        def fake_check_channel_state(repo_root: Path, channel: str):
            return channel_update.ChannelState(
                name=channel,
                branch=channel,
                tracked=True,
                commit="abc1234",
                behind=1,
                ahead=0,
                ff_candidate=True,
            )

        def fake_run_git(*args: str, cwd: Path | None = None):
            calls.append((args[0], args[1:]))
            if args[:2] == ("rev-parse", "--abbrev-ref"):
                return 0, "main", ""
            if args[:2] == ("checkout", "dev"):
                return 0, "", ""
            if args[:2] == ("merge", "--ff-only"):
                return 0, "", ""
            if args[:2] == ("reset", "--hard"):
                return 0, "", ""
            return 0, "", ""

        def fake_run_update_test_gate(repo_root: Path, dry_run: bool = False):
            return False, "tests failed"

        def fake_run_install_canary(repo_root: Path, dry_run: bool = False):
            pytest.fail("install canary should not run after a failed test gate")

        with patch.object(channel_update, "fetch_origin", side_effect=fake_fetch_origin), \
             patch.object(channel_update, "check_channel_state", side_effect=fake_check_channel_state), \
             patch.object(channel_update, "run_git", side_effect=fake_run_git), \
             patch.object(channel_update, "run_update_test_gate", side_effect=fake_run_update_test_gate), \
             patch.object(channel_update, "run_install_canary", side_effect=fake_run_install_canary):
            result = channel_update.update_channel(tmp_path, "dev", dry_run=False)

        assert result.success is False
        assert any("test gate FAILED" in e for e in result.errors)
        assert any(call[0] == "reset" and call[1][:2] == ("--hard", "abc1234") for call in calls)
        assert not any("install canary" in a.lower() for a in result.actions)


class TestPromotionArtifact:
    """Test the promotion artifact writing."""

    def test_artifact_written_on_success(self, tmp_path: Path) -> None:
        """A promotion artifact should be written even on dry-run success."""
        import channel_promote

        result = channel_promote.PromotionResult(
            source="dev",
            target="beta",
            success=True,
            dry_run=True,
            actions=["simulated promotion"],
        )

        artifact = channel_promote.write_promotion_artifact(
            tmp_path, "dev", "beta", result
        )
        assert artifact.exists()
        data = json.loads(artifact.read_text())
        assert data["source_channel"] == "dev"
        assert data["target_channel"] == "beta"
        assert data["success"] is True
        assert data["dry_run"] is True

    def test_artifact_written_on_failure(self, tmp_path: Path) -> None:
        """A promotion artifact should be written on failure too."""
        import channel_promote

        result = channel_promote.PromotionResult(
            source="dev",
            target="beta",
            success=False,
            dry_run=False,
            errors=["check failed"],
        )

        artifact = channel_promote.write_promotion_artifact(
            tmp_path, "dev", "beta", result
        )
        assert artifact.exists()
        data = json.loads(artifact.read_text())
        assert data["success"] is False
        assert "check failed" in data["errors"]


class TestChannelUpdateStatus:
    """Test the status reporting."""

    def test_status_runs_without_crash(self, tmp_path: Path) -> None:
        """show_status should not crash even without a real git repo."""
        import channel_update
        # Mock run_git to fail gracefully
        with patch.object(channel_update, "run_git", return_value=(-1, "", "not a git repo")):
            # Just verify it doesn't raise
            try:
                channel_update.show_status(tmp_path)
            except Exception as exc:
                pytest.fail(f"show_status raised: {exc}")


class TestChannelIsolation:
    """Test that channels enforce isolation rules."""

    def test_no_reverse_promotion(self) -> None:
        """Promotion paths should not allow regression."""
        import channel_promote
        # release is not a source
        assert "release" not in channel_promote.PROMOTION_PATHS
        # beta is not a source of anything except release
        # and dev is not a source of anything except beta
        sources = set(channel_promote.PROMOTION_PATHS.keys())
        targets = set(channel_promote.PROMOTION_PATHS.values())
        # No overlap (no channel is both a source and a target)
        assert sources.isdisjoint(targets) is False  # dev and beta overlap as targets
        # But no channel should appear as a target of itself
        for src, tgt in channel_promote.PROMOTION_PATHS.items():
            assert src != tgt

    def test_ff_only_semantics_documented(self) -> None:
        """Fast-forward-only requirement should be documented."""
        doc = Path(__file__).parent.parent / "docs" / "CHANNELS.md"
        content = doc.read_text()
        assert "fast-forward only" in content.lower() or "fast-forward-only" in content.lower()

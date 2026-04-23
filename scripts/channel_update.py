#!/usr/bin/env python3
"""
channel_update.py — fast-forward local channel tracking.

Usage:
    python scripts/channel_update.py dev       # track dev
    python scripts/channel_update.py beta     # track beta
    python scripts/channel_update.py release   # track release (read-only)
    python scripts/channel_update.py status    # show current tracking state
    python scripts/channel_update.py canary    # run install canary only


Each channel is a git branch. Updates are fetch + fast-forward merge only, then a post-update full test suite and install canary gate.
No silent merge of unrelated changes — if the update is not ff-able, it errors
and leaves the tree untouched.

Environment:
    CHANNEL_UPDATE_DRY_RUN=1  — simulate only, no checkout/fetch
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Add src to path for imports when run as script
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from hermesoptimizer.extensions.doctor import run_doctor
    DOCTOR_AVAILABLE = True
except ImportError:
    DOCTOR_AVAILABLE = False


CHANNELS = ["dev", "beta", "release"]
PROMOTION_PATHS = {
    "dev": "beta",
    "beta": "release",
}
CHANNEL_DOC = """
HermesOptimizer channel tracker.

Usage: channel_update.py <command>

Commands:
  dev       Track and update the dev channel
  beta      Track and update the beta channel
  release   Track and update the release channel (read-only)
  status    Show current tracking state and channel info
  canary    Run install canary only (doctor dry-run)

Examples:
  python scripts/channel_update.py dev       # fast-forward to latest dev
  python scripts/channel_update.py status     # show current channel state
"""


@dataclass
class ChannelState:
    """State of one channel worktree."""
    name: str
    branch: str
    tracked: bool
    commit: str
    behind: int = 0
    ahead: int = 0
    ff_candidate: bool = False
    canary_passed: bool = False
    canary_errors: list[str] = field(default_factory=list)


@dataclass
class UpdateResult:
    """Result of a channel update operation."""
    channel: str
    success: bool
    dry_run: bool
    actions: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    canary_report: dict | None = None


def run_git(*args: str, cwd: Path | None = None) -> tuple[int, str, str]:
    """Run a git command, return (exit_code, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["git"] + list(args),
            cwd=cwd,
            capture_output=True,
            text=True,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return -1, "", "git not found"


def get_current_branch(repo_root: Path) -> str:
    """Get the current branch name."""
    _, out, _ = run_git("rev-parse", "--abbrev-ref", "HEAD", cwd=repo_root)
    return out


def get_remote_tracking_branch(repo_root: Path, branch: str) -> str | None:
    """Get the remote tracking branch for a local branch."""
    _, out, _ = run_git("rev-parse", "--verify", f"origin/{branch}", cwd=repo_root)
    if out:
        return out
    return None


def rev_list_count(from_commit: str, to_commit: str, repo_root: Path) -> int:
    """Count commits from..to (0 if to is ancestor of from)."""
    code, out, _ = run_git("log", "--oneline", f"{from_commit}..{to_commit}", cwd=repo_root)
    if code != 0:
        return -1
    return len(out.splitlines()) if out else 0


def is_fast_forward(from_commit: str, to_commit: str, repo_root: Path) -> bool:
    """Check if from_commit can be fast-forwarded to to_commit."""
    code, out, _ = run_git("merge-base", "--is-ancestor", from_commit, to_commit, cwd=repo_root)
    return code == 0


def fetch_origin(repo_root: Path, dry_run: bool = False) -> tuple[bool, str]:
    """Fetch all remotes. Returns (success, message)."""
    if dry_run:
        return True, "would fetch from all remotes"
    code, out, err = run_git("fetch", "--all", "--prune", cwd=repo_root)
    if code != 0:
        return False, f"fetch failed: {err}"
    return True, out


def run_update_test_gate(repo_root: Path, dry_run: bool = False) -> tuple[bool, str]:
    """Run the post-update test gate.

    This is a truthful full-suite gate: it runs the entire pytest suite.
    """
    if dry_run:
        return True, "dry run — would run: pytest -q (full suite)"

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=300,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "test timed out"
    except FileNotFoundError:
        return False, "pytest not found"


def rollback_to_commit(repo_root: Path, commit: str) -> tuple[bool, str]:
    """Rollback the working tree to a known commit."""
    code, _, err = run_git("reset", "--hard", commit, cwd=repo_root)
    if code != 0:
        return False, f"rollback failed: {err}"
    return True, f"rolled back to {commit}"


def run_install_canary(repo_root: Path, dry_run: bool = False) -> tuple[bool, dict]:
    """Run the install integrity canary. Returns (passed, report)."""
    if not DOCTOR_AVAILABLE:
        return True, {"note": "doctor not available — canary skipped"}

    if dry_run:
        return True, {"note": "dry run — canary skipped"}

    try:
        report = run_doctor(dry_run=True)
        issues = report.get("issues", [])
        passed = len(issues) == 0
        return passed, report
    except Exception as exc:
        return False, {"error": str(exc)}


def check_channel_state(repo_root: Path, channel: str) -> ChannelState:
    """Get the current state of a channel."""
    branch = channel  # channel name == branch name for our model
    current = get_current_branch(repo_root)
    tracked = current == branch

    # Get local and remote commit for this branch
    _, local_sha, _ = run_git("rev-parse", branch, cwd=repo_root)
    _, remote_sha, _ = run_git("rev-parse", f"origin/{branch}", cwd=repo_root)

    behind = 0
    ahead = 0
    ff_candidate = False

    if local_sha and remote_sha:
        if is_fast_forward(local_sha, remote_sha, repo_root):
            behind = rev_list_count(local_sha, remote_sha, repo_root)
            ff_candidate = behind > 0
        elif is_fast_forward(remote_sha, local_sha, repo_root):
            ahead = rev_list_count(remote_sha, local_sha, repo_root)

    canary_passed = False
    canary_errors: list[str] = []

    if ff_candidate:
        canary_ok, canary_report = run_install_canary(repo_root, dry_run=True)
        canary_passed = canary_ok
        if not canary_ok:
            canary_errors = canary_report.get("issues", [])

    return ChannelState(
        name=channel,
        branch=branch,
        tracked=tracked,
        commit=local_sha[:8] if local_sha else "(none)",
        behind=behind,
        ahead=ahead,
        ff_candidate=ff_candidate,
        canary_passed=canary_passed,
        canary_errors=canary_errors,
    )


def update_channel(repo_root: Path, channel: str, dry_run: bool = False) -> UpdateResult:
    """Fast-forward a channel branch to its origin counterpart."""
    result = UpdateResult(channel=channel, success=False, dry_run=dry_run)

    if channel not in CHANNELS:
        result.errors.append(f"Unknown channel: {channel}. Valid: {CHANNELS}")
        return result

    if channel == "release":
        # Release is read-only — no ff merge, only manual promotion
        result.errors.append("release channel is read-only. Use promotion workflow.")
        return result

    # Step 1: fetch
    fetch_ok, fetch_msg = fetch_origin(repo_root, dry_run=dry_run)
    result.actions.append(f"fetch: {fetch_msg}")
    if not fetch_ok:
        result.errors.append(fetch_msg)
        return result

    # Step 2: check ff eligibility
    state = check_channel_state(repo_root, channel)

    if not state.ff_candidate:
        if state.behind == 0 and state.ahead == 0:
            result.actions.append(f"channel {channel} is up to date")
            result.success = True
            return result
        elif state.ahead > 0:
            result.errors.append(
                f"Local {channel} has {state.ahead} commits not on origin — "
                "cannot fast-forward. Push or reset."
            )
            return result
        else:
            result.errors.append(f"Channel {channel} is not a fast-forward candidate")
            return result

    result.actions.append(
        f"behind origin/{channel} by {state.behind} commits — fast-forward candidate"
    )

    if dry_run:
        result.actions.append(f"would: git checkout {channel} && git merge --ff-only origin/{channel}")
        result.actions.append("would run: pytest -q (full suite)")
        result.actions.append("would run install canary after update")
        result.success = True
        return result

    pre_update_commit = state.commit

    # Step 3: ensure branch is checked out before applying the fast-forward
    current = get_current_branch(repo_root)
    if current != channel:
        result.actions.append(f"checking out {channel}")
        code, _, err = run_git("checkout", channel, cwd=repo_root)
        if code != 0:
            result.errors.append(f"checkout failed: {err}")
            return result

    # Step 4: ff merge
    code, _, err = run_git("merge", "--ff-only", f"origin/{channel}", cwd=repo_root)
    if code != 0:
        result.errors.append(f"ff merge failed: {err}")
        return result
    result.actions.append(f"fast-forwarded {channel} to origin/{channel}")

    # Step 5: post-update test gate
    test_ok, test_output = run_update_test_gate(repo_root, dry_run=False)
    result.actions.append("test gate: full suite")
    if not test_ok:
        result.errors.append(f"test gate FAILED — rolling back. Output: {test_output[-200:] if len(test_output) > 200 else test_output}")
        rollback_ok, rollback_msg = rollback_to_commit(repo_root, pre_update_commit)
        result.actions.append(rollback_msg)
        if not rollback_ok:
            result.errors.append(rollback_msg)
        return result
    result.actions.append("test gate: PASSED")

    # Step 6: post-update install integrity canary
    canary_ok, canary_report = run_install_canary(repo_root, dry_run=False)
    result.canary_report = canary_report
    if not canary_ok:
        result.errors.append(f"install canary FAILED — rolling back. Issues: {canary_report.get('issues', [])}")
        rollback_ok, rollback_msg = rollback_to_commit(repo_root, pre_update_commit)
        result.actions.append(rollback_msg)
        if not rollback_ok:
            result.errors.append(rollback_msg)
        return result
    result.actions.append("install canary: PASSED")

    result.success = True
    return result


def show_status(repo_root: Path) -> None:
    """Print current channel tracking status."""
    current = get_current_branch(repo_root)
    print(f"Current branch: {current}")
    print()

    for channel in CHANNELS:
        state = check_channel_state(repo_root, channel)
        marker = ">>>" if state.tracked else "   "
        print(f"{marker} {state.name}: commit={state.commit} behind={state.behind} ahead={state.ahead}")

        if state.tracked and state.ff_candidate:
            print(f"    ff candidate — run: channel_update.py {channel}")
        if state.canary_errors:
            print(f"    canary errors: {state.canary_errors}")


def main() -> int:
    """CLI entry point."""
    args = sys.argv[1:]
    dry_run = os.environ.get("CHANNEL_UPDATE_DRY_RUN") == "1"

    repo_root = Path(__file__).parent.parent.resolve()

    # Verify we're in a git repo
    code, _, _ = run_git("rev-parse", "--git-dir", cwd=repo_root)
    if code != 0:
        print("ERROR: not inside a git repository", file=sys.stderr)
        return 1

    if not args or args[0] in ("-h", "--help", "help"):
        print(CHANNEL_DOC)
        return 0

    cmd = args[0]

    if cmd == "status":
        show_status(repo_root)
        return 0

    if cmd == "canary":
        ok, report = run_install_canary(repo_root, dry_run=dry_run)
        print(f"Canary: {'PASSED' if ok else 'FAILED'}")
        if report:
            print(json.dumps(report, indent=2))
        return 0 if ok else 1

    if cmd in CHANNELS:
        result = update_channel(repo_root, cmd, dry_run=dry_run)
        print(f"Channel: {result.channel}")
        for a in result.actions:
            print(f"  action: {a}")
        if result.errors:
            for e in result.errors:
                print(f"  ERROR: {e}", file=sys.stderr)
        print(f"Success: {result.success}")
        return 0 if result.success else 1

    print(f"Unknown command: {cmd}", file=sys.stderr)
    print(CHANNEL_DOC)
    return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
channel_promote.py — promote a channel from dev->beta or beta->release.

Usage:
    python scripts/channel_promote.py dev        # promote dev -> beta
    python scripts/channel_promote.py beta       # promote beta -> release
    python scripts/channel_promote.py status     # show promotion state
    python scripts/channel_promote.py verify      # verify promotion prerequisites

Promotion rules:
  - dev -> beta: run smoke tests, run install canary
  - beta -> release: run full test suite, run release gate
  - Never regress channels (release cannot go back to beta)
  - All operations are logged to promotion-artifacts/

Environment:
    CHANNEL_PROMOTE_DRY_RUN=1  — simulate only
    CHANNEL_PROMOTE_FORCE=1    — skip some checks (dangerous)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from hermesoptimizer.extensions.doctor import run_doctor
    DOCTOR_AVAILABLE = True
except ImportError:
    DOCTOR_AVAILABLE = False


PROMOTION_PATHS = {
    "dev": "beta",
    "beta": "release",
}

VALID_CHANNELS = ["dev", "beta", "release"]


@dataclass
class PromotionCheck:
    """One pre-promotion check."""
    name: str
    passed: bool
    detail: str = ""


@dataclass
class PromotionResult:
    """Result of a promotion attempt."""
    source: str
    target: str
    success: bool
    dry_run: bool
    checks: list[PromotionCheck] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    artifact_path: str | None = None


def run_git(*args: str, cwd: Path | None = None) -> tuple[int, str, str]:
    """Run a git command."""
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
    """Get current branch."""
    _, out, _ = run_git("rev-parse", "--abbrev-ref", "HEAD", cwd=repo_root)
    return out


def get_head_commit(repo_root: Path) -> str:
    """Get current HEAD sha short."""
    _, out, _ = run_git("rev-parse", "--short", "HEAD", cwd=repo_root)
    return out


def run_tests(repo_root: Path, test_subset: list[str] | None = None, dry_run: bool = False) -> tuple[bool, str]:
    """Run pytest for a subset or the full suite.

    Passing an empty subset means "truthful full-suite gate".
    """
    test_subset = test_subset or []
    command = [sys.executable, "-m", "pytest"]
    if test_subset:
        command.extend(test_subset)
        command.extend(["-v", "--tb=short"])
        summary = f"pytest {' '.join(test_subset)}"
    else:
        command.append("-q")
        summary = "pytest -q (full suite)"

    if dry_run:
        return True, f"dry run — would run: {summary}"

    try:
        result = subprocess.run(
            command,
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


def run_doctor_check(repo_root: Path, dry_run: bool = False) -> tuple[bool, dict]:
    """Run doctor check. Returns (passed, report)."""
    if dry_run:
        return True, {"note": "dry run — doctor skipped"}

    if not DOCTOR_AVAILABLE:
        return True, {"note": "doctor not available"}

    try:
        report = run_doctor(dry_run=True)
        issues = report.get("issues", [])
        return len(issues) == 0, report
    except Exception as exc:
        return False, {"error": str(exc)}


def verify_fast_forward(repo_root: Path, source: str, target: str) -> tuple[bool, str]:
    """Verify source can be fast-forwarded into target branch."""
    # Get commits
    _, src_sha, _ = run_git("rev-parse", source, cwd=repo_root)
    _, tgt_sha, _ = run_git("rev-parse", target, cwd=repo_root)

    if not src_sha or not tgt_sha:
        return False, "could not resolve one or both branch commits"

    # Check if source is ancestor of target (would be regression)
    code, _, _ = run_git("merge-base", "--is-ancestor", src_sha, tgt_sha, cwd=repo_root)
    if code == 0:
        return False, f"{source} is already ancestor of {target} — no forward progress"

    # Check if target is ancestor of source (ff possible)
    code, _, _ = run_git("merge-base", "--is-ancestor", tgt_sha, src_sha, cwd=repo_root)
    if code == 0:
        return True, f"fast-forward possible: {source} -> {target}"
    return False, f"not a direct fast-forward — requires manual merge"


def write_promotion_artifact(
    repo_root: Path,
    source: str,
    target: str,
    result: PromotionResult,
) -> Path:
    """Write a promotion artifact to disk."""
    artifact_dir = repo_root / "promotion-artifacts"
    artifact_dir.mkdir(exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tag = f"promotion-{source}-to-{target}-{timestamp}"

    data = {
        "tag": tag,
        "timestamp": timestamp,
        "source_channel": source,
        "target_channel": target,
        "success": result.success,
        "dry_run": result.dry_run,
        "checks": [
            {"name": c.name, "passed": c.passed, "detail": c.detail}
            for c in result.checks
        ],
        "actions": result.actions,
        "errors": result.errors,
        "head_commit": get_head_commit(repo_root),
    }

    artifact_file = artifact_dir / f"{tag}.json"
    artifact_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    result.artifact_path = str(artifact_file)
    return artifact_file


def run_promotion_checks(source: str, target: str, repo_root: Path, dry_run: bool) -> list[PromotionCheck]:
    """Run all pre-promotion checks. Returns list of check results."""
    checks: list[PromotionCheck] = []

    # Check 1: valid channels
    valid = source in VALID_CHANNELS and target in VALID_CHANNELS
    checks.append(PromotionCheck(
        name="valid_channels",
        passed=valid,
        detail=f"{source} -> {target}" if valid else f"invalid: {source} or {target}",
    ))

    # Check 2: forward only
    forward_only = PROMOTION_PATHS.get(source) == target
    checks.append(PromotionCheck(
        name="forward_only",
        passed=forward_only,
        detail=f"{source} -> {target}" if forward_only else f"{source} cannot go to {target}",
    ))

    # Check 3: fast-forward
    if forward_only:
        ff_ok, ff_detail = verify_fast_forward(repo_root, source, target)
        checks.append(PromotionCheck(
            name="fast_forward",
            passed=ff_ok,
            detail=ff_detail,
        ))
    else:
        checks.append(PromotionCheck(name="fast_forward", passed=False, detail="skipped"))

    # Check 4: source branch exists
    _, _, _ = run_git("rev-parse", "--verify", source, cwd=repo_root)
    src_exists = run_git("rev-parse", "--verify", source, cwd=repo_root)[0] == 0
    checks.append(PromotionCheck(
        name="source_exists",
        passed=src_exists,
        detail=f"{source} exists" if src_exists else f"{source} not found",
    ))

    # Check 5: test gate for dev->beta
    if source == "dev" and target == "beta":
        test_subset = [
            "tests/test_extensions_sync.py",
            "tests/test_extensions_loader.py",
            "tests/test_extensions_schema.py",
        ]
        passed, output = run_tests(repo_root, test_subset, dry_run=dry_run)
        checks.append(PromotionCheck(
            name="test_gate",
            passed=passed,
            detail=output[-200:] if len(output) > 200 else output,
        ))

    # Check 6: install canary
    canary_ok, canary_report = run_doctor_check(repo_root, dry_run=dry_run)
    checks.append(PromotionCheck(
        name="install_canary",
        passed=canary_ok,
        detail=str(canary_report)[:200],
    ))

    # Check 7: full test gate for beta->release
    if source == "beta" and target == "release":
        passed, output = run_tests(repo_root, None, dry_run=dry_run)
        checks.append(PromotionCheck(
            name="full_test_gate",
            passed=passed,
            detail=output[-200:] if len(output) > 200 else output,
        ))

    return checks


def do_promotion(source: str, target: str, repo_root: Path, dry_run: bool) -> PromotionResult:
    """Execute the actual promotion."""
    result = PromotionResult(
        source=source,
        target=target,
        success=False,
        dry_run=dry_run,
    )

    # Run all checks first
    result.checks = run_promotion_checks(source, target, repo_root, dry_run)

    all_passed = all(c.passed for c in result.checks)
    if not all_passed:
        result.errors.append("One or more checks failed — promotion blocked")
        write_promotion_artifact(repo_root, source, target, result)
        return result

    result.actions.append(f"all checks passed — promoting {source} -> {target}")

    if dry_run:
        result.actions.append(f"DRY RUN: would run:")
        result.actions.append(f"  git checkout {target}")
        result.actions.append(f"  git merge --ff-only {source}")
        result.success = True
        write_promotion_artifact(repo_root, source, target, result)
        return result

    # Perform the promotion
    # 1. Checkout target
    code, _, err = run_git("checkout", target, cwd=repo_root)
    if code != 0:
        result.errors.append(f"checkout {target} failed: {err}")
        write_promotion_artifact(repo_root, source, target, result)
        return result
    result.actions.append(f"checked out {target}")

    # 2. FF merge source
    code, _, err = run_git("merge", "--ff-only", source, cwd=repo_root)
    if code != 0:
        result.errors.append(f"merge {source} into {target} failed: {err}")
        write_promotion_artifact(repo_root, source, target, result)
        return result
    result.actions.append(f"fast-forward merged {source} into {target}")

    result.success = True
    write_promotion_artifact(repo_root, source, target, result)
    return result


def show_promotion_status(repo_root: Path) -> None:
    """Show current promotion state."""
    current = get_current_branch(repo_root)
    print(f"Current branch: {current}")
    print(f"Promotion paths: {PROMOTION_PATHS}")

    for source, target in PROMOTION_PATHS.items():
        ff_ok, detail = verify_fast_forward(repo_root, source, target)
        marker = "✓" if ff_ok else " "
        print(f"  {marker} {source} -> {target}: {detail}")


def main() -> int:
    """CLI entry point."""
    args = sys.argv[1:]
    dry_run = os.environ.get("CHANNEL_PROMOTE_DRY_RUN") == "1"
    force = os.environ.get("CHANNEL_PROMOTE_FORCE") == "1"

    repo_root = Path(__file__).parent.parent.resolve()

    # Verify git repo
    code, _, _ = run_git("rev-parse", "--git-dir", cwd=repo_root)
    if code != 0:
        print("ERROR: not inside a git repository", file=sys.stderr)
        return 1

    if not args or args[0] in ("-h", "--help", "help"):
        print("""
channel_promote.py — promote between HermesOptimizer channels

Usage:
  channel_promote.py dev      # promote dev -> beta
  channel_promote.py beta     # promote beta -> release
  channel_promote.py status   # show promotion readiness
  channel_promote.py verify    # run checks without promoting

Environment:
  CHANNEL_PROMOTE_DRY_RUN=1   # simulate promotion
  CHANNEL_PROMOTE_FORCE=1     # skip some checks (dangerous)
""")
        return 0

    cmd = args[0]

    if cmd == "status":
        show_promotion_status(repo_root)
        return 0

    if cmd == "verify":
        # Just run checks, don't promote
        if len(args) < 2:
            print("verify requires a source channel (dev or beta)", file=sys.stderr)
            return 1
        source = args[1]
        target = PROMOTION_PATHS.get(source)
        if not target:
            print(f"No promotion path from {source}", file=sys.stderr)
            return 1
        checks = run_promotion_checks(source, target, repo_root, dry_run=False)
        for c in checks:
            status = "PASS" if c.passed else "FAIL"
            print(f"  [{status}] {c.name}: {c.detail}")
        return 0 if all(c.passed for c in checks) else 1

    if cmd in PROMOTION_PATHS:
        source = cmd
        target = PROMOTION_PATHS[source]
        result = do_promotion(source, target, repo_root, dry_run)

        print(f"Promotion: {source} -> {target}")
        print(f"Dry run: {result.dry_run}")
        print(f"Success: {result.success}")
        for c in result.checks:
            status = "PASS" if c.passed else "FAIL"
            print(f"  [{status}] {c.name}")
        for a in result.actions:
            print(f"  action: {a}")
        for e in result.errors:
            print(f"  ERROR: {e}", file=sys.stderr)
        if result.artifact_path:
            print(f"Artifact: {result.artifact_path}")
        return 0 if result.success else 1

    print(f"Unknown command: {cmd}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())

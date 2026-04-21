"""CLI handlers for extension management commands."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hermesoptimizer.extensions import build_registry
from hermesoptimizer.extensions.schema import Ownership
from hermesoptimizer.extensions.status import check_all_statuses
from hermesoptimizer.extensions.sync import sync_all
from hermesoptimizer.extensions.verify import verify_all


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def handle_ext_list(args: argparse.Namespace) -> int:
    """List all registered extensions."""
    registry_dir = _repo_root() / "extensions"
    if not registry_dir.exists():
        print("No extensions directory found.", file=sys.stderr)
        return 1

    entries = build_registry(registry_dir)
    for entry in entries:
        status = "ok"
        if entry.ownership != Ownership.EXTERNAL_RUNTIME:
            if not entry.source_exists(_repo_root()):
                status = "missing_source"
        print(f"{entry.id:20} {entry.type.value:18} {entry.ownership.value:18} {status}")
    return 0


def handle_ext_status(args: argparse.Namespace) -> int:
    """Show extension status: repo source vs runtime target."""
    registry_dir = _repo_root() / "extensions"
    if not registry_dir.exists():
        print("No extensions directory found.", file=sys.stderr)
        return 1

    entries = build_registry(registry_dir)
    statuses = check_all_statuses(entries, _repo_root())

    for st in statuses:
        print(f"{st.id:20} {st.status:15} {st.detail}")
    return 0


def handle_ext_verify(args: argparse.Namespace) -> int:
    """Run verification contract for one or all extensions."""
    registry_dir = _repo_root() / "extensions"
    if not registry_dir.exists():
        print("No extensions directory found.", file=sys.stderr)
        return 1

    entries = build_registry(registry_dir)
    target_id = args.id if hasattr(args, "id") else None

    if target_id and target_id != "all":
        entries = [e for e in entries if e.id == target_id]
        if not entries:
            print(f"Extension not found: {target_id}", file=sys.stderr)
            return 1

    results = verify_all(entries, cwd=_repo_root())
    any_failed = False
    for res in results:
        status = "PASS" if res.passed else "FAIL"
        if not res.passed:
            any_failed = True
        print(f"{res.id:20} {status:6} exit={res.exit_code}")
        if args.verbose:
            if res.command:
                print(f"  command: {res.command}")
            if res.stdout:
                print(f"  stdout: {res.stdout}")
            if res.stderr:
                print(f"  stderr: {res.stderr}")
    return 1 if any_failed else 0


def handle_ext_sync(args: argparse.Namespace) -> int:
    """Sync repo-managed artifacts to install targets."""
    registry_dir = _repo_root() / "extensions"
    if not registry_dir.exists():
        print("No extensions directory found.", file=sys.stderr)
        return 1

    entries = build_registry(registry_dir)
    target_id = args.id if hasattr(args, "id") else None

    if target_id and target_id != "all":
        entries = [e for e in entries if e.id == target_id]
        if not entries:
            print(f"Extension not found: {target_id}", file=sys.stderr)
            return 1

    results = sync_all(entries, _repo_root(), dry_run=args.dry_run, force=args.force)
    any_errors = False
    for res in results:
        status = "SYNCED" if res.synced else ("SKIPPED" if res.skipped else "ERROR")
        print(f"{res.id:20} {status:8}")
        for action in res.actions:
            print(f"  + {action}")
        for error in res.errors:
            any_errors = True
            print(f"  ! {error}")
    return 1 if any_errors else 0

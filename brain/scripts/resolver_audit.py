#!/usr/bin/env python3
"""Resolver audit — verify routing coverage in resolver-cases.json.

Reads resolver cases from the fixture, inspects referenced artifacts,
and reports missing, ambiguous, or weak deterministic paths.

Examples:
  python3 resolver_audit.py
  python3 resolver_audit.py --cases brain/evals/resolver-cases.json
  python3 resolver_audit.py --output brain/reports/resolver-audit.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# --------------------------------------------------------------------------  #
# Core logic
# --------------------------------------------------------------------------  #


def load_cases(cases_path: Path) -> list[dict[str, Any]]:
    """Load resolver cases from JSON fixture. Returns empty list on error."""
    try:
        data = json.loads(cases_path.read_text())
        if isinstance(data, list):
            return data
        return []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


# Pattern to detect template/glob placeholders in paths
TEMPLATE_RE = re.compile(r"<[^>]+>")


def _resolve_first_path(first_path: str, repo_root: Path) -> tuple[bool, str]:
    """Resolve expected_first_path to an absolute path and check existence.

    Returns (exists, abs_path_or_error).
    """
    # Handle relative paths like "scripts/foo.py" or "providers/"
    if first_path.startswith("scripts/"):
        resolved = repo_root / first_path
    elif first_path.startswith("providers/"):
        resolved = repo_root / "brain" / first_path
    elif first_path.startswith("incidents/"):
        resolved = repo_root / "brain" / first_path
    elif first_path.startswith("active-work/"):
        resolved = repo_root / "brain" / first_path
    elif first_path.startswith("reports/"):
        resolved = repo_root / "brain" / first_path
    elif first_path.startswith("evals/"):
        resolved = repo_root / "brain" / first_path
    elif first_path.startswith("patterns/"):
        resolved = repo_root / "brain" / first_path
    elif first_path.startswith("brain/"):
        resolved = repo_root / first_path
    else:
        # Already absolute or unusual
        resolved = Path(first_path)

    return resolved.exists(), str(resolved)


def _check_artifact(
    artifact: str, repo_root: Path
) -> tuple[bool, list[str]]:
    """Check if expected_artifact exists.

    Handles:
      - Concrete files (providers/kimi-coding.md)
      - Directories (providers/, incidents/)
      - Template paths (active-work/<thread>.md) -> weak
      - Glob-style (skills or incident + eval) -> ambiguous

    Returns (exists, issues).
    """
    issues: list[str] = []

    # Template placeholder like <thread>.md indicates non-concrete path
    if TEMPLATE_RE.search(artifact):
        issues.append("weak:template_path")

    # Ambiguous description instead of concrete path
    if artifact in ("skills or incident + eval", "incident + eval", "skills"):
        issues.append("ambiguous:no_concrete_artifact")

    # Directory reference - only an issue if we need a specific file
    if artifact.endswith("/"):
        # Directories are acceptable as "look here first" hints
        # But if first_path is also just a directory, it's weak
        return True, []

    # Concrete file path
    if artifact.startswith("providers/"):
        resolved = repo_root / "brain" / artifact
    elif artifact.startswith("incidents/"):
        resolved = repo_root / "brain" / artifact
    elif artifact.startswith("active-work/"):
        resolved = repo_root / "brain" / artifact
    elif artifact.startswith("scripts/"):
        resolved = repo_root / artifact
    elif artifact.startswith("reports/"):
        resolved = repo_root / "brain" / artifact
    elif artifact.startswith("brain/"):
        resolved = repo_root / artifact
    elif artifact.startswith("/"):
        resolved = Path(artifact)
    else:
        resolved = repo_root / "brain" / artifact

    exists = resolved.exists()

    # If not exists and not a template, report as missing
    if not exists and not issues:
        issues.append("missing:artifact_not_found")

    return exists, issues


def check_case(case: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    """Audit a single resolver case.

    Returns a dict with:
      intent, status (pass|fail|ambiguous|weak), issues (list),
      first_path_resolved, first_path_exists, artifact_status,
      missing_artifacts (list), notes.
    """
    intent = case.get("intent", "")
    first_path = case.get("expected_first_path", "")
    artifact = case.get("expected_artifact", "")
    notes = case.get("notes", "")

    issues: list[str] = []
    missing_artifacts: list[str] = []

    # Check first_path existence
    first_path_exists, first_path_resolved = _resolve_first_path(first_path, repo_root)

    if not first_path_exists:
        issues.append("missing:first_path_not_found")
        missing_artifacts.append(first_path)

    # Check artifact
    artifact_exists, artifact_issues = _check_artifact(artifact, repo_root)
    issues.extend(artifact_issues)

    if not artifact_exists:
        missing_artifacts.append(artifact)

    # Determine status
    if not first_path_exists or "missing:artifact_not_found" in issues:
        status = "fail"
    elif any("ambiguous" in i for i in issues):
        status = "ambiguous"
    elif any("weak" in i for i in issues):
        status = "weak"
    else:
        status = "pass"

    # Special case: if first_path is just a directory (no concrete file),
    # mark as weak even if directory exists
    if first_path_exists and not first_path.endswith((".py", ".md", ".json", ".yaml")):
        if ":" not in first_path and not TEMPLATE_RE.search(first_path):
            # It's a bare directory like "incidents/" or "active-work/"
            issues.append("weak:directory_only_first_path")

    return {
        "intent": intent,
        "status": status,
        "issues": issues,
        "first_path": first_path,
        "first_path_resolved": first_path_resolved,
        "first_path_exists": first_path_exists,
        "artifact": artifact,
        "artifact_exists": artifact_exists,
        "missing_artifacts": missing_artifacts,
        "notes": notes,
    }


def build_report(cases: list[dict[str, Any]], repo_root: Path) -> dict[str, Any]:
    """Build a full audit report across all cases.

    Returns dict with:
      total_cases, cases (list of per-case results),
      missing_artifacts (aggregated list),
      ambiguous_or_weak (list of case intents),
      overall_status (pass|fail),
      timestamp (ISO).
    """
    if not cases:
        return {
            "total_cases": 0,
            "cases": [],
            "missing_artifacts": [],
            "ambiguous_or_weak": [],
            "overall_status": "fail",
            "error": "no resolver cases loaded",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    results = [check_case(c, repo_root) for c in cases]

    missing_artifacts: list[str] = []
    ambiguous_or_weak: list[dict[str, Any]] = []

    for r in results:
        missing_artifacts.extend(r["missing_artifacts"])
        if r["status"] in ("ambiguous", "weak"):
            ambiguous_or_weak.append({
                "intent": r["intent"],
                "status": r["status"],
                "issues": r["issues"],
            })

    # Deduplicate missing artifacts
    missing_artifacts = list(dict.fromkeys(missing_artifacts))

    fail_count = sum(1 for r in results if r["status"] == "fail")
    overall = "fail" if fail_count > 0 else ("pass" if not ambiguous_or_weak else "ambiguous")

    return {
        "total_cases": len(cases),
        "cases": results,
        "missing_artifacts": missing_artifacts,
        "ambiguous_or_weak": ambiguous_or_weak,
        "overall_status": overall,
        "fail_count": fail_count,
        "ambiguous_or_weak_count": len(ambiguous_or_weak),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# --------------------------------------------------------------------------  #
# CLI
# --------------------------------------------------------------------------  #


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit resolver fixture for missing or ambiguous routing paths.",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).parent.parent / "evals" / "resolver-cases.json",
        help="Path to resolver-cases.json (default: brain/evals/resolver-cases.json)",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("/home/agent/hermesagent"),
        help="Repository root (default: /home/agent/hermesagent)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write JSON report.",
    )
    args = parser.parse_args()

    # Resolve cases path relative to script if not absolute
    cases_path = args.cases
    if not cases_path.is_absolute():
        cases_path = Path(__file__).parent.parent / args.cases

    cases = load_cases(cases_path)
    report = build_report(cases, repo_root=args.repo_root)
    report["fixture_path"] = str(cases_path)
    report["repo_root"] = str(args.repo_root)

    text = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n")
    print(text)

    return 0 if report["overall_status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())

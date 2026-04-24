"""Test inventory / selector hardening for v0.9.4.

Deterministic, offline guards that verify:
- TESTPLAN.md lists every collected test file (no undocumented files).
- Baseline test count (2065) and file count (118) match live pytest collect-only.
- Selector cheat sheet covers required domains.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTPLAN_PATH = REPO_ROOT / "TESTPLAN.md"


def _collect_only() -> dict[str, int]:
    """Run pytest --collect-only -q and return {relative_path: test_count}."""
    result = subprocess.run(
        ["python", "-m", "pytest", "--collect-only", "-q"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env={**dict(subprocess.os.environ), "PYTHONPATH": "src"},
    )
    assert result.returncode == 0, f"pytest collect-only failed:\n{result.stderr}"
    mapping: dict[str, int] = {}
    for line in result.stdout.strip().splitlines():
        # Lines look like: tests/test_foo.py: 42
        if ": " in line:
            path_part, num_part = line.rsplit(": ", 1)
            try:
                mapping[path_part.strip()] = int(num_part.strip())
            except ValueError:
                continue
    return mapping


def _backticked_paths_in_testplan() -> set[str]:
    """Extract all backticked paths that look like test files from TESTPLAN.md.

    Bare filenames (e.g. `test_foo.py`) are normalised to their actual
    relative path under tests/ when the file exists unambiguously.
    """
    text = TESTPLAN_PATH.read_text(encoding="utf-8")
    pattern = re.compile(r"`([^`]*test_[^`]*\.py)`")
    raw = set(pattern.findall(text))

    # Build a lookup of basename -> relative path for every real test file
    basename_map: dict[str, str] = {}
    for p in (REPO_ROOT / "tests").rglob("test_*.py"):
        rel = str(p.relative_to(REPO_ROOT))
        basename = p.name
        # If a basename appears more than once we can't normalise it
        if basename in basename_map:
            basename_map[basename] = ""  # mark ambiguous
        else:
            basename_map[basename] = rel

    for p in (REPO_ROOT / "brain" / "scripts").rglob("test_*.py"):
        rel = str(p.relative_to(REPO_ROOT))
        basename = p.name
        if basename in basename_map:
            basename_map[basename] = ""
        else:
            basename_map[basename] = rel

    normalised: set[str] = set()
    for entry in raw:
        if "/" in entry or "\\" in entry:
            normalised.add(entry)
            continue
        mapped = basename_map.get(entry)
        if mapped:
            normalised.add(mapped)
        else:
            normalised.add(entry)
    return normalised


def _all_test_files_on_disk() -> set[str]:
    """Gather actual test_*.py files under tests/ and brain/scripts/."""
    files: set[str] = set()
    for p in (REPO_ROOT / "tests").rglob("test_*.py"):
        files.add(str(p.relative_to(REPO_ROOT)))
    for p in (REPO_ROOT / "brain" / "scripts").rglob("test_*.py"):
        files.add(str(p.relative_to(REPO_ROOT)))
    return files


# ---------------------------------------------------------------------------
# Baseline counts
# ---------------------------------------------------------------------------

EXPECTED_TEST_COUNT = 2065
EXPECTED_FILE_COUNT = 118


class TestBaselineCounts:
    """Verify live pytest collect-only matches the v0.9.4 baseline."""

    def test_total_test_count(self) -> None:
        mapping = _collect_only()
        total = sum(mapping.values())
        assert total == EXPECTED_TEST_COUNT, (
            f"Baseline test count mismatch: expected {EXPECTED_TEST_COUNT}, got {total}. "
            "Update TESTPLAN.md baseline and this guard if the change is intentional."
        )

    def test_total_file_count(self) -> None:
        mapping = _collect_only()
        assert len(mapping) == EXPECTED_FILE_COUNT, (
            f"Baseline file count mismatch: expected {EXPECTED_FILE_COUNT}, got {len(mapping)}. "
            "Update TESTPLAN.md baseline and this guard if the change is intentional."
        )


# ---------------------------------------------------------------------------
# Inventory completeness
# ---------------------------------------------------------------------------

class TestInventoryCompleteness:
    """Verify every test file on disk is documented in TESTPLAN.md."""

    def test_no_undocumented_test_files(self) -> None:
        on_disk = _all_test_files_on_disk()
        in_plan = _backticked_paths_in_testplan()
        missing = on_disk - in_plan
        assert not missing, (
            f"The following test files are not backticked in TESTPLAN.md:\n"
            + "\n".join(sorted(missing))
            + "\nAdd them to the appropriate domain section or the complete inventory."
        )

    def test_no_stale_test_file_references(self) -> None:
        """Every backticked test file in TESTPLAN.md must exist on disk."""
        on_disk = _all_test_files_on_disk()
        in_plan = _backticked_paths_in_testplan()
        stale = in_plan - on_disk
        assert not stale, (
            f"TESTPLAN.md references test files that no longer exist:\n"
            + "\n".join(sorted(stale))
            + "\nRemove stale references from TESTPLAN.md."
        )


# ---------------------------------------------------------------------------
# Selector cheat sheet coverage
# ---------------------------------------------------------------------------

REQUIRED_SELECTOR_DOMAINS = [
    ("governance/release", ["test_governance_docs.py", "test_release_readiness.py"]),
    ("extensions", ["test_extensions_"]),
    ("CLI", ["test_cli_"]),
    ("provider/model", ["test_provider_", "test_model_"]),
    ("tool-surface", ["test_tool_surface_"]),
    ("vault", ["test_vault_"]),
    ("dreams", ["test_dreams_"]),
    ("budget", ["test_budget_"]),
    ("workflow", ["test_workflow_", "test_scheduler.py", "test_guard.py", "test_devdo_executor.py", "test_todo_shaper.py", "test_ux_format.py", "test_commands.py"]),
    ("full suite", ["-q"]),  # full suite is just "pytest -q" or similar
]


class TestSelectorCheatSheet:
    """Verify TESTPLAN.md selector cheat sheet covers key domains."""

    def test_selector_cheat_sheet_exists(self) -> None:
        text = TESTPLAN_PATH.read_text(encoding="utf-8")
        assert "## v0.9.4 selector cheat sheet" in text or "## Selector cheat sheet" in text, (
            "TESTPLAN.md must contain a '## v0.9.4 selector cheat sheet' or '## Selector cheat sheet' section."
        )

    @pytest.mark.parametrize("domain,fragments", REQUIRED_SELECTOR_DOMAINS)
    def test_domain_selector_present(self, domain: str, fragments: list[str]) -> None:
        text = TESTPLAN_PATH.read_text(encoding="utf-8")
        # Look for the domain name near a code block containing at least one fragment
        lines = text.splitlines()
        in_code = False
        code_blocks: list[str] = []
        current_block: list[str] = []
        for line in lines:
            if line.strip().startswith("```"):
                if in_code:
                    code_blocks.append("\n".join(current_block))
                    current_block = []
                in_code = not in_code
                continue
            if in_code:
                current_block.append(line)
        if in_code:
            code_blocks.append("\n".join(current_block))

        # Find a code block that mentions at least one fragment
        matched = any(
            any(frag in block for frag in fragments)
            for block in code_blocks
        )
        assert matched, (
            f"Selector cheat sheet missing a code block for domain '{domain}' "
            f"(expected fragment(s): {fragments})."
        )

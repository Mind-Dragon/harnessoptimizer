from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from hermesoptimizer.sources.lane_state import LaneState

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _non_negotiable_numbers() -> list[int]:
    text = _read("GUIDELINE.md")
    section = text.split("## Non-negotiables", 1)[1].split("## Build priorities", 1)[0]
    return [int(match.group(1)) for match in re.finditer(r"^### (\d+)\. ", section, re.MULTILINE)]


def test_guideline_non_negotiables_are_sequential() -> None:
    numbers = _non_negotiable_numbers()
    assert numbers == list(range(1, len(numbers) + 1))
    assert len(numbers) == len(set(numbers))


def test_architecture_layer_count_matches_headings_and_current_helpers() -> None:
    text = _read("ARCHITECTURE.md")
    intro = re.search(r"split into (\w+) layers", text)
    assert intro is not None
    word_to_number = {"seven": 7, "7": 7}
    expected = word_to_number[intro.group(1).lower()]
    model = text.split("## System model", 1)[1].split("## Directory architecture", 1)[0]
    headings = re.findall(r"^### \d+\. ", model, re.MULTILINE)
    assert len(headings) == expected
    planned = text.split("## Planned architecture extensions", 1)[1]
    assert "Planned but not yet built" not in planned
    for helper in ["rail_loader_check.py", "brain_doctor.py", "resolver_audit.py", "active_work_lint.py"]:
        assert f"- `{helper}`" not in planned


def test_active_release_docs_do_not_reopen_closed_v093_work() -> None:
    todo = _read("TODO.md")
    active_work = _read("brain/active-work/current.md")
    forbidden = [
        "follow-up audit pending",
        "until merge policy work lands",
        "dispatch parallel whole-codebase governance audit agents",
        "dispatch audit agents",
    ]
    combined = todo + "\n" + active_work
    assert not any(token in combined for token in forbidden)
    assert "Status: closed locally; v0.9.4 testing/refactor hardening complete." in todo
    assert "Next deterministic step" in active_work
    assert "run the final v0.9.4 gate" in active_work


def test_provider_canary_lane_policy_is_generic() -> None:
    canaries = json.loads(_read("brain/evals/provider-canaries.json"))
    assert canaries, "provider canary fixture must not be empty"
    valid_states = {s.value for s in LaneState}
    seen_names: set[str] = set()

    for entry in canaries:
        name = entry.get("name")
        assert isinstance(name, str) and name, f"canary missing name: {entry}"
        assert name not in seen_names, f"duplicate canary name: {name}"
        seen_names.add(name)

        lane_state = entry.get("lane_state")
        assert lane_state in valid_states, f"canary {name} has invalid lane_state: {lane_state}"

        required_release = bool(entry.get("required_release"))
        if required_release:
            assert LaneState.from_string(lane_state) is LaneState.GREEN, (
                f"canary {name} is required_release but lane_state is {lane_state}"
            )
        else:
            assert LaneState.from_string(lane_state) is not None


def test_repo_only_empty_target_extensions_declare_no_sync_contract() -> None:
    for rel in [
        "extensions/scripts.yaml",
        "extensions/tool_surface.yaml",
        "src/hermesoptimizer/extensions/data/scripts.yaml",
        "src/hermesoptimizer/extensions/data/tool_surface.yaml",
    ]:
        data = yaml.safe_load(_read(rel))
        assert data["ownership"] == "repo_only"
        assert data["target_paths"] == []
        assert data["metadata"]["install_mode"] == "repo_only_no_sync"
        assert data["metadata"]["no_sync_reason"]


def test_release_history_has_unique_top_level_version_headings() -> None:
    changelog = _read("CHANGELOG.md")
    headings = re.findall(r"^## (v\d+\.\d+\.\d+)", changelog, re.MULTILINE)
    duplicates = sorted({version for version in headings if headings.count(version) > 1})
    assert duplicates == []

    roadmap = _read("ROADMAP.md")
    assert roadmap.count("## Completed versions") == 1

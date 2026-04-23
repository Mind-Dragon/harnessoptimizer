from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest
import yaml

from hermesoptimizer.auto_update import (
    PreflightResult,
    UpdateConfig,
    UpdatePrompt,
    apply_update,
    load_update_config,
    resolve_prompt,
    run_preflight,
)


def test_non_interactive_resolves_default() -> None:
    prompt = UpdatePrompt(
        question="restart_services",
        options=["yes", "no"],
        default_answer=None,
    )

    answer, source = resolve_prompt(prompt, UpdateConfig(non_interactive=True))

    assert answer is True
    assert source == "default"


def test_non_interactive_with_config_override_uses_config_value() -> None:
    prompt = UpdatePrompt(
        question="save_local",
        options=["yes", "no"],
        default_answer=False,
    )

    answer, source = resolve_prompt(
        prompt,
        UpdateConfig(non_interactive=True, save_local=False, auto_configure=True),
    )

    assert answer is False
    assert source == "config"


def test_unknown_prompt_fails_closed() -> None:
    prompt = UpdatePrompt(
        question="enable_experimental_feature",
        options=["yes", "no"],
        default_answer=None,
    )

    with pytest.raises(ValueError, match="requires a default answer"):
        resolve_prompt(prompt, UpdateConfig(non_interactive=True))


def test_preflight_detects_key_removal_as_destructive() -> None:
    current = {
        "model": {"default": "gpt-5.4", "provider": "openai"},
        "agent": {"verbose": False, "max_turns": 100},
    }
    incoming = {
        "model": {"default": "gpt-5.4", "provider": "openai"},
        "agent": {"verbose": False},
    }

    result = run_preflight(current, incoming)

    assert result.destructive is True
    assert any(diff["path"] == "agent.max_turns" and diff["change"] == "removed" for diff in result.config_diff)


def test_preflight_detects_section_removal_as_destructive() -> None:
    current = {
        "model": {"default": "gpt-5.4", "provider": "openai"},
        "providers": {"openai": {"api_key": "***"}},
    }
    incoming = {
        "model": {"default": "gpt-5.4", "provider": "openai"},
    }

    result = run_preflight(current, incoming)

    assert result.destructive is True
    assert any(diff["path"] == "providers" and diff["change"] == "section_removed" for diff in result.config_diff)


def test_preflight_detects_additive_as_non_destructive() -> None:
    current = {
        "model": {"default": "gpt-5.4", "provider": "openai"},
    }
    incoming = {
        "model": {"default": "gpt-5.4", "provider": "openai"},
        "update": {"non_interactive": True},
    }

    result = run_preflight(current, incoming)

    assert result.destructive is False
    assert any(diff["path"] == "update" and diff["change"] == "added" for diff in result.config_diff)


def test_preflight_detects_model_downgrade_as_destructive() -> None:
    current = {
        "model": {"default": "gpt-5.4", "provider": "openai"},
    }
    incoming = {
        "model": {"default": "gpt-4", "provider": "openai"},
    }

    result = run_preflight(current, incoming)

    assert result.destructive is True
    assert any(diff["change"] == "model_downgrade" for diff in result.config_diff)


def test_preflight_json_output_format() -> None:
    result = PreflightResult(
        destructive=True,
        config_diff=[{"path": "agent.max_turns", "change": "removed", "destructive": True}],
        plugin_diff=[{"path": "plugins", "current": ["a"], "incoming": ["a", "b"]}],
        test_gate_passed=True,
        details=["removes key: agent.max_turns"],
    )

    payload = json.loads(result.to_json())

    assert payload == asdict(result)
    assert set(payload) == {"destructive", "config_diff", "plugin_diff", "test_gate_passed", "details"}


def test_update_config_defaults_when_section_missing(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"model": {"default": "gpt-5.4"}}), encoding="utf-8")

    result = load_update_config(config_path)

    assert result == UpdateConfig()


def test_load_update_config_reads_non_interactive_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "update": {
                    "non_interactive": True,
                    "save_local": True,
                    "auto_configure": True,
                }
            }
        ),
        encoding="utf-8",
    )

    result = load_update_config(config_path)

    assert result == UpdateConfig(non_interactive=True, save_local=True, auto_configure=True)


def test_apply_update_merges_non_destructive_changes(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "model": {"default": "gpt-5.4", "provider": "openai"},
                "agent": {"verbose": False},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    incoming = {
        "model": {"default": "gpt-5.4", "provider": "openai"},
        "agent": {"verbose": True, "reasoning_effort": "high"},
        "update": {"non_interactive": True},
    }

    result = apply_update(
        config_path,
        incoming,
        UpdateConfig(non_interactive=True, save_local=True, auto_configure=True),
    )

    written = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert result.applied is True
    assert result.destructive is False
    assert written["agent"]["verbose"] is False
    assert written["agent"]["reasoning_effort"] == "high"
    assert written["update"]["non_interactive"] is True


def test_apply_update_blocks_destructive_changes(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "model": {"default": "gpt-5.4", "provider": "openai"},
                "agent": {"verbose": False, "max_turns": 100},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = apply_update(
        config_path,
        {"model": {"default": "gpt-5.4", "provider": "openai"}, "agent": {"verbose": False}},
        UpdateConfig(non_interactive=True),
    )

    written = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert result.applied is False
    assert result.destructive is True
    assert written["agent"]["max_turns"] == 100

"""Auto-update helpers for non-interactive config resolution and preflight checks."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from hermesoptimizer.config_maintainer import merge_config


DEFAULT_PROMPT_ANSWERS: dict[str, bool] = {
    "save_local": True,
    "auto_configure": True,
    "overwrite_conflicting": False,
    "run_migrations": True,
    "restart_services": True,
}


@dataclass(frozen=True)
class UpdateConfig:
    non_interactive: bool = False
    save_local: bool = True
    auto_configure: bool = True


@dataclass(frozen=True)
class UpdatePrompt:
    question: str
    options: list[str]
    default_answer: Any | None = None


@dataclass
class PreflightResult:
    destructive: bool
    config_diff: list[dict[str, Any]] = field(default_factory=list)
    plugin_diff: list[dict[str, Any]] = field(default_factory=list)
    test_gate_passed: bool = True
    details: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass
class ApplyUpdateResult:
    applied: bool
    destructive: bool
    merged_config: dict[str, Any] | None = None
    preflight: PreflightResult | None = None
    details: list[str] = field(default_factory=list)


def load_update_config(config_path: str | Path) -> UpdateConfig:
    path = Path(config_path)
    if not path.exists():
        return UpdateConfig()

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return UpdateConfig()

    update = raw.get("update") or {}
    if not isinstance(update, dict):
        return UpdateConfig()

    return UpdateConfig(
        non_interactive=bool(update.get("non_interactive", False)),
        save_local=bool(update.get("save_local", True)),
        auto_configure=bool(update.get("auto_configure", True)),
    )


def resolve_prompt(prompt: UpdatePrompt, config: UpdateConfig) -> tuple[Any, str]:
    prompt_key = _normalize_question_key(prompt.question)

    if config.non_interactive:
        config_answer = _lookup_config_answer(prompt_key, config)
        if config_answer is not None:
            return config_answer, "config"
        if prompt.default_answer is not None:
            return prompt.default_answer, "default"
        if prompt_key in DEFAULT_PROMPT_ANSWERS:
            return DEFAULT_PROMPT_ANSWERS[prompt_key], "default"
        raise ValueError(f"non-interactive prompt requires a default answer: {prompt.question}")

    if prompt.default_answer is not None:
        return prompt.default_answer, "default"

    raw_answer = input(_build_prompt_text(prompt)).strip()
    if not raw_answer:
        raise ValueError(f"interactive prompt requires an answer: {prompt.question}")

    answer = _coerce_answer(raw_answer, prompt.options)
    return answer, "interactive"


def run_preflight(
    current_config: dict[str, Any] | None,
    incoming_config: dict[str, Any] | None,
) -> PreflightResult:
    current = current_config or {}
    incoming = incoming_config or {}

    destructive = False
    config_diff: list[dict[str, Any]] = []
    plugin_diff: list[dict[str, Any]] = []
    details: list[str] = []

    def visit(current_node: Any, incoming_node: Any, path: str = "") -> None:
        nonlocal destructive

        if isinstance(current_node, dict) and isinstance(incoming_node, dict):
            current_keys = set(current_node)
            incoming_keys = set(incoming_node)

            for key in sorted(current_keys - incoming_keys):
                entry_path = _join_path(path, key)
                removed_value = current_node[key]
                change = "section_removed" if isinstance(removed_value, dict) else "removed"
                destructive = True
                config_diff.append(
                    {
                        "path": entry_path,
                        "change": change,
                        "destructive": True,
                        "current": removed_value,
                        "incoming": None,
                    }
                )
                details.append(
                    f"removes {'section' if isinstance(removed_value, dict) else 'key'}: {entry_path}"
                )

            for key in sorted(incoming_keys - current_keys):
                entry_path = _join_path(path, key)
                config_diff.append(
                    {
                        "path": entry_path,
                        "change": "added",
                        "destructive": False,
                        "current": None,
                        "incoming": incoming_node[key],
                    }
                )
                details.append(f"adds key: {entry_path}")

            for key in sorted(current_keys & incoming_keys):
                entry_path = _join_path(path, key)
                current_value = current_node[key]
                incoming_value = incoming_node[key]

                if isinstance(current_value, dict) and isinstance(incoming_value, dict):
                    visit(current_value, incoming_value, entry_path)
                    continue

                if isinstance(current_value, dict) and not isinstance(incoming_value, dict):
                    destructive = True
                    config_diff.append(
                        {
                            "path": entry_path,
                            "change": "section_removed",
                            "destructive": True,
                            "current": current_value,
                            "incoming": incoming_value,
                        }
                    )
                    details.append(f"removes section: {entry_path}")
                    continue

                if current_value != incoming_value:
                    is_downgrade = _is_model_downgrade(entry_path, current_value, incoming_value)
                    destructive = destructive or is_downgrade
                    change = "model_downgrade" if is_downgrade else "changed"
                    config_diff.append(
                        {
                            "path": entry_path,
                            "change": change,
                            "destructive": is_downgrade,
                            "current": current_value,
                            "incoming": incoming_value,
                        }
                    )
                    if is_downgrade:
                        details.append(
                            f"downgrades model at {entry_path}: {current_value} -> {incoming_value}"
                        )
                    else:
                        details.append(
                            f"changes value: {entry_path}: {current_value!r} -> {incoming_value!r}"
                        )
            return

        if current_node != incoming_node:
            is_downgrade = _is_model_downgrade(path, current_node, incoming_node)
            destructive = destructive or is_downgrade
            config_diff.append(
                {
                    "path": path,
                    "change": "model_downgrade" if is_downgrade else "changed",
                    "destructive": is_downgrade,
                    "current": current_node,
                    "incoming": incoming_node,
                }
            )
            if is_downgrade:
                details.append(f"downgrades model at {path}: {current_node} -> {incoming_node}")
            else:
                details.append(f"changes value: {path}: {current_node!r} -> {incoming_node!r}")

    visit(current, incoming)

    current_plugins = current.get("plugins") if isinstance(current, dict) else None
    incoming_plugins = incoming.get("plugins") if isinstance(incoming, dict) else None
    if current_plugins != incoming_plugins:
        plugin_diff.append(
            {
                "path": "plugins",
                "current": current_plugins,
                "incoming": incoming_plugins,
            }
        )

    return PreflightResult(
        destructive=destructive,
        config_diff=config_diff,
        plugin_diff=plugin_diff,
        test_gate_passed=True,
        details=details,
    )


def apply_update(
    current_config_path: str | Path,
    incoming_config: dict[str, Any],
    config: UpdateConfig,
) -> ApplyUpdateResult:
    path = Path(current_config_path)
    current = _load_yaml_dict(path)
    preflight = run_preflight(current, incoming_config)

    if preflight.destructive:
        return ApplyUpdateResult(
            applied=False,
            destructive=True,
            preflight=preflight,
            details=["destructive update blocked by preflight"],
        )

    merged = merge_config(current, incoming_config)
    path.write_text(
        yaml.safe_dump(merged, default_flow_style=False, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return ApplyUpdateResult(
        applied=True,
        destructive=False,
        merged_config=merged,
        preflight=preflight,
        details=[
            "update applied",
            f"non_interactive={config.non_interactive}",
            f"save_local={config.save_local}",
            f"auto_configure={config.auto_configure}",
        ],
    )


def _lookup_config_answer(prompt_key: str, config: UpdateConfig) -> Any | None:
    if prompt_key == "save_local":
        return config.save_local
    if prompt_key == "auto_configure":
        return config.auto_configure
    return None


def _load_yaml_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"config is not a YAML mapping: {path}")
    return raw


def _join_path(base: str, key: str) -> str:
    return f"{base}.{key}" if base else key


def _normalize_question_key(question: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", question.strip().lower()).strip("_")
    if normalized.endswith("_question"):
        normalized = normalized[:-9]
    return normalized


def _build_prompt_text(prompt: UpdatePrompt) -> str:
    options = "/".join(prompt.options) if prompt.options else "answer"
    return f"{prompt.question} [{options}]: "


def _coerce_answer(raw_answer: str, options: list[str]) -> Any:
    lowered = raw_answer.lower()
    if lowered in {"y", "yes", "true"}:
        return True
    if lowered in {"n", "no", "false"}:
        return False
    for option in options:
        if lowered == option.lower():
            return option
    return raw_answer


def _split_model_name(value: str) -> tuple[str, tuple[int, ...]] | None:
    match = re.match(r"^(.*?)(\d+(?:\.\d+)*)$", value)
    if not match:
        return None
    prefix = match.group(1).rstrip("-_")
    version = tuple(int(part) for part in match.group(2).split("."))
    return prefix, version


def _is_model_downgrade(path: str, current_value: Any, incoming_value: Any) -> bool:
    if not isinstance(current_value, str) or not isinstance(incoming_value, str):
        return False
    if "model" not in path.lower():
        return False

    current_model = _split_model_name(current_value)
    incoming_model = _split_model_name(incoming_value)
    if current_model is None or incoming_model is None:
        return False

    current_prefix, current_version = current_model
    incoming_prefix, incoming_version = incoming_model
    if current_prefix != incoming_prefix:
        return False
    return incoming_version < current_version

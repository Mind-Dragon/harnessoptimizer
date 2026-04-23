from __future__ import annotations

import json
from pathlib import Path

import yaml

from hermesoptimizer.yolo_mode import (
    YoloAuditEntry,
    YoloConfig,
    check_command,
    load_yolo_config,
    log_audit,
    rotate_audit_log,
    yolo_status,
)


def _write_config(tmp_path: Path, mode: str, *, enabled: bool = True) -> Path:
    config_path = tmp_path / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump(
            {
                "yolo": {
                    "enabled": enabled,
                    "mode": mode,
                    "blocklist": [
                        "rm -rf /",
                        "dd if=",
                        "mkfs.",
                        "> /dev/sd",
                        "chmod -R 777 /",
                        "DROP DATABASE",
                        "TRUNCATE",
                    ],
                    "block_patterns": [
                        {
                            "regex": "git push.*--force.*main",
                            "reason": "force push to main",
                        },
                        {
                            "regex": "hermes config set.*api_key",
                            "reason": "credential mutation via CLI",
                        },
                    ],
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return config_path


def test_rm_rf_root_blocked_in_all_modes(tmp_path: Path) -> None:
    for mode in ("off", "safe", "maximum"):
        config = load_yolo_config(_write_config(tmp_path / mode, mode, enabled=mode != "off"))
        result = check_command("rm -rf /", config)
        assert result.approved is False
        assert result.mode == mode
        if mode == "off":
            assert "yolo mode is off" in result.reason
        else:
            assert "blocklist" in result.reason


def test_ls_auto_approved_in_safe_and_maximum(tmp_path: Path) -> None:
    safe = load_yolo_config(_write_config(tmp_path / "safe", "safe"))
    maximum = load_yolo_config(_write_config(tmp_path / "maximum", "maximum"))

    assert check_command("ls -la", safe).approved is True
    assert check_command("ls -la", maximum).approved is True


def test_git_push_force_main_blocked_in_safe_and_maximum(tmp_path: Path) -> None:
    safe = load_yolo_config(_write_config(tmp_path / "safe", "safe"))
    maximum = load_yolo_config(_write_config(tmp_path / "maximum", "maximum"))

    assert check_command("git push --force main", safe).approved is False
    assert check_command("git push --force main", maximum).approved is False


def test_credential_mutation_blocked_in_safe_and_maximum(tmp_path: Path) -> None:
    safe = load_yolo_config(_write_config(tmp_path / "safe", "safe"))
    maximum = load_yolo_config(_write_config(tmp_path / "maximum", "maximum"))

    command = "hermes config set api_key sk-live"
    assert check_command(command, safe).approved is False
    assert check_command(command, maximum).approved is False


def test_off_mode_nothing_approved(tmp_path: Path) -> None:
    config = load_yolo_config(_write_config(tmp_path / "off", "off", enabled=False))

    assert check_command("ls -la", config).approved is False
    assert check_command("echo hello", config).approved is False


def test_audit_log_written(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    entry = YoloAuditEntry(
        timestamp="2026-04-23T15:36:00Z",
        command="ls -la",
        approved=True,
        reason="auto-approved by yolo mode",
        mode="safe",
    )

    log_audit(entry, audit_path)

    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["command"] == "ls -la"
    assert payload["approved"] is True


def test_rotation_at_10mb(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    audit_path.write_bytes(b"x" * (10 * 1024 * 1024))

    rotated = rotate_audit_log(audit_path)

    assert rotated is not None
    assert rotated.exists()
    assert audit_path.exists()
    assert audit_path.stat().st_size == 0


def test_blocklist_substring_matching() -> None:
    config = YoloConfig(enabled=True, mode="maximum", blocklist=["TRUNCATE"], block_patterns=[])
    result = check_command("psql -c 'truncate table users'", config)
    assert result.approved is False
    assert "TRUNCATE" in result.reason


def test_block_pattern_regex_matching() -> None:
    config = YoloConfig(
        enabled=True,
        mode="maximum",
        blocklist=[],
        block_patterns=[{"regex": r"git push.*--force.*main", "reason": "force push to main"}],
    )
    result = check_command("git push origin --force main", config)
    assert result.approved is False
    assert result.reason == "force push to main"


def test_safe_mode_blocks_generic_credential_assignment() -> None:
    config = YoloConfig(enabled=True, mode="safe", blocklist=[], block_patterns=[])
    result = check_command("export token=abc123", config)
    assert result.approved is False
    assert "credential mutation" in result.reason


def test_load_yolo_config_and_status(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path / "safe", "safe")

    config = load_yolo_config(config_path)
    status = yolo_status(config_path)

    assert config.enabled is True
    assert config.mode == "safe"
    assert status["enabled"] is True
    assert status["mode"] == "safe"
    assert status["blocklist_count"] == 7
    assert status["block_patterns_count"] == 2
    assert status["auto_approve"] is True

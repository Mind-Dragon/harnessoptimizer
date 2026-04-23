from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_BLOCKLIST = [
    "rm -rf /",
    "dd if=",
    "mkfs.",
    "> /dev/sd",
    "chmod -R 777 /",
    "DROP DATABASE",
    "TRUNCATE",
]

DEFAULT_BLOCK_PATTERNS = [
    {"regex": r"git push.*--force.*main", "reason": "force push to main"},
    {"regex": r"hermes config set.*api_key", "reason": "credential mutation via CLI"},
]

_VALID_MODES = {"off", "safe", "maximum"}
_CREDENTIAL_KEYWORDS = ("api_key", "secret", "token", "password")
_CREDENTIAL_MUTATION_RE = re.compile(
    r"(?ix)"
    r"(?:"
    r"\b(?:export|set)\b\s+[A-Za-z_][A-Za-z0-9_]*\s*=\s*[^\s]+"
    r"|\b(?:api_key|secret|token|password)\b\s*=\s*[^\s]+"
    r"|\bset\b.*\b(?:api_key|secret|token|password)\b"
    r")"
)


@dataclass(slots=True)
class YoloConfig:
    enabled: bool = False
    mode: str = "off"
    blocklist: list[str] = field(default_factory=lambda: list(DEFAULT_BLOCKLIST))
    block_patterns: list[dict[str, str]] = field(
        default_factory=lambda: [dict(item) for item in DEFAULT_BLOCK_PATTERNS]
    )


@dataclass(slots=True)
class YoloResult:
    approved: bool
    reason: str
    mode: str


@dataclass(slots=True)
class YoloAuditEntry:
    timestamp: str
    command: str
    approved: bool
    reason: str
    mode: str


def _normalize_mode(enabled: bool, mode: Any) -> str:
    normalized = str(mode or "off").strip().lower()
    if not enabled:
        return "off"
    if normalized in _VALID_MODES:
        return normalized
    return "off"



def load_yolo_config(config_path: str | Path) -> YoloConfig:
    path = Path(config_path)
    if not path.exists():
        return YoloConfig()

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return YoloConfig()

    yolo = raw.get("yolo") or {}
    if not isinstance(yolo, dict):
        return YoloConfig()

    enabled = bool(yolo.get("enabled", False))
    mode = _normalize_mode(enabled, yolo.get("mode", "off"))

    blocklist_raw = yolo.get("blocklist", DEFAULT_BLOCKLIST)
    if isinstance(blocklist_raw, list):
        blocklist = [str(item) for item in blocklist_raw if str(item).strip()]
    else:
        blocklist = list(DEFAULT_BLOCKLIST)

    block_patterns_raw = yolo.get("block_patterns", DEFAULT_BLOCK_PATTERNS)
    block_patterns: list[dict[str, str]] = []
    if isinstance(block_patterns_raw, list):
        for item in block_patterns_raw:
            if not isinstance(item, dict):
                continue
            regex = str(item.get("regex", "")).strip()
            if not regex:
                continue
            block_patterns.append(
                {
                    "regex": regex,
                    "reason": str(item.get("reason", "blocked by YOLO pattern")),
                }
            )

    return YoloConfig(
        enabled=enabled,
        mode=mode,
        blocklist=blocklist or list(DEFAULT_BLOCKLIST),
        block_patterns=block_patterns or [dict(item) for item in DEFAULT_BLOCK_PATTERNS],
    )



def _blocklist_reason(command: str, config: YoloConfig) -> str | None:
    lowered = command.lower()
    for blocked in config.blocklist:
        if blocked.lower() in lowered:
            return f"blocked by blocklist: {blocked}"
    return None



def _pattern_reason(command: str, config: YoloConfig) -> str | None:
    for item in config.block_patterns:
        regex = item.get("regex", "")
        if regex and re.search(regex, command, flags=re.IGNORECASE):
            return item.get("reason", f"blocked by pattern: {regex}")
    return None



def _credential_mutation_reason(command: str, mode: str) -> str | None:
    if mode != "safe":
        return None

    lowered = command.lower()
    if not any(keyword in lowered for keyword in _CREDENTIAL_KEYWORDS):
        return None

    if _CREDENTIAL_MUTATION_RE.search(command):
        return "blocked in safe mode: credential mutation requires manual approval"

    return None



def check_command(command: str, config: YoloConfig) -> YoloResult:
    normalized_command = command.strip()
    mode = _normalize_mode(config.enabled, config.mode)

    if mode == "off":
        return YoloResult(
            approved=False,
            reason="manual approval required: yolo mode is off",
            mode="off",
        )

    reason = _blocklist_reason(normalized_command, config)
    if reason:
        return YoloResult(approved=False, reason=reason, mode=mode)

    reason = _pattern_reason(normalized_command, config)
    if reason:
        return YoloResult(approved=False, reason=reason, mode=mode)

    reason = _credential_mutation_reason(normalized_command, mode)
    if reason:
        return YoloResult(approved=False, reason=reason, mode=mode)

    return YoloResult(approved=True, reason="auto-approved by yolo mode", mode=mode)



def rotate_audit_log(audit_path: str | Path, max_bytes: int = 10 * 1024 * 1024) -> Path | None:
    path = Path(audit_path)
    if not path.exists() or path.stat().st_size < max_bytes:
        return None

    index = 1
    while True:
        rotated_path = path.with_name(f"{path.name}.{index}")
        if not rotated_path.exists():
            break
        index += 1

    os.replace(path, rotated_path)
    path.touch()
    return rotated_path



def log_audit(entry: YoloAuditEntry, audit_path: str | Path) -> None:
    path = Path(audit_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rotate_audit_log(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(entry), sort_keys=True) + "\n")



def yolo_status(config_path: str | Path) -> dict[str, Any]:
    config = load_yolo_config(config_path)
    mode = _normalize_mode(config.enabled, config.mode)
    return {
        "enabled": config.enabled,
        "mode": mode,
        "blocklist_count": len(config.blocklist),
        "block_patterns_count": len(config.block_patterns),
        "auto_approve": mode != "off",
    }


__all__ = [
    "DEFAULT_BLOCKLIST",
    "DEFAULT_BLOCK_PATTERNS",
    "YoloAuditEntry",
    "YoloConfig",
    "YoloResult",
    "check_command",
    "load_yolo_config",
    "log_audit",
    "rotate_audit_log",
    "yolo_status",
]

"""Emit findings when AI configs violate network policy."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from hermesoptimizer.catalog import Finding
from hermesoptimizer.network.validator import validate_config_ports, validate_config_ips


def enforce_network_policy(
    config_path: Path,
    db_path: str | Path,
) -> list[Finding]:
    """Read a config file and emit findings for port/IP violations.

    Args:
        config_path: Path to the config file (YAML or JSON).
        db_path: Path to the SQLite catalog.

    Returns:
        List of Finding objects for violations.
    """
    findings: list[Finding] = []

    try:
        raw = config_path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw) or {}
    except Exception:
        return findings

    if not isinstance(data, dict):
        return findings

    findings.extend(validate_config_ports(data, db_path))
    findings.extend(validate_config_ips(data))

    # Add file_path to findings that only have a dict path
    for f in findings:
        if f.file_path and not str(f.file_path).startswith(str(config_path)):
            f.file_path = f"{config_path}:{f.file_path}"
        elif not f.file_path:
            f.file_path = str(config_path)

    return findings

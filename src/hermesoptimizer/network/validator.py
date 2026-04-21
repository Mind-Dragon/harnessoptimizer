"""Validate configs for forbidden ports and localhost usage."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from hermesoptimizer.catalog import Finding
from hermesoptimizer.network.inventory import is_port_allowed, is_localhost, ensure_forbidden_ports


_PORT_RE = re.compile(r'(?i)(port|listen|bind)\s*[:=]\s*(\d+)')
_URL_PORT_RE = re.compile(r':(\d{2,5})(?:/|$)')
_IP_RE = re.compile(r'(?i)(host|bind|listen|url|base_url)\s*[:=]\s*["\']?([^"\'\s]+)')


def validate_config_ports(config_data: dict[str, Any], db_path: str | Path) -> list[Finding]:
    """Scan config dict for forbidden or unreserved port numbers."""
    findings: list[Finding] = []
    ensure_forbidden_ports(db_path)

    def _scan(obj: Any, path: str = "") -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                current = f"{path}.{key}" if path else key
                # Check numeric port fields
                if isinstance(value, int) and _is_port_like_key(key):
                    _check_port(value, current, findings, db_path)
                # Check string fields that might contain ports
                elif isinstance(value, str):
                    for match in _PORT_RE.finditer(value):
                        port = int(match.group(2))
                        _check_port(port, current, findings, db_path)
                    for match in _URL_PORT_RE.finditer(value):
                        port = int(match.group(1))
                        _check_port(port, current, findings, db_path)
                _scan(value, current)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                _scan(item, f"{path}[{i}]")

    _scan(config_data)
    return findings


def _is_port_like_key(key: str) -> bool:
    """Return True if the key name suggests a port number."""
    kl = key.lower()
    return kl in ("port", "listen", "bind", "proxy_port", "server_port", "gateway_port")


def _check_port(port: int, path: str, findings: list[Finding], db_path: str | Path) -> None:
    if port in (3000, 8080):
        findings.append(
            Finding(
                file_path=path,
                line_num=None,
                category="network_policy",
                severity="CRITICAL",
                kind="forbidden_port",
                sample_text=f"Port {port} is permanently forbidden",
                router_note=f"Use `hermesoptimizer port-reserve` to select an available port (3000 and 8080 are off-limits)",
            )
        )
    elif not is_port_allowed(db_path, port):
        findings.append(
            Finding(
                file_path=path,
                line_num=None,
                category="network_policy",
                severity="WARNING",
                kind="reserved_port",
                sample_text=f"Port {port} is already reserved",
                router_note="Select a different port or run `hermesoptimizer port-list` to see available ports",
            )
        )
    elif not (3000 <= port <= 65530):
        findings.append(
            Finding(
                file_path=path,
                line_num=None,
                category="network_policy",
                severity="WARNING",
                kind="out_of_range_port",
                sample_text=f"Port {port} is outside the recommended range (3000-65530)",
                router_note="Use a port in the 3000-65530 range",
            )
        )


def validate_config_ips(config_data: dict[str, Any]) -> list[Finding]:
    """Scan config dict for localhost / 127.0.0.1 usage."""
    findings: list[Finding] = []

    def _scan(obj: Any, path: str = "") -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                current = f"{path}.{key}" if path else key
                if isinstance(value, str):
                    # Check for localhost / 127.x in URLs or host fields
                    if _is_host_like_key(key) and is_localhost(value):
                        findings.append(
                            Finding(
                                file_path=current,
                                line_num=None,
                                category="network_policy",
                                severity="CRITICAL",
                                kind="localhost_forbidden",
                                sample_text=f"{key} = {value}",
                                router_note="localhost and 127.0.0.1 are forbidden. Use `hermesoptimizer ip-list` to select an actual network IP",
                            )
                        )
                    # Also check URLs embedded in strings
                    elif "127.0.0.1" in value or "localhost" in value.lower():
                        findings.append(
                            Finding(
                                file_path=current,
                                line_num=None,
                                category="network_policy",
                                severity="CRITICAL",
                                kind="localhost_in_url",
                                sample_text=value,
                                router_note="Replace localhost/127.0.0.1 with an actual network IP from `hermesoptimizer ip-list`",
                            )
                        )
                _scan(value, current)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                _scan(item, f"{path}[{i}]")

    _scan(config_data)
    return findings


def _is_host_like_key(key: str) -> bool:
    kl = key.lower()
    return kl in ("host", "bind", "listen", "server_host", "proxy_host", "gateway_host", "url", "base_url")

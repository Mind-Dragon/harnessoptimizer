"""
Phase 1 Hermes config scanner.

Parses Hermes config.yaml and surfaces findings for:
- Missing required fields in provider definitions
- Stale or unknown provider/model names
- Bad or malformed endpoints (non-https, invalid URL format)
"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import yaml

from hermesoptimizer.catalog import Finding

# Known-good provider name prefixes
_KNOWN_PROVIDERS = {"openai", "anthropic", "cohere", "google", "mistral", "azure", "aws", "huggingface"}
# Known-good model name patterns (partial, not strict)
_KNOWN_MODEL_PATTERNS = [
    re.compile(r"gpt-4", re.IGNORECASE),
    re.compile(r"gpt-3.5", re.IGNORECASE),
    re.compile(r"claude-3", re.IGNORECASE),
    re.compile(r"claude-2", re.IGNORECASE),
    re.compile(r"gemini", re.IGNORECASE),
    re.compile(r"mistral", re.IGNORECASE),
    re.compile(r"command-", re.IGNORECASE),
]

# Required top-level keys
_REQUIRED_PROVIDER_FIELDS = ["base_url", "auth_type", "auth_key_env", "model", "lane"]


def _check_url(url: str) -> bool:
    """Return True if URL is well-formed and uses https."""
    try:
        parsed = urlparse(url)
        return bool(parsed.scheme) and bool(parsed.netloc)
    except Exception:
        return False


def _is_https(url: str) -> bool:
    """Return True if URL uses https."""
    try:
        parsed = urlparse(url)
        return parsed.scheme == "https"
    except Exception:
        return False


def _is_known_model(model: str) -> bool:
    """Return True if model name looks familiar."""
    if not model:
        return False
    for pat in _KNOWN_MODEL_PATTERNS:
        if pat.search(model):
            return True
    return False


def _is_known_provider(provider: str) -> bool:
    """Return True if provider name is known."""
    if not provider:
        return False
    return provider.lower() in _KNOWN_PROVIDERS


def scan_config(path: str | Path) -> list[Finding]:
    """
    Phase 1 scan of a Hermes config.yaml file.

    Returns a list of Finding records for each issue detected.
    """
    findings: list[Finding] = []
    p = Path(path) if isinstance(path, str) else path
    if not p.exists():
        return findings

    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception:
        findings.append(
            Finding(
                file_path=str(p),
                line_num=None,
                category="config-signal",
                severity="high",
                kind="config-bad-endpoint",
                fingerprint=f"{p}:parse-error",
                sample_text="failed to parse YAML",
                count=1,
                confidence="high",
                router_note="yaml-parse-error",
                lane=None,
            )
        )
        return findings

    if not isinstance(data, dict):
        return findings

    providers = data.get("providers", {})
    if not isinstance(providers, dict):
        return findings

    for provider_name, provider_data in providers.items():
        if not isinstance(provider_data, dict):
            findings.append(
                Finding(
                    file_path=str(p),
                    line_num=None,
                    category="config-signal",
                    severity="medium",
                    kind="config-missing-field",
                    fingerprint=f"{p}:{provider_name}:not-dict",
                    sample_text=f"provider '{provider_name}' is not a dict",
                    count=1,
                    confidence="high",
                    router_note=f"provider '{provider_name}' schema invalid",
                    lane=provider_data.get("lane") if isinstance(provider_data, dict) else None,
                )
            )
            continue

        # Check required fields
        for field in _REQUIRED_PROVIDER_FIELDS:
            if field not in provider_data or provider_data[field] is None or provider_data[field] == "":
                findings.append(
                    Finding(
                        file_path=str(p),
                        line_num=None,
                        category="config-signal",
                        severity="high",
                        kind="config-missing-field",
                        fingerprint=f"{p}:{provider_name}:{field}",
                        sample_text=f"provider '{provider_name}' missing required field '{field}'",
                        count=1,
                        confidence="high",
                        router_note=f"missing '{field}' in provider '{provider_name}'",
                        lane=provider_data.get("lane"),
                    )
                )

        # Check base_url
        base_url = provider_data.get("base_url", "")
        if base_url:
            if not _check_url(base_url):
                findings.append(
                    Finding(
                        file_path=str(p),
                        line_num=None,
                        category="config-signal",
                        severity="high",
                        kind="config-bad-endpoint",
                        fingerprint=f"{p}:{provider_name}:base_url",
                        sample_text=f"base_url '{base_url}' is malformed",
                        count=1,
                        confidence="high",
                        router_note=f"invalid URL for provider '{provider_name}'",
                        lane=provider_data.get("lane"),
                    )
                )
            elif not _is_https(base_url):
                findings.append(
                    Finding(
                        file_path=str(p),
                        line_num=None,
                        category="config-signal",
                        severity="high",
                        kind="config-bad-endpoint",
                        fingerprint=f"{p}:{provider_name}:not-https",
                        sample_text=f"base_url '{base_url}' does not use https",
                        count=1,
                        confidence="high",
                        router_note=f"insecure endpoint (no TLS) for provider '{provider_name}'",
                        lane=provider_data.get("lane"),
                    )
                )

        # Check provider name
        if not _is_known_provider(provider_name):
            findings.append(
                Finding(
                    file_path=str(p),
                    line_num=None,
                    category="config-signal",
                    severity="medium",
                    kind="config-stale-provider",
                    fingerprint=f"{p}:{provider_name}",
                    sample_text=f"provider name '{provider_name}' is not in known list",
                    count=1,
                    confidence="medium",
                    router_note=f"unknown provider '{provider_name}'",
                    lane=provider_data.get("lane"),
                )
            )

        # Check model name
        model = provider_data.get("model", "")
        if model and not _is_known_model(model):
            findings.append(
                Finding(
                    file_path=str(p),
                    line_num=None,
                    category="config-signal",
                    severity="medium",
                    kind="config-stale-provider",
                    fingerprint=f"{p}:{provider_name}:model",
                    sample_text=f"model '{model}' does not match known patterns",
                    count=1,
                    confidence="low",
                    router_note=f"unusual model name '{model}' for provider '{provider_name}'",
                    lane=provider_data.get("lane"),
                )
            )

    return findings


def scan_config_paths(paths: list[str | Path]) -> list[Finding]:
    """
    Scan a list of config file paths and return findings.
    Phase 1 implementation delegates to scan_config.
    """
    findings: list[Finding] = []
    for path in paths:
        findings.extend(scan_config(path))
    return findings

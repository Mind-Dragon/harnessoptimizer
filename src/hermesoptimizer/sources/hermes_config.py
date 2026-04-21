"""
Phase 1 Hermes config scanner.

Parses Hermes config.yaml and surfaces findings for:
- Missing required fields in provider definitions
- Stale or unknown provider/model names
- Bad or malformed endpoints (non-https, invalid URL format)
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlparse

import yaml

from hermesoptimizer.catalog import Finding
from hermesoptimizer.sources.provider_truth import canonical_provider_name

# Known-good provider families (canonicalized).
_KNOWN_PROVIDERS = {
    "openai",
    "openrouter",
    "anthropic",
    "cohere",
    "google",
    "mistral",
    "azure",
    "aws",
    "huggingface",
    "qwen",
    "kimi",
    "zai",
    "xai",
    "minimax",
    "fireworks-ai",
    "kilocode",
    "nacrof",
}

# Known-good model name patterns by provider family.
_KNOWN_MODEL_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "openai": [
        re.compile(r"gpt-4", re.IGNORECASE),
        re.compile(r"gpt-3\.5", re.IGNORECASE),
        re.compile(r"gpt-5", re.IGNORECASE),
        re.compile(r"codex", re.IGNORECASE),
    ],
    "anthropic": [
        re.compile(r"claude-3", re.IGNORECASE),
        re.compile(r"claude-2", re.IGNORECASE),
    ],
    "google": [
        re.compile(r"gemini", re.IGNORECASE),
    ],
    "mistral": [
        re.compile(r"mistral", re.IGNORECASE),
    ],
    "cohere": [
        re.compile(r"command-", re.IGNORECASE),
    ],
    "qwen": [
        # International / Global / US / EU families from Alibaba Cloud Model Studio.
        re.compile(r"^qwen(?:\d+(?:\.\d+)?)?(?:-[a-z0-9.]+)*(?:-\d{4}-\d{2}-\d{2})?$", re.IGNORECASE),
        re.compile(r"^qwen3(?:\.\d+)?-(?:plus|flash|max|coder(?:-plus)?|vl-(?:plus|flash)|omni-(?:plus|flash)|mt-(?:plus|flash|lite|turbo)|rerank)(?:-\d{4}-\d{2}-\d{2})?$", re.IGNORECASE),
        re.compile(r"^qwen3-(?:coder|vl|omni|livetranslate|asr|tts|rerank|deep-research|mt|image|video|audio|speech|search|vision|embedding|math)(?:-[a-z0-9.-]+)?$", re.IGNORECASE),
        # Chinese mainland / region-scoped product families exposed under Qwen routing.
        re.compile(r"^qwq(?:-[a-z0-9.-]+)?$", re.IGNORECASE),
        re.compile(r"^qvq(?:-[a-z0-9.-]+)?$", re.IGNORECASE),
        re.compile(r"^wan(?:[0-9.]+)?(?:-[a-z0-9.-]+)?$", re.IGNORECASE),
        re.compile(r"^z-image(?:-[a-z0-9.-]+)?$", re.IGNORECASE),
        re.compile(r"^cosyvoice(?:-[a-z0-9.-]+)?$", re.IGNORECASE),
        re.compile(r"^fun-asr(?:-[a-z0-9.-]+)?$", re.IGNORECASE),
        re.compile(r"^paraformer(?:-[a-z0-9.-]+)?$", re.IGNORECASE),
        re.compile(r"^tongyi-(?:embedding|intent-detect|embedding-vision)(?:-[a-z0-9.-]+)?$", re.IGNORECASE),
        re.compile(r"^text-embedding-v[34](?:-[a-z0-9.-]+)?$", re.IGNORECASE),
        re.compile(r"^qwen-mt(?:-[a-z0-9.-]+)?$", re.IGNORECASE),
    ],
    "kimi": [
        re.compile(r"kimi(?:-k\d+(?:\.\d+)?)?(?:-\d{4}-\d{2}-\d{2})?$", re.IGNORECASE),
    ],
    "zai": [
        re.compile(r"glm", re.IGNORECASE),
    ],
    "xai": [
        re.compile(r"grok", re.IGNORECASE),
    ],
    "minimax": [
        re.compile(r"minimax", re.IGNORECASE),
    ],
}

# Provider-specific env overrides that can conflict with canonical routing.
_PROVIDER_ENV_VARS: dict[str, tuple[str, str]] = {
    "openai": ("OPENAI_BASE_URL", "OPENAI_API_KEY"),
    "openrouter": ("OPENROUTER_BASE_URL", "OPENROUTER_API_KEY"),
    "qwen": ("DASHSCOPE_BASE_URL", "DASHSCOPE_API_KEY"),
    "kimi": ("KIMI_BASE_URL", "KIMI_API_KEY"),
    "zai": ("ZAI_BASE_URL", "ZAI_API_KEY"),
    "xai": ("XAI_BASE_URL", "XAI_API_KEY"),
    "minimax": ("MINIMAX_BASE_URL", "MINIMAX_API_KEY"),
}


def _provider_env_vars(provider_name: str) -> tuple[str, str] | None:
    return _PROVIDER_ENV_VARS.get(canonical_provider_name(provider_name))


def _stale_model_field_findings(path: Path, model_block: dict[str, object]) -> list[Finding]:
    findings: list[Finding] = []
    for field in ("base_url", "api_key"):
        value = model_block.get(field)
        if value:
            router_note = "stale value was cleared"
            if field == "api_key":
                router_note = "stale value was cleared without exposing the secret"
            sample = f"model.{field} is set and should be removed from canonical config"
            if field == "api_key":
                sample = "model.api_key is set and should be removed from canonical config"
            findings.append(
                Finding(
                    file_path=str(path),
                    line_num=None,
                    category="config-signal",
                    severity="medium",
                    kind="config-stale-model-field",
                    fingerprint=f"{path}:model:{field}",
                    sample_text=sample,
                    count=1,
                    confidence="high",
                    router_note=router_note,
                    lane=None,
                )
            )
    return findings


def _stale_model_provider_findings(path: Path, model_block: dict[str, object]) -> tuple[list[Finding], str | None]:
    findings: list[Finding] = []
    provider_name = str(model_block.get("provider") or "").strip()
    if not provider_name:
        return findings, None
    canonical_name = canonical_provider_name(provider_name)
    if canonical_name != provider_name and canonical_name in _KNOWN_PROVIDERS:
        findings.append(
            Finding(
                file_path=str(path),
                line_num=None,
                category="config-signal",
                severity="medium",
                kind="config-stale-provider",
                fingerprint=f"{path}:model:provider",
                sample_text=f"model.provider '{provider_name}' should normalize to canonical provider '{canonical_name}'",
                count=1,
                confidence="high",
                router_note=f"canonical provider alias '{provider_name}' should resolve to '{canonical_name}'",
                lane=None,
            )
        )
    return findings, canonical_name


def _provider_entry_name(entry: object) -> str:
    if isinstance(entry, str):
        return entry.strip()
    if isinstance(entry, dict):
        for key in ("provider", "name", "id"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _provider_field(provider_data: dict[str, object], *keys: str) -> object:
    for key in keys:
        value = provider_data.get(key)
        if value not in (None, ""):
            return value
    return ""


def _fallback_provider_findings(path: Path, fallback_providers: object, seen_families: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(fallback_providers, list):
        return findings
    for index, entry in enumerate(fallback_providers):
        provider_name = _provider_entry_name(entry)
        if not provider_name:
            findings.append(
                Finding(
                    file_path=str(path),
                    line_num=None,
                    category="config-signal",
                    severity="medium",
                    kind="config-missing-field",
                    fingerprint=f"{path}:fallback_providers:{index}:blank",
                    sample_text=f"fallback_providers[{index}] is blank or missing provider name",
                    count=1,
                    confidence="high",
                    router_note="blank fallback provider entry should be removed",
                    lane=None,
                )
            )
            continue
        canonical_name = canonical_provider_name(provider_name)
        if canonical_name in seen_families:
            findings.append(
                Finding(
                    file_path=str(path),
                    line_num=None,
                    category="config-signal",
                    severity="high",
                    kind="config-duplicate-provider",
                    fingerprint=f"{path}:{canonical_name}:fallback:{index}",
                    sample_text=f"fallback provider '{provider_name}' conflicts with canonical family '{canonical_name}'",
                    count=1,
                    confidence="high",
                    router_note=f"duplicate provider family '{canonical_name}' in fallback providers",
                    lane=None,
                )
            )
        else:
            seen_families.add(canonical_name)
        if canonical_name != provider_name and canonical_name in _KNOWN_PROVIDERS:
            findings.append(
                Finding(
                    file_path=str(path),
                    line_num=None,
                    category="config-signal",
                    severity="medium",
                    kind="config-stale-provider",
                    fingerprint=f"{path}:{provider_name}:fallback-alias:{index}",
                    sample_text=f"fallback provider alias '{provider_name}' should normalize to '{canonical_name}'",
                    count=1,
                    confidence="high",
                    router_note=f"provider alias '{provider_name}' should resolve to '{canonical_name}' in fallback providers",
                    lane=None,
                )
            )
    return findings


def _env_override_conflicts(path: Path, provider_name: str, provider_data: dict[str, object]) -> list[Finding]:
    env_vars = _provider_env_vars(provider_name)
    if env_vars is None:
        return []
    base_url_var, api_key_var = env_vars
    findings: list[Finding] = []
    if os.environ.get(base_url_var):
        findings.append(
            Finding(
                file_path=str(path),
                line_num=None,
                category="config-signal",
                severity="medium",
                kind="config-env-override-conflict",
                fingerprint=f"{path}:{provider_name}:{base_url_var}",
                sample_text=f"{base_url_var} is set and can shadow canonical routing for provider '{provider_name}'",
                count=1,
                confidence="high",
                router_note="ignore or clear the env override so the canonical route wins",
                lane=provider_data.get("lane"),
            )
        )
    if os.environ.get(api_key_var):
        findings.append(
            Finding(
                file_path=str(path),
                line_num=None,
                category="config-signal",
                severity="medium",
                kind="config-env-override-conflict",
                fingerprint=f"{path}:{provider_name}:{api_key_var}",
                sample_text=f"{api_key_var} is set and can shadow canonical routing for provider '{provider_name}'",
                count=1,
                confidence="high",
                router_note="ignore or clear the env override so the canonical route wins",
                lane=provider_data.get("lane"),
            )
        )
    return findings



# Required provider fields — supports both old (base_url/model/auth_type) and
# new (api/default_model) config formats. The trigger check (line 417) fires
# if ANY of these names appears in the provider dict, then validates each.
_REQUIRED_PROVIDER_FIELDS = [
    "base_url", "api",
    "auth_type",
    "auth_key_env", "key_env",
    "model", "default_model",
    "lane",
]

# Pairs: if the canonical name is absent, check the alias
_REQUIRED_PROVIDER_ALIASES = {
    "base_url": "api",
    "model": "default_model",
    "auth_key_env": "key_env",
}


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


def _is_known_model(provider: str, model: str) -> bool:
    """Return True if model name looks familiar for the given provider family."""
    if not model:
        return False
    family = canonical_provider_name(provider)
    patterns = _KNOWN_MODEL_PATTERNS.get(family, [])
    if not patterns:
        return True
    return any(pat.search(model) for pat in patterns)


def _is_known_provider(provider: str) -> bool:
    """Return True if provider family is known after canonicalization."""
    if not provider:
        return False
    return canonical_provider_name(provider) in _KNOWN_PROVIDERS


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

    model_block = data.get("model")
    model_canonical_name: str | None = None
    if isinstance(model_block, dict):
        findings.extend(_stale_model_field_findings(p, model_block))
        model_findings, model_canonical_name = _stale_model_provider_findings(p, model_block)
        findings.extend(model_findings)

    providers = data.get("providers", {})
    if not isinstance(providers, dict):
        return findings

    seen_provider_families: set[str] = set()
    if model_canonical_name:
        seen_provider_families.add(model_canonical_name)

    for provider_name, provider_data in providers.items():
        canonical_name = canonical_provider_name(provider_name)
        if canonical_name in seen_provider_families:
            findings.append(
                Finding(
                    file_path=str(p),
                    line_num=None,
                    category="config-signal",
                    severity="high",
                    kind="config-duplicate-provider",
                    fingerprint=f"{p}:{canonical_name}:duplicate",
                    sample_text=f"provider '{provider_name}' conflicts with existing provider family '{canonical_name}'",
                    count=1,
                    confidence="high",
                    router_note=f"duplicate provider family '{canonical_name}'",
                    lane=provider_data.get("lane") if isinstance(provider_data, dict) else None,
                )
            )
            continue
        seen_provider_families.add(canonical_name)

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

        findings.extend(_env_override_conflicts(p, provider_name, provider_data))

        # Check required fields for the newer provider schema.
        # Uses _REQUIRED_PROVIDER_ALIASES to handle both old and new field names.
        if any(field in provider_data for field in _REQUIRED_PROVIDER_FIELDS):
            for field in ["base_url", "auth_type", "auth_key_env", "model", "lane"]:
                alias = _REQUIRED_PROVIDER_ALIASES.get(field)
                has_field = bool(
                    provider_data.get(field) not in (None, "")
                    or (alias and provider_data.get(alias) not in (None, ""))
                )
                if not has_field:
                    field_label = f"{field}/{alias}" if alias else field
                    findings.append(
                        Finding(
                            file_path=str(p),
                            line_num=None,
                            category="config-signal",
                            severity="high",
                            kind="config-missing-field",
                            fingerprint=f"{p}:{provider_name}:{field_label}",
                            sample_text=f"provider '{provider_name}' missing required field '{field_label}'",
                            count=1,
                            confidence="high",
                            router_note=f"missing '{field_label}' in provider '{provider_name}'",
                            lane=provider_data.get("lane") or provider_data.get("model"),
                        )
                    )

        # Check base_url
        base_url = _provider_field(provider_data, "base_url", "api")
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
        model = _provider_field(provider_data, "model", "default_model")
        if model and not _is_known_model(provider_name, model):
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

    fallback_providers = data.get("fallback_providers", [])
    findings.extend(_fallback_provider_findings(p, fallback_providers, seen_provider_families))

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

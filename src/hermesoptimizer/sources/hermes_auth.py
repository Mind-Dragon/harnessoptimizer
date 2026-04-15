"""
Phase 1 Hermes auth/credential pool scanner.

Parses Hermes auth.json files and surfaces findings for:
- blank or malformed credential pool entries
- re-seeded credentials from suppressed/manual/config sources
- duplicate canonical provider families in the credential pool
- alias providers that should normalize to a canonical provider family
"""
from __future__ import annotations

import json
from pathlib import Path

from hermesoptimizer.catalog import Finding
from hermesoptimizer.sources.provider_truth import canonical_provider_name


def _entry_provider_name(provider_name: str) -> tuple[str, str]:
    canonical = canonical_provider_name(provider_name)
    return provider_name.strip(), canonical


def _entry_source(entry: object) -> str:
    if not isinstance(entry, dict):
        return ""
    source = entry.get("source")
    return source.strip() if isinstance(source, str) else ""


def _credential_entry_name(entry: object) -> str:
    if isinstance(entry, dict):
        for key in ("label", "source", "auth_type"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _credential_findings(path: Path, provider_name: str, entries: object, seen_families: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(entries, list):
        return findings

    provider_label, canonical = _entry_provider_name(provider_name)
    if canonical in seen_families:
        findings.append(
            Finding(
                file_path=str(path),
                line_num=None,
                category="auth-signal",
                severity="high",
                kind="auth-duplicate-provider",
                fingerprint=f"{path}:{canonical}:credential-pool",
                sample_text=f"credential pool provider '{provider_label}' conflicts with canonical family '{canonical}'",
                count=1,
                confidence="high",
                router_note=f"duplicate credential pool family '{canonical}'",
                lane=None,
            )
        )
    else:
        seen_families.add(canonical)

    if canonical != provider_label and canonical:
        findings.append(
            Finding(
                file_path=str(path),
                line_num=None,
                category="auth-signal",
                severity="medium",
                kind="auth-stale-provider",
                fingerprint=f"{path}:{provider_label}:canonical-alias",
                sample_text=f"credential pool provider '{provider_label}' should normalize to '{canonical}'",
                count=1,
                confidence="high",
                router_note=f"credential pool provider alias '{provider_label}' should resolve to '{canonical}'",
                lane=None,
            )
        )

    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            findings.append(
                Finding(
                    file_path=str(path),
                    line_num=None,
                    category="auth-signal",
                    severity="medium",
                    kind="auth-invalid-entry",
                    fingerprint=f"{path}:{provider_label}:entry:{index}:not-dict",
                    sample_text=f"credential_pool[{provider_label}][{index}] is not a dict",
                    count=1,
                    confidence="high",
                    router_note="credential pool entry is malformed",
                    lane=None,
                )
            )
            continue

        source = _entry_source(entry)
        label = _credential_entry_name(entry) or f"entry[{index}]"
        if not source:
            findings.append(
                Finding(
                    file_path=str(path),
                    line_num=None,
                    category="auth-signal",
                    severity="medium",
                    kind="auth-blank-source",
                    fingerprint=f"{path}:{provider_label}:{index}:blank-source",
                    sample_text=f"credential_pool[{provider_label}][{index}] has no source",
                    count=1,
                    confidence="high",
                    router_note="blank credential source should not be reused",
                    lane=None,
                )
            )
            continue

        if source in {"gh_cli", "manual:device_code"} or source.startswith("config:") or source == "model_config":
            findings.append(
                Finding(
                    file_path=str(path),
                    line_num=None,
                    category="auth-signal",
                    severity="high",
                    kind="auth-reseeded-credential",
                    fingerprint=f"{path}:{provider_label}:{source}:{index}",
                    sample_text=f"credential_pool[{provider_label}][{index}] was seeded from '{source}'",
                    count=1,
                    confidence="high",
                    router_note=f"credential source '{source}' should be suppressed or migrated",
                    lane=None,
                )
            )

    return findings


def scan_auth(path: str | Path) -> list[Finding]:
    """Scan a Hermes auth.json file for credential source hygiene issues."""
    findings: list[Finding] = []
    p = Path(path) if isinstance(path, str) else path
    if not p.exists():
        return findings

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        findings.append(
            Finding(
                file_path=str(p),
                line_num=None,
                category="auth-signal",
                severity="high",
                kind="auth-invalid-entry",
                fingerprint=f"{p}:parse-error",
                sample_text="failed to parse auth.json",
                count=1,
                confidence="high",
                router_note="json-parse-error",
                lane=None,
            )
        )
        return findings

    if not isinstance(data, dict):
        return findings

    credential_pool = data.get("credential_pool", {})
    if not isinstance(credential_pool, dict):
        return findings

    seen_families: set[str] = set()
    for provider_name, entries in credential_pool.items():
        findings.extend(_credential_findings(p, provider_name, entries, seen_families))

    return findings


def scan_auth_files(paths: list[str | Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        findings.extend(scan_auth(path))
    return findings

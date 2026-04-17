from __future__ import annotations

from dataclasses import dataclass

from .inventory import VaultEntry


@dataclass(frozen=True, slots=True)
class DeduplicationResult:
    canonical: VaultEntry
    duplicates: list[VaultEntry]


def deduplicate_entries(entries: list[VaultEntry]) -> list[DeduplicationResult]:
    """Group entries by fingerprint and choose a deterministic canonical entry."""
    grouped: dict[str, list[VaultEntry]] = {}
    for entry in entries:
        grouped.setdefault(entry.fingerprint, []).append(entry)

    results: list[DeduplicationResult] = []
    for group in grouped.values():
        if not group:
            continue
        ordered = sorted(group, key=lambda entry: (str(entry.source_path), entry.key_name, entry.source_kind))
        results.append(DeduplicationResult(canonical=ordered[0], duplicates=ordered[1:]))
    return results

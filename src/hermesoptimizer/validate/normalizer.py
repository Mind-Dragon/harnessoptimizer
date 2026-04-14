from __future__ import annotations

from dataclasses import replace

from hermesoptimizer.catalog import Finding, Record

VALID_LANES = {"coding", "compression", "web-extract", "research", "auxiliary"}


def normalize_lane(lane: str | None) -> str | None:
    if lane is None:
        return None
    lane = lane.strip().lower()
    return lane if lane in VALID_LANES else None


def normalize_record(record: Record) -> Record:
    return replace(record, lane=normalize_lane(record.lane))


def normalize_finding(finding: Finding) -> Finding:
    return replace(finding, lane=normalize_lane(finding.lane))

from __future__ import annotations

from hermesoptimizer.catalog import Finding, Record
from hermesoptimizer.validate.lanes import assign_lane
from hermesoptimizer.validate.normalizer import normalize_finding, normalize_record


def test_normalize_record_lane() -> None:
    record = Record(
        provider="a",
        model="b",
        base_url="c",
        auth_type="bearer",
        auth_key="KEY",
        lane="invalid",
        region=None,
        capabilities=[],
        context_window=0,
        source="manual",
        confidence="low",
    )
    normalized = normalize_record(record)
    assert normalized.lane is None


def test_assign_lane() -> None:
    finding = Finding(
        file_path=None,
        line_num=None,
        category="log-signal",
        severity="medium",
    )
    assert assign_lane(finding) == "auxiliary"
    assert normalize_finding(finding).lane is None

from __future__ import annotations

from hermesoptimizer.catalog import Finding
from hermesoptimizer.route.diagnosis import (
    BUCKET_LABELS,
    Priority,
    build_recommendations,
    bucket_by_priority,
    diagnose_findings,
    infer_routing_from_config,
    infer_routing_from_findings,
    rank_findings,
)


def test_infer_routing_from_config() -> None:
    routing = infer_routing_from_config(
        {
            "providers": {
                "openai": {"lane": "coding"},
                "anthropic": {"lane": "reasoning"},
            }
        }
    )
    assert routing["coding"] == ["openai"]
    assert routing["reasoning"] == ["anthropic"]


def test_infer_routing_from_findings() -> None:
    findings = [
        Finding(
            file_path="x",
            line_num=1,
            category="log-signal",
            severity="medium",
            kind="log-auth-failure",
            fingerprint="x",
            sample_text="provider openai selected for lane=coding",
            count=1,
            confidence="low",
            router_note="r",
            lane="coding",
        )
    ]
    routing = infer_routing_from_findings(findings)
    assert routing["coding"] == ["openai"]


def test_diagnose_and_rank_auth_failure() -> None:
    finding = Finding(
        file_path="x",
        line_num=1,
        category="log-signal",
        severity="medium",
        kind="log-auth-failure",
        fingerprint="x",
        sample_text="401 unauthorized provider openai selected for lane=coding",
        count=1,
        confidence="low",
        router_note="r",
        lane="coding",
    )
    diagnoses = diagnose_findings([finding], {"coding": ["openai"]})
    assert diagnoses[0].priority == Priority.CRITICAL
    assert diagnoses[0].code == "AUTH_FAILURE"
    assert rank_findings([finding])[0].code == "AUTH_FAILURE"


def test_build_recommendations_and_buckets() -> None:
    finding = Finding(
        file_path="x",
        line_num=1,
        category="log-signal",
        severity="medium",
        kind="log-auth-failure",
        fingerprint="x",
        sample_text="401 unauthorized provider openai selected for lane=coding",
        count=1,
        confidence="low",
        router_note="r",
        lane="coding",
    )
    recs = build_recommendations(diagnose_findings([finding], {"coding": ["openai"]}))
    buckets = bucket_by_priority(recs)
    assert Priority.CRITICAL in buckets
    assert BUCKET_LABELS[Priority.CRITICAL].startswith("🔴")

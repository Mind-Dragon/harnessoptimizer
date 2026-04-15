from __future__ import annotations

from pathlib import Path

from hermesoptimizer.catalog import Finding
from hermesoptimizer.report.issues import group_findings_by_fingerprint, recommendation_summary
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


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "hermes"


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
    summary = recommendation_summary(recs, include_detail=True)
    assert any("Critical" in line for line in summary)
    assert any("Recommendation:" in line for line in summary)


def test_group_findings_by_fingerprint_collapses_duplicates() -> None:
    duplicate = Finding(
        file_path="x",
        line_num=1,
        category="log-signal",
        severity="medium",
        kind="log-provider-failure",
        fingerprint="dup",
        sample_text="provider timeout",
        count=1,
        confidence="high",
        router_note="r",
        lane="coding",
    )
    groups = group_findings_by_fingerprint([duplicate, duplicate])
    assert list(groups.keys()) == ["dup"]
    assert len(groups["dup"]) == 2


def test_diagnose_broken_fallback_chain_with_multi_provider_fixture() -> None:
    config_path = FIXTURE_DIR / "config_multi_provider.yaml"
    routing = infer_routing_from_config(
        {
            "providers": {
                "openai_primary": {"lane": "coding"},
                "openai_fallback": {"lane": "coding"},
                "anthropic_primary": {"lane": "reasoning"},
                "anthropic_fallback": {"lane": "reasoning"},
            },
            "gateway": {"fallback_routes": "coding:openai_primary>openai_fallback,reasoning:anthropic_primary>anthropic_fallback"},
        }
    )
    findings = [
        Finding(
            file_path=str(config_path),
            line_num=10,
            category="log-signal",
            severity="high",
            kind="log-auth-failure",
            fingerprint="openai_primary:1",
            sample_text='provider openai_primary selected for lane=coding auth failure',
            count=1,
            confidence="high",
            router_note="auth failure",
            lane="coding",
        ),
        Finding(
            file_path=str(config_path),
            line_num=16,
            category="log-signal",
            severity="high",
            kind="log-auth-failure",
            fingerprint="anthropic_primary:1",
            sample_text='provider anthropic_primary selected for lane=reasoning auth failure',
            count=1,
            confidence="high",
            router_note="auth failure",
            lane="reasoning",
        ),
    ]
    diagnoses = diagnose_findings(findings, routing)
    assert any(d.code == "BROKEN_FALLBACK" for d in diagnoses)

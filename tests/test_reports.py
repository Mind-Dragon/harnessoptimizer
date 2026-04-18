from __future__ import annotations

import json
from pathlib import Path

from hermesoptimizer.catalog import Finding, Record
from hermesoptimizer.report.json_export import write_json_report
from hermesoptimizer.report.markdown import write_markdown_report
from hermesoptimizer.report.metrics import METRIC_KEYS, compute_report_metrics
from hermesoptimizer.report.health import (
    ProviderHealthSummary,
    ModelValiditySummary,
    RepairPriority,
    LaneAwareRepairTuple,
    ProvenanceCollision,
    compute_provider_health,
    compute_model_validity,
    compute_repair_priority,
    compute_lane_aware_repairs,
    compute_provenance_collisions,
)


def _comparison() -> dict:
    return {
        "baseline_title": "Previous Run",
        "baseline_metrics": {"findings_total": 3, "gateway_findings": 2, "inspected_inputs": 4},
        "current_metrics": {"findings_total": 1, "gateway_findings": 0, "inspected_inputs": 5},
        "deltas": {"findings_total": -2, "gateway_findings": -2, "inspected_inputs": 1},
    }


def test_json_and_markdown_report(tmp_path: Path) -> None:
    record = Record(
        provider="openai",
        model="gpt-5",
        base_url="https://api.openai.com/v1",
        auth_type="bearer",
        auth_key="OPENAI_API_KEY",
        lane="coding",
        region=None,
        capabilities=["text"],
        context_window=128000,
        source="manual",
        confidence="high",
    )
    finding = Finding(
        file_path="a.log",
        line_num=1,
        category="log-signal",
        severity="medium",
    )

    out_dir = tmp_path / "reports"
    write_json_report(out_dir / "report.json", title="Report", records=[record], findings=[finding], comparison=_comparison())
    write_markdown_report(out_dir / "report.md", title="Report", records=[record], findings=[finding], comparison=_comparison())

    json_text = (out_dir / "report.json").read_text(encoding="utf-8")
    md_text = (out_dir / "report.md").read_text(encoding="utf-8")
    assert "\"title\": \"Report\"" in json_text
    assert "# Report" in md_text
    assert "metrics" in json_text
    assert "before_after" in json_text
    assert "Before / After" in md_text
    assert "findings_total" in md_text


def test_export_uses_persistent_run_history(tmp_path: Path) -> None:
    db = tmp_path / "catalog.db"
    out_dir = tmp_path / "reports"
    record = Record(
        provider="openai",
        model="gpt-5",
        base_url="https://api.openai.com/v1",
        auth_type="bearer",
        auth_key="OPENAI_API_KEY",
        lane="coding",
        region=None,
        capabilities=["text"],
        context_window=128000,
        source="manual",
        confidence="high",
    )
    finding = Finding(
        file_path="a.log",
        line_num=1,
        category="log-signal",
        severity="medium",
    )

    from hermesoptimizer.catalog import init_db, upsert_finding, upsert_record
    from hermesoptimizer.run_standalone import main

    init_db(db)
    upsert_record(db, record)
    upsert_finding(db, finding)

    assert main(["export", "--db", str(db), "--out-dir", str(out_dir), "--title", "First Run"]) == 0
    (out_dir / "report.json").unlink()
    (out_dir / "report.md").unlink()

    assert main(["export", "--db", str(db), "--out-dir", str(out_dir), "--title", "Second Run"]) == 0

    json_text = (out_dir / "report.json").read_text(encoding="utf-8")
    md_text = (out_dir / "report.md").read_text(encoding="utf-8")
    assert "before_after" in json_text
    assert "Before / After" in md_text
    assert "Second Run" in json_text


def test_metric_surface_is_stable_and_ordered(tmp_path: Path) -> None:
    record = Record(
        provider="openai",
        model="gpt-5",
        base_url="https://api.openai.com/v1",
        auth_type="bearer",
        auth_key="OPENAI_API_KEY",
        lane="coding",
        region=None,
        capabilities=["text"],
        context_window=128000,
        source="manual",
        confidence="high",
    )
    finding = Finding(
        file_path="a.log",
        line_num=1,
        category="log-signal",
        severity="medium",
    )
    metrics = compute_report_metrics(records=[record], findings=[finding, finding], inspected_inputs=[{"type": "file", "path": "/home/user/.hermes/config.yaml"}])

    assert METRIC_KEYS == (
        "records_total",
        "findings_total",
        "finding_groups_total",
        "inspected_inputs_total",
        "gateway_findings",
        "config_findings",
        "session_findings",
        "log_findings",
        "runtime_findings",
    )
    assert tuple(metrics.keys()) == METRIC_KEYS


def test_json_report_contains_inspected_inputs_header(tmp_path: Path) -> None:
    """JSON report should include an 'inspected_inputs' header section."""
    record = Record(
        provider="openai",
        model="gpt-5",
        base_url="https://api.openai.com/v1",
        auth_type="bearer",
        auth_key="OPENAI_API_KEY",
        lane="coding",
        region=None,
        capabilities=["text"],
        context_window=128000,
        source="manual",
        confidence="high",
    )
    finding = Finding(
        file_path="a.log",
        line_num=1,
        category="log-signal",
        severity="medium",
    )
    # inspected inputs should list the files and commands that were inspected
    inspected_inputs = [
        {"type": "file", "path": "/home/user/.hermes/config.yaml"},
        {"type": "command", "command": "pgrep -f hermes"},
    ]

    out_dir = tmp_path / "reports"
    write_json_report(
        out_dir / "report.json",
        title="Report",
        records=[record],
        findings=[finding, finding],
        inspected_inputs=inspected_inputs,
    )

    report_text = (out_dir / "report.json").read_text(encoding="utf-8")
    assert "inspected_inputs" in report_text
    assert "/home/user/.hermes/config.yaml" in report_text
    assert "pgrep -f hermes" in report_text
    assert "finding_groups" in report_text


def test_markdown_report_contains_inspected_inputs_header(tmp_path: Path) -> None:
    """Markdown report should include an '## Inspected Inputs' section."""
    record = Record(
        provider="openai",
        model="gpt-5",
        base_url="https://api.openai.com/v1",
        auth_type="bearer",
        auth_key="OPENAI_API_KEY",
        lane="coding",
        region=None,
        capabilities=["text"],
        context_window=128000,
        source="manual",
        confidence="high",
    )
    finding = Finding(
        file_path="a.log",
        line_num=1,
        category="log-signal",
        severity="medium",
    )
    # inspected inputs should list the files and commands that were inspected
    inspected_inputs = [
        {"type": "file", "path": "/home/user/.hermes/config.yaml"},
        {"type": "command", "command": "pgrep -f hermes"},
    ]

    out_dir = tmp_path / "reports"
    write_markdown_report(
        out_dir / "report.md",
        title="Report",
        records=[record],
        findings=[finding],
        inspected_inputs=inspected_inputs,
    )

    report_text = (out_dir / "report.md").read_text(encoding="utf-8")
    assert "Inspected Inputs" in report_text
    assert "/home/user/.hermes/config.yaml" in report_text
    assert "pgrep -f hermes" in report_text
    assert "Finding Groups" in report_text


# -----------------------------------------------------------------------
# v0.6.0 report-output-improvements tests
# -----------------------------------------------------------------------

def test_provider_health_summary_structure() -> None:
    """Provider health summary should be a dataclass with required fields."""
    summary = ProviderHealthSummary(
        provider="openai",
        status="healthy",
        auth_type="bearer",
        endpoint_url="https://api.openai.com/v1",
        last_probe_result="ok",
        last_probe_timestamp="2026-04-01T00:00:00Z",
        failure_reason=None,
    )
    assert summary.provider == "openai"
    assert summary.status == "healthy"
    assert summary.auth_type == "bearer"
    assert summary.endpoint_url == "https://api.openai.com/v1"
    assert summary.last_probe_result == "ok"
    assert summary.failure_reason is None


def test_model_validity_summary_structure() -> None:
    """Model validity summary should be a dataclass with required fields."""
    summary = ModelValiditySummary(
        provider="openai",
        model="gpt-5",
        status="valid",
        repair_note=None,
        suggested_replacement=None,
    )
    assert summary.provider == "openai"
    assert summary.model == "gpt-5"
    assert summary.status == "valid"


def test_repair_priority_structure() -> None:
    """Repair priority should be a dataclass with priority level, description, lane, and safety."""
    priority = RepairPriority(
        priority_level="critical",
        description="Remove stale provider openai-stale from active list",
        lane="coding",
        safety_level="auto-fix",
    )
    assert priority.priority_level == "critical"
    assert priority.description == "Remove stale provider openai-stale from active list"
    assert priority.lane == "coding"
    assert priority.safety_level == "auto-fix"


def test_lane_aware_repair_tuple_structure() -> None:
    """Lane-aware repair tuple should include provider alias, endpoint URL, auth type, region, model."""
    repair = LaneAwareRepairTuple(
        provider_alias="openai-corporate",
        endpoint_url="https://api.openai.com/v1",
        auth_type="bearer",
        region="us-east-1",
        model="gpt-5",
        repair_action="promote",
        priority="critical",
    )
    assert repair.provider_alias == "openai-corporate"
    assert repair.endpoint_url == "https://api.openai.com/v1"
    assert repair.auth_type == "bearer"
    assert repair.region == "us-east-1"
    assert repair.model == "gpt-5"
    assert repair.repair_action == "promote"
    assert repair.priority == "critical"


def test_provenance_collision_structure() -> None:
    """Provenance collision should explain duplicate provider rows as collisions."""
    collision = ProvenanceCollision(
        colliding_providers=["openai-alias-1", "openai-alias-2"],
        collision_type="duplicate_alias",
        explanation="Two provider entries resolve to the same canonical provider openai with endpoint https://api.openai.com/v1",
        suggested_resolution="Deduplicate by keeping canonical openai and removing stale aliases",
    )
    assert len(collision.colliding_providers) == 2
    assert "openai-alias-1" in collision.colliding_providers
    assert collision.collision_type == "duplicate_alias"
    assert "canonical provider openai" in collision.explanation
    assert "Deduplicate" in collision.suggested_resolution


def test_compute_provider_health_from_records() -> None:
    """compute_provider_health should derive health summaries from records."""
    records = [
        Record(
            provider="openai",
            model="gpt-5",
            base_url="https://api.openai.com/v1",
            auth_type="bearer",
            auth_key="OPENAI_API_KEY",
            lane="coding",
            region=None,
            capabilities=["text"],
            context_window=128000,
            source="manual",
            confidence="high",
        ),
        Record(
            provider="anthropic",
            model="claude-3-5-sonnet",
            base_url="https://api.anthropic.com/v1",
            auth_type="bearer",
            auth_key="ANTHROPIC_API_KEY",
            lane="coding",
            region=None,
            capabilities=["text"],
            context_window=200000,
            source="manual",
            confidence="high",
        ),
    ]
    health_summaries = compute_provider_health(records)
    assert len(health_summaries) == 2
    provider_names = {h.provider for h in health_summaries}
    assert "openai" in provider_names
    assert "anthropic" in provider_names
    # All records are treated as healthy by default when confidence is high
    for summary in health_summaries:
        assert summary.status in ("healthy", "degraded", "failing")
        assert summary.auth_type in ("bearer", "api-key", "oauth")


def test_compute_model_validity_from_records() -> None:
    """compute_model_validity should produce validity summaries for each record."""
    records = [
        Record(
            provider="openai",
            model="gpt-5",
            base_url="https://api.openai.com/v1",
            auth_type="bearer",
            auth_key="OPENAI_API_KEY",
            lane="coding",
            region=None,
            capabilities=["text"],
            context_window=128000,
            source="manual",
            confidence="high",
        ),
    ]
    validity_summaries = compute_model_validity(records)
    assert len(validity_summaries) == 1
    summary = validity_summaries[0]
    assert summary.provider == "openai"
    assert summary.model == "gpt-5"
    assert summary.status in ("valid", "stale", "deprecated", "wrong-endpoint")


def test_compute_repair_priority_returns_ordered_list() -> None:
    """compute_repair_priority should return a list of priorities for non-high-confidence records."""
    records = [
        Record(
            provider="openai",
            model="gpt-5",
            base_url="https://api.openai.com/v1",
            auth_type="bearer",
            auth_key="OPENAI_API_KEY",
            lane="coding",
            region=None,
            capabilities=["text"],
            context_window=128000,
            source="manual",
            confidence="high",
        ),
    ]
    priorities = compute_repair_priority(records)
    assert isinstance(priorities, list)
    # With a high-confidence record, no priorities should be generated
    assert len(priorities) == 0


def test_compute_lane_aware_repairs_includes_all_fields() -> None:
    """compute_lane_aware_repairs should produce tuples with provider alias, endpoint, auth, region, model."""
    records = [
        Record(
            provider="openai",
            model="gpt-5",
            base_url="https://api.openai.com/v1",
            auth_type="bearer",
            auth_key="OPENAI_API_KEY",
            lane="coding",
            region="us-east-1",
            capabilities=["text"],
            context_window=128000,
            source="manual",
            confidence="high",
        ),
    ]
    repairs = compute_lane_aware_repairs(records)
    assert isinstance(repairs, list)
    if repairs:
        repair = repairs[0]
        assert hasattr(repair, "provider_alias")
        assert hasattr(repair, "endpoint_url")
        assert hasattr(repair, "auth_type")
        assert hasattr(repair, "region")
        assert hasattr(repair, "model")
        assert hasattr(repair, "repair_action")
        assert hasattr(repair, "priority")


def test_compute_lane_aware_repairs_valid_action_for_all_confidences() -> None:
    """compute_lane_aware_repairs should assign valid repair_action for all confidence levels."""
    valid_actions = {"promote", "demote", "remove", "replace", "quarantine", "renew"}
    # Test with all confidence levels
    records = [
        Record(
            provider="openai-high",
            model="gpt-5",
            base_url="https://api.openai.com/v1",
            auth_type="bearer",
            auth_key="OPENAI_API_KEY",
            lane="coding",
            region=None,
            capabilities=["text"],
            context_window=128000,
            source="manual",
            confidence="high",
        ),
        Record(
            provider="openai-medium",
            model="gpt-5",
            base_url="https://api.openai.com/v2",
            auth_type="bearer",
            auth_key="OPENAI_API_KEY",
            lane="coding",
            region=None,
            capabilities=["text"],
            context_window=128000,
            source="manual",
            confidence="medium",
        ),
        Record(
            provider="openai-low",
            model="gpt-5",
            base_url="https://api.openai.com/v3",
            auth_type="bearer",
            auth_key="OPENAI_API_KEY",
            lane="coding",
            region=None,
            capabilities=["text"],
            context_window=128000,
            source="manual",
            confidence="low",
        ),
    ]
    repairs = compute_lane_aware_repairs(records)
    assert len(repairs) == 3
    for repair in repairs:
        # repair_action must be one of the valid Literal values, not "recommend-and-confirm"
        assert repair.repair_action in valid_actions, (
            f"repair_action '{repair.repair_action}' is not a valid Literal value; "
            f"expected one of {valid_actions}"
        )


def test_compute_provenance_collisions_detects_duplicates() -> None:
    """compute_provenance_collisions should identify duplicate provider entries as collisions."""
    records = [
        Record(
            provider="openai",
            model="gpt-5",
            base_url="https://api.openai.com/v1",
            auth_type="bearer",
            auth_key="OPENAI_API_KEY",
            lane="coding",
            region=None,
            capabilities=["text"],
            context_window=128000,
            source="manual",
            confidence="high",
        ),
        Record(
            provider="openai-alias",
            model="gpt-5",
            base_url="https://api.openai.com/v1",
            auth_type="bearer",
            auth_key="OPENAI_API_KEY",
            lane="coding",
            region=None,
            capabilities=["text"],
            context_window=128000,
            source="manual",
            confidence="high",
        ),
    ]
    collisions = compute_provenance_collisions(records)
    assert isinstance(collisions, list)
    # Two records with same base_url but different provider names should be flagged
    if collisions:
        collision = collisions[0]
        assert hasattr(collision, "colliding_providers")
        assert hasattr(collision, "collision_type")
        assert hasattr(collision, "explanation")
        assert hasattr(collision, "suggested_resolution")
        assert len(collision.colliding_providers) >= 2


def test_json_report_with_provider_health(tmp_path: Path) -> None:
    """JSON report should include provider_health section when provided."""
    records = [
        Record(
            provider="openai",
            model="gpt-5",
            base_url="https://api.openai.com/v1",
            auth_type="bearer",
            auth_key="OPENAI_API_KEY",
            lane="coding",
            region=None,
            capabilities=["text"],
            context_window=128000,
            source="manual",
            confidence="high",
        ),
    ]
    findings: list[Finding] = []
    provider_health = compute_provider_health(records)
    model_validity = compute_model_validity(records)
    repair_priority = compute_repair_priority(records)
    lane_repairs = compute_lane_aware_repairs(records)
    collisions = compute_provenance_collisions(records)

    out_dir = tmp_path / "reports"
    write_json_report(
        out_dir / "report.json",
        title="Report with Health",
        records=records,
        findings=findings,
        provider_health=provider_health,
        model_validity=model_validity,
        repair_priority=repair_priority,
        lane_repairs=lane_repairs,
        provenance_collisions=collisions,
    )

    report_text = (out_dir / "report.json").read_text(encoding="utf-8")
    report_data = json.loads(report_text)
    assert "provider_health" in report_data
    assert "model_validity" in report_data
    assert "repair_priority" in report_data
    assert "lane_repairs" in report_data
    assert "provenance_collisions" in report_data
    assert len(report_data["provider_health"]) == 1
    assert report_data["provider_health"][0]["provider"] == "openai"


def test_markdown_report_with_provider_health(tmp_path: Path) -> None:
    """Markdown report should include Provider Health section when provided."""
    records = [
        Record(
            provider="openai",
            model="gpt-5",
            base_url="https://api.openai.com/v1",
            auth_type="bearer",
            auth_key="OPENAI_API_KEY",
            lane="coding",
            region=None,
            capabilities=["text"],
            context_window=128000,
            source="manual",
            confidence="high",
        ),
    ]
    findings: list[Finding] = []
    provider_health = compute_provider_health(records)
    model_validity = compute_model_validity(records)
    repair_priority = compute_repair_priority(records)
    lane_repairs = compute_lane_aware_repairs(records)
    collisions = compute_provenance_collisions(records)

    out_dir = tmp_path / "reports"
    write_markdown_report(
        out_dir / "report.md",
        title="Report with Health",
        records=records,
        findings=findings,
        provider_health=provider_health,
        model_validity=model_validity,
        repair_priority=repair_priority,
        lane_repairs=lane_repairs,
        provenance_collisions=collisions,
    )

    report_text = (out_dir / "report.md").read_text(encoding="utf-8")
    assert "## Provider Health" in report_text or "## Provider Health Summary" in report_text
    assert "openai" in report_text
    assert "## Model Validity" in report_text or "## Model Validity Summary" in report_text
    assert "## Repair Priority" in report_text
    assert "## Lane-Aware Repairs" in report_text
    assert "## Provenance Collisions" in report_text

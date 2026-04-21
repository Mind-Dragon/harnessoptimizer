"""Tests for v0.9.1 catalog schema extensions."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from hermesoptimizer.catalog import (
    init_db,
    insert_token_usage,
    get_token_usage,
    insert_provider_perf,
    get_provider_perf,
    insert_tool_usage,
    get_tool_usage,
    upsert_network_inventory,
    get_network_inventory,
    delete_network_inventory,
)


@pytest.fixture
def db_path() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    init_db(path)
    yield path
    path.unlink(missing_ok=True)


class TestTokenUsageTable:
    def test_insert_and_retrieve(self, db_path: Path) -> None:
        insert_token_usage(
            db_path,
            session_id="sess-001",
            provider="openai",
            model="gpt-4o",
            lane="coding",
            role="implement",
            tokens_in=1500,
            tokens_out=320,
            tokens_total=1820,
            cost_estimate=0.054,
            duration_ms=4200,
        )
        rows = get_token_usage(db_path)
        assert len(rows) == 1
        assert rows[0]["session_id"] == "sess-001"
        assert rows[0]["tokens_in"] == 1500
        assert rows[0]["tokens_out"] == 320
        assert rows[0]["tokens_total"] == 1820

    def test_default_values(self, db_path: Path) -> None:
        insert_token_usage(db_path, session_id="sess-002")
        rows = get_token_usage(db_path)
        assert rows[0]["tokens_in"] == 0
        assert rows[0]["tokens_out"] == 0
        assert rows[0]["tokens_total"] == 0

    def test_limit(self, db_path: Path) -> None:
        for i in range(5):
            insert_token_usage(db_path, session_id=f"sess-{i}")
        rows = get_token_usage(db_path, limit=2)
        assert len(rows) == 2


class TestProviderPerfTable:
    def test_insert_and_retrieve(self, db_path: Path) -> None:
        insert_provider_perf(
            db_path,
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            endpoint="https://api.anthropic.com/v1/messages",
            response_time_ms=1200,
            tokens_per_second=45.5,
            error_code=None,
            error_message=None,
            tool_used="browser_navigate",
            session_id="sess-003",
        )
        rows = get_provider_perf(db_path)
        assert len(rows) == 1
        assert rows[0]["provider"] == "anthropic"
        assert rows[0]["response_time_ms"] == 1200
        assert rows[0]["tokens_per_second"] == 45.5

    def test_insert_error(self, db_path: Path) -> None:
        insert_provider_perf(
            db_path,
            provider="openai",
            model="gpt-4o",
            error_code="429",
            error_message="Rate limit exceeded",
            session_id="sess-004",
        )
        rows = get_provider_perf(db_path)
        assert rows[0]["error_code"] == "429"
        assert rows[0]["error_message"] == "Rate limit exceeded"


class TestToolUsageTable:
    def test_insert_and_retrieve(self, db_path: Path) -> None:
        insert_tool_usage(
            db_path,
            session_id="sess-005",
            provider="openai",
            model="gpt-4o",
            lane="coding",
            tool_name="image_generate",
            tool_count=3,
            manual_workaround_detected=False,
        )
        rows = get_tool_usage(db_path)
        assert len(rows) == 1
        assert rows[0]["tool_name"] == "image_generate"
        assert rows[0]["tool_count"] == 3
        assert rows[0]["manual_workaround_detected"] == 0

    def test_manual_workaround(self, db_path: Path) -> None:
        insert_tool_usage(
            db_path,
            session_id="sess-006",
            manual_workaround_detected=True,
        )
        rows = get_tool_usage(db_path)
        assert rows[0]["manual_workaround_detected"] == 1


class TestNetworkInventoryTable:
    def test_upsert_and_retrieve(self, db_path: Path) -> None:
        upsert_network_inventory(
            db_path,
            resource_type="port",
            value="9200",
            status="reserved",
            purpose="local verification server",
            added_by="user",
        )
        rows = get_network_inventory(db_path)
        assert len(rows) == 1
        assert rows[0]["value"] == "9200"
        assert rows[0]["status"] == "reserved"

    def test_upsert_updates_existing(self, db_path: Path) -> None:
        upsert_network_inventory(db_path, resource_type="port", value="9201", status="available")
        upsert_network_inventory(db_path, resource_type="port", value="9201", status="reserved")
        rows = get_network_inventory(db_path, resource_type="port")
        assert len(rows) == 1
        assert rows[0]["status"] == "reserved"

    def test_filter_by_resource_type(self, db_path: Path) -> None:
        upsert_network_inventory(db_path, resource_type="port", value="9202")
        upsert_network_inventory(db_path, resource_type="ip", value="192.168.1.100")
        ports = get_network_inventory(db_path, resource_type="port")
        ips = get_network_inventory(db_path, resource_type="ip")
        assert len(ports) == 1
        assert len(ips) == 1

    def test_filter_by_status(self, db_path: Path) -> None:
        upsert_network_inventory(db_path, resource_type="port", value="9203", status="forbidden")
        upsert_network_inventory(db_path, resource_type="port", value="9204", status="available")
        forbidden = get_network_inventory(db_path, status="forbidden")
        assert len(forbidden) == 1
        assert forbidden[0]["value"] == "9203"

    def test_delete(self, db_path: Path) -> None:
        upsert_network_inventory(db_path, resource_type="port", value="9205")
        delete_network_inventory(db_path, resource_type="port", value="9205")
        rows = get_network_inventory(db_path)
        assert len(rows) == 0

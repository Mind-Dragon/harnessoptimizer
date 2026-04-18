"""Tests for Phase 3 recall reheating: transcript parsing, recall_log fallback,
sidecar DB reheating updates, and pre-sweep integration.

These tests verify:
1. Transcript parsing extracts supermemory_search calls and result IDs
2. recall_log.jsonl is read as a fallback when transcripts are unreliable
3. Importance is boosted by 0.3 per recall, capped at 5.0
4. recall_count and last_recalled are updated atomically in the DB
5. Pre-sweep integration reports reheated/skipped counts

All tests use temporary fixture data -- no live ~/.hermes mutation.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Generator

import pytest


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def temp_db(tmp_path: Path) -> Generator[Path, None, None]:
    """Yield a temp DB path."""
    yield tmp_path / "test_memory_meta.db"


@pytest.fixture
def temp_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Yield a temp directory."""
    d = tmp_path / "sub"
    d.mkdir()
    yield d


@pytest.fixture
def temp_jsonl_file(tmp_path: Path) -> Generator[Path, None, None]:
    """Yield a temp .jsonl file path."""
    yield tmp_path / "recall_log.jsonl"


class MockTranscriptSession:
    """Minimal mock transcript structure matching ~/.hermes/sessions/ format."""

    def __init__(
        self,
        supermemory_id: str,
        query: str,
        result_ids: list[str],
        tool_response_available: bool = True,
    ) -> None:
        self.supermemory_id = supermemory_id
        self.query = query
        self.result_ids = result_ids
        self.tool_response_available = tool_response_available


def make_session_with_search(
    search_query: str,
    result_ids: list[str],
    tool_response_available: bool = True,
) -> dict:
    """Create a minimal session transcript dict with a supermemory_search call.

    Args:
        search_query: The query passed to supermemory_search.
        result_ids: List of entry IDs returned by the search.
        tool_response_available: If False, the tool response is marked as cleared.

    Returns:
        A dict representing the session transcript structure.
    """
    session_id = f"session-{search_query[:8]}"

    # Build assistant tool_calls block
    assistant_block = {
        "role": "assistant",
        "tool_calls": [
            {
                "function": {
                    "name": "supermemory_search",
                    "arguments": json.dumps({"query": search_query}),
                }
            }
        ],
    }

    # Build tool response block
    if tool_response_available:
        tool_response_block = {
            "role": "tool",
            "content": json.dumps({
                "results": [{"id": rid, "content": f"content-{rid}", "similarity": 80 + i}
                            for i, rid in enumerate(result_ids)],
                "count": len(result_ids),
            }),
        }
    else:
        # Simulates "[Old tool output cleared to save context space]"
        tool_response_block = {
            "role": "tool",
            "content": "[Old tool output cleared to save context space]",
        }

    return {
        "session_id": session_id,
        "messages": [assistant_block, tool_response_block],
    }


def make_session_with_no_results(search_query: str) -> dict:
    """Create a session transcript where the search returned empty results."""
    session_id = f"session-{search_query[:8]}"
    return {
        "session_id": session_id,
        "messages": [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "supermemory_search",
                            "arguments": json.dumps({"query": search_query}),
                        }
                    }
                ],
            },
            {
                "role": "tool",
                "content": json.dumps({"results": [], "count": 0}),
            },
        ],
    }


def make_session_with_unclear_response(search_query: str) -> dict:
    """Create a session transcript where the tool response format is unrecognized."""
    session_id = f"session-{search_query[:8]}"
    return {
        "session_id": session_id,
        "messages": [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "supermemory_search",
                            "arguments": json.dumps({"query": search_query}),
                        }
                    }
                ],
            },
            {
                "role": "tool",
                "content": "Something went wrong",
            },
        ],
    }


def make_session_with_intervening_message(
    search_query: str,
    result_ids: list[str],
    tool_call_id: str = "call_abc123",
) -> dict:
    """Create a session where tool response is NOT the immediate next message.

    This simulates a transcript where there is an intervening assistant message
    (or other message) between the tool call and its response. The tool response
    should still be matched by its tool_call_id field.
    """
    session_id = f"session-{search_query[:8]}"
    return {
        "session_id": session_id,
        "messages": [
            # Assistant message with tool call that has an explicit id
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": tool_call_id,
                        "function": {
                            "name": "supermemory_search",
                            "arguments": json.dumps({"query": search_query}),
                        },
                    }
                ],
            },
            # Intervening message (e.g., another assistant message or user message)
            {
                "role": "assistant",
                "content": "Let me think about this...",
            },
            # Tool response with matching tool_call_id
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": json.dumps({
                    "results": [{"id": rid, "content": f"content-{rid}", "similarity": 80 + i}
                                for i, rid in enumerate(result_ids)],
                    "count": len(result_ids),
                }),
            },
        ],
    }


def make_recall_log_entry(
    query: str,
    hit_count: int,
    ids: list[str],
    ts: str | None = None,
) -> dict:
    """Create a single recall_log.jsonl entry dict."""
    if ts is None:
        ts = "2025-04-18T10:00:00Z"
    return {"ts": ts, "query": query, "hit_count": hit_count, "ids": ids}


# ------------------------------------------------------------------------------------------------------------------------------------------
# Tests for transcript parsing
# ------------------------------------------------------------------------------------------------------------------------------------------


class TestTranscriptParser:
    """Test that transcript parsing extracts supermemory_search calls and IDs."""

    def test_extracts_result_ids_from_valid_response(self) -> None:
        """Given a session with a valid supermemory_search response, extract IDs."""
        from hermesoptimizer.dreams.recall import parse_session_transcript

        session = make_session_with_search(
            search_query="python async patterns",
            result_ids=["ID-ABC123", "ID-DEF456"],
        )

        parsed = parse_session_transcript(session)

        assert parsed is not None
        assert set(parsed["result_ids"]) == {"ID-ABC123", "ID-DEF456"}
        assert parsed["query"] == "python async patterns"

    def test_returns_none_when_tool_response_cleared(self) -> None:
        """When tool response is cleared, parse_session_transcript returns None."""
        from hermesoptimizer.dreams.recall import parse_session_transcript

        session = make_session_with_search(
            search_query="python async patterns",
            result_ids=["ID-ABC123"],
            tool_response_available=False,
        )

        result = parse_session_transcript(session)

        # Cleared responses should return None (parser should not guess)
        assert result is None

    def test_returns_none_for_empty_results(self) -> None:
        """When search returns empty results, return None (no IDs to reheal)."""
        from hermesoptimizer.dreams.recall import parse_session_transcript

        session = make_session_with_no_results("no results query")

        result = parse_session_transcript(session)

        assert result is None

    def test_returns_none_for_unrecognized_response_format(self) -> None:
        """When tool response is not valid JSON, return None."""
        from hermesoptimizer.dreams.recall import parse_session_transcript

        session = make_session_with_unclear_response("bad format")

        result = parse_session_transcript(session)

        assert result is None

    def test_extracts_multiple_ids_from_results(self) -> None:
        """Search with multiple results extracts all IDs."""
        from hermesoptimizer.dreams.recall import parse_session_transcript

        ids = [f"ID-{i:03d}" for i in range(10)]
        session = make_session_with_search("many results", ids)

        parsed = parse_session_transcript(session)

        assert parsed is not None
        assert len(parsed["result_ids"]) == 10
        assert set(parsed["result_ids"]) == set(ids)

    def test_returns_none_when_no_supermemory_search_call(self) -> None:
        """Session without supermemory_search tool call returns None."""
        from hermesoptimizer.dreams.recall import parse_session_transcript

        session = {
            "session_id": "no-search-session",
            "messages": [
                {"role": "assistant", "content": "Hello"},
            ],
        }

        result = parse_session_transcript(session)

        assert result is None

    def test_extracts_query_from_tool_call_arguments(self) -> None:
        """The query field should be extracted from tool call arguments."""
        from hermesoptimizer.dreams.recall import parse_session_transcript

        session = make_session_with_search(
            search_query="exact query string",
            result_ids=["R1"],
        )

        parsed = parse_session_transcript(session)

        assert parsed is not None
        assert parsed["query"] == "exact query string"

    def test_matches_tool_response_by_tool_call_id_when_available(self) -> None:
        """When a tool response is not the immediate next message, matching by
        tool_call_id (or call_id) should still find the correct response.

        This handles cases where there are intervening messages between a
        tool call and its response.
        """
        from hermesoptimizer.dreams.recall import parse_session_transcript

        # Create a session with an intervening message between tool call and response
        session = make_session_with_intervening_message(
            search_query="search with intervening message",
            result_ids=["ID-X", "ID-Y"],
            tool_call_id="call_xyz789",
        )

        parsed = parse_session_transcript(session)

        # Should still correctly extract IDs even though response is not immediate next
        assert parsed is not None, (
            "Parser failed to match tool response by tool_call_id when response "
            "is separated from tool call by intervening message"
        )
        assert set(parsed["result_ids"]) == {"ID-X", "ID-Y"}
        assert parsed["query"] == "search with intervening message"


class TestTranscriptScanner:
    """Test scanning multiple session files for recall signals."""

    def test_scan_sessions_directory_returns_unique_ids_only(self, temp_dir: Path) -> None:
        """scan_sessions_directory should return deduplicated IDs.

        If the same ID appears in multiple sessions, it should appear only once
        in the result list (not duplicated).
        """
        from hermesoptimizer.dreams.recall import scan_sessions_directory

        sessions_dir = temp_dir / "sessions"
        sessions_dir.mkdir()

        # Session 1: returns IDs A, B
        (sessions_dir / "session-001.json").write_text(
            json.dumps(make_session_with_search("query1", ["A", "B"]))
        )
        # Session 2: returns ID A again (duplicate) and C
        (sessions_dir / "session-002.json").write_text(
            json.dumps(make_session_with_search("query2", ["A", "C"]))
        )
        # Session 3: returns ID B again (duplicate) and D
        (sessions_dir / "session-003.json").write_text(
            json.dumps(make_session_with_search("query3", ["B", "D"]))
        )

        all_ids = scan_sessions_directory(sessions_dir)

        # IDs should be unique - no duplicates
        assert len(all_ids) == len(set(all_ids)), (
            f"Expected unique IDs but got duplicates: {all_ids}"
        )
        assert set(all_ids) == {"A", "B", "C", "D"}

    def test_scans_directory_and_extracts_all_recalled_ids(self, temp_dir: Path) -> None:
        """Given a directory of session files, extract all recalled IDs."""
        from hermesoptimizer.dreams.recall import scan_sessions_directory

        # Create temp dir with session files
        sessions_dir = temp_dir / "sessions"
        sessions_dir.mkdir()

        # Session 1: returns IDs A, B
        (sessions_dir / "session-001.json").write_text(
            json.dumps(make_session_with_search("query1", ["A", "B"]))
        )
        # Session 2: returns IDs C, D (with cleared response -> skipped)
        (sessions_dir / "session-002.json").write_text(
            json.dumps(make_session_with_search(
                "query2", ["C", "D"], tool_response_available=False
            ))
        )
        # Session 3: returns ID E
        (sessions_dir / "session-003.json").write_text(
            json.dumps(make_session_with_search("query3", ["E"]))
        )

        all_ids = scan_sessions_directory(sessions_dir)

        # Only session-001 and session-003 have valid responses
        assert set(all_ids) == {"A", "B", "E"}

    def test_empty_directory_returns_empty_list(self, temp_dir: Path) -> None:
        """Empty sessions directory returns empty list."""
        from hermesoptimizer.dreams.recall import scan_sessions_directory

        sessions_dir = temp_dir / "sessions"
        sessions_dir.mkdir()

        result = scan_sessions_directory(sessions_dir)
        assert result == []

    def test_skips_non_json_files(self, temp_dir: Path) -> None:
        """Non-JSON files in sessions dir are ignored."""
        from hermesoptimizer.dreams.recall import scan_sessions_directory

        sessions_dir = temp_dir / "sessions"
        sessions_dir.mkdir()

        (sessions_dir / "session-001.json").write_text(
            json.dumps(make_session_with_search("q", ["ID1"]))
        )
        (sessions_dir / "readme.txt").write_text("not a session")

        result = scan_sessions_directory(sessions_dir)

        assert "ID1" in result


# ------------------------------------------------------------------------------------------------------------------------------------------
# Tests for recall_log.jsonl fallback
# ------------------------------------------------------------------------------------------------------------------------------------------


class TestRecallLog:
    """Test recall_log.jsonl read/write as fallback when transcripts fail."""

    def test_reads_recall_log_entries(self, temp_jsonl_file: Path) -> None:
        """read_recall_log returns all entries from the log file."""
        from hermesoptimizer.dreams.recall import read_recall_log

        temp_jsonl_file.write_text(
            '{"ts": "2025-04-18T10:00:00Z", "query": "q1", "hit_count": 2, "ids": ["A", "B"]}\n'
            '{"ts": "2025-04-18T11:00:00Z", "query": "q2", "hit_count": 1, "ids": ["C"]}\n'
        )

        entries = read_recall_log(temp_jsonl_file)

        assert len(entries) == 2
        assert entries[0]["ids"] == ["A", "B"]
        assert entries[1]["ids"] == ["C"]

    def test_read_recall_log_returns_empty_list_for_missing_file(self) -> None:
        """Missing recall_log file returns empty list (not an error)."""
        from hermesoptimizer.dreams.recall import read_recall_log

        result = read_recall_log(Path("/nonexistent/recall_log.jsonl"))
        assert result == []

    def test_read_recall_log_extracts_all_ids(self, temp_jsonl_file: Path) -> None:
        """All IDs across all entries are extracted."""
        from hermesoptimizer.dreams.recall import read_recall_log_ids

        temp_jsonl_file.write_text(
            '{"ts": "2025-04-18T10:00:00Z", "query": "q1", "hit_count": 2, "ids": ["A", "B"]}\n'
            '{"ts": "2025-04-18T11:00:00Z", "query": "q2", "hit_count": 3, "ids": ["C", "D", "E"]}\n'
        )

        all_ids = read_recall_log_ids(temp_jsonl_file)

        assert set(all_ids) == {"A", "B", "C", "D", "E"}

    def test_append_recall_log_entry_writes_line(self, temp_jsonl_file: Path) -> None:
        """append_recall_log_entry appends a JSON line to the file."""
        from hermesoptimizer.dreams.recall import append_recall_log_entry, read_recall_log

        temp_jsonl_file.write_text(
            '{"ts": "2025-04-18T10:00:00Z", "query": "q1", "hit_count": 1, "ids": ["A"]}\n'
        )

        append_recall_log_entry(temp_jsonl_file, query="q2", hit_count=2, ids=["B", "C"])

        entries = read_recall_log(temp_jsonl_file)
        assert len(entries) == 2
        assert entries[1]["query"] == "q2"
        assert entries[1]["ids"] == ["B", "C"]

    def test_append_creates_file_if_missing(self, tmp_path: Path) -> None:
        """append_recall_log_entry creates the file if it doesn't exist."""
        from hermesoptimizer.dreams.recall import append_recall_log_entry, read_recall_log

        log_path = tmp_path / "new_recall_log.jsonl"

        append_recall_log_entry(log_path, query="first", hit_count=1, ids=["X"])

        entries = read_recall_log(log_path)
        assert len(entries) == 1
        assert entries[0]["ids"] == ["X"]


# ------------------------------------------------------------------------------------------------------------------------------------------
# Tests for importance capping
# ------------------------------------------------------------------------------------------------------------------------------------------


class TestReheatImportanceCapping:
    """Test that importance boost is capped at 5.0."""

    def test_importance_boost_capped_at_five(self) -> None:
        """Boosted importance cannot exceed 5.0."""
        from hermesoptimizer.dreams.recall import compute_reheated_importance

        # Start at 4.9, add 0.3 -> should cap at 5.0
        result = compute_reheated_importance(current_importance=4.9, boost=0.3)
        assert result == 5.0

    def test_importance_below_cap_not_capped(self) -> None:
        """Importance below cap is boosted normally."""
        from hermesoptimizer.dreams.recall import compute_reheated_importance

        result = compute_reheated_importance(current_importance=3.0, boost=0.3)
        assert result == 3.3

    def test_exactly_at_cap_is_capped(self) -> None:
        """Exactly at cap stays at cap."""
        from hermesoptimizer.dreams.recall import compute_reheated_importance

        result = compute_reheated_importance(current_importance=5.0, boost=0.3)
        assert result == 5.0


# ------------------------------------------------------------------------------------------------------------------------------------------
# Tests for DB reheating updates
# ------------------------------------------------------------------------------------------------------------------------------------------


class TestReheatDbUpdates:
    """Test that reheating updates the sidecar DB correctly."""

    def test_apply_recall_reheat_updates_recall_count_and_last_recalled(
        self, temp_db: Path
    ) -> None:
        """apply_recall_reheat increments recall_count and updates last_recalled."""
        from hermesoptimizer.dreams.memory_meta import (
            apply_recall_reheat,
            init_db,
            upsert,
        )

        init_db(temp_db)
        upsert(temp_db, supermemory_id="entry-1", content_hash="hash1")

        apply_recall_reheat(temp_db, "entry-1")

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT recall_count, last_recalled FROM memory_meta WHERE supermemory_id=?",
            ("entry-1",),
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == 1  # recall_count
        assert row[1] is not None  # last_recalled was set

    def test_apply_recall_reheat_boosts_importance(self, temp_db: Path) -> None:
        """apply_recall_reheat boosts importance by 0.3 (capped at 5.0)."""
        from hermesoptimizer.dreams.memory_meta import (
            apply_recall_reheat,
            init_db,
            upsert,
        )

        init_db(temp_db)
        upsert(temp_db, supermemory_id="entry-1", content_hash="hash1", importance=2.0)

        apply_recall_reheat(temp_db, "entry-1")

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT importance FROM memory_meta WHERE supermemory_id=?",
            ("entry-1",),
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == 2.3

    def test_apply_recall_reheat_caps_importance_at_five(self, temp_db: Path) -> None:
        """apply_recall_reheat caps importance at 5.0."""
        from hermesoptimizer.dreams.memory_meta import (
            apply_recall_reheat,
            init_db,
            upsert,
        )

        init_db(temp_db)
        upsert(temp_db, supermemory_id="entry-1", content_hash="hash1", importance=4.9)

        apply_recall_reheat(temp_db, "entry-1")

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT importance FROM memory_meta WHERE supermemory_id=?",
            ("entry-1",),
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == 5.0

    def test_apply_recall_reheat_accumulates_recall_count(self, temp_db: Path) -> None:
        """Multiple apply_recall_reheat calls on same ID accumulate count."""
        from hermesoptimizer.dreams.memory_meta import (
            apply_recall_reheat,
            init_db,
            upsert,
        )

        init_db(temp_db)
        upsert(temp_db, supermemory_id="entry-1", content_hash="hash1")

        apply_recall_reheat(temp_db, "entry-1")
        apply_recall_reheat(temp_db, "entry-1")
        apply_recall_reheat(temp_db, "entry-1")

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT recall_count FROM memory_meta WHERE supermemory_id=?",
            ("entry-1",),
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == 3

    def test_apply_recall_reheat_raises_for_unknown_id(self, temp_db: Path) -> None:
        """apply_recall_reheat raises KeyError for unknown supermemory_id."""
        from hermesoptimizer.dreams.memory_meta import apply_recall_reheat, init_db

        init_db(temp_db)

        with pytest.raises(KeyError, match="nonexistent"):
            apply_recall_reheat(temp_db, "nonexistent")


# ------------------------------------------------------------------------------------------------------------------------------------------
# Tests for pre-sweep integration
# ------------------------------------------------------------------------------------------------------------------------------------------


class TestPreSweepIntegration:
    """Test that pre-sweep script integrates recall reheating correctly."""

    def test_pre_sweep_version_is_phase3_when_reheat_enabled(
        self, temp_db: Path, tmp_path: Path
    ) -> None:
        """When --reheat is enabled, output version should be 0.7.0-phase3 not phase2."""
        import subprocess
        import sys

        from hermesoptimizer.dreams.memory_meta import init_db, upsert

        init_db(temp_db)
        upsert(temp_db, supermemory_id="entry-1", content_hash="hash1", importance=1.0)

        # Run pre-sweep with --reheat flag
        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).parent.parent / "scripts" / "dreaming_pre_sweep.py"),
                "--db-path", str(temp_db),
                "--reheat",
                "--recall-ids", "entry-1",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)

        # Phase 3 reheating should report version 0.7.0-phase3
        assert output["version"] == "0.7.0-phase3", (
            f"Expected version '0.7.0-phase3' when --reheat is used, got '{output.get('version')}'"
        )

    def test_reheat_from_transcripts_applies_to_db(self, temp_db: Path) -> None:
        """Reheating via transcript parsing updates the DB."""
        from hermesoptimizer.dreams.memory_meta import init_db, query_by_score, upsert
        from hermesoptimizer.dreams.recall import reheat_recalled_ids

        init_db(temp_db)
        # Bootstrap entries
        upsert(temp_db, supermemory_id="ID-ABC123", content_hash="hash1", importance=1.0)
        upsert(temp_db, supermemory_id="ID-DEF456", content_hash="hash2", importance=1.0)

        # Simulate recalled IDs from transcripts
        recalled_ids = ["ID-ABC123", "ID-DEF456"]
        stats = reheat_recalled_ids(temp_db, recalled_ids)

        assert stats["reheated"] == 2
        assert stats["skipped"] == 0

        # Verify recall_count was incremented
        results = query_by_score(temp_db, threshold=0.0)
        for r in results:
            assert r["recall_count"] == 1

    def test_reheat_skips_unknown_ids(self, temp_db: Path) -> None:
        """IDs not in DB are skipped without error."""
        from hermesoptimizer.dreams.memory_meta import init_db, upsert
        from hermesoptimizer.dreams.recall import reheat_recalled_ids

        init_db(temp_db)
        upsert(temp_db, supermemory_id="known-id", content_hash="hash1")

        stats = reheat_recalled_ids(temp_db, ["known-id", "unknown-id"])

        assert stats["reheated"] == 1
        assert stats["skipped"] == 1

    def test_pre_sweep_output_includes_reheat_stats(
        self, temp_db: Path, tmp_path: Path
    ) -> None:
        """Pre-sweep JSON output includes reheated/skipped counts when reheating is enabled."""
        import subprocess
        import sys

        from hermesoptimizer.dreams.memory_meta import init_db, upsert

        init_db(temp_db)
        upsert(temp_db, supermemory_id="entry-1", content_hash="hash1", importance=1.0)

        # Create a temp sessions dir for the pre-sweep to scan
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Run pre-sweep with --reheat flag and --db-path
        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).parent.parent / "scripts" / "dreaming_pre_sweep.py"),
                "--db-path", str(temp_db),
                "--reheat",
                "--recall-ids", "entry-1",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)

        assert "reheat_stats" in output
        assert output["reheat_stats"]["reheated"] == 1
        assert output["reheat_stats"]["skipped"] == 0

"""Phase 3 recall reheating: transcript parsing, recall_log fallback, and DB reheating.

This module provides:
- Transcript parsing: extracts supermemory_search calls and result IDs from session files
- recall_log.jsonl: append-only fallback log for recall events
- Reheating helpers: apply recall signals to the sidecar DB

All functions accept explicit paths so tests can use temp fixtures.
In production, paths default to ~/.hermes/{sessions,dreams/recall_log.jsonl}.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------

DEFAULT_SESSIONS_DIR = Path.home() / ".hermes" / "sessions"
DEFAULT_RECALL_LOG = Path.home() / ".hermes" / "dreams" / "recall_log.jsonl"


# ---------------------------------------------------------------------------
# Transcript parsing
# ---------------------------------------------------------------------------

# Marker for cleared tool responses
_CLEARED_RESPONSE_MARKER = "[Old tool output cleared to save context space]"


def parse_session_transcript(session: dict[str, Any]) -> dict[str, Any] | None:
    """Parse a session transcript dict and extract supermemory_search recall signals.

    Extracts the query and result IDs from the first supermemory_search tool call
    and its corresponding tool response. If the tool response is missing, cleared,
    empty, or malformed, returns None (parser refuses to guess).

    When the tool call has an explicit `id` field, the tool response is matched
    by `tool_call_id` rather than assuming the immediate next message is the response.
    This handles transcripts where intervening messages exist between a tool call
    and its response.

    Args:
        session: A session dict with 'session_id' and 'messages' keys,
            as produced by Hermes session exports.

    Returns:
        A dict with 'query' (str) and 'result_ids' (list[str]), or None if
        no valid supermemory_search response was found.
    """
    messages = session.get("messages", [])
    search_call = None
    search_call_id: str | None = None
    search_call_index: int = -1

    # Find the supermemory_search tool call
    for i, msg in enumerate(messages):
        if msg.get("role") != "assistant":
            continue
        tool_calls = msg.get("tool_calls", [])
        for tc in tool_calls:
            fn = tc.get("function", {})
            if fn.get("name") == "supermemory_search":
                search_call = fn
                # Capture the tool call id if present (used for matching response)
                search_call_id = tc.get("id") or tc.get("call_id")
                search_call_index = i
                break
        if search_call is not None:
            break

    if search_call is None:
        return None

    # Look for the tool response
    if search_call_id is not None:
        # Match by tool_call_id: search through messages for matching response
        for msg in messages:
            if msg.get("role") == "tool" and msg.get("tool_call_id") == search_call_id:
                search_response = msg.get("content", "")
                break
    elif search_call_index >= 0:
        # Fallback: assume the tool response is the immediate next message
        # (only valid when there's no call_id to match)
        if search_call_index + 1 < len(messages):
            next_msg = messages[search_call_index + 1]
            if next_msg.get("role") == "tool":
                search_response = next_msg.get("content", "")

    if search_response is None:
        return None

    # Check for cleared response
    if search_response == _CLEARED_RESPONSE_MARKER:
        return None

    # Try to parse the JSON response
    try:
        response_data = json.loads(search_response)
    except (json.JSONDecodeError, TypeError):
        return None

    # Extract result IDs
    results = response_data.get("results", [])
    if not results:
        return None

    ids = []
    for r in results:
        rid = r.get("id")
        if rid:
            ids.append(rid)

    if not ids:
        return None

    # Extract query from tool call arguments
    query = ""
    try:
        args = json.loads(search_call.get("arguments", "{}"))
        query = args.get("query", "")
    except (json.JSONDecodeError, TypeError):
        pass

    return {
        "query": query,
        "result_ids": ids,
    }


def scan_sessions_directory(sessions_dir: Path) -> list[str]:
    """Scan a directory of session transcript JSON files and return all recalled IDs.

    Reads all .json files in the directory, parses each with parse_session_transcript,
    and collects all unique result IDs.

    Args:
        sessions_dir: Path to ~/.hermes/sessions/ or a test fixture directory.

    Returns:
        List of unique supermemory IDs that were recalled across all sessions.
        Duplicates are removed - each ID appears at most once.
    """
    seen_ids: set[str] = set()
    all_ids: list[str] = []

    if not sessions_dir.exists():
        return all_ids

    for file_path in sessions_dir.iterdir():
        if not file_path.is_file() or file_path.suffix != ".json":
            continue
        try:
            session = json.loads(file_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        parsed = parse_session_transcript(session)
        if parsed is not None:
            for rid in parsed["result_ids"]:
                if rid not in seen_ids:
                    seen_ids.add(rid)
                    all_ids.append(rid)

    return all_ids


# ---------------------------------------------------------------------------
# recall_log.jsonl reader/writer
# ---------------------------------------------------------------------------

def read_recall_log(log_path: Path) -> list[dict[str, Any]]:
    """Read entries from a recall_log.jsonl file.

    Each line is a JSON object with: ts, query, hit_count, ids.

    Args:
        log_path: Path to the recall_log.jsonl file.

    Returns:
        List of entry dicts. Returns empty list if file does not exist.
    """
    if not log_path.exists():
        return []

    entries: list[dict[str, Any]] = []
    try:
        text = log_path.read_text()
    except OSError:
        return []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    return entries


def read_recall_log_ids(log_path: Path) -> list[str]:
    """Read all IDs from a recall_log.jsonl file.

    Collects all IDs from all entries in the log file.

    Args:
        log_path: Path to the recall_log.jsonl file.

    Returns:
        List of all supermemory IDs found in the log.
    """
    entries = read_recall_log(log_path)
    ids: list[str] = []
    for entry in entries:
        ids.extend(entry.get("ids", []))
    return ids


def append_recall_log_entry(
    log_path: Path,
    query: str,
    hit_count: int,
    ids: list[str],
    ts: str | None = None,
) -> None:
    """Append a recall event to the append-only recall_log.jsonl.

    Args:
        log_path: Path to the recall_log.jsonl file. Created if it doesn't exist.
        query: The search query that produced this recall.
        hit_count: Number of results returned.
        ids: List of supermemory entry IDs that were recalled.
        ts: ISO-8601 timestamp string. Defaults to current UTC time.
    """
    if ts is None:
        ts = datetime.now(timezone.utc).isoformat()

    entry = {
        "ts": ts,
        "query": query,
        "hit_count": hit_count,
        "ids": ids,
    }

    log_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# Importance reheating helpers
# ---------------------------------------------------------------------------

REHEAT_BOOST = 0.3
REHEAT_CAP = 5.0


def compute_reheated_importance(
    current_importance: float,
    boost: float = REHEAT_BOOST,
    cap: float = REHEAT_CAP,
) -> float:
    """Compute a reheated importance value with capping.

    Args:
        current_importance: The entry's current importance value.
        boost: The amount to boost by. Default REHEAT_BOOST = 0.3.
        cap: Maximum allowed importance. Default REHEAT_CAP = 5.0.

    Returns:
        The boosted importance, capped at `cap`.
    """
    return min(current_importance + boost, cap)


# ---------------------------------------------------------------------------
# DB reheating (delegated to memory_meta.apply_recall_reheat)
# ---------------------------------------------------------------------------

def reheat_recalled_ids(
    db_path: Path,
    recalled_ids: list[str],
    boost: float = REHEAT_BOOST,
) -> dict[str, int]:
    """Apply recall reheating to multiple IDs in the sidecar DB.

    For each ID in recalled_ids that exists in the DB:
    - Increment recall_count
    - Set last_recalled to now
    - Boost importance by `boost` (capped at REHEAT_CAP)

    IDs not found in the DB are silently skipped.

    Args:
        db_path: Path to the memory_meta.db sidecar database.
        recalled_ids: List of supermemory IDs to reheat.
        boost: Importance boost amount per recall (default 0.3).

    Returns:
        Dict with 'reheated' (int, count of IDs found and updated) and
        'skipped' (int, count of IDs not found in DB).
    """
    from .memory_meta import apply_recall_reheat

    reheated = 0
    skipped = 0

    for sid in recalled_ids:
        try:
            apply_recall_reheat(db_path, sid, boost=boost)
            reheated += 1
        except KeyError:
            skipped += 1

    return {"reheated": reheated, "skipped": skipped}

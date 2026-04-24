from __future__ import annotations

from collections import Counter

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "brain" / "scripts" / "request_dump_digest.py"
spec = importlib.util.spec_from_file_location("request_dump_digest", SCRIPT)
assert spec and spec.loader
request_dump_digest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(request_dump_digest)


def test_request_dump_failures_become_provider_health_inputs() -> None:
    buckets = Counter(
        {
            ("https://openrouter.ai/api/v1/chat/completions", "inclusionai/ling-2.6-flash:free", "HTTP 429 quota"): 3,
            ("https://openrouter.ai/api/v1/chat/completions", "inclusionai/ling-2.6-flash:free", "ok"): 1,
        }
    )
    rows = request_dump_digest.build_provider_health_inputs(buckets)
    assert rows[0]["provider"] == "openrouter"
    assert rows[0]["failure_count"] == 3
    assert rows[0]["success_count"] == 1
    assert rows[0]["quarantine_candidate"] is True

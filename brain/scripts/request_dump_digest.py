#!/usr/bin/env python3
"""Summarize Hermes request dumps into a compact JSON report.

Default source: ~/.hermes/sessions/request_dump_*.json

Examples:
  python3 request_dump_digest.py --limit 50
  python3 request_dump_digest.py --source ~/.hermes/sessions --output ../reports/request-dump-summary.json
"""

from __future__ import annotations

import argparse
import glob
import json
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse
from typing import Any


def load_dump(path: str) -> dict[str, Any] | None:
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return None


def _provider_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "openrouter" in host:
        return "openrouter"
    if "kilocode" in host:
        return "kilocode"
    if "nousresearch" in host:
        return "nous"
    if "openai" in host:
        return "openai-codex"
    if "kimi" in host or "moonshot" in host:
        return "kimi"
    if "minimax" in host:
        return "minimax"
    return host or "unknown"


def _is_failure_reason(reason: str) -> bool:
    lowered = reason.lower()
    return any(token in lowered for token in ("fail", "error", "timeout", "retry", "retries", "429", "401", "403", "404", "quota", "auth", "blocked"))


def build_provider_health_inputs(url_model_reason: Counter[tuple[str, str, str]]) -> list[dict[str, Any]]:
    """Convert request-dump failure buckets into provider health/quarantine input."""
    health: dict[tuple[str, str], dict[str, Any]] = {}
    for (url, model, reason), count in url_model_reason.items():
        provider = _provider_from_url(url)
        key = (provider, model or "unknown")
        row = health.setdefault(
            key,
            {
                "provider": provider,
                "model": model or "unknown",
                "failure_count": 0,
                "success_count": 0,
                "reasons": [],
                "quarantine_candidate": False,
            },
        )
        if _is_failure_reason(reason):
            row["failure_count"] += count
            row["reasons"].append({"reason": reason, "count": count, "url": url})
        else:
            row["success_count"] += count
    for row in health.values():
        row["quarantine_candidate"] = row["failure_count"] >= 3
    return sorted(health.values(), key=lambda item: (-item["failure_count"], item["provider"], item["model"]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=str(Path.home() / ".hermes" / "sessions"))
    parser.add_argument("--glob", default="request_dump_*.json")
    parser.add_argument("--limit", type=int, default=0, help="0 means all")
    parser.add_argument("--output")
    args = parser.parse_args()

    pattern = str(Path(args.source) / args.glob)
    paths = sorted(glob.glob(pattern))
    if args.limit:
        paths = paths[-args.limit :]

    reasons = Counter()
    urls = Counter()
    models = Counter()
    url_model_reason = Counter()
    sessions_by_reason: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)

    for path in paths:
        dump = load_dump(path)
        if not dump:
            continue
        reason = dump.get("reason", "unknown")
        request = dump.get("request", {})
        body = request.get("body", {}) if isinstance(request.get("body", {}), dict) else {}
        url = request.get("url", "")
        model = body.get("model", "")
        session_id = dump.get("session_id", "")
        timestamp = dump.get("timestamp", "")

        reasons[reason] += 1
        urls[url] += 1
        models[model] += 1
        url_model_reason[(url, model, reason)] += 1
        if len(sessions_by_reason[reason]) < 10:
            sessions_by_reason[reason].append(
                {
                    "session_id": session_id,
                    "timestamp": timestamp,
                    "url": url,
                    "model": model,
                    "path": path,
                }
            )

    report = {
        "source": args.source,
        "files_analyzed": len(paths),
        "reasons": reasons.most_common(),
        "top_urls": urls.most_common(20),
        "top_models": models.most_common(20),
        "top_url_model_reason": [
            {"url": u, "model": m, "reason": r, "count": c}
            for (u, m, r), c in url_model_reason.most_common(20)
        ],
        "provider_health_inputs": build_provider_health_inputs(url_model_reason),
        "sample_sessions_by_reason": sessions_by_reason,
    }

    text = json.dumps(report, indent=2, default=lambda x: dict(x))
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

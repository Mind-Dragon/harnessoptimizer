"""Analyze sessions for AI API performance metrics."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hermesoptimizer.perf.models import ProviderPerf, ProviderOutage


class PerfAnalyzer:
    """Analyze provider performance from session files."""

    def __init__(self, session_paths: list[Path]) -> None:
        self.session_paths = session_paths
        self.perf_data: dict[str, dict[str, Any]] = {}
        self.outages: list[ProviderOutage] = []

    def analyze(self) -> None:
        """Parse all sessions and aggregate performance data."""
        for path in self.session_paths:
            self._parse_session(path)
        self._detect_outages()

    def _parse_session(self, path: Path) -> None:
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return

        provider = data.get("provider", "unknown")
        model = data.get("model", "unknown")
        status = data.get("status", "completed")
        duration_ms = data.get("duration_ms", 0)
        retries = data.get("retries", 0)
        messages = data.get("messages", [])

        key = f"{provider}:{model}"
        if key not in self.perf_data:
            self.perf_data[key] = {
                "provider": provider,
                "model": model,
                "total_requests": 0,
                "success_count": 0,
                "error_count": 0,
                "retry_count": 0,
                "total_duration_ms": 0,
                "total_tokens_in": 0,
                "total_tokens_out": 0,
                "durations": [],
                "errors": [],
            }

        pd = self.perf_data[key]
        pd["total_requests"] += 1
        pd["retry_count"] += retries

        if status in ("completed", "success"):
            pd["success_count"] += 1
        else:
            pd["error_count"] += 1
            error_msg = data.get("error", "Unknown error")
            pd["errors"].append(error_msg)

        if duration_ms > 0:
            pd["total_duration_ms"] += duration_ms
            pd["durations"].append(duration_ms)

        # Estimate tokens from messages
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                tokens = max(1, len(content) // 4)
            else:
                tokens = max(1, len(str(content)) // 4)
            if msg.get("role") in ("user", "system", "tool"):
                pd["total_tokens_in"] += tokens
            else:
                pd["total_tokens_out"] += tokens

    def _detect_outages(self) -> None:
        """Detect provider outages from consecutive failures."""
        # Group sessions by provider:model and sort by time
        sessions_by_key: dict[str, list[dict]] = {}
        for path in self.session_paths:
            try:
                data = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            key = f"{data.get('provider', 'unknown')}:{data.get('model', 'unknown')}"
            if key not in sessions_by_key:
                sessions_by_key[key] = []
            sessions_by_key[key].append(data)

        for key, sessions in sessions_by_key.items():
            sessions.sort(key=lambda s: s.get("created_at", ""))
            provider, model = key.split(":", 1)

            consecutive_failures = 0
            outage_start: str | None = None
            for s in sessions:
                if s.get("status") not in ("completed", "success"):
                    consecutive_failures += 1
                    if outage_start is None:
                        outage_start = s.get("created_at", "")
                else:
                    if consecutive_failures >= 3:
                        self.outages.append(
                            ProviderOutage(
                                provider=provider,
                                model=model,
                                start_time=outage_start or "",
                                end_time=s.get("created_at", ""),
                                error_reason="Consecutive failures",
                                affected_sessions=consecutive_failures,
                            )
                        )
                    consecutive_failures = 0
                    outage_start = None

    def get_provider_perf(self) -> list[ProviderPerf]:
        """Generate ProviderPerf objects from analyzed data."""
        results: list[ProviderPerf] = []
        for pd in self.perf_data.values():
            total = pd["total_requests"]
            if total == 0:
                continue
            avg_duration = pd["total_duration_ms"] / total if pd["total_duration_ms"] > 0 else 0
            total_tokens = pd["total_tokens_in"] + pd["total_tokens_out"]
            tps = (total_tokens / (pd["total_duration_ms"] / 1000)) if pd["total_duration_ms"] > 0 else 0
            results.append(
                ProviderPerf(
                    provider=pd["provider"],
                    model=pd["model"],
                    total_requests=total,
                    success_count=pd["success_count"],
                    error_count=pd["error_count"],
                    retry_count=pd["retry_count"],
                    total_duration_ms=pd["total_duration_ms"],
                    total_tokens_in=pd["total_tokens_in"],
                    total_tokens_out=pd["total_tokens_out"],
                    avg_response_ms=avg_duration,
                    tokens_per_second=tps,
                    error_rate=pd["error_count"] / total,
                    retry_rate=pd["retry_count"] / total,
                )
            )
        return results

    def get_outages(self) -> list[ProviderOutage]:
        return self.outages

    def get_failure_reasons(self) -> dict[str, list[str]]:
        """Get unique failure reasons per provider:model."""
        reasons: dict[str, list[str]] = {}
        for pd in self.perf_data.values():
            key = f"{pd['provider']}:{pd['model']}"
            if pd["errors"]:
                reasons[key] = list(set(pd["errors"]))
        return reasons

"""CLI commands for AI API performance monitoring."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hermesoptimizer.perf.analyzer import PerfAnalyzer
from hermesoptimizer.perf.reporter import PerfReporter


def _find_sessions(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return list(path.rglob("*.json"))


def handle_perf_report(args: argparse.Namespace) -> int:
    paths = _find_sessions(Path(args.path))
    if not paths:
        print("No session files found.", file=sys.stderr)
        return 1

    analyzer = PerfAnalyzer(paths)
    analyzer.analyze()
    reporter = PerfReporter(analyzer)
    print(reporter.generate_report())

    if args.json_out:
        perf = analyzer.get_provider_perf()
        outages = analyzer.get_outages()
        report = {
            "providers": [
                {
                    "provider": p.provider,
                    "model": p.model,
                    "total_requests": p.total_requests,
                    "success_count": p.success_count,
                    "error_count": p.error_count,
                    "retry_count": p.retry_count,
                    "avg_response_ms": p.avg_response_ms,
                    "tokens_per_second": p.tokens_per_second,
                    "error_rate": p.error_rate,
                    "retry_rate": p.retry_rate,
                }
                for p in perf
            ],
            "outages": [
                {
                    "provider": o.provider,
                    "model": o.model,
                    "start_time": o.start_time,
                    "end_time": o.end_time,
                    "error_reason": o.error_reason,
                    "affected_sessions": o.affected_sessions,
                }
                for o in outages
            ],
            "failure_reasons": analyzer.get_failure_reasons(),
        }
        Path(args.json_out).write_text(json.dumps(report, indent=2))
        print(f"\nJSON report written to {args.json_out}")

    return 0


def handle_perf_check(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 1

    analyzer = PerfAnalyzer([path])
    analyzer.analyze()
    perf = analyzer.get_provider_perf()

    if not perf:
        print("No performance data found.")
        return 0

    p = perf[0]
    print(f"Provider: {p.provider}")
    print(f"Model: {p.model}")
    print(f"Requests: {p.total_requests}")
    print(f"Success: {p.success_count}")
    print(f"Errors: {p.error_count} ({p.error_rate:.1%})")
    print(f"Retries: {p.retry_count} ({p.retry_rate:.1%})")
    print(f"Avg response: {p.avg_response_ms:.0f}ms")
    print(f"Tokens/sec: {p.tokens_per_second:.1f}")
    return 0

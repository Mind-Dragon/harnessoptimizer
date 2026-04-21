"""CLI commands for tool usage analysis and optimization."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hermesoptimizer.tools.analyzer import ToolAnalyzer
from hermesoptimizer.tools.optimizer import ToolOptimizer


def _find_sessions(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return list(path.rglob("*.json"))


def handle_tool_report(args: argparse.Namespace) -> int:
    paths = _find_sessions(Path(args.path))
    if not paths:
        print("No session files found.", file=sys.stderr)
        return 1

    analyzer = ToolAnalyzer(paths)
    analyzer.analyze()
    optimizer = ToolOptimizer(analyzer)
    recs = optimizer.generate_recommendations()

    print("=" * 60)
    print("TOOL USAGE REPORT")
    print("=" * 60)
    print(f"Sessions analyzed: {len(paths)}")
    print(f"Total tool calls: {sum(u.call_count for u in analyzer.usages)}")
    print(f"Total misses: {len(analyzer.misses)}")
    print(f"Miss rate: {analyzer.miss_rate():.2f} per session")
    print()

    print("By Tool:")
    for tool, data in analyzer.by_tool().items():
        print(f"  {tool:20s}  calls={data['calls']:>4}  success={data['success']:>4}  fail={data['failure']:>4}")
    print()

    print("By Provider:")
    for provider, data in analyzer.by_provider().items():
        print(f"  {provider:15s}  calls={data['calls']:>4}  tools={data['tools']:>2}  sessions={data['sessions']}")
    print()

    print("By Model:")
    for model, data in analyzer.by_model().items():
        print(f"  {model:20s}  calls={data['calls']:>4}  tools={data['tools']:>2}  sessions={data['sessions']}")
    print()

    print("By Lane:")
    for lane, data in analyzer.by_lane().items():
        print(f"  {lane:15s}  calls={data['calls']:>4}  tools={data['tools']:>2}  sessions={data['sessions']}")
    print()

    print("Misses by Type:")
    for miss_type, total in analyzer.misses_by_type().items():
        print(f"  {miss_type:25s}  {total}")
    print()

    print("Recommendations:")
    for r in recs:
        print(f"  [{r.target_type}] {r.target_id}")
        print(f"    {r.recommendation}")
        print(f"    Expected: {r.expected_improvement} (confidence: {r.confidence:.0%})")
    print()

    if args.json_out:
        report = {
            "sessions": len(paths),
            "total_calls": sum(u.call_count for u in analyzer.usages),
            "total_misses": len(analyzer.misses),
            "miss_rate": analyzer.miss_rate(),
            "by_tool": analyzer.by_tool(),
            "by_provider": analyzer.by_provider(),
            "by_model": analyzer.by_model(),
            "by_lane": analyzer.by_lane(),
            "misses_by_type": analyzer.misses_by_type(),
            "recommendations": [
                {
                    "target_type": r.target_type,
                    "target_id": r.target_id,
                    "recommendation": r.recommendation,
                    "expected_improvement": r.expected_improvement,
                    "confidence": r.confidence,
                }
                for r in recs
            ],
        }
        Path(args.json_out).write_text(json.dumps(report, indent=2))
        print(f"JSON report written to {args.json_out}")

    return 0


def handle_tool_check(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 1

    analyzer = ToolAnalyzer([path])
    analyzer.analyze()

    print(f"Session: {path.name}")
    print(f"  Tool calls: {sum(u.call_count for u in analyzer.usages)}")
    print(f"  Misses: {len(analyzer.misses)}")
    for m in analyzer.misses:
        print(f"    [{m.severity}] {m.miss_type}: {m.description}")
        if m.suggested_tool:
            print(f"      Suggested tool: {m.suggested_tool}")
    return 0

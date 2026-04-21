"""CLI commands for token usage analysis and optimization."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hermesoptimizer.tokens.analyzer import TokenAnalyzer
from hermesoptimizer.tokens.optimizer import TokenOptimizer


def _find_sessions(path: Path) -> list[Path]:
    """Find session JSON files recursively."""
    if path.is_file():
        return [path]
    return list(path.rglob("*.json"))


def handle_token_report(args: argparse.Namespace) -> int:
    paths = _find_sessions(Path(args.path))
    if not paths:
        print("No session files found.", file=sys.stderr)
        return 1

    analyzer = TokenAnalyzer(paths)
    analyzer.analyze()
    optimizer = TokenOptimizer(analyzer)
    recs = optimizer.generate_recommendations()

    print("=" * 60)
    print("TOKEN USAGE REPORT")
    print("=" * 60)
    print(f"Sessions analyzed: {len(paths)}")
    print(f"Total token records: {len(analyzer.usages)}")
    print(f"Total waste detected: {analyzer.total_waste()} tokens")
    print()

    print("By Provider:")
    for provider, data in analyzer.by_provider().items():
        print(f"  {provider:20s}  in={data['tokens_in']:,}  out={data['tokens_out']:,}  sessions={data['sessions']}")
    print()

    print("By Model:")
    for model, data in analyzer.by_model().items():
        print(f"  {model:20s}  in={data['tokens_in']:,}  out={data['tokens_out']:,}  sessions={data['sessions']}")
    print()

    print("By Lane:")
    for lane, data in analyzer.by_lane().items():
        print(f"  {lane:20s}  in={data['tokens_in']:,}  out={data['tokens_out']:,}  sessions={data['sessions']}")
    print()

    print("Waste by Type:")
    for waste_type, total in analyzer.waste_by_type().items():
        print(f"  {waste_type:20s}  {total:,} tokens")
    print()

    print("Recommendations:")
    for r in recs:
        print(f"  [{r.target_type}] {r.target_id}")
        print(f"    {r.recommendation}")
        print(f"    Estimated savings: {r.estimated_savings:,} tokens (confidence: {r.confidence:.0%})")
    print()

    if args.json_out:
        report = {
            "sessions": len(paths),
            "total_usages": len(analyzer.usages),
            "total_waste": analyzer.total_waste(),
            "by_provider": analyzer.by_provider(),
            "by_model": analyzer.by_model(),
            "by_lane": analyzer.by_lane(),
            "waste_by_type": analyzer.waste_by_type(),
            "recommendations": [
                {
                    "target_type": r.target_type,
                    "target_id": r.target_id,
                    "recommendation": r.recommendation,
                    "estimated_savings": r.estimated_savings,
                    "confidence": r.confidence,
                }
                for r in recs
            ],
        }
        Path(args.json_out).write_text(json.dumps(report, indent=2))
        print(f"JSON report written to {args.json_out}")

    return 0


def handle_token_check(args: argparse.Namespace) -> int:
    """Quick check: show token stats for a single session."""
    path = Path(args.path)
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 1

    analyzer = TokenAnalyzer([path])
    analyzer.analyze()

    if not analyzer.usages:
        print("No token data found in session.")
        return 0

    total_in = sum(u.tokens_in for u in analyzer.usages)
    total_out = sum(u.tokens_out for u in analyzer.usages)
    print(f"Session: {path.name}")
    print(f"  Input tokens:  {total_in:,}")
    print(f"  Output tokens: {total_out:,}")
    print(f"  Waste detected: {analyzer.total_waste():,} tokens")
    for w in analyzer.wastes:
        print(f"    [{w.severity}] {w.waste_type}: {w.description}")
    return 0

"""Orphan CLI handlers wiring tool_surface, verify, and dreams into the CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable

from hermesoptimizer.sources.provider_truth import ProviderTruthStore, load_provider_truth, seed_from_config
from hermesoptimizer.tool_surface.commands import (
    CommandResult,
    _handle_dreams_inspect,
    _handle_provider_list,
    _handle_report_latest,
    _handle_workflow_list,
)


def _wrap_handler(fn: Callable[[], CommandResult]) -> Callable[[argparse.Namespace], int]:
    """Wrap a CommandResult-returning handler into an int-returning CLI handler."""

    def wrapper(_args: argparse.Namespace) -> int:
        result = fn()
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.exit_code

    return wrapper


HANDLERS: dict[str, Callable[[argparse.Namespace], int]] = {}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_config_path() -> Path:
    return Path.home() / ".hermes" / "config.yaml"


def _load_truth_store(args: argparse.Namespace) -> ProviderTruthStore:
    truth_path = getattr(args, "truth_path", None)
    config_path = getattr(args, "config_path", None)

    if truth_path:
        return load_provider_truth(truth_path)

    candidate = Path(config_path).expanduser() if config_path else _default_config_path()
    if candidate.exists():
        return seed_from_config(candidate)

    return ProviderTruthStore()


def _dump_json_if_requested(payload: dict, json_out: str | None) -> None:
    if not json_out:
        return
    out_path = Path(json_out).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _build_recommender():
    from hermesoptimizer.schemas.provider_endpoint import ProviderEndpointCatalog
    from hermesoptimizer.schemas.provider_model import ProviderModelCatalog
    from hermesoptimizer.tool_surface.provider_recommend import ProviderRecommender

    repo_root = _repo_root()
    endpoint_catalog = ProviderEndpointCatalog.from_file(repo_root / "data" / "provider_endpoints.json")
    model_catalog = ProviderModelCatalog.from_file(repo_root / "data" / "provider_models.json")
    truth_store = seed_from_config(_default_config_path()) if _default_config_path().exists() else ProviderTruthStore()
    return ProviderRecommender(
        truth_store=truth_store,
        endpoint_catalog=endpoint_catalog,
        model_catalog=model_catalog,
    )


def _format_recommendations(output, limit: int) -> str:
    recs = output.recommendations[:limit]
    if not recs:
        return "No provider recommendations matched the requested filters."

    lines = [
        f"Recommendations: {len(recs)} shown / {output.total_candidates} candidates considered",
        f"Validation passed: {output.validation_passed}",
        "",
    ]
    for idx, rec in enumerate(recs, start=1):
        lines.extend(
            [
                f"{idx}. provider={rec.provider} model={rec.model or '-'} lane={rec.lane.value} score={rec.rank_score:.2f}",
                f"   endpoint: {rec.endpoint}",
                f"   reason: {rec.reason}",
                f"   provenance: {rec.provenance}",
            ]
        )
        if rec.config_snippet:
            lines.append("   config:")
            for snippet_line in rec.config_snippet.splitlines():
                lines.append(f"     {snippet_line}")
    return "\n".join(lines)


def handle_verify_endpoints(args: argparse.Namespace) -> int:
    try:
        from hermesoptimizer.verify.endpoints import verify_endpoint, verify_endpoint_with_live

        truth_store = _load_truth_store(args)
        if args.live:
            result = verify_endpoint_with_live(
                args.provider,
                args.endpoint,
                args.model,
                truth_store,
                use_live_truth=True,
            )
        else:
            result = verify_endpoint(args.provider, args.endpoint, args.model, truth_store)

        payload = {
            "provider": result.provider,
            "model": result.model,
            "configured_endpoint": result.configured_endpoint,
            "status": result.status.value,
            "message": result.message,
            "details": result.details,
        }
        _dump_json_if_requested(payload, args.json_out)

        print(f"status: {result.status.value}")
        print(f"provider: {result.provider}")
        if result.model:
            print(f"model: {result.model}")
        print(f"endpoint: {result.configured_endpoint}")
        print(f"message: {result.message}")
        if result.details:
            print("details:")
            for key, value in sorted(result.details.items()):
                print(f"  {key}: {value}")
        return 0
    except Exception as exc:
        print(f"verify-endpoints failed: {exc}", file=sys.stderr)
        return 1


def handle_dreams_sweep(args: argparse.Namespace) -> int:
    try:
        from hermesoptimizer.dreams.memory_meta import init_db as init_dreams_db
        from hermesoptimizer.dreams.memory_meta import query_by_score, set_fidelity
        from hermesoptimizer.dreams.sweep import run_sweep

        db_path = Path(args.db).expanduser() if args.db else None
        init_dreams_db(db_path)
        effective_db = db_path or Path.home() / ".hermes" / "dreams" / "memory_meta.db"
        entries = query_by_score(effective_db, threshold=0.0)
        result = run_sweep(entries, injected_memory_pct=args.injected_memory_pct)

        if args.apply:
            for decision in result["decisions"]:
                if decision["action"] in {"demote", "prune"}:
                    set_fidelity(effective_db, decision["supermemory_id"], decision["tier"])

        _dump_json_if_requested(result, args.json_out)

        summary = result["summary"]
        print(f"dreams db: {effective_db}")
        print(
            "summary: "
            f"total={summary['total']} kept={summary['kept']} demoted={summary['demoted']} pruned={summary['pruned']}"
        )
        print(f"injected_memory_pct: {summary['injected_memory_pct']}")
        print(f"applied: {args.apply}")
        return 0
    except Exception as exc:
        print(f"dreams-sweep failed: {exc}", file=sys.stderr)
        return 1


def handle_provider_recommend(args: argparse.Namespace) -> int:
    try:
        from hermesoptimizer.tool_surface.provider_recommend import ProviderRecommendInput, SafetyLane

        recommender = _build_recommender()
        desired_lane = SafetyLane(args.lane)
        inp = ProviderRecommendInput(
            desired_capabilities=list(args.capability or []),
            desired_lane=desired_lane,
            region_preference=args.region,
            auth_presence={},
        )
        output = recommender.recommend(inp)
        payload = {
            "total_candidates": output.total_candidates,
            "validation_passed": output.validation_passed,
            "recommendations": [
                {
                    "provider": rec.provider,
                    "model": rec.model,
                    "endpoint": rec.endpoint,
                    "rank_score": rec.rank_score,
                    "reason": rec.reason,
                    "lane": rec.lane.value,
                    "config_snippet": rec.config_snippet,
                    "provenance": rec.provenance,
                }
                for rec in output.recommendations[: args.limit]
            ],
        }
        _dump_json_if_requested(payload, args.json_out)
        print(_format_recommendations(output, args.limit))
        return 0
    except Exception as exc:
        print(f"provider-recommend failed: {exc}", file=sys.stderr)
        return 1


def add_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Register orphan subcommands under the given subparsers action."""
    p_list = subparsers.add_parser("provider-list", help="List available providers")
    p_list.set_defaults(handler=_wrap_handler(_handle_provider_list))
    HANDLERS["provider-list"] = _wrap_handler(_handle_provider_list)

    p_rec = subparsers.add_parser("provider-recommend", help="Rank provider/model recommendations")
    p_rec.add_argument("--capability", action="append", default=[], help="Required capability (repeatable)")
    p_rec.add_argument("--lane", choices=["coding", "reasoning", "general"], default="general")
    p_rec.add_argument("--region", help="Preferred region")
    p_rec.add_argument("--limit", type=int, default=5, help="Maximum recommendations to print")
    p_rec.add_argument("--json-out", help="Optional JSON output path")
    p_rec.set_defaults(handler=handle_provider_recommend)
    HANDLERS["provider-recommend"] = handle_provider_recommend

    w_list = subparsers.add_parser("workflow-list", help="List workflow plans and runs")
    w_list.set_defaults(handler=_wrap_handler(_handle_workflow_list))
    HANDLERS["workflow-list"] = _wrap_handler(_handle_workflow_list)

    d_inspect = subparsers.add_parser("dreams-inspect", help="Inspect memory/dream state")
    d_inspect.set_defaults(handler=_wrap_handler(_handle_dreams_inspect))
    HANDLERS["dreams-inspect"] = _wrap_handler(_handle_dreams_inspect)

    r_latest = subparsers.add_parser("report-latest", help="Get the latest report")
    r_latest.set_defaults(handler=_wrap_handler(_handle_report_latest))
    HANDLERS["report-latest"] = _wrap_handler(_handle_report_latest)

    v_endpoints = subparsers.add_parser("verify-endpoints", help="Verify a provider endpoint/model against truth data")
    v_endpoints.add_argument("--provider", required=True, help="Provider name")
    v_endpoints.add_argument("--endpoint", required=True, help="Configured endpoint/base URL")
    v_endpoints.add_argument("--model", help="Configured model name")
    v_endpoints.add_argument("--live", action="store_true", help="Probe the endpoint with live-truth checks")
    v_endpoints.add_argument("--config-path", help="Config.yaml path used to seed truth store")
    v_endpoints.add_argument("--truth-path", help="Provider-truth YAML path")
    v_endpoints.add_argument("--json-out", help="Optional JSON output path")
    v_endpoints.set_defaults(handler=handle_verify_endpoints)
    HANDLERS["verify-endpoints"] = handle_verify_endpoints

    d_sweep = subparsers.add_parser("dreams-sweep", help="Run a read-only dreams memory sweep summary")
    d_sweep.add_argument("--db", help="Override dreams memory_meta.db path")
    d_sweep.add_argument("--injected-memory-pct", type=float, default=0.0, help="Current injected memory fill percentage")
    d_sweep.add_argument("--apply", action="store_true", help="Apply demote/prune tiers back to the sidecar DB")
    d_sweep.add_argument("--json-out", help="Optional JSON output path")
    d_sweep.set_defaults(handler=handle_dreams_sweep)
    HANDLERS["dreams-sweep"] = handle_dreams_sweep

    from hermesoptimizer.extensions.commands import handle_ext_list
    e_list = subparsers.add_parser("ext-list", help="List registered extensions")
    e_list.set_defaults(handler=handle_ext_list)
    HANDLERS["ext-list"] = handle_ext_list

    from hermesoptimizer.extensions.doctor import run_doctor

    def handle_ext_doctor(args: argparse.Namespace) -> int:
        try:
            report = run_doctor(dry_run=args.dry_run)
            print(f"extensions checked: {report['extensions_checked']}")
            print(f"healthy: {report['healthy']}")
            print(f"missing_source: {report['missing_source']}")
            print(f"external: {report['external']}")
            if report["issues"]:
                print("issues:")
                for issue in report["issues"]:
                    print(f"  - {issue['id']}: {issue['issue']} ({issue['source_path']})")
            return 0
        except Exception as exc:
            print(f"ext-doctor failed: {exc}", file=sys.stderr)
            return 1

    e_doctor = subparsers.add_parser("ext-doctor", help="Run extension health check")
    e_doctor.add_argument("--dry-run", action="store_true", help="Validate without writing checkpoint")
    e_doctor.set_defaults(handler=handle_ext_doctor)
    HANDLERS["ext-doctor"] = handle_ext_doctor

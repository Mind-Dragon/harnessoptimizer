from __future__ import annotations

from hermesoptimizer.cli import build_parser


def _choices(parser) -> set[str]:
    for action in parser._actions:  # type: ignore[attr-defined]
        if getattr(action, "choices", None):
            return set(action.choices.keys())
    return set()


def test_unified_parser_contains_closeout_commands() -> None:
    parser = build_parser()
    commands = _choices(parser)

    expected = {
        "run",
        "verify-endpoints",
        "dreams-sweep",
        "provider-recommend",
        "report-latest",
        "db-vacuum",
        "db-retention",
        "db-stats",
    }

    missing = expected - commands
    assert not missing, f"missing commands: {sorted(missing)}"


def test_verify_endpoints_parser_accepts_real_arguments() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "verify-endpoints",
            "--provider",
            "openai",
            "--endpoint",
            "https://api.openai.com/v1",
            "--model",
            "gpt-5",
        ]
    )

    assert args.command == "verify-endpoints"
    assert args.provider == "openai"
    assert args.endpoint == "https://api.openai.com/v1"
    assert args.model == "gpt-5"


def test_dreams_sweep_parser_accepts_summary_arguments() -> None:
    parser = build_parser()
    args = parser.parse_args(["dreams-sweep", "--json-out", "summary.json"])

    assert args.command == "dreams-sweep"
    assert args.json_out == "summary.json"


def test_provider_recommend_parser_accepts_capability_and_lane() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "provider-recommend",
            "--capability",
            "text",
            "--capability",
            "reasoning",
            "--lane",
            "coding",
            "--limit",
            "3",
        ]
    )

    assert args.command == "provider-recommend"
    assert args.capability == ["text", "reasoning"]
    assert args.lane == "coding"
    assert args.limit == 3

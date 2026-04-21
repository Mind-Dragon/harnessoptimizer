"""Backward-compatible shim – re-exports the public CLI API from cli.legacy / cli."""
from __future__ import annotations

from hermesoptimizer.cli import build_parser as _build_parser, dispatch as _dispatch
from hermesoptimizer.cli.legacy import (
    _comparison_from_history,
    _delta_metrics,
    _finding_from_args,
    _inspected_inputs_from_rows,
    _record_from_args,
    _report_metrics,
)

__all__ = [
    "build_parser",
    "main",
    "_comparison_from_history",
    "_delta_metrics",
    "_finding_from_args",
    "_inspected_inputs_from_rows",
    "_record_from_args",
    "_report_metrics",
]


def build_parser() -> "argparse.ArgumentParser":
    """Backward-compatible parser builder (delegates to hermesoptimizer.cli)."""
    return _build_parser()


def main(argv=None) -> int:
    """Backward-compatible main entry point (delegates to hermesoptimizer.cli.dispatch)."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    return _dispatch(args)

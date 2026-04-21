"""Orphan CLI handlers wiring tool_surface and verify into the CLI."""

from __future__ import annotations

import argparse
import sys
from typing import Callable

from hermesoptimizer.tool_surface.commands import (
    CommandResult,
    _handle_dreams_inspect,
    _handle_provider_list,
    _handle_provider_recommend,
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


def _stub_handler(message: str) -> Callable[[argparse.Namespace], int]:
    """Create a stub handler that prints a message and returns 0."""

    def wrapper(_args: argparse.Namespace) -> int:
        print(message)
        return 0

    return wrapper


#: Handlers registered by add_subparsers.
HANDLERS: dict[str, Callable[[argparse.Namespace], int]] = {}


def add_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Register orphan subcommands under the given subparsers action."""
    # provider-list
    p_list = subparsers.add_parser("provider-list", help="List available providers")
    p_list.set_defaults(handler=_wrap_handler(_handle_provider_list))
    HANDLERS["provider-list"] = _wrap_handler(_handle_provider_list)

    # provider-recommend
    p_rec = subparsers.add_parser(
        "provider-recommend", help="Placeholder for provider recommender"
    )
    p_rec.set_defaults(handler=_wrap_handler(_handle_provider_recommend))
    HANDLERS["provider-recommend"] = _wrap_handler(_handle_provider_recommend)

    # workflow-list
    w_list = subparsers.add_parser("workflow-list", help="List workflow plans and runs")
    w_list.set_defaults(handler=_wrap_handler(_handle_workflow_list))
    HANDLERS["workflow-list"] = _wrap_handler(_handle_workflow_list)

    # dreams-inspect
    d_inspect = subparsers.add_parser("dreams-inspect", help="Inspect memory/dream state")
    d_inspect.set_defaults(handler=_wrap_handler(_handle_dreams_inspect))
    HANDLERS["dreams-inspect"] = _wrap_handler(_handle_dreams_inspect)

    # report-latest
    r_latest = subparsers.add_parser("report-latest", help="Get the latest report")
    r_latest.set_defaults(handler=_wrap_handler(_handle_report_latest))
    HANDLERS["report-latest"] = _wrap_handler(_handle_report_latest)

    # verify-endpoints (stub)
    v_endpoints = subparsers.add_parser(
        "verify-endpoints", help="Verify endpoint configurations"
    )
    v_endpoints.set_defaults(
        handler=_stub_handler("verify-endpoints: not yet implemented")
    )
    HANDLERS["verify-endpoints"] = _stub_handler("verify-endpoints: not yet implemented")

    # dreams-sweep (stub)
    d_sweep = subparsers.add_parser("dreams-sweep", help="Run dreams memory sweep")
    d_sweep.set_defaults(handler=_stub_handler("dreams-sweep: not yet implemented"))
    HANDLERS["dreams-sweep"] = _stub_handler("dreams-sweep: not yet implemented")

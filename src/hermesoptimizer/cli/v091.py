"""CLI handlers for hermesoptimizer v0.9.1 commands.

This module exposes:
- add_subparsers(subparsers) -> None: registers all v0.9.1 subcommands
- HANDLERS: dict mapping command name -> handler function
"""
from __future__ import annotations

import argparse
from typing import Callable

from hermesoptimizer.paths import get_db_path


# Token usage analysis commands
def _add_token_report_subparser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("token-report", help="Generate token usage report")
    parser.add_argument("path", help="Path to session file or directory")
    parser.add_argument("--json-out", help="Write JSON report to file")
    return parser


def _add_token_check_subparser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("token-check", help="Check token usage for a session")
    parser.add_argument("path", help="Path to session file")
    return parser


# Performance monitoring commands
def _add_perf_report_subparser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("perf-report", help="Generate performance report")
    parser.add_argument("path", help="Path to session file or directory")
    parser.add_argument("--json-out", help="Write JSON report to file")
    return parser


def _add_perf_check_subparser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("perf-check", help="Check performance for a session")
    parser.add_argument("path", help="Path to session file")
    return parser


# Tool usage analysis commands
def _add_tool_report_subparser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("tool-report", help="Generate tool usage report")
    parser.add_argument("path", help="Path to session file or directory")
    parser.add_argument("--json-out", help="Write JSON report to file")
    return parser


def _add_tool_check_subparser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("tool-check", help="Check tool usage for a session")
    parser.add_argument("path", help="Path to session file")
    return parser


# Network resource discipline commands
def _add_port_reserve_subparser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("port-reserve", help="Reserve a port number")
    parser.add_argument("port", type=int, help="Port number to reserve")
    parser.add_argument("--purpose", default="", help="Description of what this port is for")
    parser.add_argument("--db", default=str(get_db_path()), help="Path to catalog database")
    return parser


def _add_port_list_subparser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("port-list", help="List port reservations")
    parser.add_argument("--status", choices=["reserved", "available", "forbidden"], help="Filter by status")
    parser.add_argument("--db", default=str(get_db_path()), help="Path to catalog database")
    return parser


def _add_port_release_subparser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("port-release", help="Release a reserved port")
    parser.add_argument("port", type=int, help="Port number to release")
    parser.add_argument("--db", default=str(get_db_path()), help="Path to catalog database")
    return parser


def _add_ip_list_subparser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("ip-list", help="List registered IP addresses")
    parser.add_argument("--type", choices=["local_v4", "vpn", "public", "custom"], help="Filter by type")
    parser.add_argument("--db", default=str(get_db_path()), help="Path to catalog database")
    return parser


def _add_ip_add_subparser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("ip-add", help="Register an IP address")
    parser.add_argument("ip", help="IP address to register")
    parser.add_argument("--type", default="custom", choices=["local_v4", "vpn", "public", "custom"], help="IP type")
    parser.add_argument("--purpose", default="", help="Description")
    parser.add_argument("--db", default=str(get_db_path()), help="Path to catalog database")
    return parser


def _add_network_scan_subparser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("network-scan", help="Auto-detect and register local IPs")
    parser.add_argument("--db", default=str(get_db_path()), help="Path to catalog database")
    return parser


# -----------------------------------------------------------------------
# Handler implementations
# -----------------------------------------------------------------------

def _handle_token_report(args: argparse.Namespace) -> int:
    from hermesoptimizer.tokens.commands import handle_token_report
    return handle_token_report(args)


def _handle_token_check(args: argparse.Namespace) -> int:
    from hermesoptimizer.tokens.commands import handle_token_check
    return handle_token_check(args)


def _handle_perf_report(args: argparse.Namespace) -> int:
    from hermesoptimizer.perf.commands import handle_perf_report
    return handle_perf_report(args)


def _handle_perf_check(args: argparse.Namespace) -> int:
    from hermesoptimizer.perf.commands import handle_perf_check
    return handle_perf_check(args)


def _handle_tool_report(args: argparse.Namespace) -> int:
    from hermesoptimizer.tools.commands import handle_tool_report
    return handle_tool_report(args)


def _handle_tool_check(args: argparse.Namespace) -> int:
    from hermesoptimizer.tools.commands import handle_tool_check
    return handle_tool_check(args)


def _handle_port_reserve(args: argparse.Namespace) -> int:
    from hermesoptimizer.network.commands import handle_port_reserve
    return handle_port_reserve(args)


def _handle_port_list(args: argparse.Namespace) -> int:
    from hermesoptimizer.network.commands import handle_port_list
    return handle_port_list(args)


def _handle_port_release(args: argparse.Namespace) -> int:
    from hermesoptimizer.network.commands import handle_port_release
    return handle_port_release(args)


def _handle_ip_list(args: argparse.Namespace) -> int:
    from hermesoptimizer.network.commands import handle_ip_list
    return handle_ip_list(args)


def _handle_ip_add(args: argparse.Namespace) -> int:
    from hermesoptimizer.network.commands import handle_ip_add
    return handle_ip_add(args)


def _handle_network_scan(args: argparse.Namespace) -> int:
    from hermesoptimizer.network.commands import handle_network_scan
    return handle_network_scan(args)


# -----------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------

HANDLERS: dict[str, Callable[[argparse.Namespace], int]] = {
    "token-report": _handle_token_report,
    "token-check": _handle_token_check,
    "perf-report": _handle_perf_report,
    "perf-check": _handle_perf_check,
    "tool-report": _handle_tool_report,
    "tool-check": _handle_tool_check,
    "port-reserve": _handle_port_reserve,
    "port-list": _handle_port_list,
    "port-release": _handle_port_release,
    "ip-list": _handle_ip_list,
    "ip-add": _handle_ip_add,
    "network-scan": _handle_network_scan,
}


def add_subparsers(subparsers) -> None:
    """Register all v0.9.1 subcommand parsers with the given subparsers object."""
    _add_token_report_subparser(subparsers)
    _add_token_check_subparser(subparsers)
    _add_perf_report_subparser(subparsers)
    _add_perf_check_subparser(subparsers)
    _add_tool_report_subparser(subparsers)
    _add_tool_check_subparser(subparsers)
    _add_port_reserve_subparser(subparsers)
    _add_port_list_subparser(subparsers)
    _add_port_release_subparser(subparsers)
    _add_ip_list_subparser(subparsers)
    _add_ip_add_subparser(subparsers)
    _add_network_scan_subparser(subparsers)

"""CLI commands for network resource discipline."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hermesoptimizer.catalog import init_db
from hermesoptimizer.network.inventory import (
    reserve_port,
    release_port,
    list_ports,
    add_ip,
    list_ips,
    ensure_forbidden_ports,
)
from hermesoptimizer.network.scanner import scan_local_ips, get_primary_ip
from hermesoptimizer.paths import get_db_path


_DEFAULT_DB = get_db_path()


def _db_path(args: argparse.Namespace) -> Path:
    return Path(getattr(args, "db", str(_DEFAULT_DB)))


def handle_port_reserve(args: argparse.Namespace) -> int:
    db = _db_path(args)
    init_db(db)
    try:
        r = reserve_port(db, args.port, purpose=args.purpose, added_by="user")
        print(f"Reserved port {r.port} ({r.status})")
        if r.purpose:
            print(f"  Purpose: {r.purpose}")
        return 0
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def handle_port_list(args: argparse.Namespace) -> int:
    db = _db_path(args)
    init_db(db)
    ensure_forbidden_ports(db)
    ports = list_ports(db, status=args.status)
    if not ports:
        print("No ports found.")
        return 0
    print(f"{'Port':>8}  {'Status':>10}  {'Purpose':20}  {'Added By'}")
    print("-" * 60)
    for p in ports:
        purpose = (p.purpose or "")[:20]
        print(f"{p.port:>8}  {p.status:>10}  {purpose:20}  {p.added_by}")
    return 0


def handle_port_release(args: argparse.Namespace) -> int:
    db = _db_path(args)
    init_db(db)
    try:
        release_port(db, args.port)
        print(f"Released port {args.port}")
        return 0
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def handle_ip_list(args: argparse.Namespace) -> int:
    db = _db_path(args)
    init_db(db)
    ips = list_ips(db, ip_type=args.type)
    if not ips:
        print("No IPs registered.")
        return 0
    print(f"{'IP':>18}  {'Type':>10}  {'Purpose'}")
    print("-" * 50)
    for ip in ips:
        purpose = ip.purpose or ""
        print(f"{ip.ip:>18}  {ip.ip_type:>10}  {purpose}")
    return 0


def handle_ip_add(args: argparse.Namespace) -> int:
    db = _db_path(args)
    init_db(db)
    ip = add_ip(db, args.ip, ip_type=args.type, purpose=args.purpose, added_by="user")
    print(f"Added IP {ip.ip} ({ip.ip_type})")
    return 0


def handle_network_scan(args: argparse.Namespace) -> int:
    db = _db_path(args)
    init_db(db)
    detected = scan_local_ips()
    primary = get_primary_ip()
    print("Detected local IPv4 addresses:")
    for ip in detected:
        marker = "  <-- primary" if ip.ip == primary else ""
        print(f"  {ip.ip}{marker}")
    if primary and not any(ip.ip == primary for ip in detected):
        print(f"  {primary}  <-- primary (via routing)")
    # Auto-register into inventory
    for ip in detected:
        add_ip(db, ip.ip, ip_type="local_v4", purpose=ip.purpose, added_by="auto")
    print(f"Registered {len(detected)} IP(s) in inventory.")
    return 0


# ---------------------------------------------------------------------------
# Subparser registration
# ---------------------------------------------------------------------------

def add_port_reserve_subparser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("port-reserve", help="Reserve a port number")
    parser.add_argument("port", type=int, help="Port number to reserve")
    parser.add_argument("--purpose", default="", help="Description of what this port is for")
    parser.add_argument("--db", default=str(get_db_path()), help="Path to catalog database")
    return parser


def add_port_list_subparser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("port-list", help="List port reservations")
    parser.add_argument("--status", choices=["reserved", "available", "forbidden"], help="Filter by status")
    parser.add_argument("--db", default=str(get_db_path()), help="Path to catalog database")
    return parser


def add_port_release_subparser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("port-release", help="Release a reserved port")
    parser.add_argument("port", type=int, help="Port number to release")
    parser.add_argument("--db", default=str(get_db_path()), help="Path to catalog database")
    return parser


def add_ip_list_subparser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("ip-list", help="List registered IP addresses")
    parser.add_argument("--type", choices=["local_v4", "vpn", "public", "custom"], help="Filter by type")
    parser.add_argument("--db", default=str(get_db_path()), help="Path to catalog database")
    return parser


def add_ip_add_subparser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("ip-add", help="Register an IP address")
    parser.add_argument("ip", help="IP address to register")
    parser.add_argument("--type", default="custom", choices=["local_v4", "vpn", "public", "custom"], help="IP type")
    parser.add_argument("--purpose", default="", help="Description")
    parser.add_argument("--db", default=str(get_db_path()), help="Path to catalog database")
    return parser


def add_network_scan_subparser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("network-scan", help="Auto-detect and register local IPs")
    parser.add_argument("--db", default=str(get_db_path()), help="Path to catalog database")
    return parser

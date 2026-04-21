"""SQLite-backed port and IP registry using the catalog connection."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Literal

from hermesoptimizer.catalog import (
    connect,
    get_network_inventory,
    upsert_network_inventory,
    delete_network_inventory,
)
from hermesoptimizer.network.models import PortReservation, IPAssignment


# Ports that are forever forbidden
_FORBIDDEN_PORTS: set[int] = {3000, 8080}


def init_network_db(conn: sqlite3.Connection) -> None:
    """Ensure the network_inventory table exists (called by catalog.init_db)."""
    # The table is already in catalog.SCHEMA; this is a no-op hook for future migrations.
    pass


def _seed_forbidden_ports(db_path: str | Path) -> None:
    """Ensure forbidden ports are present in the inventory."""
    for port in _FORBIDDEN_PORTS:
        upsert_network_inventory(
            db_path,
            resource_type="port",
            value=str(port),
            status="forbidden",
            purpose="Permanently forbidden — conflicts with common defaults",
            added_by="system",
        )


def ensure_forbidden_ports(db_path: str | Path) -> None:
    """Idempotent seed of forbidden ports. Called on first use."""
    existing = get_network_inventory(db_path, resource_type="port", status="forbidden")
    existing_values = {r["value"] for r in existing}
    for port in _FORBIDDEN_PORTS:
        if str(port) not in existing_values:
            forbid_port(db_path, port)


def reserve_port(
    db_path: str | Path,
    port: int,
    purpose: str | None = None,
    added_by: str = "user",
) -> PortReservation:
    """Reserve a port number. Raises ValueError if port is forbidden."""
    if port in _FORBIDDEN_PORTS:
        raise ValueError(f"Port {port} is permanently forbidden")
    if not (3000 <= port <= 65530):
        raise ValueError(f"Port {port} out of allowed range (3000-65530)")
    upsert_network_inventory(
        db_path,
        resource_type="port",
        value=str(port),
        status="reserved",
        purpose=purpose,
        added_by=added_by,
    )
    return PortReservation(port=port, status="reserved", purpose=purpose, added_by=added_by)


def forbid_port(db_path: str | Path, port: int) -> PortReservation:
    """Forbid a port number permanently."""
    upsert_network_inventory(
        db_path,
        resource_type="port",
        value=str(port),
        status="forbidden",
        purpose="Permanently forbidden",
        added_by="system",
    )
    return PortReservation(port=port, status="forbidden", purpose="Permanently forbidden", added_by="system")


def release_port(db_path: str | Path, port: int) -> None:
    """Release a reserved port back to available. Cannot release forbidden ports."""
    if port in _FORBIDDEN_PORTS:
        raise ValueError(f"Port {port} is permanently forbidden and cannot be released")
    delete_network_inventory(db_path, resource_type="port", value=str(port))


def list_ports(
    db_path: str | Path,
    status: Literal["reserved", "available", "forbidden"] | None = None,
) -> list[PortReservation]:
    """List port reservations."""
    ensure_forbidden_ports(db_path)
    rows = get_network_inventory(db_path, resource_type="port", status=status)
    result: list[PortReservation] = []
    for row in rows:
        try:
            p = int(row["value"])
        except ValueError:
            continue
        result.append(
            PortReservation(
                port=p,
                status=row["status"],
                purpose=row.get("purpose"),
                added_by=row.get("added_by", "auto"),
            )
        )
    return sorted(result, key=lambda r: r.port)


def is_port_allowed(db_path: str | Path, port: int) -> bool:
    """Return True if the port is not reserved or forbidden."""
    ensure_forbidden_ports(db_path)
    rows = get_network_inventory(db_path, resource_type="port")
    for row in rows:
        if row["value"] == str(port) and row["status"] in ("reserved", "forbidden"):
            return False
    return True


def add_ip(
    db_path: str | Path,
    ip: str,
    ip_type: Literal["local_v4", "vpn", "public", "custom"] = "custom",
    purpose: str | None = None,
    added_by: str = "user",
) -> IPAssignment:
    """Register an IP address in the inventory."""
    upsert_network_inventory(
        db_path,
        resource_type="ip",
        value=ip,
        status="reserved",
        purpose=purpose or f"{ip_type} address",
        added_by=added_by,
    )
    return IPAssignment(ip=ip, ip_type=ip_type, purpose=purpose, added_by=added_by)


def list_ips(
    db_path: str | Path,
    ip_type: Literal["local_v4", "vpn", "public", "custom"] | None = None,
) -> list[IPAssignment]:
    """List registered IP addresses."""
    rows = get_network_inventory(db_path, resource_type="ip")
    result: list[IPAssignment] = []
    for row in rows:
        result.append(
            IPAssignment(
                ip=row["value"],
                ip_type=_guess_ip_type(row.get("purpose", "")),
                purpose=row.get("purpose"),
                added_by=row.get("added_by", "auto"),
            )
        )
    if ip_type:
        result = [r for r in result if r.ip_type == ip_type]
    return result


def _guess_ip_type(purpose: str) -> Literal["local_v4", "vpn", "public", "custom"]:
    p = purpose.lower()
    if "vpn" in p:
        return "vpn"
    if "public" in p:
        return "public"
    if "local" in p:
        return "local_v4"
    return "custom"


def is_localhost(ip: str) -> bool:
    """Return True if the IP is a loopback address."""
    ip = ip.strip().lower()
    if ip in ("localhost", "127.0.0.1", "::1"):
        return True
    if ip.startswith("127."):
        return True
    return False

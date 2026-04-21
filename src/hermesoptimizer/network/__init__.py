from __future__ import annotations

"""Network resource discipline — port and IP inventory, validation, enforcement."""

from hermesoptimizer.network.models import PortReservation, IPAssignment
from hermesoptimizer.network.inventory import (
    init_network_db,
    reserve_port,
    forbid_port,
    release_port,
    list_ports,
    is_port_allowed,
    add_ip,
    list_ips,
    is_localhost,
)
from hermesoptimizer.network.scanner import scan_local_ips, get_primary_ip
from hermesoptimizer.network.validator import validate_config_ports, validate_config_ips
from hermesoptimizer.network.enforcer import enforce_network_policy

__all__ = [
    "PortReservation",
    "IPAssignment",
    "init_network_db",
    "reserve_port",
    "forbid_port",
    "release_port",
    "list_ports",
    "is_port_allowed",
    "add_ip",
    "list_ips",
    "is_localhost",
    "scan_local_ips",
    "get_primary_ip",
    "validate_config_ports",
    "validate_config_ips",
    "enforce_network_policy",
]

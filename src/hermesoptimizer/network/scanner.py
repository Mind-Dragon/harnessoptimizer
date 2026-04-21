"""Auto-detect local IPv4 addresses excluding loopback."""
from __future__ import annotations

import socket
from typing import List

from hermesoptimizer.network.models import IPAssignment


def scan_local_ips() -> list[IPAssignment]:
    """Scan all local IPv4 addresses excluding loopback.

    Returns:
        List of IPAssignment for each non-loopback IPv4 interface.
    """
    assignments: list[IPAssignment] = []
    try:
        hostname = socket.gethostname()
        addr_info = socket.getaddrinfo(hostname, None, socket.AF_INET)
    except socket.gaierror:
        addr_info = []

    seen: set[str] = set()
    for info in addr_info:
        ip = info[4][0]
        if ip.startswith("127.") or ip == "0.0.0.0":
            continue
        if ip in seen:
            continue
        seen.add(ip)
        assignments.append(
            IPAssignment(
                ip=ip,
                ip_type="local_v4",
                interface=info[4][0],
                purpose=f"Auto-detected local IPv4 from {hostname}",
                added_by="auto",
            )
        )

    return assignments


def get_primary_ip() -> str | None:
    """Return the primary non-loopback IPv4 address.

    Uses a UDP socket trick to discover the routing IP without
    actually sending any data.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(2)
            s.connect(("8.8.8.8", 53))
            ip = s.getsockname()[0]
            if ip and not ip.startswith("127."):
                return ip
    except OSError:
        pass

    # Fallback: scan local IPs and return first
    ips = scan_local_ips()
    if ips:
        return ips[0].ip
    return None

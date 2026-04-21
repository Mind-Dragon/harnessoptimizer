"""Data models for network resource discipline."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(slots=True)
class PortReservation:
    port: int
    status: Literal["reserved", "available", "forbidden"]
    purpose: str | None = None
    added_by: str = "auto"


@dataclass(slots=True)
class IPAssignment:
    ip: str
    ip_type: Literal["local_v4", "vpn", "public", "custom"]
    interface: str | None = None
    purpose: str | None = None
    added_by: str = "auto"

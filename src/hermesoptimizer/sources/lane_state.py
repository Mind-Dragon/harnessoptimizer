"""Generic lane-state policy for provider/model canaries.

States:
  green          — healthy, may be used for required release work
  fallback_only  — available for opportunistic fallback, not required work
  quota_blocked  — temporarily blocked by quota/rate-limit, not required work
  quarantined    — explicitly quarantined, excluded from normal provider lists
  unknown        — status not known, not eligible for required work

Legacy aliases:
  active   -> green
  inactive -> unknown
"""
from __future__ import annotations

from enum import Enum


class LaneState(Enum):
    GREEN = "green"
    FALLBACK_ONLY = "fallback_only"
    QUOTA_BLOCKED = "quota_blocked"
    QUARANTINED = "quarantined"
    UNKNOWN = "unknown"

    @classmethod
    def from_string(cls, value: str | None) -> "LaneState":
        if value is None:
            return cls.UNKNOWN
        normalized = str(value).strip().lower()
        # Legacy aliases
        if normalized == "active":
            return cls.GREEN
        if normalized == "inactive":
            return cls.UNKNOWN
        # Direct enum value match
        try:
            return cls(normalized)
        except ValueError:
            return cls.UNKNOWN

    def is_green(self) -> bool:
        return self is LaneState.GREEN

    def eligible_for_required_release(self) -> bool:
        return self is LaneState.GREEN

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"LaneState.{self.name}"

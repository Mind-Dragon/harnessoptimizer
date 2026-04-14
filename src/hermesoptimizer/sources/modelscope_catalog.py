from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CatalogEntry:
    provider: str
    model: str
    base_url: str
    auth_type: str


def load_catalog() -> list[CatalogEntry]:
    return []

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RouteDecision:
    label: str
    confidence: str
    note: str = ""


def route_text(text: str) -> RouteDecision:
    lowered = text.lower()
    if any(token in lowered for token in ("error", "timeout", "auth")):
        return RouteDecision(label="failure", confidence="medium", note="keyword match")
    return RouteDecision(label="informational", confidence="low", note="default route")

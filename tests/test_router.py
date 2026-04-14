from __future__ import annotations

from hermesoptimizer.route.router import route_text


def test_route_text_failure() -> None:
    decision = route_text("provider timeout error")
    assert decision.label == "failure"


def test_route_text_informational() -> None:
    decision = route_text("plain text")
    assert decision.label == "informational"

"""Data models for token usage tracking and optimization."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(slots=True)
class TokenUsage:
    session_id: str
    provider: str
    model: str
    lane: str
    role: str
    tokens_in: int
    tokens_out: int
    timestamp: str


@dataclass(slots=True)
class TokenWaste:
    session_id: str
    waste_type: str
    description: str
    tokens_wasted: int
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


@dataclass(slots=True)
class TokenRecommendation:
    target_type: str
    target_id: str
    recommendation: str
    estimated_savings: int
    confidence: float

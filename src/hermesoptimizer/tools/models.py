"""Data models for tool usage tracking and optimization."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(slots=True)
class ToolUsage:
    session_id: str
    provider: str
    model: str
    lane: str
    tool_name: str
    call_count: int
    success_count: int
    failure_count: int


@dataclass(slots=True)
class ToolMiss:
    session_id: str
    miss_type: str
    description: str
    suggested_tool: str
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


@dataclass(slots=True)
class ToolRecommendation:
    target_type: str
    target_id: str
    recommendation: str
    expected_improvement: str
    confidence: float

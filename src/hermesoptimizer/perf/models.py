"""Data models for AI API performance monitoring."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(slots=True)
class ProviderPerf:
    provider: str
    model: str
    total_requests: int
    success_count: int
    error_count: int
    retry_count: int
    total_duration_ms: int
    total_tokens_in: int
    total_tokens_out: int
    avg_response_ms: float
    tokens_per_second: float
    error_rate: float
    retry_rate: float


@dataclass(slots=True)
class ProviderOutage:
    provider: str
    model: str
    start_time: str
    end_time: str | None
    error_reason: str
    affected_sessions: int

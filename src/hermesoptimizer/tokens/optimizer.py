"""Generate token optimization recommendations based on analyzed data."""
from __future__ import annotations

from typing import Any

from hermesoptimizer.tokens.models import TokenRecommendation
from hermesoptimizer.tokens.analyzer import TokenAnalyzer


# Rough cost ratios relative to gpt-4o-mini (cheapest)
MODEL_COST_RATIOS: dict[str, float] = {
    "gpt-4o-mini": 1.0,
    "gpt-4o": 10.0,
    "gpt-4": 20.0,
    "claude-sonnet-4": 8.0,
    "claude-opus-4": 25.0,
    "claude-sonnet-4": 8.0,
    "gemini-1.5-flash": 1.5,
    "gemini-1.5-pro": 10.0,
    "qwen-max": 5.0,
    "qwen-coder": 2.0,
    "deepseek-chat": 1.0,
    "deepseek-coder": 1.0,
    "kimi-k2": 3.0,
    "unknown": 5.0,
}


class TokenOptimizer:
    """Generate token optimization recommendations."""

    def __init__(self, analyzer: TokenAnalyzer) -> None:
        self.analyzer = analyzer

    def generate_recommendations(self) -> list[TokenRecommendation]:
        """Generate all recommendations based on analyzed data."""
        recs: list[TokenRecommendation] = []
        recs.extend(self._model_efficiency_recs())
        recs.extend(self._prompt_compression_recs())
        recs.extend(self._lane_optimization_recs())
        recs.extend(self._retry_mitigation_recs())
        return recs

    def _model_efficiency_recs(self) -> list[TokenRecommendation]:
        """Recommend cheaper models for lanes with low complexity output."""
        recs: list[TokenRecommendation] = []
        by_model = self.analyzer.by_model()

        for model, data in by_model.items():
            ratio = data["tokens_out"] / max(data["tokens_in"], 1)
            # If output is tiny relative to input, might be over-modelled
            if ratio < 0.1 and data["tokens_in"] > 10000:
                cheaper = self._find_cheaper_model(model)
                if cheaper:
                    recs.append(
                        TokenRecommendation(
                            target_type="model",
                            target_id=model,
                            recommendation=f"Consider downgrading from {model} to {cheaper} for low-output lanes",
                            estimated_savings=int(data["tokens_out"] * 0.5),
                            confidence=0.7,
                        )
                    )
        return recs

    def _prompt_compression_recs(self) -> list[TokenRecommendation]:
        """Recommend prompt compression for high-input sessions."""
        recs: list[TokenRecommendation] = []
        by_lane = self.analyzer.by_lane()

        for lane, data in by_lane.items():
            if data["tokens_in"] > 8000:
                recs.append(
                    TokenRecommendation(
                        target_type="lane",
                        target_id=lane,
                        recommendation="Implement prompt compression or truncation for this lane",
                        estimated_savings=int(data["tokens_in"] * 0.2),
                        confidence=0.8,
                    )
                )
        return recs

    def _lane_optimization_recs(self) -> list[TokenRecommendation]:
        """Recommend lane-specific optimizations."""
        recs: list[TokenRecommendation] = []
        by_lane = self.analyzer.by_lane()

        for lane, data in by_lane.items():
            sessions = data.get("sessions", 0)
            avg_in = data["tokens_in"] // max(sessions, 1)
            if avg_in > 5000:
                recs.append(
                    TokenRecommendation(
                        target_type="lane",
                        target_id=lane,
                        recommendation=f"Lane '{lane}' averages {avg_in} input tokens per session. Consider batching or chunking.",
                        estimated_savings=int(data["tokens_in"] * 0.15),
                        confidence=0.75,
                    )
                )
        return recs

    def _retry_mitigation_recs(self) -> list[TokenRecommendation]:
        """Recommend reducing retries."""
        recs: list[TokenRecommendation] = []
        waste_by_type = self.analyzer.waste_by_type()

        if "retries" in waste_by_type:
            recs.append(
                TokenRecommendation(
                    target_type="system",
                    target_id="retries",
                    recommendation="Implement circuit breaker or fallback provider to reduce retry waste",
                    estimated_savings=waste_by_type["retries"],
                    confidence=0.85,
                )
            )

        if "tool_loop" in waste_by_type:
            recs.append(
                TokenRecommendation(
                    target_type="system",
                    target_id="tool_loops",
                    recommendation="Add tool call limits per turn to prevent excessive tooling",
                    estimated_savings=waste_by_type["tool_loop"],
                    confidence=0.8,
                )
            )

        return recs

    def _find_cheaper_model(self, current: str) -> str | None:
        """Find a cheaper alternative model."""
        current_cost = MODEL_COST_RATIOS.get(current, 5.0)
        best: str | None = None
        best_cost = current_cost
        for model, cost in MODEL_COST_RATIOS.items():
            if cost < best_cost and model != current:
                best = model
                best_cost = cost
        return best

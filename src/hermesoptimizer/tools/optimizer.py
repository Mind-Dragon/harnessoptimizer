"""Generate tool usage optimization recommendations."""
from __future__ import annotations

from hermesoptimizer.tools.models import ToolRecommendation
from hermesoptimizer.tools.analyzer import ToolAnalyzer


class ToolOptimizer:
    """Generate tool usage optimization recommendations."""

    def __init__(self, analyzer: ToolAnalyzer) -> None:
        self.analyzer = analyzer

    def generate_recommendations(self) -> list[ToolRecommendation]:
        """Generate all recommendations based on analyzed data."""
        recs: list[ToolRecommendation] = []
        recs.extend(self._tool_avoidance_recs())
        recs.extend(self._manual_workaround_recs())
        recs.extend(self._repeated_failure_recs())
        recs.extend(self._provider_tool_recs())
        recs.extend(self._lane_tool_recs())
        return recs

    def _tool_avoidance_recs(self) -> list[ToolRecommendation]:
        """Recommend tool usage for providers/models that avoid tools."""
        recs: list[ToolRecommendation] = []
        misses_by_type = self.analyzer.misses_by_type()

        if "tool_avoidance" in misses_by_type:
            recs.append(
                ToolRecommendation(
                    target_type="system",
                    target_id="tool_usage",
                    recommendation="Add explicit tool-use instructions to system prompts for all lanes",
                    expected_improvement="Reduce manual workarounds by 50%+",
                    confidence=0.8,
                )
            )
        return recs

    def _manual_workaround_recs(self) -> list[ToolRecommendation]:
        """Recommend specific tools for common manual workaround patterns."""
        recs: list[ToolRecommendation] = []
        for miss in self.analyzer.misses:
            if miss.miss_type.endswith("_manual"):
                recs.append(
                    ToolRecommendation(
                        target_type="tool",
                        target_id=miss.suggested_tool,
                        recommendation=f"When AI tries to {miss.miss_type.replace('_manual', '')} manually, force use of {miss.suggested_tool}",
                        expected_improvement="Eliminate manual workarounds for this task type",
                        confidence=0.85,
                    )
                )
        return recs

    def _repeated_failure_recs(self) -> list[ToolRecommendation]:
        """Recommend fallback tools for repeatedly failing tools."""
        recs: list[ToolRecommendation] = []
        for miss in self.analyzer.misses:
            if miss.miss_type == "repeated_tool_failure":
                recs.append(
                    ToolRecommendation(
                        target_type="tool",
                        target_id=miss.suggested_tool,
                        recommendation=f"Add fallback mechanism for tool failures",
                        expected_improvement="Reduce session failures from tool errors",
                        confidence=0.75,
                    )
                )
        return recs

    def _provider_tool_recs(self) -> list[ToolRecommendation]:
        """Recommend tool usage improvements per provider."""
        recs: list[ToolRecommendation] = []
        by_provider = self.analyzer.by_provider()

        for provider, data in by_provider.items():
            if data["calls"] == 0 and data["sessions"] > 0:
                recs.append(
                    ToolRecommendation(
                        target_type="provider",
                        target_id=provider,
                        recommendation=f"Provider {provider} has {data['sessions']} sessions but zero tool calls. Check if tools are enabled in config.",
                        expected_improvement="Enable tool usage for this provider",
                        confidence=0.9,
                    )
                )
        return recs

    def _lane_tool_recs(self) -> list[ToolRecommendation]:
        """Recommend tool usage improvements per lane."""
        recs: list[ToolRecommendation] = []
        by_lane = self.analyzer.by_lane()

        for lane, data in by_lane.items():
            if data["tools"] < 3 and data["sessions"] > 5:
                recs.append(
                    ToolRecommendation(
                        target_type="lane",
                        target_id=lane,
                        recommendation=f"Lane '{lane}' uses only {data['tools']} tools across {data['sessions']} sessions. Expand tool availability.",
                        expected_improvement="Increase tool diversity for this lane",
                        confidence=0.7,
                    )
                )
        return recs

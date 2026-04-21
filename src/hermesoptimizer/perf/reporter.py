"""Generate performance reports from analyzed data."""
from __future__ import annotations

from hermesoptimizer.perf.analyzer import PerfAnalyzer


class PerfReporter:
    """Generate human-readable performance reports."""

    def __init__(self, analyzer: PerfAnalyzer) -> None:
        self.analyzer = analyzer

    def generate_report(self) -> str:
        """Generate a text performance report."""
        lines: list[str] = []
        lines.append("=" * 70)
        lines.append("AI API PERFORMANCE REPORT")
        lines.append("=" * 70)
        lines.append("")

        perf = self.analyzer.get_provider_perf()
        if not perf:
            lines.append("No performance data available.")
            return "\n".join(lines)

        lines.append(f"Providers analyzed: {len(perf)}")
        lines.append("")

        lines.append("Provider Performance Summary:")
        lines.append("-" * 70)
        lines.append(
            f"{'Provider':<15} {'Model':<20} {'Reqs':>6} {'Success':>7} {'ErrRate':>8} {'RetryRt':>8} {'AvgMs':>8} {'Tok/s':>8}"
        )
        lines.append("-" * 70)
        for p in sorted(perf, key=lambda x: x.error_rate):
            lines.append(
                f"{p.provider:<15} {p.model:<20} {p.total_requests:>6} {p.success_count:>7} "
                f"{p.error_rate:>7.1%} {p.retry_rate:>7.1%} {p.avg_response_ms:>7.0f} {p.tokens_per_second:>7.1f}"
            )
        lines.append("")

        outages = self.analyzer.get_outages()
        if outages:
            lines.append("Detected Outages:")
            lines.append("-" * 70)
            for o in outages:
                lines.append(
                    f"  {o.provider}:{o.model}  {o.start_time} → {o.end_time or 'ongoing'}  "
                    f"({o.affected_sessions} sessions)"
                )
            lines.append("")

        failure_reasons = self.analyzer.get_failure_reasons()
        if failure_reasons:
            lines.append("Failure Reasons:")
            lines.append("-" * 70)
            for key, reasons in failure_reasons.items():
                lines.append(f"  {key}:")
                for reason in reasons[:5]:
                    lines.append(f"    - {reason}")
            lines.append("")

        working = [p for p in perf if p.error_rate == 0]
        failing = [p for p in perf if p.error_rate > 0.1]

        if working:
            lines.append("Healthy Providers:")
            for p in working:
                lines.append(f"  ✓ {p.provider}:{p.model} ({p.total_requests} requests)")
            lines.append("")

        if failing:
            lines.append("Failing Providers (>10% error rate):")
            for p in failing:
                lines.append(
                    f"  ✗ {p.provider}:{p.model} ({p.error_rate:.1%} errors, {p.total_requests} requests)"
                )
            lines.append("")

        return "\n".join(lines)

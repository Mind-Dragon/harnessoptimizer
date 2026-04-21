"""Analyze sessions and logs for token usage patterns and waste."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from hermesoptimizer.json_utils import load_json_text_lossy
from hermesoptimizer.tokens.models import TokenUsage, TokenWaste


def estimate_tokens(text: str) -> int:
    """Rough token estimation: ~4 characters per token for English text."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def parse_session_tokens(session_path: Path) -> tuple[list[TokenUsage], list[TokenWaste]]:
    """Parse a single session file for token usage and waste patterns."""
    usages: list[TokenUsage] = []
    wastes: list[TokenWaste] = []

    try:
        data = load_json_text_lossy(session_path)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return usages, wastes

    session_id = data.get("session_id", session_path.stem)
    provider = data.get("provider", "unknown")
    model = data.get("model", "unknown")
    lane = data.get("lane", "default")
    messages = data.get("messages", [])
    retries = data.get("retries", 0)

    if not messages:
        return usages, wastes

    # Calculate tokens per role
    role_tokens: dict[str, tuple[int, int]] = {}
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if isinstance(content, str):
            tokens = estimate_tokens(content)
        elif isinstance(content, list):
            tokens = sum(estimate_tokens(str(item)) for item in content)
        else:
            tokens = estimate_tokens(str(content))

        if role not in role_tokens:
            role_tokens[role] = (0, 0)
        prev_in, prev_out = role_tokens[role]
        if role in ("user", "system", "tool"):
            role_tokens[role] = (prev_in + tokens, prev_out)
        else:
            role_tokens[role] = (prev_in, prev_out + tokens)

    # Create TokenUsage records
    total_in = 0
    total_out = 0
    for role, (t_in, t_out) in role_tokens.items():
        total_in += t_in
        total_out += t_out
        usages.append(
            TokenUsage(
                session_id=session_id,
                provider=provider,
                model=model,
                lane=lane,
                role=role,
                tokens_in=t_in,
                tokens_out=t_out,
                timestamp=data.get("created_at", ""),
            )
        )

    # Detect waste patterns
    # 1. High input, low output (prompt bloat)
    if total_in > 4000 and total_out < 500:
        wastes.append(
            TokenWaste(
                session_id=session_id,
                waste_type="prompt_bloat",
                description=f"High input ({total_in}) with very low output ({total_out})",
                tokens_wasted=total_in - total_out,
                severity="HIGH",
            )
        )

    # 2. Retries
    if retries > 2:
        wastes.append(
            TokenWaste(
                session_id=session_id,
                waste_type="retries",
                description=f"Session required {retries} retries",
                tokens_wasted=total_in * retries,
                severity="MEDIUM",
            )
        )

    # 3. Tool call loops (multiple tool_calls in one assistant message)
    tool_call_count = 0
    for msg in messages:
        if msg.get("role") == "assistant":
            tool_calls = msg.get("tool_calls", [])
            tool_call_count += len(tool_calls)
            if len(tool_calls) > 5:
                wastes.append(
                    TokenWaste(
                        session_id=session_id,
                        waste_type="tool_loop",
                        description=f"Assistant made {len(tool_calls)} tool calls in one turn",
                        tokens_wasted=total_in,
                        severity="HIGH",
                    )
                )

    if tool_call_count > 10:
        wastes.append(
            TokenWaste(
                session_id=session_id,
                waste_type="excessive_tooling",
                description=f"Session used {tool_call_count} total tool calls",
                tokens_wasted=total_in // 2,
                severity="MEDIUM",
            )
        )

    # 4. Context window overflow (very long sessions)
    if total_in + total_out > 120000:
        wastes.append(
            TokenWaste(
                session_id=session_id,
                waste_type="context_overflow",
                description=f"Session tokens ({total_in + total_out}) near context limit",
                tokens_wasted=total_in + total_out - 100000,
                severity="CRITICAL",
            )
        )

    return usages, wastes


class TokenAnalyzer:
    """Analyze token usage across sessions."""

    def __init__(self, session_paths: list[Path]) -> None:
        self.session_paths = session_paths
        self.usages: list[TokenUsage] = []
        self.wastes: list[TokenWaste] = []

    def analyze(self) -> None:
        """Parse all sessions and aggregate token data."""
        for path in self.session_paths:
            usages, wastes = parse_session_tokens(path)
            self.usages.extend(usages)
            self.wastes.extend(wastes)

    def by_provider(self) -> dict[str, dict[str, Any]]:
        """Aggregate token usage by provider."""
        result: dict[str, dict[str, Any]] = {}
        for u in self.usages:
            if u.provider not in result:
                result[u.provider] = {"tokens_in": 0, "tokens_out": 0, "sessions": set()}
            result[u.provider]["tokens_in"] += u.tokens_in
            result[u.provider]["tokens_out"] += u.tokens_out
            result[u.provider]["sessions"].add(u.session_id)
        for k, v in result.items():
            v["sessions"] = len(v["sessions"])
        return result

    def by_model(self) -> dict[str, dict[str, Any]]:
        """Aggregate token usage by model."""
        result: dict[str, dict[str, Any]] = {}
        for u in self.usages:
            if u.model not in result:
                result[u.model] = {"tokens_in": 0, "tokens_out": 0, "sessions": set()}
            result[u.model]["tokens_in"] += u.tokens_in
            result[u.model]["tokens_out"] += u.tokens_out
            result[u.model]["sessions"].add(u.session_id)
        for k, v in result.items():
            v["sessions"] = len(v["sessions"])
        return result

    def by_lane(self) -> dict[str, dict[str, Any]]:
        """Aggregate token usage by lane."""
        result: dict[str, dict[str, Any]] = {}
        for u in self.usages:
            if u.lane not in result:
                result[u.lane] = {"tokens_in": 0, "tokens_out": 0, "sessions": set()}
            result[u.lane]["tokens_in"] += u.tokens_in
            result[u.lane]["tokens_out"] += u.tokens_out
            result[u.lane]["sessions"].add(u.session_id)
        for k, v in result.items():
            v["sessions"] = len(v["sessions"])
        return result

    def total_waste(self) -> int:
        return sum(w.tokens_wasted for w in self.wastes)

    def waste_by_type(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for w in self.wastes:
            result[w.waste_type] = result.get(w.waste_type, 0) + w.tokens_wasted
        return result

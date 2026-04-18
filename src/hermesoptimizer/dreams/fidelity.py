"""Phase 2 fidelity-tier storage and representation selection.

This module provides:
1. Structured JSON payload creation for full/summary/essence/tier representations
2. best_representation() - selects the best fidelity tier given budget and score
3. Helpers for applying downgrade decisions from the pre-sweep script

The structured JSON format stored in supermemory:
    {
        "full": "...",      # full verbatim content
        "summary": "...",   # condensed summary
        "essence": "...",   # minimal core essence
        "tier": "full"      # current active tier
    }

best_representation() implements the TEMM1E packing algorithm:
- Caps the returned tier at min(current_tier, max_tier_by_score)
- Budget is used to determine if full/summary/essence fits within constraints
- Score thresholds determine the maximum allowable tier

Phase 2 does NOT include Phase 3 transcript reheating or Phase 4 cron reflection.
"""

from __future__ import annotations

from typing import Any


# --------------------------------------------------------------------------
# Structured Fidelity Payload
# --------------------------------------------------------------------------

# Token size estimates per representation tier
# These are rough estimates used for budget-aware packing decisions
FULL_TOKEN_RATIO = 4.0  # chars per token (English text)
SUMMARY_TOKEN_RATIO = 3.0  # summaries are more token-dense
ESSENCE_TOKEN_RATIO = 2.5  # essence is minimal


def make_fidelity_payload(
    full: str,
    summary: str,
    essence: str,
    tier: str = "full",
) -> dict[str, str]:
    """Create a structured fidelity payload for supermemory storage.

    Args:
        full: The full verbatim memory content.
        summary: A condensed summary of the full content.
        essence: A minimal core essence capturing the key point.
        tier: The current active fidelity tier. Defaults to 'full'.

    Returns:
        A dict with keys: full, summary, essence, tier.

    Examples:
        >>> payload = make_fidelity_payload("Full content here", "Summary", "Essence")
        >>> payload["tier"]
        'full'
    """
    return {
        "full": full,
        "summary": summary,
        "essence": essence,
        "tier": tier,
    }


def parse_fidelity_payload(data: str | dict) -> dict[str, Any]:
    """Parse a fidelity payload from JSON string or dict.

    Args:
        data: JSON string or already-parsed dict.

    Returns:
        The parsed fidelity payload dict.

    Raises:
        ValueError: If the payload is missing required keys.
    """
    if isinstance(data, str):
        import json

        data = json.loads(data)

    required_keys = {"full", "summary", "essence", "tier"}
    missing = required_keys - set(data.keys())
    if missing:
        raise ValueError(f"Fidelity payload missing required keys: {missing}")

    return {
        "full": data["full"],
        "summary": data["summary"],
        "essence": data["essence"],
        "tier": data["tier"],
    }


def get_active_content(payload: dict[str, str]) -> str:
    """Return the content for the active tier in the payload.

    Args:
        payload: A fidelity payload dict.

    Returns:
        The content string for the active tier.

    Raises:
        ValueError: If tier is not recognized.
    """
    tier = payload.get("tier", "full")
    if tier == "full":
        return payload["full"]
    elif tier == "summary":
        return payload["summary"]
    elif tier == "essence":
        return payload["essence"]
    else:
        raise ValueError(f"Unknown tier: {tier}")


def estimate_tokens(text: str, ratio: float = FULL_TOKEN_RATIO) -> int:
    """Estimate token count from character count.

    Args:
        text: The text to estimate.
        ratio: Characters per token ratio (default 4.0 for full text).

    Returns:
        Estimated token count.
    """
    return max(1, int(len(text) / ratio))


# --------------------------------------------------------------------------
# best_representation selection (TEMM1E packing algorithm)
# --------------------------------------------------------------------------

# Tier rank for comparison (higher = more complete)
TIER_RANK = {"full": 3, "summary": 2, "essence": 1, "gone": 0}

# Tier token size estimates (in tokens)
TIER_TOKEN_ESTIMATES = {
    "full": 1000,  # full content is largest
    "summary": 200,  # summary is medium
    "essence": 50,  # essence is minimal
}


def best_representation(
    entry: Any,
    budget: int,
    score: float,
    thresholds: dict[str, float],
) -> str:
    """Select the best representation tier given budget and score constraints.

    Implements TEMM1E's packing algorithm:
    1. Determine the maximum tier allowed by the score (hot/warm/cool thresholds)
    2. If budget is sufficient for that tier, use it
    3. Otherwise, step down to the next tier that fits
    4. Never upgrade beyond the entry's current tier
    5. Never return 'gone' - gone means prune, not representation selection

    Args:
        entry: Entry object/dict with fidelity_tier attribute or key.
        budget: Available token budget for this entry.
        score: The decayed score for this entry.
        thresholds: Dict with hot/warm/cool/gone thresholds.

    Returns:
        One of: 'full', 'summary', 'essence'.

    Examples:
        >>> # Hot score, generous budget -> full
        >>> best_representation(entry, budget=10000, score=3.0,
        ...                     thresholds={"hot":2.0,"warm":1.0,"cool":0.3,"gone":0.01})
        'full'

        >>> # Hot score, tiny budget -> essence
        >>> best_representation(entry, budget=50, score=2.5,
        ...                     thresholds={"hot":2.0,"warm":1.0,"cool":0.3,"gone":0.01})
        'essence'
    """
    # Get entry's current tier (cap we cannot exceed)
    current_tier = getattr(entry, "fidelity_tier", None)
    if current_tier is None:
        current_tier = entry.get("fidelity_tier", "full") if isinstance(entry, dict) else "full"

    current_rank = TIER_RANK.get(current_tier, 3)

    # Determine max tier by score
    if score >= thresholds.get("hot", 2.0):
        max_tier = "full"
    elif score >= thresholds.get("warm", 1.0):
        max_tier = "summary"
    elif score >= thresholds.get("cool", 0.3):
        max_tier = "essence"
    else:
        max_tier = "essence"  # Even below gone, we still have essence as minimum

    max_rank = TIER_RANK.get(max_tier, 1)

    # The actual cap is the minimum of current tier and score-based max
    capped_rank = min(current_rank, max_rank)

    # Try tiers from highest to lowest, picking the first that fits in budget
    # But only consider tiers up to capped_rank
    candidates = []
    if capped_rank >= TIER_RANK["full"]:
        candidates.append("full")
    if capped_rank >= TIER_RANK["summary"]:
        candidates.append("summary")
    if capped_rank >= TIER_RANK["essence"]:
        candidates.append("essence")

    # If no candidates (shouldn't happen), default to essence
    if not candidates:
        candidates = ["essence"]

    # For each candidate, check if it fits in budget
    # We estimate based on the entry's actual content lengths if available
    for tier in candidates:
        tier_tokens = _estimate_entry_tier_tokens(entry, tier)
        if tier_tokens <= budget:
            return tier

    # Budget is too small even for essence - return essence anyway
    # (the caller should handle pruning if content doesn't fit)
    return "essence"


def _estimate_entry_tier_tokens(entry: Any, tier: str) -> int:
    """Estimate token count for a specific tier of an entry.

    Args:
        entry: Entry with content attributes.
        tier: Target tier ('full', 'summary', 'essence').

    Returns:
        Estimated token count for that tier.
    """
    # Get the content for the requested tier
    content = _get_tier_content(entry, tier)

    # Use appropriate ratio for the tier
    if tier == "full":
        ratio = FULL_TOKEN_RATIO
    elif tier == "summary":
        ratio = SUMMARY_TOKEN_RATIO
    else:
        ratio = ESSENCE_TOKEN_RATIO

    return estimate_tokens(content, ratio)


def _get_tier_content(entry: Any, tier: str) -> str:
    """Get the content string for a specific tier from an entry.

    Args:
        entry: Entry object or dict.
        tier: Target tier.

    Returns:
        Content string for that tier, or empty string if not available.
    """
    # Try attribute access first, then dict
    if hasattr(entry, f"{tier}_content"):
        return getattr(entry, f"{tier}_content", "") or ""

    if isinstance(entry, dict):
        key = f"{tier}_content"
        return entry.get(key, "") or ""

    return ""


# --------------------------------------------------------------------------
# Downgrade decision helpers
# --------------------------------------------------------------------------

# Valid tiers for downgrade decisions
VALID_TIERS = {"full", "summary", "essence", "gone"}


def get_downgrade_target(previous_tier: str, new_tier: str) -> str | None:
    """Determine the target tier for a downgrade action.

    Args:
        previous_tier: The tier before the sweep decision.
        new_tier: The tier determined by the sweep (based on score).

    Returns:
        The tier to rewrite to, or None if no rewrite is needed.

    Examples:
        >>> get_downgrade_target("full", "summary")
        'summary'
        >>> get_downgrade_target("full", "full")
        None  # no rewrite needed
        >>> get_downgrade_target("essence", "gone")
        None  # prune, not rewrite
    """
    if previous_tier == new_tier:
        return None  # no change needed

    # gone means prune, not rewrite
    if new_tier == "gone":
        return None

    # full->summary, summary->essence are downgrades that need rewrite
    return new_tier


def is_downgrade(previous_tier: str, new_tier: str) -> bool:
    """Check if a tier change is a downgrade (demotion).

    Args:
        previous_tier: The tier before the decision.
        new_tier: The tier after the decision.

    Returns:
        True if this is a downgrade, False otherwise.
    """
    prev_rank = TIER_RANK.get(previous_tier, 0)
    new_rank = TIER_RANK.get(new_tier, 0)
    return new_rank < prev_rank

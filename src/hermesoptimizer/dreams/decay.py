"""Phase 1 exponential decay scoring and threshold classification.

This module implements the TEMM1E-inspired lambda-memory decay formula for
the v0.7.0 dreaming architecture.

decay_score(importance, hours_since_access, lambda=0.01) = importance * exp(-lambda * hours)

Fidelity thresholds (default):
  - hot  >= 2.0 -> 'full'
  - warm >= 1.0 -> 'summary'
  - cool >= 0.3 -> 'essence'
  - gone <  0.01 -> 'gone' (eligible for pruning)

Adaptive thresholds: when injected_memory_pct > 40%, thresholds scale
proportionally to the memory pressure ratio.
"""

from __future__ import annotations

import math
from typing import Any


# ---------------------------------------------------------------------------
# Default thresholds
# ---------------------------------------------------------------------------

DEFAULT_HOT_THRESHOLD = 2.0
DEFAULT_WARM_THRESHOLD = 1.0
DEFAULT_COOL_THRESHOLD = 0.3
DEFAULT_GONE_THRESHOLD = 0.01

MEMORY_PRESSURE_TRIGGER_PCT = 40.0  # threshold above which adaptive scaling kicks in


# ---------------------------------------------------------------------------
# Core decay formula
# ---------------------------------------------------------------------------


def decay_score(
    importance: float,
    hours_since_access: float,
    lambda_: float = 0.01,
) -> float:
    """Compute the decayed score for a memory entry.

    score = importance * exp(-lambda * hours_since_access)

    Args:
        importance: The entry's importance score (0.0 to ~5.0 typical range).
        hours_since_access: Hours elapsed since the entry was last accessed.
        lambda_: Decay constant. Higher = faster decay.
            Default 0.01 gives a half-life of ~69.3 hours (ln(2)/lambda).

    Returns:
        The decayed score (>= 0).

    Examples:
        >>> decay_score(importance=2.0, hours_since_access=0.0)
        2.0
        >>> decay_score(importance=2.0, hours_since_access=100.0)  # exp(-1.0) ~ 0.3678
        0.7358...
    """
    if importance <= 0.0:
        return 0.0
    return importance * math.exp(-lambda_ * hours_since_access)


# ---------------------------------------------------------------------------
# Threshold classification
# ---------------------------------------------------------------------------


def classify_tier(
    score: float,
    injected_memory_pct: float = 0.0,
) -> str:
    """Classify a decayed score into a fidelity tier.

    Uses adaptive thresholds when injected_memory_pct > 40%, scaling
    all thresholds proportionally to the memory pressure ratio.

    Tier promotion logic (never upgrades, only demotes or keeps):
      - 'full'    : score >= hot threshold
      - 'summary' : score >= warm threshold (but < hot)
      - 'essence' : score >= cool threshold (but < warm)
      - 'gone'    : score < gone threshold (eligible for pruning)

    Args:
        score: The decayed score for this entry.
        injected_memory_pct: Current injected memory fill percentage (0-100).
            When > 40, thresholds scale up proportionally.

    Returns:
        One of: 'full', 'summary', 'essence', 'gone'.

    Examples:
        >>> classify_tier(score=3.0)
        'full'
        >>> classify_tier(score=1.5)
        'summary'
        >>> classify_tier(score=0.5)
        'essence'
        >>> classify_tier(score=0.005)
        'gone'
    """
    thresholds = get_adaptive_thresholds(injected_memory_pct)

    if score >= thresholds["hot"]:
        return "full"
    elif score >= thresholds["warm"]:
        return "summary"
    elif score >= thresholds["cool"]:
        return "essence"
    else:
        return "gone"


def get_adaptive_thresholds(
    injected_memory_pct: float,
) -> dict[str, float]:
    """Return the current fidelity thresholds, scaled under memory pressure.

    When injected_memory_pct <= 40%, returns the default thresholds.
    When > 40%, scales all thresholds proportionally to the pressure ratio:

        pressure_ratio = 1 + (injected_memory_pct - 40) / 40
                        = injected_memory_pct / 40 + 0.5

    At 40%: ratio = 1.0 (no scaling)
    At 50%: ratio = 1.25
    At 60%: ratio = 1.5
    At 80%: ratio = 2.0
    At 100%: ratio = 2.5

    Args:
        injected_memory_pct: Current injected memory fill percentage (0-100).

    Returns:
        Dict with keys: 'hot', 'warm', 'cool', 'gone'.

    Examples:
        >>> get_adaptive_thresholds(0.0)
        {'hot': 2.0, 'warm': 1.0, 'cool': 0.3, 'gone': 0.01}
        >>> get_adaptive_thresholds(50.0)['hot']
        2.5
    """
    if injected_memory_pct <= MEMORY_PRESSURE_TRIGGER_PCT:
        return {
            "hot": DEFAULT_HOT_THRESHOLD,
            "warm": DEFAULT_WARM_THRESHOLD,
            "cool": DEFAULT_COOL_THRESHOLD,
            "gone": DEFAULT_GONE_THRESHOLD,
        }

    pressure_ratio = 1.0 + (injected_memory_pct - MEMORY_PRESSURE_TRIGGER_PCT) / MEMORY_PRESSURE_TRIGGER_PCT
    # Equivalent: pressure_ratio = injected_memory_pct / 40.0 + 0.5

    return {
        "hot": DEFAULT_HOT_THRESHOLD * pressure_ratio,
        "warm": DEFAULT_WARM_THRESHOLD * pressure_ratio,
        "cool": DEFAULT_COOL_THRESHOLD * pressure_ratio,
        "gone": DEFAULT_GONE_THRESHOLD * pressure_ratio,
    }

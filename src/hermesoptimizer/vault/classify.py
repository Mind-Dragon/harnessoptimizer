"""Auto-classification module for vault entries.

Classifies keys as 'secret' (should be encrypted) or 'metadata' (safe to store as plaintext).
"""

from __future__ import annotations

import re
from pathlib import Path


# Secret patterns: case-insensitive suffix matches
_SECRET_SUFFIX_PATTERNS = (
    "_KEY",
    "_TOKEN",
    "_SECRET",
    "_PASSWORD",
    "_PASS",
    "_API_KEY",
    "_ACCESS_KEY",
    "_PRIVATE_KEY",
    "_AUTH",
    "_CREDENTIAL",
)

# Exact secret name matches (case-insensitive)
_SECRET_EXACT_NAMES = {
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_key",
    "private_key",
    "auth_token",
    "bearer_token",
    "refresh_token",
    "client_secret",
}

# Metadata patterns: case-insensitive suffix matches
_METADATA_SUFFIX_PATTERNS = (
    "_URL",
    "_ENDPOINT",
    "_HOST",
    "_PORT",
    "_REGION",
    "_BASE_URL",
    "_API_URL",
    "_SERVER",
)

# Pre-compile regex patterns for suffix matching (case-insensitive)
_SECRET_PATTERN = re.compile(
    r"(?i)(" + "|".join(re.escape(s) for s in _SECRET_SUFFIX_PATTERNS) + ")$"
)
_METADATA_PATTERN = re.compile(
    r"(?i)(" + "|".join(re.escape(s) for s in _METADATA_SUFFIX_PATTERNS) + ")$"
)


def classify_key(key_name: str) -> str:
    """Classify a key name as 'secret' or 'metadata'.

    Secret patterns (case-insensitive suffix):
        *_KEY, *_TOKEN, *_SECRET, *_PASSWORD, *_PASS, *_API_KEY,
        *_ACCESS_KEY, *_PRIVATE_KEY, *_AUTH, *_CREDENTIAL

    Also exact matches: password, secret, token, api_key, apikey, access_key,
        private_key, auth_token, bearer_token, refresh_token, client_secret

    Metadata patterns (case-insensitive suffix):
        *_URL, *_ENDPOINT, *_HOST, *_PORT, *_REGION, *_BASE_URL, *_API_URL, *_SERVER

    Default: 'metadata' (safe default - only encrypt what looks like a secret)

    Args:
        key_name: The key name to classify.

    Returns:
        'secret' if the key looks like a secret, 'metadata' otherwise.
    """
    # Check exact name match (case-insensitive)
    if key_name.lower() in _SECRET_EXACT_NAMES:
        return "secret"

    # Check suffix patterns
    if _SECRET_PATTERN.search(key_name):
        return "secret"

    if _METADATA_PATTERN.search(key_name):
        return "metadata"

    # Default to metadata (safe default)
    return "metadata"


def load_classification_override(path: Path) -> dict[str, str]:
    """Load classification override file.

    Format: KEY_NAME=secret or KEY_NAME=metadata, one per line.
    Lines starting with # are treated as comments.
    Empty lines are ignored.

    Args:
        path: Path to the .classification override file.

    Returns:
        Dictionary mapping key names to their classification ('secret' or 'metadata').
        Returns empty dict if file doesn't exist or is empty.
    """
    overrides: dict[str, str] = {}

    if not path.exists():
        return overrides

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue
        # Parse KEY=classification
        if "=" not in line:
            continue
        key, classification = line.split("=", 1)
        key = key.strip()
        classification = classification.strip().lower()
        # Only accept valid classifications
        if classification in ("secret", "metadata"):
            overrides[key] = classification

    return overrides

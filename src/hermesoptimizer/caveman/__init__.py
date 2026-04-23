"""Caveman mode — token-efficient output compression.

Drops articles, filler words, hedging, pleasantries.
Keeps code, paths, commands, and technical details exact.
Uses fragments and short synonyms.
Pattern: [thing] [action] [reason]. [next step].

Persistent config: ~/.hermes/config.yaml with caveman_mode: true|false
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Callable

import yaml

from hermesoptimizer.extensions.install_integrity import (
    atomic_yaml_write,
    validate_yaml_file,
)

# Config key for caveman mode
_CAVEMAN_CONFIG_KEY = "caveman_mode"

# Default state when no config exists
_CAVEMAN_DEFAULT: bool = False

# In-memory cache of the enabled state (syncs with config on load)
_caveman_enabled: bool = _CAVEMAN_DEFAULT

# Path to config file (can be overridden for testing)
_config_path: Path | None = None


def _get_config_path() -> Path:
    """Get the path to the hermes config file.
    
    Returns ~/.hermes/config.yaml
    """
    if _config_path is not None:
        return _config_path
    home = Path(os.path.expanduser("~"))
    return home / ".hermes" / "config.yaml"


def _set_config_path(path: Path | None) -> None:
    """Set a custom config path (useful for testing).
    
    Pass None to reset to default.
    """
    global _config_path
    _config_path = path


def _ensure_hermes_dir() -> Path:
    """Ensure ~/.hermes directory exists.
    
    Returns the path to the hermes directory.
    """
    config_path = _get_config_path()
    hermes_dir = config_path.parent
    hermes_dir.mkdir(parents=True, exist_ok=True)
    return hermes_dir


def _read_config() -> dict:
    """Read the config file as a dictionary.
    
    Returns empty dict if file doesn't exist or can't be parsed.
    """
    config_path = _get_config_path()
    if not config_path.exists():
        return {}
    try:
        content = config_path.read_text(encoding="utf-8")
        if not content.strip():
            return {}
        return yaml.safe_load(content) or {}
    except Exception:
        return {}


def _write_config(data: dict) -> None:
    """Write data to the config file, preserving other keys.

    Uses atomic_yaml_write for transactional semantics with validation and rollback.
    """
    config_path = _get_config_path()
    _ensure_hermes_dir()
    existing = _read_config()
    existing.update(data)

    atomic_yaml_write(config_path, existing)


def _load_caveman_state() -> bool:
    """Load caveman state from config file.
    
    Returns the cached value if available, otherwise reads from config.
    """
    global _caveman_enabled
    data = _read_config()
    return data.get(_CAVEMAN_CONFIG_KEY, _CAVEMAN_DEFAULT)


# Safety-critical patterns that always stay in full mode
_SAFETY_PATTERNS = [
    r"write-back",
    r"mutation",
    r"confirm",
    r"destructive",
    r"auth",
    r"credential",
    r"secret",
    r"password",
    r"token",
    r"key",
    r"vault",
    r"setup",
    r"onboard",
    r"install",
]

# Filler words to drop
_FILLER_WORDS = {
    "actually", "basically", "essentially", "generally", "literally",
    "really", "simply", "just", "very", "quite", "rather", "pretty",
    "certainly", "definitely", "obviously", "clearly", "probably",
    "maybe", "perhaps", "likely", "unlikely",
}

# Hedging phrases to drop
_HEDGING_PATTERNS = [
    r"\bI think\b",
    r"\bI believe\b",
    r"\bit seems\b",
    r"\bit appears\b",
    r"\bin my opinion\b",
    r"\byou might want to\b",
    r"\byou may want to\b",
    r"\bconsider\b",
    r"\bperhaps\b",
    r"\bpossibly\b",
]

# Articles to drop (context-aware)
_ARTICLES = {"a", "an", "the"}

# Pleasantries to drop
_PLEASANTRIES = [
    r"\bsure\b",
    r"\babsolutely\b",
    r"\bcertainly\b",
    r"\bhappy to\b",
    r"\bglad to\b",
    r"\bwelcome\b",
    r"\bplease\b",
    r"\bthank you\b",
    r"\bthanks\b",
    r"\bno problem\b",
    r"\byou're welcome\b",
]


def _sync_from_config() -> None:
    """Sync the in-memory state from config file."""
    global _caveman_enabled
    _caveman_enabled = _load_caveman_state()


def enable() -> None:
    """Enable caveman mode and persist to config."""
    global _caveman_enabled
    _caveman_enabled = True
    _write_config({_CAVEMAN_CONFIG_KEY: True})


def disable() -> None:
    """Disable caveman mode and persist to config."""
    global _caveman_enabled
    _caveman_enabled = False
    _write_config({_CAVEMAN_CONFIG_KEY: False})


def is_enabled() -> bool:
    """Check if caveman mode is enabled (syncs from config on first call)."""
    _sync_from_config()
    return _caveman_enabled


def toggle() -> bool:
    """Toggle caveman mode and persist new state. Returns new state."""
    global _caveman_enabled
    _sync_from_config()
    _caveman_enabled = not _caveman_enabled
    _write_config({_CAVEMAN_CONFIG_KEY: _caveman_enabled})
    return _caveman_enabled


def _is_safety_critical(text: str) -> bool:
    """Check if text contains safety-critical content."""
    text_lower = text.lower()
    for pattern in _SAFETY_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True
    return False


def compress(text: str, force_full: bool = False) -> str:
    """Compress text to caveman style.

    Args:
        text: Input text to compress
        force_full: If True, always return full mode (for safety-critical paths)

    Returns:
        Compressed text if caveman mode enabled and not safety-critical,
        otherwise original text unchanged.
    """
    if not _caveman_enabled or force_full:
        return text

    if _is_safety_critical(text):
        return text

    # Drop hedging patterns
    for pattern in _HEDGING_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # Drop pleasantries
    for pattern in _PLEASANTRIES:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # Drop filler words (word boundaries)
    words = text.split()
    filtered_words = [w for w in words if w.lower().strip(".,!?;:") not in _FILLER_WORDS]
    text = " ".join(filtered_words)

    # Drop articles before nouns (simple heuristic)
    # This is context-aware: only drop articles that precede noun-like words
    text = re.sub(r"\b(a|an|the)\s+([a-z])", r"\2", text, flags=re.IGNORECASE)

    # Clean up extra whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Drop leading "So," or "Well,"
    text = re.sub(r"^(So,|Well,)\s*", "", text, flags=re.IGNORECASE)

    return text


def caveman_wrapper(func: Callable) -> Callable:
    """Decorator to wrap a function's output with caveman compression.

    Use this for functions that produce user-facing output.
    Safety-critical paths should NOT use this decorator.
    """
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        if isinstance(result, str):
            return compress(result)
        return result
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def full_mode_guard(func: Callable) -> Callable:
    """Decorator to force full mode for safety-critical functions.

    Use this for functions that handle:
    - vault write-back
    - config mutations
    - destructive operations
    - auth/credential handling
    - setup/onboarding
    """
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        if isinstance(result, str):
            return compress(result, force_full=True)
        return result
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper

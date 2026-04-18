from __future__ import annotations

from hashlib import sha256


def fingerprint_secret(secret: str) -> str:
    """Return a short, non-reversible fingerprint for a secret value.

    Returns 'fp20:' + 20 hex characters (25 chars total).
    """
    digest = sha256(secret.encode("utf-8")).hexdigest()
    return f"fp20:{digest[:20]}"


def migrate_fingerprint(old_fp: str) -> str:
    """Migrate a fingerprint to the new format.

    - If already 'fp20:' format, return unchanged.
    - If already 'fp12:' format, return unchanged.
    - If old 12-char format (no prefix), prefix with 'fp12:' to mark as legacy.

    Note: We cannot re-derive the full 20-char fingerprint from the old 12-char
    version since we don't have the original secret, so we mark it as 'fp12:'.
    """
    if old_fp.startswith("fp20:") or old_fp.startswith("fp12:"):
        return old_fp
    # Assume old 12-char format without prefix
    return f"fp12:{old_fp}"

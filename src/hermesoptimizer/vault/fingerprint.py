from __future__ import annotations

from hashlib import sha256


def fingerprint_secret(secret: str) -> str:
    """Return a short, non-reversible fingerprint for a secret value."""
    digest = sha256(secret.encode("utf-8")).hexdigest()
    return digest[:12]

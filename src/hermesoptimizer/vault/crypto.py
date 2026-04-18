"""Vault cryptographic utilities using ChaCha20-Poly1305 and Argon2id."""
import base64
import os
from typing import Tuple

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305


class VaultCrypto:
    """Encryption/decryption using ChaCha20-Poly1305."""

    def encrypt(self, plaintext: str, master_key: bytes) -> str:
        """
        Encrypt plaintext using ChaCha20-Poly1305.

        Args:
            plaintext: The string to encrypt
            master_key: 32-byte key for ChaCha20

        Returns:
            Base64-encoded ciphertext with 12-byte nonce prepended
        """
        # Generate random 12-byte nonce
        nonce = os.urandom(12)

        # Create cipher
        chacha = ChaCha20Poly1305(master_key)

        # Encrypt (encode plaintext to bytes first)
        plaintext_bytes = plaintext.encode("utf-8")
        ciphertext = chacha.encrypt(nonce, plaintext_bytes, None)

        # Prepend nonce to ciphertext
        ciphertext_with_nonce = nonce + ciphertext

        # Return base64-encoded result
        return base64.b64encode(ciphertext_with_nonce).decode("ascii")

    def decrypt(self, ciphertext_b64: str, master_key: bytes) -> str:
        """
        Decrypt ciphertext using ChaCha20-Poly1305.

        Args:
            ciphertext_b64: Base64-encoded ciphertext with 12-byte nonce prepended
            master_key: 32-byte key for ChaCha20

        Returns:
            Decrypted plaintext string

        Raises:
            InvalidTag: If authentication fails (wrong key or tampered data)
        """
        # Decode base64
        ciphertext_with_nonce = base64.b64decode(ciphertext_b64)

        # Extract nonce (first 12 bytes) and ciphertext
        nonce = ciphertext_with_nonce[:12]
        ciphertext = ciphertext_with_nonce[12:]

        # Create cipher and decrypt
        chacha = ChaCha20Poly1305(master_key)
        plaintext_bytes = chacha.decrypt(nonce, ciphertext, None)

        # Return as string
        return plaintext_bytes.decode("utf-8")


def derive_key(passphrase: str, salt: bytes | None = None) -> Tuple[bytes, bytes]:
    """
    Derive a key from a passphrase using Argon2id.

    Args:
        passphrase: The passphrase to derive the key from
        salt: 16-byte salt (if None, a random one is generated)

    Returns:
        Tuple of (derived_key_bytes, salt_used)
        The key is 32 bytes for use with ChaCha20
    """
    from argon2 import low_level  # lazy import to avoid import-time dep

    # Generate random salt if not provided
    if salt is None:
        salt = os.urandom(16)

    # Derive key using Argon2id with raw output
    derived = low_level.hash_secret_raw(
        secret=passphrase.encode("utf-8"),
        salt=salt,
        time_cost=3,
        memory_cost=65536,
        parallelism=4,
        hash_len=32,
        type=low_level.Type.ID,
    )

    return derived, salt


def generate_master_key() -> bytes:
    """
    Generate a random 32-byte master key.

    Returns:
        32 bytes of cryptographically secure random data
    """
    return os.urandom(32)

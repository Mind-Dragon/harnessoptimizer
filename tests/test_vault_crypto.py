"""Tests for VaultCrypto module - ChaCha20-Poly1305 encryption with Argon2id KDF."""
import base64
import pytest
from cryptography.exceptions import InvalidTag

from hermesoptimizer.vault.crypto import VaultCrypto, derive_key, generate_master_key


class TestVaultCrypto:
    """Test suite for VaultCrypto class."""

    def test_encrypt_decrypt_roundtrip(self):
        """Encrypt and decrypt should return original plaintext."""
        crypto = VaultCrypto()
        plaintext = "Hello, World! This is a secret message."
        master_key = generate_master_key()

        ciphertext_b64 = crypto.encrypt(plaintext, master_key)
        decrypted = crypto.decrypt(ciphertext_b64, master_key)

        assert decrypted == plaintext

    def test_encrypt_produces_different_ciphertext_each_time(self):
        """Same plaintext with same key should produce different ciphertext due to random nonce."""
        crypto = VaultCrypto()
        plaintext = "Same message"
        master_key = generate_master_key()

        ciphertext1 = crypto.encrypt(plaintext, master_key)
        ciphertext2 = crypto.encrypt(plaintext, master_key)

        assert ciphertext1 != ciphertext2

        # But both should decrypt to the same plaintext
        assert crypto.decrypt(ciphertext1, master_key) == plaintext
        assert crypto.decrypt(ciphertext2, master_key) == plaintext

    def test_decrypt_with_wrong_key_fails(self):
        """Decryption with wrong key should raise InvalidTag (authentication failure)."""
        crypto = VaultCrypto()
        plaintext = "Secret data"
        master_key = generate_master_key()
        wrong_key = generate_master_key()

        ciphertext_b64 = crypto.encrypt(plaintext, master_key)

        with pytest.raises(InvalidTag):
            crypto.decrypt(ciphertext_b64, wrong_key)

    def test_decrypt_with_tampered_ciphertext_fails(self):
        """Tampering with ciphertext should cause decryption to fail."""
        crypto = VaultCrypto()
        plaintext = "Important data"
        master_key = generate_master_key()

        ciphertext_b64 = crypto.encrypt(plaintext, master_key)
        # Decode, tamper, re-encode
        ciphertext_bytes = base64.b64decode(ciphertext_b64)
        tampered = bytearray(ciphertext_bytes)
        tampered[-1] ^= 0xFF  # Flip bits in last byte
        tampered_b64 = base64.b64encode(bytes(tampered)).decode()

        with pytest.raises(InvalidTag):
            crypto.decrypt(tampered_b64, master_key)


class TestDeriveKey:
    """Test suite for derive_key function."""

    def test_derive_key_deterministic_with_same_salt(self):
        """Same passphrase and salt should produce same key."""
        passphrase = "my_secure_password"
        salt = b"1234567890abcdef"

        key1, salt1 = derive_key(passphrase, salt)
        key2, salt2 = derive_key(passphrase, salt)

        assert key1 == key2
        assert salt1 == salt2

    def test_derive_key_different_salt_different_key(self):
        """Different salts should produce different keys even with same passphrase."""
        passphrase = "my_secure_password"
        salt1 = b"1234567890abcdef"
        salt2 = b"fedcba0987654321"

        key1, _ = derive_key(passphrase, salt1)
        key2, _ = derive_key(passphrase, salt2)

        assert key1 != key2

    def test_derive_key_generates_random_salt_if_none(self):
        """If salt is None, a random 16-byte salt should be generated."""
        passphrase = "test_password"

        key1, salt1 = derive_key(passphrase, None)
        key2, salt2 = derive_key(passphrase, None)

        # Keys should be different because salts are random
        assert key1 != key2
        assert salt1 != salt2
        assert len(salt1) == 16
        assert len(salt2) == 16

    def test_derive_key_returns_32_byte_key(self):
        """Derived key should be 32 bytes for ChaCha20."""
        passphrase = "password"
        salt = b"1234567890abcdef"

        key, _ = derive_key(passphrase, salt)

        assert len(key) == 32


class TestGenerateMasterKey:
    """Test suite for generate_master_key function."""

    def test_generate_master_key_is_32_bytes(self):
        """Generated master key should be 32 bytes."""
        key = generate_master_key()
        assert len(key) == 32

    def test_generate_master_key_is_random(self):
        """Each call should generate a different key."""
        key1 = generate_master_key()
        key2 = generate_master_key()
        assert key1 != key2

import pytest

from app.keys.encryption import decrypt_api_key, encrypt_api_key


def test_encrypt_decrypt_roundtrip():
    original = "sk-test-key-12345"
    encrypted = encrypt_api_key(original)
    assert isinstance(encrypted, bytes)
    assert encrypted != original.encode()
    decrypted = decrypt_api_key(encrypted)
    assert decrypted == original


def test_encrypt_produces_different_ciphertexts():
    key = "sk-another-key"
    e1 = encrypt_api_key(key)
    e2 = encrypt_api_key(key)
    assert e1 != e2


def test_decrypt_invalid_data():
    with pytest.raises(Exception):
        decrypt_api_key(b"not-valid-fernet-data")

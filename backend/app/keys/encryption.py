from cryptography.fernet import Fernet

from app.config import settings

_fernet = Fernet(settings.fernet_key.encode())


def encrypt_api_key(raw_key: str) -> bytes:
    return _fernet.encrypt(raw_key.encode())


def decrypt_api_key(encrypted_key: bytes) -> str:
    return _fernet.decrypt(encrypted_key).decode()

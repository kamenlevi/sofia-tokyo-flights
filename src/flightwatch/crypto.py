import json

from cryptography.fernet import Fernet


def new_key() -> str:
    return Fernet.generate_key().decode()


def encrypt_json(obj, key: str) -> bytes:
    return Fernet(key.encode()).encrypt(json.dumps(obj).encode())


def decrypt_json(data: bytes, key: str):
    return json.loads(Fernet(key.encode()).decrypt(data))

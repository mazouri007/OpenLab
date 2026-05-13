from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import get_settings

SECRET_PREFIX = "enc:v1:"
DEV_SECRET_KEY = "K7T1ua7IshX1OPP9cqajFI7cdqfRgYT-DCQY2TRTwWY="


class SecretDecryptionError(RuntimeError):
    """Raised when an encrypted secret cannot be decrypted with configured keys."""


class SecretConfigurationError(RuntimeError):
    """Raised when secret encryption keys are not configured correctly."""


def encrypt_secret(value: str | None) -> str | None:
    if value is None or value == "":
        return value
    if is_encrypted_secret(value):
        return value
    token = _fernet().encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{SECRET_PREFIX}{token}"


def decrypt_secret(value: str | None) -> str | None:
    if value is None or value == "":
        return value
    if not is_encrypted_secret(value):
        return value
    token = value.removeprefix(SECRET_PREFIX)
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise SecretDecryptionError("Unable to decrypt stored secret with APP_SECRET_KEYS.") from exc


def rotate_secret(value: str | None) -> str | None:
    plaintext = decrypt_secret(value)
    if plaintext is None or plaintext == "":
        return plaintext
    token = _primary_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")
    return f"{SECRET_PREFIX}{token}"


def is_encrypted_secret(value: str | None) -> bool:
    return bool(value and value.startswith(SECRET_PREFIX))


def has_secret(value: str | None) -> bool:
    return bool(value)


def mask_secret(value: str | None) -> str | None:
    plaintext = decrypt_secret(value)
    if not plaintext:
        return None
    if len(plaintext) <= 8:
        return "****"
    return f"{plaintext[:4]}...{plaintext[-4:]}"


@lru_cache
def _fernet() -> MultiFernet:
    return MultiFernet([Fernet(key) for key in _secret_keys()])


def _primary_fernet() -> Fernet:
    return Fernet(_secret_keys()[0])


def _secret_keys() -> list[str]:
    settings = get_settings()
    raw = settings.app_secret_keys
    keys = [item.strip() for item in raw.split(",") if item.strip()]
    if not keys:
        if settings.app_env in {"dev", "test"}:
            return [DEV_SECRET_KEY]
        raise SecretConfigurationError("APP_SECRET_KEYS must contain at least one Fernet key.")
    return keys

"""Cryptographic and token primitives shared across modules."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import string
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet
from jwt import ExpiredSignatureError, PyJWTError

from humbee_sfa.core.clock import utc_now
from humbee_sfa.core.settings import get_settings

_password_hasher = PasswordHasher()


class InvalidTokenError(ValueError):
    def __init__(self, message: str, *, expired: bool = False) -> None:
        super().__init__(message)
        self.expired = expired


def hash_otp_code(code: str) -> str:
    return _password_hasher.hash(code)


def verify_otp_code(code: str, hashed: str) -> bool:
    try:
        return _password_hasher.verify(hashed, code)
    except (VerifyMismatchError, VerificationError):
        return False


def hmac_phone(phone_e164: str) -> str:
    secret = get_settings().phone_hmac_secret.encode("utf-8")
    return hmac.new(secret, phone_e164.encode("utf-8"), hashlib.sha256).hexdigest()


def _fernet() -> Fernet:
    return Fernet(get_settings().phone_enc_key.encode("utf-8"))


def encrypt_phone(phone_e164: str) -> bytes:
    return _fernet().encrypt(phone_e164.encode("utf-8"))


def decrypt_phone(ciphertext: bytes) -> str:
    return _fernet().decrypt(ciphertext).decode("utf-8")


def generate_otp_code(length: int) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(length))


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_access_token(
    *,
    employee_id: str,
    session_id: str,
    device_id: str,
    role: str,
    tenant_id: str,
    ttl_seconds: int,
) -> tuple[str, datetime]:
    settings = get_settings()
    issued_at = utc_now()
    expires_at = issued_at + timedelta(seconds=ttl_seconds)
    payload = {
        "employee_id": employee_id,
        "session_id": session_id,
        "device_id": device_id,
        "role": role,
        "tenant_id": tenant_id,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_at


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={
                "require": [
                    "employee_id",
                    "session_id",
                    "device_id",
                    "role",
                    "tenant_id",
                    "iat",
                    "exp",
                ]
            },
        )
    except ExpiredSignatureError as exc:
        raise InvalidTokenError("Access token has expired.", expired=True) from exc
    except PyJWTError as exc:
        raise InvalidTokenError("Access token is invalid.", expired=False) from exc

    if not isinstance(payload, dict):
        raise InvalidTokenError("Access token payload is invalid.", expired=False)
    return payload


def utc_from_timestamp(timestamp: float) -> datetime:
    return datetime.fromtimestamp(timestamp, tz=UTC)

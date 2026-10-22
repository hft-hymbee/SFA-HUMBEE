"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from humbee_sfa.core.db import get_db_session
from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.core.security import InvalidTokenError, decode_access_token, utc_from_timestamp


@dataclass(frozen=True)
class AccessTokenClaims:
    employee_id: str
    session_id: str
    device_id: str
    role: str
    tenant_id: str
    issued_at: datetime
    access_token_expires_at: datetime


def _parse_authorization_header(header: str | None) -> str:
    if not header:
        raise ApiError(
            401,
            "refresh_invalid",
            "Authentication credentials are missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise ApiError(
            401,
            "refresh_invalid",
            "Authentication credentials are invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return parts[1].strip()


def _parse_timestamp(payload: dict[str, Any], key: str) -> datetime:
    value = payload.get(key)
    if not isinstance(value, (int, float)):
        raise ApiError(
            401,
            "refresh_invalid",
            "Authentication credentials are invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return utc_from_timestamp(value)


def _require_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ApiError(
            401,
            "refresh_invalid",
            "Authentication credentials are invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return value


# A valid signature is not a live session. The persisted-session check (R-IDN-21) belongs to
# `identity`, which owns `identity_sessions`, but every authenticated route in every module
# must run it — so `identity` registers its guard here at import time and `core` stays free of
# any module import. Exactly one guard is installed; the last registration wins.
SessionGuard = Callable[[Session, "AccessTokenClaims"], None]

_session_guard: SessionGuard | None = None


def register_session_guard(guard: SessionGuard) -> None:
    global _session_guard
    _session_guard = guard


def get_current_claims(
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
) -> AccessTokenClaims:
    claims = _decode_claims(request)
    if _session_guard is not None:
        _session_guard(session, claims)
    return claims


def _decode_claims(request: Request) -> AccessTokenClaims:
    token = _parse_authorization_header(request.headers.get("Authorization"))
    try:
        payload = decode_access_token(token)
    except InvalidTokenError as exc:
        if exc.expired:
            raise ApiError(
                401,
                "session_expired",
                "Session expired. Please re-authenticate.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        raise ApiError(
            401,
            "refresh_invalid",
            "Authentication credentials are invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return AccessTokenClaims(
        employee_id=_require_string(payload, "employee_id"),
        session_id=_require_string(payload, "session_id"),
        device_id=_require_string(payload, "device_id"),
        role=_require_string(payload, "role"),
        tenant_id=_require_string(payload, "tenant_id"),
        issued_at=_parse_timestamp(payload, "iat"),
        access_token_expires_at=_parse_timestamp(payload, "exp"),
    )

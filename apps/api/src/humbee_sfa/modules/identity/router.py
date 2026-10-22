"""Identity HTTP routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from humbee_sfa.core.db import get_db_session
from humbee_sfa.core.deps import AccessTokenClaims, get_current_claims, register_session_guard
from humbee_sfa.modules.identity import schemas
from humbee_sfa.modules.identity.service import IdentityService, assert_live_session

router = APIRouter(prefix="/api/v1", tags=["Identity & Session"])

# Identity owns `identity_sessions`, so it supplies the persisted live-session check that
# every authenticated route in every module runs (R-IDN-21).
register_session_guard(assert_live_session)


def _request_ip(request: Request) -> str | None:
    return request.client.host if request.client is not None else None


@router.post("/auth/otp/request", response_model=schemas.OtpRequestResponse)
async def request_otp(
    body: schemas.OtpRequestBody,
    request: Request,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    raw_body = await request.body()
    status_code, payload = IdentityService(session).request_otp(
        phone_e164=body.phone_e164,
        purpose=body.purpose,
        client_device_id=body.client_device_id,
        requester_ip=_request_ip(request),
        user_agent=request.headers.get("User-Agent"),
        idempotency_key=idempotency_key,
        raw_body=raw_body,
    )
    return JSONResponse(status_code=status_code, content=payload)


@router.post("/auth/otp/verify", response_model=schemas.TokenResponse)
async def verify_otp(
    body: schemas.OtpVerifyBody,
    request: Request,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    raw_body = await request.body()
    status_code, payload = IdentityService(session).verify_otp(
        challenge_id=body.challenge_id,
        code=body.code,
        purpose=body.purpose,
        client_device_id=body.client_device_id,
        platform_=body.platform,
        app_version=body.app_version,
        requester_ip=_request_ip(request),
        user_agent=request.headers.get("User-Agent"),
        idempotency_key=idempotency_key,
        raw_body=raw_body,
    )
    return JSONResponse(status_code=status_code, content=payload)


@router.post("/auth/token/refresh", response_model=schemas.TokenResponse)
async def refresh_token(
    body: schemas.RefreshBody,
    request: Request,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    raw_body = await request.body()
    status_code, payload = IdentityService(session).refresh_token(
        refresh_token=body.refresh_token,
        client_device_id=body.client_device_id,
        requester_ip=_request_ip(request),
        user_agent=request.headers.get("User-Agent"),
        idempotency_key=idempotency_key,
        raw_body=raw_body,
    )
    return JSONResponse(status_code=status_code, content=payload)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: schemas.LogoutBody,
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
) -> Response:
    status_code, _ = IdentityService(session).logout(
        refresh_token=body.refresh_token,
        requester_ip=_request_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )
    return Response(status_code=status_code)


@router.get("/me", response_model=schemas.MeResponse)
def get_me(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    svc = IdentityService(session)
    return svc.get_me(claims=claims)


@router.get("/auth/manager-contact", response_model=schemas.ManagerContactResponse)
def get_manager_contact(
    challenge_id: Annotated[str, Query(pattern=schemas.ULID_PATTERN)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    svc = IdentityService(session)
    return svc.get_manager_contact(challenge_id=challenge_id)


@router.get("/auth/session", response_model=schemas.SessionIntrospectResponse)
def introspect_session(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    svc = IdentityService(session)
    return svc.introspect_session(claims=claims)


@router.get("/auth/config", response_model=schemas.AuthConfigResponse)
def get_auth_config(session: Annotated[Session, Depends(get_db_session)]) -> dict[str, int]:
    svc = IdentityService(session)
    return svc.get_auth_config()


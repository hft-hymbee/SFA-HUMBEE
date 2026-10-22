"""Attendance / Official-Work HTTP routes — M09 §10.

Handlers translate HTTP only; scope resolution and transaction ownership are the services'.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Path, Query, Response, status
from fastapi import Request as HttpRequest
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from humbee_sfa.core.db import get_db_session
from humbee_sfa.core.deps import AccessTokenClaims, get_current_claims
from humbee_sfa.modules.attendance import schemas
from humbee_sfa.modules.attendance.service import AttendanceService, OfficialWorkService

router = APIRouter(prefix="/api/v1", tags=["Attendance"])

IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", max_length=128)]
SessionId = Annotated[str, Path(min_length=26, max_length=26)]
JobId = Annotated[str, Path(min_length=1, max_length=26)]


@router.get("/attendance/today", response_model=schemas.AttendanceTodayResponse)
def get_today(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return AttendanceService(session).today(claims=claims)


@router.post(
    "/attendance/punches",
    response_model=schemas.AttendanceTodayResponse,
    status_code=status.HTTP_201_CREATED,
)
async def punch(
    body: schemas.PunchBody,
    request: HttpRequest,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    status_code, payload = AttendanceService(session).punch(
        claims=claims, body=body, idempotency_key=idempotency_key, raw_body=await request.body()
    )
    return JSONResponse(status_code=status_code, content=payload)


@router.get("/attendance/history", response_model=schemas.AttendanceHistoryResponse)
def get_history(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    month: Annotated[str, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")],
) -> dict[str, Any]:
    return AttendanceService(session).history(claims=claims, month=month)


@router.get("/attendance/team", response_model=schemas.TeamAttendanceResponse)
def get_team(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    business_date: Annotated[date, Query()],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    return AttendanceService(session).team(
        claims=claims, business_date=business_date, page=page, page_size=page_size
    )

# TODO(reporting): This currently creates only a queued export job. Implement the report worker
# and artifact storage/download flow before treating attendance export as complete.
@router.post(
    "/attendance/exports",
    response_model=schemas.ExportJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_export(
    body: schemas.ExportRequestBody,
    request: HttpRequest,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    status_code, payload = AttendanceService(session).request_export(
        claims=claims, body=body, idempotency_key=idempotency_key, raw_body=await request.body()
    )
    return JSONResponse(status_code=status_code, content=payload)


@router.get("/attendance/exports/{job_id}", response_model=schemas.ExportJobResponse)
def get_export(
    job_id: JobId,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return AttendanceService(session).get_export(claims=claims, job_id=job_id)


@router.get("/official-work/sessions/current", response_model=schemas.OfficialWorkSessionItem | None)
def get_current_official_work(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> Response:
    payload = OfficialWorkService(session).current(claims=claims)
    if payload is None:
        return JSONResponse(status_code=status.HTTP_200_OK, content=None)
    return JSONResponse(status_code=status.HTTP_200_OK, content=payload)


@router.post(
    "/official-work/sessions",
    response_model=schemas.OfficialWorkSessionItem,
    status_code=status.HTTP_201_CREATED,
)
async def start_official_work(
    body: schemas.OfficialWorkStartBody,
    request: HttpRequest,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    status_code, payload = OfficialWorkService(session).start(
        claims=claims, body=body, idempotency_key=idempotency_key, raw_body=await request.body()
    )
    return JSONResponse(status_code=status_code, content=payload)


@router.post("/official-work/sessions/{session_id}/end", response_model=schemas.OfficialWorkSessionItem)
async def end_official_work(
    session_id: SessionId,
    body: schemas.OfficialWorkEndBody,
    request: HttpRequest,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    status_code, payload = OfficialWorkService(session).end(
        claims=claims, session_id=session_id, body=body, idempotency_key=idempotency_key,
        raw_body=await request.body(),
    )
    return JSONResponse(status_code=status_code, content=payload)


@router.get("/official-work/sessions", response_model=schemas.OfficialWorkHistoryResponse)
def list_official_work(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    from_date: Annotated[date, Query(alias="from")],
    to_date: Annotated[date, Query(alias="to")],
) -> dict[str, Any]:
    return OfficialWorkService(session).history(claims=claims, from_date=from_date, to_date=to_date)

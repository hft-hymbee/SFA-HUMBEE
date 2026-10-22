"""Targets HTTP routes — M13 §10 (S-TGT1, S-LEAD1).

Setting only. `GET /targets/me`, `GET /targets/team` and `/achievement` are deliberately absent:
they exist to show achievement against a target, and Humbee's achievement capability (X-2/H9) has
no agreed request shape yet, so there is nothing truthful for them to return.

Handlers translate HTTP only; transactions and rules are the service's.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Path, Query
from fastapi import Request as HttpRequest
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from starlette.convertors import Convertor, register_url_convertor

from humbee_sfa.core.db import get_db_session
from humbee_sfa.core.deps import AccessTokenClaims, get_current_claims
from humbee_sfa.modules.targets import schemas
from humbee_sfa.modules.targets.service import TargetService


class _UlidPath(Convertor[str]):
    regex = r"[0-9A-HJKMNP-TV-Z]{26}"

    def convert(self, value: str) -> str:
        return value

    def to_string(self, value: str) -> str:
        return value


register_url_convertor("ulid", _UlidPath())

router = APIRouter(prefix="/api/v1", tags=["Targets"])

IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", max_length=128)]
TargetId = Annotated[str, Path(min_length=26, max_length=26)]


@router.get("/masters/manufacturers", response_model=schemas.ManufacturerRosterResponse)
def list_manufacturers(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """The manufacturer roster a sales target's lines are built from."""

    del claims
    return TargetService(session).list_manufacturers()


@router.get("/targets", response_model=schemas.TargetListResponse)
def list_targets(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    employee_id: Annotated[str, Query(min_length=1, max_length=26)],
    period_month: Annotated[date, Query()],
    target_type: Annotated[schemas.TargetType | None, Query(alias="type")] = None,
) -> dict[str, Any]:
    """S-TGT1 edit-mode load — the active targets an employee holds for one month."""

    return TargetService(session).list_targets(
        claims=claims,
        employee_id=employee_id,
        period_month=period_month,
        target_type=target_type,
    )


@router.get("/targets/roster", response_model=schemas.TargetRosterResponse)
def list_roster(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    period_month: Annotated[date | None, Query()] = None,
) -> dict[str, Any]:
    return TargetService(session).list_roster(claims=claims, period_month=period_month)


@router.get("/targets/{target_id:ulid}", response_model=schemas.TargetOut)
def get_target(
    target_id: TargetId,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return TargetService(session).get_target(claims=claims, target_id=target_id)


@router.post("/targets", response_model=schemas.TargetOut, status_code=201)
async def create_target(
    body: schemas.CreateTargetBody,
    request: HttpRequest,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    """S-TGT1 save. 409 when a target of that type already exists for the month — the client
    reloads and PUTs, rather than a second active target being created."""

    status_code, payload = TargetService(session).create_target(
        claims=claims,
        body=body,
        idempotency_key=idempotency_key,
        raw_body=await request.body(),
    )
    return JSONResponse(status_code=status_code, content=payload)


@router.put("/targets/{target_id:ulid}", response_model=schemas.TargetOut)
async def update_target(
    target_id: TargetId,
    body: schemas.UpdateTargetBody,
    request: HttpRequest,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Whole-target replacement, including its lines. `version` must match: 409 on conflict."""

    return TargetService(session).update_target(
        claims=claims,
        target_id=target_id,
        body=body,
        idempotency_key=idempotency_key,
        raw_body=await request.body(),
    )


@router.delete("/targets/{target_id:ulid}", response_model=schemas.RemoveTargetResponse)
async def remove_target(
    target_id: TargetId,
    request: HttpRequest,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Soft delete — the employee reads "No target" afterwards, and the row stays auditable."""

    return TargetService(session).remove_target(
        claims=claims,
        target_id=target_id,
        idempotency_key=idempotency_key,
        raw_body=await request.body(),
    )


@router.post("/leads", response_model=schemas.LeadOut, status_code=201)
async def capture_lead(
    body: schemas.CaptureLeadBody,
    request: HttpRequest,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    """S-LEAD1 save — a salesperson captures a prospective business as a lead for follow-up."""

    status_code, payload = TargetService(session).capture_lead(
        claims=claims,
        body=body,
        idempotency_key=idempotency_key,
        raw_body=await request.body(),
    )
    return JSONResponse(status_code=status_code, content=payload)

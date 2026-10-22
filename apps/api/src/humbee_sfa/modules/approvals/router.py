"""Approvals HTTP routes.

Handlers validate and translate HTTP only: authorisation is the service's resolved `ScopeContext`
plus `policies.can_decide`, transaction ownership is the service's, and errors leave as raised
`ApiError`s for the application-level handlers to envelope. There is no create endpoint here by
design — a request is created by the subject's own endpoint calling `approvals.service.create`, and
the decision endpoints below are the only way a request changes state.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Path, Query, status
from fastapi import Request as HttpRequest
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from humbee_sfa.core.db import get_db_session
from humbee_sfa.core.deps import AccessTokenClaims, get_current_claims
from humbee_sfa.modules.approvals import schemas
from humbee_sfa.modules.approvals.service import ApprovalService
from humbee_sfa.platform.telemetry.middleware import get_request_id

router = APIRouter(prefix="/api/v1", tags=["Approvals"])

ApprovalId = Annotated[str, Path(min_length=1, max_length=26)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)]
# `If-Match` carries the `subject_version` the client is deciding on.
IfMatch = Annotated[int | None, Header(alias="If-Match", ge=1)]


@router.get("/approvals", response_model=schemas.ApprovalListResponse)
def list_approvals(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    approval_status: Annotated[
        str | None,
        Query(
            alias="status",
            pattern=r"^(pending|approved|approved_with_edits|auto_approved|rejected|withdrawn|expired)$",
        ),
    ] = None,
    subject_type: Annotated[
        str | None, Query(pattern=r"^(all|order|beat|leave|outlet)$")
    ] = None,
    assigned_to_me: Annotated[bool, Query()] = False,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    cursor: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> dict[str, Any]:
    return ApprovalService(session).list_requests(
        claims=claims,
        status=approval_status,
        subject_type_filter=subject_type,
        assigned_to_me=assigned_to_me,
        from_date=from_date,
        to_date=to_date,
        cursor=cursor,
        limit=limit,
    )


@router.get("/approvals/summary", response_model=schemas.ApprovalSummaryResponse)
def get_summary(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return ApprovalService(session).get_summary(claims=claims)


@router.get("/approvals/mine", response_model=schemas.ApprovalListResponse)
def list_my_requests(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    cursor: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> dict[str, Any]:
    return ApprovalService(session).list_mine(claims=claims, cursor=cursor, limit=limit)


@router.get("/approvals/{approval_id}", response_model=schemas.ApprovalDetailResponse)
def get_approval(
    approval_id: ApprovalId,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return ApprovalService(session).get_detail(claims=claims, approval_id=approval_id)


@router.get("/approvals/{approval_id}/timeline", response_model=schemas.TimelineResponse)
def get_timeline(
    approval_id: ApprovalId,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return ApprovalService(session).get_timeline(claims=claims, approval_id=approval_id)


@router.get(
    "/approvals/{approval_id}/editable-fields", response_model=schemas.EditableFieldsResponse
)
def get_editable_fields(
    approval_id: ApprovalId,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return ApprovalService(session).get_editable_fields(claims=claims, approval_id=approval_id)


@router.post(
    "/approvals/{approval_id}/approve",
    response_model=schemas.ApprovalListItem,
    status_code=status.HTTP_200_OK,
)
async def approve(
    approval_id: ApprovalId,
    body: schemas.ApproveBody,
    request: HttpRequest,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    if_match: IfMatch = None,
) -> JSONResponse:
    status_code, payload = await run_in_threadpool(
        ApprovalService(session).approve,
        claims=claims,
        approval_id=approval_id,
        note=body.note,
        idempotency_key=idempotency_key,
        raw_body=await request.body(),
        if_match=if_match,
        request_id=get_request_id(request),
    )
    return JSONResponse(status_code=status_code, content=payload)


@router.post("/approvals/{approval_id}/reject", response_model=schemas.ApprovalListItem)
async def reject(
    approval_id: ApprovalId,
    body: schemas.RejectBody,
    request: HttpRequest,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    if_match: IfMatch = None,
) -> JSONResponse:
    status_code, payload = await run_in_threadpool(
        ApprovalService(session).reject,
        claims=claims,
        approval_id=approval_id,
        reason=body.reason,
        idempotency_key=idempotency_key,
        raw_body=await request.body(),
        if_match=if_match,
        request_id=get_request_id(request),
    )
    return JSONResponse(status_code=status_code, content=payload)


@router.post("/approvals/{approval_id}/edit-and-approve", response_model=schemas.ApprovalListItem)
async def edit_and_approve(
    approval_id: ApprovalId,
    body: schemas.EditAndApproveBody,
    request: HttpRequest,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    if_match: IfMatch = None,
) -> JSONResponse:
    status_code, payload = await run_in_threadpool(
        ApprovalService(session).edit_and_approve,
        claims=claims,
        approval_id=approval_id,
        patch=body.patch,
        note=body.note,
        idempotency_key=idempotency_key,
        raw_body=await request.body(),
        if_match=if_match,
        request_id=get_request_id(request),
    )
    return JSONResponse(status_code=status_code, content=payload)


@router.post("/approvals/{approval_id}/withdraw", response_model=schemas.ApprovalListItem)
async def withdraw(
    approval_id: ApprovalId,
    body: schemas.WithdrawBody,
    request: HttpRequest,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    if_match: IfMatch = None,
) -> JSONResponse:
    status_code, payload = await run_in_threadpool(
        ApprovalService(session).withdraw,
        claims=claims,
        approval_id=approval_id,
        reason=body.reason,
        idempotency_key=idempotency_key,
        raw_body=await request.body(),
        if_match=if_match,
        request_id=get_request_id(request),
    )
    return JSONResponse(status_code=status_code, content=payload)

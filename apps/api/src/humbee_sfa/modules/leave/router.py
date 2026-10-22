"""Leave HTTP routes — M12 §10.

Handlers translate HTTP only; scope resolution and transaction ownership are the service's.

**There is no decision endpoint here, by design.** Approve, reject and withdraw all go through
`POST /api/v1/approvals/{approval_request_id}/{approve|reject|withdraw}` — adding a leave-specific
one would violate R-LV-01 and R-AP-01. S-LV2's Withdraw action posts to the approvals withdraw
route using the `approval_request_id` each row carries.

Deliberately not built, because no screen in this epic consumes them (M12 §10 marks every path
"inferred"): `GET /leave/requests/{id}` and `PATCH /leave/requests/{id}` (there is no leave-detail
screen at all — §12 Q3 — and v1 is withdraw-and-reapply, §12 Q16), `GET /leave/types` (a closed
v1 enum the client already ships — §12 Q8), `GET /leave/routing-preview` (M06-owned, and the
routing banner is not part of this story), `GET /leave/balances/{employee_id}` ("no screen consumes
this yet"), and `GET /leave/days` / `GET /leave/on-leave` (their consumers, M08/M09, do not exist —
`leave.service.is_on_leave` / `granted_leave_dates` already serve them in-process).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, status
from fastapi import Request as HttpRequest
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from humbee_sfa.core.db import get_db_session
from humbee_sfa.core.deps import AccessTokenClaims, get_current_claims
from humbee_sfa.modules.leave import schemas
from humbee_sfa.modules.leave.service import LeaveService
from humbee_sfa.platform.telemetry.middleware import get_request_id

router = APIRouter(prefix="/api/v1", tags=["Leave"])

IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", max_length=128)]


@router.get("/leave/balances/me", response_model=schemas.LeaveBalancesResponse)
def get_my_balances(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return LeaveService(session).get_my_balances(claims=claims)


@router.get("/leave/preview", response_model=schemas.LeavePreviewResponse)
def preview(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    leave_type: Annotated[schemas.LeaveTypeName, Query()],
    from_date: Annotated[date, Query()],
    to_date: Annotated[date, Query()],
) -> dict[str, Any]:
    return LeaveService(session).preview(
        claims=claims, leave_type=leave_type, from_date=from_date, to_date=to_date
    )


@router.get("/leave/requests/mine", response_model=schemas.LeaveRequestListResponse)
def list_my_requests(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    # The S-LV2 tabs, server-side (R-LV-17).
    request_status: Annotated[
        str, Query(alias="status", pattern=r"^(all|pending|history)$")
    ] = "all",
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    return LeaveService(session).list_mine(
        claims=claims, status_filter=request_status, limit=limit, offset=offset
    )


@router.get("/leave/team", response_model=schemas.TeamLeaveListResponse)
def list_team(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    # The S-LV3 filter chips, server-side (R-LV-17). `approved` and `auto_approved` are distinct.
    request_status: Annotated[
        str, Query(alias="status", pattern=r"^(all|pending|approved|auto_approved|rejected)$")
    ] = "all",
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    return LeaveService(session).list_team(
        claims=claims, status_filter=request_status, limit=limit, offset=offset
    )


@router.post(
    "/leave/requests",
    response_model=schemas.LeaveRequestItem,
    status_code=status.HTTP_201_CREATED,
)
async def submit_leave(
    body: schemas.SubmitLeaveBody,
    request: HttpRequest,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    # R-LV-10: the returned status may be `auto_approved`, not only `pending`.
    status_code, payload = LeaveService(session).submit(
        claims=claims,
        body=body,
        idempotency_key=idempotency_key,
        raw_body=await request.body(),
        request_id=get_request_id(request),
    )
    return JSONResponse(status_code=status_code, content=payload)

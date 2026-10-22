"""Org HTTP routes.

These handlers only validate and translate HTTP. Authorisation is the service's resolved
`ScopeContext`, transaction ownership is the service's, and errors leave as raised `ApiError`s for
the application-level handlers to envelope.
"""

from __future__ import annotations

import secrets
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Path, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from humbee_sfa.core.db import get_db_session
from humbee_sfa.core.deps import AccessTokenClaims, get_current_claims
from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.core.settings import get_settings
from humbee_sfa.modules.org import schemas
from humbee_sfa.modules.org.service import OrgService
from humbee_sfa.platform.telemetry.middleware import get_request_id

router = APIRouter(prefix="/api/v1", tags=["Organization & Workforce"])

EmployeeId = Annotated[str, Path(min_length=1, max_length=26)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", max_length=128)]
ApiKey = Annotated[str, Header(alias="api-key", max_length=512)]


@router.get("/org/employees", response_model=schemas.EmployeeListResponse)
def list_employees(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    q: Annotated[str | None, Query(max_length=120)] = None,
    # Roster facets are All / Sales / Managers / Inactive: an Admin holds no
    # position in the reporting tree and is not a row here, so it is not a filter value either.
    role: Annotated[str | None, Query(pattern=r"^(sales_person|manager)$")] = None,
    employee_status: Annotated[
        str | None, Query(alias="status", pattern=r"^(active|inactive)$")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> dict[str, Any]:
    return OrgService(session).list_employees(
        claims=claims,
        search=q,
        role_code=role,
        status=employee_status,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/org/employees",
    response_model=schemas.EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_employee(
    body: schemas.CreateEmployeeBody,
    request: Request,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    status_code, payload = OrgService(session).create_employee(
        claims=claims,
        body=body,
        idempotency_key=idempotency_key,
        raw_body=await request.body(),
        request_id=get_request_id(request),
    )
    return JSONResponse(status_code=status_code, content=payload)


@router.post(
    "/org/admins",
    response_model=schemas.EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_admin(
    body: schemas.CreateAdminBody,
    request: Request,
    idempotency_key: IdempotencyKey,
    api_key: ApiKey,
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    """Create an Admin using the configured API key, without access-token authentication."""

    expected_api_key = get_settings().humbee_api_key
    if not expected_api_key or not secrets.compare_digest(api_key, expected_api_key):
        raise ApiError(status.HTTP_401_UNAUTHORIZED, "invalid_api_key", "Invalid API key.")

    status_code, payload = OrgService(session).create_admin(
        body=body,
        idempotency_key=idempotency_key,
        raw_body=await request.body(),
        request_id=get_request_id(request),
    )
    return JSONResponse(status_code=status_code, content=payload)


@router.get("/org/employees/{employee_id}", response_model=schemas.EmployeeResponse)
def get_employee(
    employee_id: EmployeeId,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return OrgService(session).get_employee_detail(claims=claims, employee_id=employee_id)


@router.patch("/org/employees/{employee_id}", response_model=schemas.EmployeeResponse)
def update_employee(
    employee_id: EmployeeId,
    body: schemas.UpdateEmployeeBody,
    request: Request,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return OrgService(session).update_employee(
        claims=claims,
        employee_id=employee_id,
        body=body,
        request_id=get_request_id(request),
    )


@router.post("/org/employees/{employee_id}/deactivate", response_model=schemas.EmployeeResponse)
async def deactivate_employee(
    employee_id: EmployeeId,
    body: schemas.DeactivateEmployeeBody,
    request: Request,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    status_code, payload = OrgService(session).deactivate_employee(
        claims=claims,
        employee_id=employee_id,
        reason=body.reason,
        idempotency_key=idempotency_key,
        raw_body=await request.body(),
        request_id=get_request_id(request),
    )
    return JSONResponse(status_code=status_code, content=payload)


@router.get(
    "/org/employees/{employee_id}/move-candidates",
    response_model=schemas.MoveCandidateListResponse,
)
def list_move_candidates(
    employee_id: EmployeeId,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return OrgService(session).list_move_candidates(claims=claims, employee_id=employee_id)


@router.post("/org/employees/{employee_id}/move", response_model=schemas.EmployeeResponse)
async def move_employee(
    employee_id: EmployeeId,
    body: schemas.MoveEmployeeBody,
    request: Request,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    status_code, payload = OrgService(session).move_employee(
        claims=claims,
        employee_id=employee_id,
        new_manager_employee_id=body.new_manager_employee_id,
        idempotency_key=idempotency_key,
        raw_body=await request.body(),
        request_id=get_request_id(request),
    )
    return JSONResponse(status_code=status_code, content=payload)


@router.get("/org/tree", response_model=schemas.TreeResponse)
def get_tree(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return OrgService(session).get_tree(claims=claims)

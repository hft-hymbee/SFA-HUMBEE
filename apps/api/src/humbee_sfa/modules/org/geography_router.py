"""Geography HTTP routes.

Validation and translation only: authorisation is the service's resolved `ScopeContext`, the
transaction is the service's, and errors leave as raised `ApiError`s for the application-level
handlers to envelope.

No Location-level route exists here on purpose — see the open-decision note at the top of
`geography_service.py`.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy.orm import Session

from humbee_sfa.core.db import get_db_session
from humbee_sfa.core.deps import AccessTokenClaims, get_current_claims
from humbee_sfa.modules.org import geography_schemas as schemas
from humbee_sfa.modules.org.geography_service import GeographyService
from humbee_sfa.platform.telemetry.middleware import get_request_id

router = APIRouter(prefix="/api/v1", tags=["Organization & Geography"])

EmployeeId = Annotated[str, Path(min_length=1, max_length=26)]


@router.get("/org/geography/zones", response_model=schemas.ZonesResponse)
def list_geography_zones(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return GeographyService(session).list_zones(claims=claims)


@router.get("/org/geography/states", response_model=schemas.StatesResponse)
def list_geography_states(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    zone_ids: Annotated[list[str] | None, Query()] = None,
) -> dict[str, Any]:
    return GeographyService(session).list_states(claims=claims, zone_ids=zone_ids or [])


@router.get("/org/geography/districts", response_model=schemas.DistrictsResponse)
def list_geography_districts(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    state_ids: Annotated[list[str] | None, Query()] = None,
) -> dict[str, Any]:
    return GeographyService(session).list_districts(claims=claims, state_ids=state_ids or [])


@router.get(
    "/org/employees/{employee_id}/geography-scope", response_model=schemas.GeoScopeResponse
)
def get_geography_scope(
    employee_id: EmployeeId,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return GeographyService(session).get_geography_scope(claims=claims, employee_id=employee_id)


@router.put(
    "/org/employees/{employee_id}/geography-scope", response_model=schemas.GeoScopeResponse
)
def assign_geography_scope(
    employee_id: EmployeeId,
    body: schemas.AssignGeoScopeBody,
    request: Request,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Full replacement of the employee's scope, so no `Idempotency-Key` is required: replaying
    the same body converges on the same row."""

    return GeographyService(session).assign_geography_scope(
        claims=claims,
        employee_id=employee_id,
        body=body,
        request_id=get_request_id(request),
    )

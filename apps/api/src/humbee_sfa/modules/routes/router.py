"""Routes/Visits HTTP routes — M08 §10.

Handlers translate HTTP only; transaction ownership and scope resolution are the service's.

Endpoints intentionally **not** built, matching the beats/attendance routers' precedent of naming
skips explicitly:

- `GET /route-plans/beat-options` — S-ROUTE2b's "assigned today vs other" grouping is presentation
  over data the client already has from `GET /beats?status=approved` (M07); no new SFA fact is
  computed, so the client can group client-side rather than SFA growing a second beat-listing
  endpoint. `POST /route-plans/switch-beat` still derives `run_origin` server-side (R-RTE-11),
  which is the part that actually has to be authoritative.
- `PATCH /route-plans/{id}` — no screen reorders/edits a saved plan's stops after creation; the
  documented flows only ever create a plan (S-ROUTE2a) or replace it wholesale (S-ROUTE2b).
- `POST /routes/sequence-preview` — a PostGIS per-leg distance preview with no consuming screen
  logic built yet; stop distances are written when stops are appended to a plan.
- `GET /outlets/{outlet_ref}/visit-snapshot` and `/activity` — Humbee-proxy reads owned by M14's
  outlet projection/ACL, not this module; not part of Story 3.3.
- `POST /uploads` — object-storage signed URLs depend on epic 06 (not done yet), matching
  Story 3.2's precedent for `attendance_export_jobs`. Outcome photos stay unsupported until then
  (R-RTE-18 already treats a missing photo as never blocking).
- `DELETE /combined-visits/{id}` — no screen offers cancelling a scheduled tag-along yet (M08
  §12.26 is an open question); adding a cancel path with no caller would be speculative.
- `DELETE /visits/{id}` — deliberately absent; visits are never deleted (R-RTE-35).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Path, Query
from fastapi import Request as HttpRequest
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from humbee_sfa.core.clock import utc_now
from humbee_sfa.core.db import get_db_session, get_engine, get_sessionmaker
from humbee_sfa.core.deps import AccessTokenClaims, get_current_claims
from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.modules.org.scope import OrgResource, Scope, ScopeResolver
from humbee_sfa.modules.routes import schemas
from humbee_sfa.modules.routes.service import RouteService
from humbee_sfa.modules.routes.sweep import SWEEP_JOB_NAME, run_end_of_day_sweep
from humbee_sfa.platform.models.sweep_run import SweepRun
from humbee_sfa.platform.scheduler import SupervisedJobRunner

router = APIRouter(prefix="/api/v1", tags=["Routes"])

VisitId = Annotated[str, Path(min_length=1, max_length=26)]
CombinedVisitId = Annotated[str, Path(min_length=1, max_length=26)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", max_length=128)]


@router.get("/route-plans/current", response_model=schemas.RoutePlanResponse)
def get_current_route_plan(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    business_date: Annotated[date | None, Query()] = None,
    employee_id: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    """S-ROUTE1/3. A manager/admin may pass `employee_id` for S-ROUTE5's drill-down."""

    return RouteService(session).get_day(
        claims=claims, business_date=business_date, employee_id=employee_id
    )


@router.post("/route-plans/switch-beat", response_model=schemas.RoutePlanResponse)
async def start_beat(
    body: schemas.SwitchBeatBody,
    request: HttpRequest,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    """Transition #12 (S-ROUTE2b)."""

    status_code, payload = RouteService(session).start_beat(
        claims=claims, body=body, idempotency_key=idempotency_key, raw_body=await request.body(),
    )
    return JSONResponse(status_code=status_code, content=payload)


@router.get("/routes/unplanned-outlets", response_model=list[schemas.UnplannedOutletItem])
def list_unplanned_outlets(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[dict[str, Any]]:
    """Assigned outlets available as an unplanned stop. Today's route is excluded client-side."""

    return RouteService(session).list_unplanned_outlets(claims=claims)


@router.get("/route-plans/days", response_model=schemas.RouteDaysResponse)
def route_days(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    employee_id: Annotated[str, Query()],
    from_date: Annotated[date, Query(alias="from")],
    to_date: Annotated[date, Query(alias="to")],
) -> dict[str, Any]:
    """S-CVIS1's day picker (R-RTE-30)."""

    return RouteService(session).route_days(
        claims=claims, employee_id=employee_id, from_date=from_date, to_date=to_date
    )


@router.post("/visits/{visit_id}/check-in", response_model=schemas.VisitResponse)
async def check_in(
    visit_id: VisitId,
    body: schemas.CheckInBody,
    request: HttpRequest,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    """Transitions #2/#3 (S-ROUTE4 entry, or "Add unplanned visit")."""

    status_code, payload = RouteService(session).check_in(
        claims=claims, visit_id=visit_id, body=body, idempotency_key=idempotency_key,
        raw_body=await request.body(),
    )
    return JSONResponse(status_code=status_code, content=payload)


@router.post(
    "/visits/{visit_id}/outlet-coordinates", response_model=schemas.CoordinateCorrectionResponse
)
async def submit_coordinate_correction(
    visit_id: VisitId,
    body: schemas.CoordinateCorrectionBody,
    request: HttpRequest,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    """O-4 field pin correction."""

    status_code, payload = RouteService(session).submit_coordinate_correction(
        claims=claims, visit_id=visit_id, body=body, idempotency_key=idempotency_key,
        raw_body=await request.body(),
    )
    return JSONResponse(status_code=status_code, content=payload)


@router.post("/visits/{visit_id}/outcome", response_model=schemas.VisitResponse)
async def log_outcome(
    visit_id: VisitId,
    body: schemas.OutcomeBody,
    request: HttpRequest,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    """Transition #6 (S-VISIT1)."""

    status_code, payload = RouteService(session).log_outcome(
        claims=claims, visit_id=visit_id, body=body, idempotency_key=idempotency_key,
        raw_body=await request.body(),
    )
    return JSONResponse(status_code=status_code, content=payload)


@router.get("/visits/{visit_id}/outcome", response_model=schemas.VisitOutcomeDetail)
def get_visit_outcome(
    visit_id: VisitId,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Read-back for S-VISIT1 — reopening a completed visit shows its recorded outcome."""

    return RouteService(session).get_visit_outcome(claims=claims, visit_id=visit_id)


@router.get("/outlets/{outlet_ref}/last-visit", response_model=schemas.LastOutletVisitResponse)
def get_last_outlet_visit(
    outlet_ref: Annotated[str, Path(min_length=1, max_length=64)],
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return RouteService(session).get_last_outlet_visit(claims=claims, outlet_ref=outlet_ref)


@router.post("/visits/{visit_id}/check-out", response_model=schemas.VisitResponse)
def check_out(
    visit_id: VisitId,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """"End visit & check out" (S-ROUTE4). `422 OUTCOME_REQUIRED` per R-RTE-15. Never mutates
    state (see `RouteService.check_out`), so no `Idempotency-Key` is required."""

    _, payload = RouteService(session).check_out(claims=claims, visit_id=visit_id)
    return payload


@router.get("/missed-visits", response_model=schemas.MissedVisitsResponse)
def list_missed_visits(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    employee_id: Annotated[str | None, Query()] = None,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
) -> dict[str, Any]:
    """S-VISIT2 — read-only audit trail (R-RTE-19). Defaults to the trailing 7 days ("this week")."""

    return RouteService(session).list_missed_visits(
        claims=claims, employee_id=employee_id, from_date=from_date, to_date=to_date
    )


@router.get("/coverage/team", response_model=schemas.CoverageResponse)
def coverage_team(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    business_date: Annotated[date, Query()],
    only_sales_person: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    """S-ROUTE5 (Manager `OWN_TREE` / Admin `ORG`, same path)."""

    return RouteService(session).coverage_team(
        claims=claims, business_date=business_date, only_sales_person=only_sales_person,
    )


@router.post("/combined-visits", response_model=schemas.CombinedVisitResponse, status_code=201)
async def create_combined_visit(
    body: schemas.CreateCombinedVisitBody,
    request: HttpRequest,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    """S-CVIS1."""

    status_code, payload = RouteService(session).create_combined_visit(
        claims=claims, body=body, idempotency_key=idempotency_key, raw_body=await request.body(),
    )
    return JSONResponse(status_code=status_code, content=payload)


@router.get("/combined-visits")
def list_combined_visits(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """S-CVIS1's "manager's scheduled and pending-feedback tag-alongs" list."""

    return RouteService(session).list_combined_visits(claims=claims)


@router.get("/combined-visits/{combined_visit_id}", response_model=schemas.CombinedVisitResponse)
def get_combined_visit(
    combined_visit_id: CombinedVisitId,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """S-CVIS2 entry."""

    return RouteService(session).get_combined_visit(claims=claims, combined_visit_id=combined_visit_id)


@router.post(
    "/combined-visits/{combined_visit_id}/feedback", response_model=schemas.CombinedVisitResponse
)
async def submit_combined_visit_feedback(
    combined_visit_id: CombinedVisitId,
    body: schemas.CombinedVisitFeedbackBody,
    request: HttpRequest,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    """S-CVIS2."""

    status_code, payload = RouteService(session).submit_combined_visit_feedback(
        claims=claims, combined_visit_id=combined_visit_id, body=body,
        idempotency_key=idempotency_key, raw_body=await request.body(),
    )
    return JSONResponse(status_code=status_code, content=payload)


@router.post("/admin/jobs/end-of-day-sweep", response_model=schemas.SweepRunResponse)
def trigger_end_of_day_sweep(
    business_date: Annotated[date, Query()],
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Operator-only manual trigger for `routes.end_of_day_sweep` (M08 §3b, §10). Not a product
    capability — no screen calls this; it is a manual recovery/re-run path beside the scheduled
    worker trigger."""

    scope = ScopeResolver.resolve_from_claims(claims, OrgResource.ACTIVITY_DATA)
    if scope.scope is not Scope.ORG:
        raise ApiError(403, "forbidden", "The end-of-day sweep is operator-only.")

    runner = SupervisedJobRunner(get_engine(), get_sessionmaker())
    runner.run(
        job_name=SWEEP_JOB_NAME,
        tenant_id=scope.tenant_id,
        business_date=business_date,
        body=lambda connection, run_id: run_end_of_day_sweep(
            connection,
            run_id,
            tenant_id=scope.tenant_id,
            business_date=business_date,
            now=utc_now(),
        ),
    )

    run_row = (
        session.query(SweepRun)
.filter(
            SweepRun.tenant_id == scope.tenant_id,
            SweepRun.sweep_type == SWEEP_JOB_NAME,
            SweepRun.business_date == business_date,
        )
.one_or_none()
    )
    return schemas.SweepRunResponse(
        business_date=business_date,
        status=run_row.status if run_row else "unknown",
        visits_missed=run_row.rows_affected if run_row else None,
    ).model_dump(mode="json")

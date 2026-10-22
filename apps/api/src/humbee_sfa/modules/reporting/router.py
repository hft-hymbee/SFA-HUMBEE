"""Reporting HTTP routes for KPI dashboard surfaces."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, Response
from sqlalchemy.orm import Session

from humbee_sfa.core.db import get_db_session
from humbee_sfa.core.deps import AccessTokenClaims, get_current_claims
from humbee_sfa.modules.reporting import schemas
from humbee_sfa.modules.reporting.exports import AdminReportsService
from humbee_sfa.modules.reporting.service import ReportingService

router = APIRouter(prefix="/api/v1/reporting", tags=["Reporting"])

KpiSurface = Annotated[schemas.ReportingKpiSurface, Path()]


@router.get("/kpi-surfaces/{surface}", response_model=schemas.KpiSurfaceResponse)
def get_kpi_surface(
    surface: KpiSurface,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    business_date: Annotated[date | None, Query()] = None,
) -> dict[str, Any]:
    return ReportingService(session).kpi_surface(
        claims=claims, surface=surface, business_date=business_date
    )


@router.get("/admin/coverage-trend", response_model=schemas.AdminCoverageTrendResponse)
def get_admin_coverage_trend(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    business_date: Annotated[date | None, Query()] = None,
    days: Annotated[int, Query(ge=1, le=31)] = 7,
) -> dict[str, Any]:
    return ReportingService(session).admin_coverage_trend(
        claims=claims, business_date=business_date, days=days
    )


DashboardPeriod = Annotated[schemas.DashboardPeriod, Query()]


@router.get("/dashboards/sales-person", response_model=schemas.SpDashboardKpisResponse)
def get_sales_person_dashboard(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    period: DashboardPeriod = "mtd",
) -> dict[str, Any]:
    """Sales Person visit/call KPIs, honouring `period`.

    Manufacturer-scoped target progress is a separate call — see
    `/dashboards/sales-person/targets` — so switching manufacturer doesn't
    re-run these queries.
    """
    return ReportingService(session).get_sp_dashboard_kpis(claims=claims, period=period)


@router.get("/dashboards/sales-person/targets", response_model=schemas.SpTargetsKpisResponse)
def get_sales_person_targets(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    manufacturer_id: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    """Sales Person dashboard: manufacturer-scoped target progress (always MTD)."""
    return ReportingService(session).get_sp_targets_kpis(
        claims=claims, manufacturer_id=manufacturer_id
    )


@router.get("/dashboards/sales-person/attention", response_model=schemas.SpAttentionResponse)
def get_sales_person_attention(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return ReportingService(session).get_sp_attention(claims=claims)


@router.get("/dashboards/manager", response_model=schemas.ManagerDashboardKpisResponse)
def get_manager_dashboard(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    period: DashboardPeriod = "mtd",
    manufacturer_id: Annotated[str | None, Query()] = None,
    designation_code: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    """Manager team dashboard.

    `team_metrics` honours `period`. `scatter`, `districts`, and `mom` are always MTD and
    whole-tree. `league` and `targets` are always MTD and scoped to one hierarchy level
    (`designation_code`, defaulting to one level below the caller) — see `designation_scope`.
    """
    return ReportingService(session).get_manager_dashboard_kpis(
        claims=claims,
        period=period,
        manufacturer_id=manufacturer_id,
        designation_code=designation_code,
    )


@router.get("/dashboards/admin", response_model=schemas.AdminDashboardKpisResponse)
def get_admin_dashboard(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    period: DashboardPeriod = "mtd",
    manufacturer_id: Annotated[str | None, Query()] = None,
    designation_code: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    """Admin org-wide dashboard.

    `org_metrics` honours `period`. `targets`, `targets_summary`,
    `manufacturer_movement`, `approval_latency`, and `mom` are always MTD;
    `targets_summary` and `manufacturer_movement` always span every manufacturer.
    `employee_progress` is always MTD; `designation_code` narrows it to one hierarchy
    level and defaults to `all` (every level, ordered by level then name) — see
    `designation_scope`.
    """
    return ReportingService(session).get_admin_dashboard_kpis(
        claims=claims,
        period=period,
        manufacturer_id=manufacturer_id,
        designation_code=designation_code,
    )


@router.get("/admin/reports/geography-mapping", response_model=None)
def download_geography_mapping_report(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> Response:
    return AdminReportsService(session).geography_mapping_report(claims=claims)


@router.get("/admin/reports/employee-hierarchy", response_model=None)
def download_employee_hierarchy_report(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> Response:
    return AdminReportsService(session).employee_hierarchy_report(claims=claims)


@router.get("/admin/reports/beats", response_model=None)
def download_beats_report(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> Response:
    return AdminReportsService(session).beats_report(claims=claims)


@router.get("/admin/reports/beat-outlets", response_model=None)
def download_beat_outlets_report(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> Response:
    return AdminReportsService(session).beat_outlets_report(claims=claims)


@router.get("/admin/reports/unassigned-outlets", response_model=None)
def download_unassigned_outlets_report(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> Response:
    return AdminReportsService(session).unassigned_outlets_report(claims=claims)


@router.get("/admin/reports/attendance", response_model=None)
def download_attendance_report(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    from_date: Annotated[date, Query()],
    to_date: Annotated[date, Query()],
) -> Response:
    return AdminReportsService(session).attendance_report(claims=claims, from_date=from_date, to_date=to_date)


CallsKpiScope = Annotated[schemas.CallsKpiScope, Path()]


@router.get("/kpis/calls/{scope}", response_model=schemas.CallsKpiResponse)
def get_calls_kpis(
    scope: CallsKpiScope,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    for_employee_id: Annotated[str | None, Query()] = None,
    business_date: Annotated[date | None, Query()] = None,
) -> dict[str, Any]:
    """One calls-KPI drill level (TC/PC/SC/UTC), today+MTD.

    `for_employee_id` roots the level at that employee; omitted, it roots at the
    caller (admin: the top-level managers). Rows are the root's direct reportees and
    `totals` is the root's own roll-up. The activity timeline stays on `coverage`.
    """
    return ReportingService(session).kpis_calls(
        claims=claims,
        scope_path=scope,
        for_employee_id=for_employee_id,
        business_date=business_date,
    )


"""Routes/Visits persistence. Thin, scoped, no business decisions.

Routes/visits are activity data: SELF for the owning Sales Person, OWN_TREE for their
manager, ORG for Admin — the same resolution table `beats` and `attendance` use.
"""

from __future__ import annotations

import typing
from dataclasses import dataclass
from datetime import date
from typing import Any

from geoalchemy2 import Geometry
from geoalchemy2.elements import WKTElement
from sqlalchemy import CursorResult, Numeric, Select, and_, case, cast, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from humbee_sfa.modules.org.scope import Scope, ScopeContext, apply_scope
from humbee_sfa.modules.routes.models.route_combined_visit import RouteCombinedVisit
from humbee_sfa.modules.routes.models.route_combined_visit_feedback import (
    RouteCombinedVisitFeedback,
)
from humbee_sfa.modules.routes.models.route_missed_visit_audit import RouteMissedVisitAudit
from humbee_sfa.modules.routes.models.route_outlet_coordinate_correction import (
    RouteOutletCoordinateCorrection,
)
from humbee_sfa.modules.routes.models.route_plan import RoutePlan
from humbee_sfa.modules.routes.models.route_stop import RouteStop
from humbee_sfa.modules.routes.models.route_visit import RouteVisit
from humbee_sfa.modules.routes.models.route_visit_outcome import RouteVisitOutcome
from humbee_sfa.platform.models.form_definition import FormDefinition

VISITED_STATES = ("visited_with_order", "visited_no_order")
OPEN_PLAN_STATES = ("scheduled", "in_progress")


@dataclass(frozen=True)
class DayTotals:
    planned: int
    planned_visited: int
    unplanned_visited: int
    productive: int

    @property
    def visited(self) -> int:
        return self.planned_visited + self.unplanned_visited

    @property
    def coverage_pct(self) -> int | None:
        denominator = self.planned + self.unplanned_visited
        return round(self.visited / denominator * 100) if denominator else None

    def __add__(self, other: DayTotals) -> DayTotals:
        return DayTotals(
            planned=self.planned + other.planned,
            planned_visited=self.planned_visited + other.planned_visited,
            unplanned_visited=self.unplanned_visited + other.unplanned_visited,
            productive=self.productive + other.productive,
        )


NO_ACTIVITY = DayTotals(planned=0, planned_visited=0, unplanned_visited=0, productive=0)


def _scoped(model: Any, scope: ScopeContext) -> Select[Any]:
    return apply_scope(
        select(model), scope, tenant_column=model.tenant_id, employee_id_column=model.employee_id
    ).where(model.is_active.is_(True))


# ---------------------------------------------------------------------------
# Route plans / stops
# ---------------------------------------------------------------------------


def get_active_plan(
    session: Session, *, tenant_id: str, employee_id: str, business_date: date
) -> RoutePlan | None:
    stmt = select(RoutePlan).where(
        RoutePlan.tenant_id == tenant_id,
        RoutePlan.employee_id == employee_id,
        RoutePlan.business_date == business_date,
        RoutePlan.is_active.is_(True),
    )
    return session.execute(stmt).scalar_one_or_none()


def lock_or_create_plan(
    session: Session,
    *,
    tenant_id: str,
    employee_id: str,
    business_date: date,
    beat_id: str,
    beat_version_id: str,
    created_by_employee_id: str,
    plan_id: str | None = None,
) -> RoutePlan:
    values: dict[str, Any] = {
        "tenant_id": tenant_id,
        "employee_id": employee_id,
        "business_date": business_date,
        "beat_id": beat_id,
        "beat_version_id": beat_version_id,
        "state": "scheduled",
        "created_by_employee_id": created_by_employee_id,
    }
    if plan_id is not None:
        values["id"] = plan_id
    session.execute(
        insert(RoutePlan)
        .values(**values)
        .on_conflict_do_nothing(index_elements=["tenant_id", "employee_id", "business_date"])
    )
    stmt = (
        select(RoutePlan)
        .where(
            RoutePlan.tenant_id == tenant_id,
            RoutePlan.employee_id == employee_id,
            RoutePlan.business_date == business_date,
            RoutePlan.is_active.is_(True),
        )
        .with_for_update()
    )
    return session.execute(stmt).scalar_one()


def get_plan(session: Session, *, scope: ScopeContext, plan_id: str) -> RoutePlan | None:
    stmt = _scoped(RoutePlan, scope).where(RoutePlan.id == plan_id)
    return session.execute(stmt).scalar_one_or_none()


def list_stops(session: Session, *, route_plan_id: str) -> list[RouteStop]:
    stmt = (
        select(RouteStop)
        .where(RouteStop.route_plan_id == route_plan_id)
        .order_by(RouteStop.sequence_no)
    )
    return list(session.execute(stmt).scalars().all())


def outlet_points(
    session: Session, *, tenant_id: str, outlet_refs: list[str]
) -> dict[str, WKTElement]:
    """`{outlet_ref: point}` from each outlet's latest accepted coordinate correction — the only
    outlet coordinate SFA stores; outlets without one are absent."""

    if not outlet_refs:
        return {}
    stmt = (
        select(
            RouteOutletCoordinateCorrection.humbee_outlet_id,
            RouteOutletCoordinateCorrection.longitude,
            RouteOutletCoordinateCorrection.latitude,
        )
        .where(
            RouteOutletCoordinateCorrection.tenant_id == tenant_id,
            RouteOutletCoordinateCorrection.humbee_outlet_id.in_(outlet_refs),
            RouteOutletCoordinateCorrection.status == "accepted",
            RouteOutletCoordinateCorrection.is_active.is_(True),
        )
        .distinct(RouteOutletCoordinateCorrection.humbee_outlet_id)
        .order_by(
            RouteOutletCoordinateCorrection.humbee_outlet_id,
            RouteOutletCoordinateCorrection.captured_at.desc(),
        )
    )
    return {
        outlet_ref: WKTElement(f"POINT({longitude} {latitude})", srid=4326)
        for outlet_ref, longitude, latitude in session.execute(stmt)
    }


def fill_stop_distances(session: Session, *, route_plan_id: str) -> None:
    """Write every stop's `distance_from_prev_km` in one statement: PostGIS distance (metres) to the
    previous stop's snapshot point, `NULL` for the first stop or when either point is missing."""

    previous_point = func.lag(RouteStop.snapshot_point).over(order_by=RouteStop.sequence_no)
    legs = (
        select(
            RouteStop.id.label("stop_id"),
            cast(func.ST_Distance(RouteStop.snapshot_point, previous_point) / 1000.0, Numeric(5, 1)).label(
                "distance_km"
            ),
        )
        .where(RouteStop.route_plan_id == route_plan_id)
        .subquery()
    )
    session.execute(
        update(RouteStop)
        .where(RouteStop.id == legs.c.stop_id)
        .values(distance_from_prev_km=legs.c.distance_km)
    )


def route_business_dates(
    session: Session, *, tenant_id: str, employee_id: str, from_date: date, to_date: date
) -> list[date]:
    """The combined-visit day picker: business dates the employee already has a live plan for."""

    stmt = (
        select(RoutePlan.business_date)
        .where(
            RoutePlan.tenant_id == tenant_id,
            RoutePlan.employee_id == employee_id,
            RoutePlan.is_active.is_(True),
            RoutePlan.business_date.between(from_date, to_date),
        )
        .distinct()
        .order_by(RoutePlan.business_date)
    )
    return [row[0] for row in session.execute(stmt).all()]


# ---------------------------------------------------------------------------
# Visits
# ---------------------------------------------------------------------------


def get_visit(session: Session, *, tenant_id: str, visit_id: str) -> RouteVisit | None:
    stmt = select(RouteVisit).where(
        RouteVisit.tenant_id == tenant_id, RouteVisit.id == visit_id, RouteVisit.is_active.is_(True)
    )
    return session.execute(stmt).scalar_one_or_none()


def get_active_visit(session: Session, *, tenant_id: str, employee_id: str) -> RouteVisit | None:
    stmt = select(RouteVisit).where(
        RouteVisit.tenant_id == tenant_id,
        RouteVisit.employee_id == employee_id,
        RouteVisit.state == "in_progress",
    )
    return session.execute(stmt).scalar_one_or_none()


def list_day_visits(
    session: Session, *, tenant_id: str, employee_id: str, business_date: date
) -> list[RouteVisit]:
    stmt = (
        select(RouteVisit)
        .where(
            RouteVisit.tenant_id == tenant_id,
            RouteVisit.employee_id == employee_id,
            RouteVisit.business_date == business_date,
            RouteVisit.is_active.is_(True),
        )
        .order_by(RouteVisit.created_at, RouteVisit.id)
    )
    return list(session.execute(stmt).scalars().all())


def list_open_day_visits(
    session: Session, *, tenant_id: str, business_date: date
) -> list[RouteVisit]:
    stmt = (
        select(RouteVisit)
        .where(
            RouteVisit.tenant_id == tenant_id,
            RouteVisit.business_date == business_date,
            RouteVisit.state.in_(OPEN_PLAN_STATES),
            RouteVisit.is_active.is_(True),
        )
        .order_by(RouteVisit.created_at, RouteVisit.id)
        .with_for_update()
    )
    return list(session.execute(stmt).scalars().all())


def attach_day_visits_to_plan(
    session: Session,
    *,
    tenant_id: str,
    employee_id: str,
    business_date: date,
    route_plan_id: str,
) -> int:
    stmt = (
        update(RouteVisit)
        .where(
            RouteVisit.tenant_id == tenant_id,
            RouteVisit.employee_id == employee_id,
            RouteVisit.business_date == business_date,
            RouteVisit.route_plan_id.is_(None),
            RouteVisit.is_active.is_(True),
        )
        .values(route_plan_id=route_plan_id)
    )
    result = typing.cast(CursorResult[Any], session.execute(stmt))
    return int(result.rowcount or 0)


def checkin_points_for_visits(
    session: Session, *, visit_ids: list[str],
) -> dict[str, tuple[float, float]]:
    """`{visit_id: (lat, lng)}` for visits with a recorded check-in GPS point. `ST_X`/`ST_Y` need a
    geometry, not a geography, hence the cast (both describe the same point)."""

    if not visit_ids:
        return {}
    checkin_geometry = cast(RouteVisit.checkin_gps, Geometry(geometry_type="POINT", srid=4326))
    stmt = select(
        RouteVisit.id, func.ST_Y(checkin_geometry), func.ST_X(checkin_geometry),
    ).where(RouteVisit.id.in_(visit_ids), RouteVisit.checkin_gps.is_not(None))
    return {row[0]: (row[1], row[2]) for row in session.execute(stmt)}


def outcomes_for_visits(
    session: Session, *, visit_ids: list[str],
) -> dict[str, RouteVisitOutcome]:
    """`{visit_id: RouteVisitOutcome}` — one closed-out visit's outcome, for the day-drill-down
    timeline's "what happened here in short"."""

    if not visit_ids:
        return {}
    stmt = select(RouteVisitOutcome).where(RouteVisitOutcome.visit_id.in_(visit_ids))
    return {row.visit_id: row for row in session.execute(stmt).scalars().all()}


def last_closed_outlet_visit(
    session: Session, *, tenant_id: str, humbee_outlet_id: str
) -> tuple[RouteVisit, RouteVisitOutcome] | None:
    stmt = (
        select(RouteVisit, RouteVisitOutcome)
        .join(RouteVisitOutcome, RouteVisitOutcome.visit_id == RouteVisit.id)
        .where(
            RouteVisit.tenant_id == tenant_id,
            RouteVisit.humbee_outlet_id == humbee_outlet_id,
            RouteVisit.state.in_(VISITED_STATES),
            RouteVisit.is_active.is_(True),
        )
        .order_by(RouteVisit.business_date.desc(), RouteVisit.checked_out_at.desc(), RouteVisit.id.desc())
        .limit(1)
    )
    row = session.execute(stmt).first()
    return (row[0], row[1]) if row else None


def get_confirmed_visit(
    session: Session, *, tenant_id: str, employee_id: str, humbee_outlet_id: str, business_date: date
) -> RouteVisit | None:
    """A visit that reached at least `in_progress` for this employee/outlet/day — R-CVIS check."""

    stmt = select(RouteVisit).where(
        RouteVisit.tenant_id == tenant_id,
        RouteVisit.employee_id == employee_id,
        RouteVisit.humbee_outlet_id == humbee_outlet_id,
        RouteVisit.business_date == business_date,
        RouteVisit.state.in_(("in_progress", *VISITED_STATES)),
        RouteVisit.is_active.is_(True),
    )
    return session.execute(stmt).scalars().first()


def find_scheduled_day_visit(
    session: Session,
    *,
    tenant_id: str,
    employee_id: str,
    business_date: date,
    outlet_ref: str,
) -> RouteVisit | None:
    stmt = (
        select(RouteVisit)
        .where(
            RouteVisit.tenant_id == tenant_id,
            RouteVisit.employee_id == employee_id,
            RouteVisit.business_date == business_date,
            RouteVisit.humbee_outlet_id == outlet_ref,
            RouteVisit.state == "scheduled",
            RouteVisit.route_stop_id.is_not(None),
            RouteVisit.is_active.is_(True),
        )
        .order_by(RouteVisit.created_at.desc())
    )
    return session.execute(stmt).scalars().first()


def list_missed_visits(
    session: Session,
    *,
    scope: ScopeContext,
    employee_id: str | None,
    from_date: date,
    to_date: date,
) -> list[tuple[RouteMissedVisitAudit, RouteStop | None]]:
    scoped_audits = _scoped(RouteMissedVisitAudit, scope).where(
        RouteMissedVisitAudit.business_date.between(from_date, to_date)
    )
    if employee_id is not None:
        scoped_audits = scoped_audits.where(RouteMissedVisitAudit.employee_id == employee_id)
    audits = scoped_audits.subquery()
    stmt = (
        select(RouteMissedVisitAudit, RouteStop)
        .join(audits, RouteMissedVisitAudit.id == audits.c.id)
        .outerjoin(
            RouteStop,
            and_(
                RouteStop.tenant_id == RouteMissedVisitAudit.tenant_id,
                RouteStop.visit_id == RouteMissedVisitAudit.visit_id,
            ),
        )
        .order_by(RouteMissedVisitAudit.business_date.desc())
    )
    return [(audit, stop) for audit, stop in session.execute(stmt).all()]


def count_visited_in_window(
    session: Session,
    *,
    scope: ScopeContext,
    employee_id: str | None,
    from_date: date,
    to_date: date,
    planned_only: bool = False,
) -> int:
    stmt = _scoped(RouteVisit, scope).where(
        RouteVisit.business_date.between(from_date, to_date), RouteVisit.state.in_(VISITED_STATES)
    )
    if planned_only:
        stmt = stmt.where(RouteVisit.route_stop_id.is_not(None))
    if employee_id is not None:
        stmt = stmt.where(RouteVisit.employee_id == employee_id)
    return int(session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one())


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------


def day_totals(
    session: Session, *, tenant_id: str, employee_ids: list[str], business_date: date
) -> dict[str, DayTotals]:
    if not employee_ids:
        return {}
    planned_stmt = (
        select(RoutePlan.employee_id, func.count(RouteStop.id))
        .join(RouteStop, RouteStop.route_plan_id == RoutePlan.id)
        .where(
            RoutePlan.tenant_id == tenant_id,
            RoutePlan.employee_id.in_(employee_ids),
            RoutePlan.business_date == business_date,
            RoutePlan.is_active.is_(True),
        )
        .group_by(RoutePlan.employee_id)
    )
    planned_by_employee = {
        employee_id: int(count)
        for employee_id, count in session.execute(planned_stmt).all()
    }
    visited_stmt = (
        select(
            RouteVisit.employee_id,
            func.sum(
                case(
                    (
                        and_(
                            RouteVisit.route_stop_id.is_not(None),
                            RouteVisit.state.in_(VISITED_STATES),
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("planned_visited"),
            func.sum(
                case(
                    (
                        and_(
                            RouteVisit.route_stop_id.is_(None),
                            RouteVisit.state.in_(VISITED_STATES),
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("unplanned_visited"),
            func.sum(
                case((RouteVisit.state == "visited_with_order", 1), else_=0)
            ).label("productive"),
        )
        .where(
            RouteVisit.tenant_id == tenant_id,
            RouteVisit.employee_id.in_(employee_ids),
            RouteVisit.business_date == business_date,
            RouteVisit.is_active.is_(True),
        )
        .group_by(RouteVisit.employee_id)
    )
    visits_by_employee = {
        employee_id: (int(planned_visited), int(unplanned_visited), int(productive))
        for employee_id, planned_visited, unplanned_visited, productive in session.execute(
            visited_stmt
        ).all()
    }
    return {
        employee_id: DayTotals(
            planned_by_employee.get(employee_id, 0),
            *visits_by_employee.get(employee_id, (0, 0, 0)),
        )
        for employee_id in employee_ids
    }


# ---------------------------------------------------------------------------
# Combined visits
# ---------------------------------------------------------------------------


def _combined_visit_stmt(scope: ScopeContext) -> Select[Any]:
    stmt = apply_scope(
        select(RouteCombinedVisit),
        scope,
        tenant_column=RouteCombinedVisit.tenant_id,
        employee_id_column=RouteCombinedVisit.manager_employee_id,
    ).where(RouteCombinedVisit.is_active.is_(True))
    if scope.scope is Scope.OWN_TREE and scope.actor_employee_id is not None:
        stmt = stmt.where(RouteCombinedVisit.manager_employee_id == scope.actor_employee_id)
    return stmt


def get_combined_visit(session: Session, *, scope: ScopeContext, combined_visit_id: str) -> RouteCombinedVisit | None:
    stmt = _combined_visit_stmt(scope).where(RouteCombinedVisit.id == combined_visit_id)
    return session.execute(stmt).scalar_one_or_none()


def list_combined_visits(session: Session, *, scope: ScopeContext) -> list[RouteCombinedVisit]:
    stmt = _combined_visit_stmt(scope).order_by(RouteCombinedVisit.scheduled_business_date.desc())
    return list(session.execute(stmt).scalars().all())


def list_scheduled_combined_visits_for_sales_person(
    session: Session, *, tenant_id: str, sales_person_employee_id: str, business_date: date,
) -> list[RouteCombinedVisit]:
    stmt = select(RouteCombinedVisit).where(
        RouteCombinedVisit.tenant_id == tenant_id,
        RouteCombinedVisit.sales_person_employee_id == sales_person_employee_id,
        RouteCombinedVisit.scheduled_business_date == business_date,
        RouteCombinedVisit.state == "scheduled",
        RouteCombinedVisit.is_active.is_(True),
    )
    return list(session.execute(stmt).scalars().all())


def list_scheduled_combined_visits_for_day(
    session: Session, *, tenant_id: str, business_date: date
) -> list[RouteCombinedVisit]:
    stmt = select(RouteCombinedVisit).where(
        RouteCombinedVisit.tenant_id == tenant_id,
        RouteCombinedVisit.scheduled_business_date == business_date,
        RouteCombinedVisit.state == "scheduled",
        RouteCombinedVisit.is_active.is_(True),
    )
    return list(session.execute(stmt).scalars().all())


def get_combined_visit_feedback(
    session: Session, *, tenant_id: str, combined_visit_id: str
) -> RouteCombinedVisitFeedback | None:
    stmt = select(RouteCombinedVisitFeedback).where(
        RouteCombinedVisitFeedback.tenant_id == tenant_id,
        RouteCombinedVisitFeedback.combined_visit_id == combined_visit_id,
        RouteCombinedVisitFeedback.is_active.is_(True),
    )
    return session.execute(stmt).scalar_one_or_none()


def get_or_create_form_definition(
    session: Session, *, tenant_id: str, form_key: str, schema_payload: dict[str, Any]
) -> FormDefinition:
    """Lazily provisions the one `platform_form_definitions` row a still-pending-schema form
    needs, mirroring `attendance.repository.get_or_create_form_definition`."""

    stmt = (
        select(FormDefinition)
        .where(FormDefinition.tenant_id == tenant_id, FormDefinition.form_key == form_key)
        .order_by(FormDefinition.version.desc())
        .limit(1)
    )
    existing = session.execute(stmt).scalar_one_or_none()
    if existing is not None:
        return existing
    row = FormDefinition(
        tenant_id=tenant_id, form_key=form_key, version=1, schema_payload=schema_payload, is_published=True
    )
    session.add(row)
    session.flush()
    return row

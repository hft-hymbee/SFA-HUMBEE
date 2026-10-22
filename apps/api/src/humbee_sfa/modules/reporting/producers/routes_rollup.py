"""Routes producer rollup — stream `routes`.

Recomputes `fact_employee_day` / `fact_employee_outlet_day`'s visit and plan columns from the
`routes` stream's own event log on every `visit_completed` / `route_plan_saved` event — never by
importing `routes.models` (forbidden by `pyproject.toml`'s "Modules must not import each other's
internals" contract) and never a `+= 1` counter.

`visit_completed` carries `{employee_id, business_date, outlet_ref, productive, planned,
visit_type, outlet_seconds, no_order_reason | order_ids}`, so planned-vs-unplanned,
telephonic-vs-physical and outlet time are read from it directly. `business_date` is the day of
the visit's check-in, matching the live route-day read; `planned` means the visit had a route stop
when the event was published. A visit linked to a stop after it closed publishes `visit_completed`
again, so the day's visits are the latest event per visit (`aggregate_id`). `outlet_seconds` is
`null` when the day-close sweep closed the visit and its real duration is unknown.

`route_plan_saved` carries `{employee_id, business_date, beat_id, run_origin, stop_count}`; its
`business_date` is the plan's target business date (plans can be saved for a future day), which is
why the plan fold reads it from the payload rather than the event's published-on date. A plan row
is mutable (`routes_plans` collapses to one row per employee/date; a re-save publishes another
`route_plan_saved` with the same `aggregate_id`), so the day's planned count is the sum of
`stop_count` over each distinct plan's most recent event, never a running total.

`combined_visit_feedback_submitted`'s payload carries only `{overall_rating}` — no outlet,
employee or visit id — so CVIS cannot be derived from this event alone; not handled here rather
than guessed.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from humbee_sfa.modules.reporting.models import FactEmployeeOutletDay
from humbee_sfa.modules.reporting.producers.event_log import latest_payload_day_events
from humbee_sfa.modules.reporting.projector import (
    upsert_fact_employee_day,
    upsert_fact_employee_outlet_day,
)
from humbee_sfa.platform.models import DomainEvent

STREAM = "routes"
VISIT_COMPLETED = "visit_completed"
ROUTE_PLAN_SAVED = "route_plan_saved"


def apply(session: Session, event: DomainEvent) -> None:
    """Fold one `routes` event by recomputing that employee/day's visit + plan columns."""

    payload = event.payload
    if event.event_type == VISIT_COMPLETED:
        business_date = date.fromisoformat(payload["business_date"])
    elif event.event_type == ROUTE_PLAN_SAVED:
        business_date = _plan_business_date(payload, event)
    else:
        return
    _recompute_day(
        session,
        tenant_id=event.tenant_id,
        employee_id=payload["employee_id"],
        business_date=business_date,
        last_event_at=event.occurred_at,
    )


def recompute_employee_day(
    session: Session, *, tenant_id: str, employee_id: str, business_date: date
) -> None:
    """Recompute one employee/day's visit + plan columns from the event log (backfill/replay).

    Same recompute as a live event fold, minus the event stamp: `last_event_at` stays whatever the
    log last set (see `upsert_fact_employee_day`). Idempotent.
    """

    _recompute_day(
        session,
        tenant_id=tenant_id,
        employee_id=employee_id,
        business_date=business_date,
        last_event_at=None,
    )


def _recompute_day(
    session: Session,
    *,
    tenant_id: str,
    employee_id: str,
    business_date: date,
    last_event_at: datetime | None,
) -> None:
    visits = [
        event.payload
        for event in latest_payload_day_events(
            session,
            stream=STREAM,
            tenant_id=tenant_id,
            employee_id=employee_id,
            business_date=business_date,
            event_type=VISIT_COMPLETED,
        )
    ]
    planned_visits = [visit for visit in visits if visit["planned"]]
    telephonic_count = _telephonic_count(visits)

    upsert_fact_employee_day(
        session,
        tenant_id=tenant_id,
        employee_id=employee_id,
        business_date=business_date,
        last_event_at=last_event_at,
        fields={
            "visits_total": len(visits),
            "visits_physical": len(visits) - telephonic_count,
            "visits_telephonic": telephonic_count,
            "productive_visits": sum(1 for visit in visits if visit["productive"]),
            "unplanned_visits": len(visits) - len(planned_visits),
            "planned_outlets": _planned_outlets(
                session, tenant_id=tenant_id, employee_id=employee_id, business_date=business_date
            ),
            "visited_planned_outlets": len({visit["outlet_ref"] for visit in planned_visits}),
            "outlet_seconds": sum(visit["outlet_seconds"] or 0 for visit in visits),
        },
    )

    visits_by_outlet: dict[str, list[dict[str, Any]]] = {}
    for visit in visits:
        visits_by_outlet.setdefault(visit["outlet_ref"], []).append(visit)
    for outlet_ref, outlet_visits in visits_by_outlet.items():
        outlet_telephonic_count = _telephonic_count(outlet_visits)
        upsert_fact_employee_outlet_day(
            session,
            tenant_id=tenant_id,
            employee_id=employee_id,
            business_date=business_date,
            humbee_outlet_id=outlet_ref,
            fields={
                "visits_physical": len(outlet_visits) - outlet_telephonic_count,
                "visits_telephonic": outlet_telephonic_count,
                "is_scheduled": any(visit["planned"] for visit in outlet_visits),
            },
        )
    _clear_idle_outlet_days(
        session,
        tenant_id=tenant_id,
        employee_id=employee_id,
        business_date=business_date,
        visited_outlet_ids=set(visits_by_outlet),
    )


def _telephonic_count(visits: list[dict[str, Any]]) -> int:
    return sum(1 for visit in visits if visit["visit_type"] == "telephonic")


def _clear_idle_outlet_days(
    session: Session,
    *,
    tenant_id: str,
    employee_id: str,
    business_date: date,
    visited_outlet_ids: set[str],
) -> None:
    """Zero the visit columns on outlet-day rows the day no longer has visits for, and delete the
    row once the orders stream has nothing on it either."""

    rows = (
        session.execute(
            select(FactEmployeeOutletDay).where(
                FactEmployeeOutletDay.tenant_id == tenant_id,
                FactEmployeeOutletDay.employee_id == employee_id,
                FactEmployeeOutletDay.business_date == business_date,
            )
        )
        .scalars()
        .all()
    )
    for row in rows:
        if row.humbee_outlet_id in visited_outlet_ids:
            continue
        row.visits_physical = 0
        row.visits_telephonic = 0
        row.is_scheduled = False
        if not (row.orders_count or row.net_value_paise or row.lines_count):
            session.delete(row)


def _plan_business_date(payload: dict[str, object], event: DomainEvent) -> date:
    try:
        return date.fromisoformat(str(payload["business_date"]))
    except (KeyError, TypeError, ValueError):
        return event.business_date


def _planned_outlets(
    session: Session, *, tenant_id: str, employee_id: str, business_date: date
) -> int:
    """The day's planned-stop count: sum of `stop_count` over the latest `route_plan_saved` event
    per distinct plan. A re-saved plan publishes again with the same `aggregate_id`, so the most
    recent event per plan is the authoritative cumulative total."""

    return sum(
        int(event.payload.get("stop_count") or 0)
        for event in latest_payload_day_events(
            session,
            stream=STREAM,
            tenant_id=tenant_id,
            employee_id=employee_id,
            business_date=business_date,
            event_type=ROUTE_PLAN_SAVED,
        )
    )

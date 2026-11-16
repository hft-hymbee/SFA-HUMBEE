"""Business profiler (BP) filled-outlet counts over the distinct outlets visited.

An outlet counts as filled when its % at the end of the visited day is at or above
`business_profiler_filled_threshold_pct`; an outlet with no % counts as not filled.

- A day is frozen once the day-close job (`business_profiler_close`) has run for it: its
  `fact_employee_outlet_day.business_profiler_filled` flags and
  `fact_employee_day.business_profiler_filled_outlet_count` are then the answer.
- Any other day (today, or a past day not frozen yet) is computed live: the day's visited outlets
  from the route tables, each outlet's % as of the day's end from the BP history. Humbee's push
  keeps that history current, so today's numbers move without a visit. No Humbee call is made here.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from humbee_sfa.core.settings import Settings
from humbee_sfa.modules.outlets import service as outlets_service
from humbee_sfa.modules.reporting.models import FactEmployeeOutletDay
from humbee_sfa.modules.routes.service import RouteService
from humbee_sfa.platform.models import SweepRun

DAY_CLOSE_JOB_NAME = "reporting.business_profiler_day_close"

# Per employee: each distinct visited outlet -> (last visited day in the range, filled at that day's end).
OutletStatuses = dict[str, dict[str, tuple[date, bool]]]


@dataclass(frozen=True)
class BpCounts:
    filled: int
    not_filled: int


def is_filled(pct: int | None, threshold: int) -> bool:
    return pct is not None and pct >= threshold


def frozen_dates(session: Session, *, tenant_id: str, from_date: date, to_date: date) -> set[date]:
    return set(
        session.scalars(
            select(SweepRun.business_date).where(
                SweepRun.tenant_id == tenant_id,
                SweepRun.sweep_type == DAY_CLOSE_JOB_NAME,
                SweepRun.status == "succeeded",
                SweepRun.business_date.between(from_date, to_date),
            )
        )
    )


def live_day_statuses(
    session: Session,
    *,
    settings: Settings,
    tenant_id: str,
    business_date: date,
    employee_ids: list[str] | None,
) -> dict[str, dict[str, bool]]:
    """Per employee, each outlet visited on `business_date` -> filled at the day's end (live)."""

    visited = RouteService(session).visited_outlets_by_employee(
        tenant_id=tenant_id, business_date=business_date, employee_ids=employee_ids
    )
    outlet_ids = sorted({outlet for outlets in visited.values() for outlet in outlets})
    pct = outlets_service.business_profiler_as_of(
        session,
        tenant_id=tenant_id,
        outlet_ids=outlet_ids,
        business_date=business_date,
        day_boundary_hour_ist=settings.day_boundary_hour_ist,
    )
    threshold = settings.business_profiler_filled_threshold_pct
    return {
        employee_id: {outlet: is_filled(pct.get(outlet), threshold) for outlet in outlets}
        for employee_id, outlets in visited.items()
    }


def outlet_statuses(
    session: Session,
    *,
    settings: Settings,
    tenant_id: str,
    employee_ids: list[str],
    from_date: date,
    to_date: date,
) -> OutletStatuses:
    """Each employee's distinct visited outlets over `[from_date, to_date]`, with the filled status
    at the end of the outlet's last visited day. Frozen days come from the facts, the rest live."""

    result: OutletStatuses = {}
    if not employee_ids or to_date < from_date:
        return result

    def keep(employee_id: str, outlet: str, day: date, filled: bool) -> None:
        current = result.setdefault(employee_id, {}).get(outlet)
        if current is None or current[0] < day:
            result[employee_id][outlet] = (day, filled)

    frozen = frozen_dates(session, tenant_id=tenant_id, from_date=from_date, to_date=to_date)
    if frozen:
        fact = FactEmployeeOutletDay
        for employee_id, outlet, day, filled in session.execute(
            select(fact.employee_id, fact.humbee_outlet_id, fact.business_date, fact.business_profiler_filled).where(
                fact.tenant_id == tenant_id,
                fact.employee_id.in_(employee_ids),
                fact.business_date.in_(frozen),
                fact.visits_physical + fact.visits_telephonic > 0,
            )
        ).all():
            keep(employee_id, outlet, day, bool(filled))

    day = from_date
    while day <= to_date:
        if day not in frozen:
            for employee_id, outlets in live_day_statuses(
                session, settings=settings, tenant_id=tenant_id, business_date=day, employee_ids=employee_ids
            ).items():
                for outlet, filled in outlets.items():
                    keep(employee_id, outlet, day, filled)
        day += timedelta(days=1)
    return result


def count(statuses: OutletStatuses, employee_ids: Iterable[str]) -> BpCounts:
    """Distinct outlets across `employee_ids` (an outlet two of them visited counts once, with the
    status of its latest visited day)."""

    merged: dict[str, tuple[date, bool]] = {}
    for employee_id in employee_ids:
        for outlet, (day, filled) in statuses.get(employee_id, {}).items():
            if outlet not in merged or merged[outlet][0] < day:
                merged[outlet] = (day, filled)
    filled = sum(1 for _, is_bp_filled in merged.values() if is_bp_filled)
    return BpCounts(filled=filled, not_filled=len(merged) - filled)

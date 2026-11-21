"""Business profiler (BP) filled-outlet counts over the distinct outlets visited.

The period only picks which outlets count: the distinct outlets visited in it (planned or unplanned,
physical or telephonic). Whether each is filled is its **current** %, at or above
`business_profiler_filled_threshold_pct`; an outlet with no % counts as not filled.

The current % is the latest `outlets_business_profiler_history` row (kept current by Humbee's push).
An outlet with no row yet is fetched from Humbee once and recorded. The day-close job still freezes
each day's end-of-day % into the facts, but no read here uses them.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from humbee_sfa.core.settings import Settings
from humbee_sfa.modules.outlets.service import OutletReadService, is_filled
from humbee_sfa.modules.routes.service import RouteService
from humbee_sfa.platform.models import SweepRun

DAY_CLOSE_JOB_NAME = "reporting.business_profiler_day_close"


@dataclass(frozen=True)
class BpCounts:
    filled: int
    not_filled: int


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


# Total Humbee fallback wait per request: screens must not hang, a report download can wait.
SCREEN_BUDGET_S = 3.0
REPORT_BUDGET_S = 30.0

# (employee_id, business_date) -> distinct outlets visited that day.
VisitedOutlets = dict[tuple[str, date], set[str]]


def visited_by_employee_day(
    session: Session,
    *,
    tenant_id: str,
    employee_ids: list[str] | None,
    from_date: date,
    to_date: date,
) -> VisitedOutlets:
    return RouteService(session).visited_outlets_by_employee_day(
        tenant_id=tenant_id, employee_ids=employee_ids, from_date=from_date, to_date=to_date
    )


def filled_by_outlet(
    session: Session,
    *,
    settings: Settings,
    tenant_id: str,
    outlet_ids: Iterable[str],
    budget_s: float,
) -> tuple[dict[str, bool], bool]:
    """Each outlet's current filled status, and whether Humbee answered for every outlet it was
    asked about. May end the caller's read transaction (Humbee fallback). An outlet with no known %
    counts as not filled; only one Humbee did not answer for (failure, time limit) makes the result
    incomplete — one it answered for but left out does not."""

    refs = sorted(set(outlet_ids))
    if not refs:
        return {}, True
    pct, unanswered = OutletReadService(session, settings=settings).current_business_profiler(
        tenant_id=tenant_id, outlet_ids=refs, budget_s=budget_s
    )
    threshold = settings.business_profiler_filled_threshold_pct
    return {ref: is_filled(pct.get(ref), threshold) for ref in refs}, unanswered == 0


def outlets_of(visited: VisitedOutlets) -> set[str]:
    return {outlet for outlets in visited.values() for outlet in outlets}


def count(visited: VisitedOutlets, filled: dict[str, bool], employee_ids: Iterable[str]) -> BpCounts:
    """Distinct outlets the employees visited (an outlet two of them visited counts once)."""

    wanted = set(employee_ids)
    outlets = {
        outlet
        for (employee_id, _), day_outlets in visited.items()
        if employee_id in wanted
        for outlet in day_outlets
    }
    filled_count = sum(1 for outlet in outlets if filled.get(outlet, False))
    return BpCounts(filled=filled_count, not_filled=len(outlets) - filled_count)

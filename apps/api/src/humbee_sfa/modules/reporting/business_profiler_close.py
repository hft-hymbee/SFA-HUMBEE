"""Day-close freeze of business profiler counts, run by the end-of-day sweep worker.

For the business date just closed: pull every visited outlet's % from Humbee once (the safety net
for a lost push or an admin change Humbee never pushes), record it as that day's evidence, then
recompute each visiting employee's day so the BP fact columns are written. Raises if Humbee does not
answer; the run is recorded failed and the worker retries it on its next poll.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from humbee_sfa.core.db import transaction
from humbee_sfa.modules.outlets.service import OutletReadService
from humbee_sfa.modules.reporting.business_profiler import DAY_CLOSE_JOB_NAME
from humbee_sfa.modules.reporting.producers import routes_rollup
from humbee_sfa.modules.routes.service import RouteService

__all__ = ["DAY_CLOSE_JOB_NAME", "run_business_profiler_day_close"]


def run_business_profiler_day_close(
    connection: Connection, run_id: str, *, tenant_id: str, business_date: date
) -> int:
    del run_id
    with Session(bind=connection, autoflush=False, expire_on_commit=False) as session:
        with transaction(session):
            visited = RouteService(session).visited_outlets_by_employee(
                tenant_id=tenant_id, business_date=business_date
            )
            outlet_ids = sorted({outlet for outlets in visited.values() for outlet in outlets})
            OutletReadService(session).pull_business_profiler_for_day(
                tenant_id=tenant_id, outlet_ids=outlet_ids, business_date=business_date
            )
            for employee_id in sorted(visited):
                routes_rollup.recompute_employee_day(
                    session,
                    tenant_id=tenant_id,
                    employee_id=employee_id,
                    business_date=business_date,
                    business_profiler_frozen=True,
                )
        return len(outlet_ids)

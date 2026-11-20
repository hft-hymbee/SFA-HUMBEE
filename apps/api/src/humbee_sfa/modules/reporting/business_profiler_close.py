"""Day-close freeze of business profiler counts, run by the end-of-day sweep worker.

For the business date just closed: pull every visited outlet's % from Humbee once (the safety net
for a lost push or an admin change Humbee never pushes), record it as that day's evidence, then
recompute each visiting employee's day so the BP fact columns are written. Raises if Humbee does not
answer; the run is recorded failed and the worker retries it on its next poll.

No DB transaction is held across the Humbee wait: the visited outlets are read on a short-lived
connection, Humbee is called with nothing open, and only then does the job write on the runner's
connection (which has run no statement until that point, so no transaction was begun on it).
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from humbee_sfa.core.db import transaction
from humbee_sfa.modules.outlets.service import OutletReadService
from humbee_sfa.modules.reporting.business_profiler import DAY_CLOSE_JOB_NAME
from humbee_sfa.modules.reporting.producers import routes_rollup
from humbee_sfa.modules.routes.service import RouteService

__all__ = ["DAY_CLOSE_JOB_NAME", "run_business_profiler_day_close"]


def run_business_profiler_day_close(
    connection: Connection,
    run_id: str,
    *,
    tenant_id: str,
    business_date: date,
    read_bind: Engine | Connection | None = None,
) -> int:
    """`read_bind` is where the visited outlets are read; it defaults to a fresh connection from the
    runner's engine (tests pass their own connection to see uncommitted fixtures)."""

    del run_id
    with Session(bind=read_bind or connection.engine) as read_session:
        visited = RouteService(read_session).visited_outlets_by_employee(
            tenant_id=tenant_id, business_date=business_date
        )
    outlet_ids = sorted({outlet for outlets in visited.values() for outlet in outlets})

    with Session(bind=connection, autoflush=False, expire_on_commit=False) as session:
        outlets = OutletReadService(session)
        batches = outlets.fetch_business_profiler_for_day(
            tenant_id=tenant_id, outlet_ids=outlet_ids
        )
        with transaction(session):
            outlets.record_day_close(
                tenant_id=tenant_id, batches=batches, business_date=business_date
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

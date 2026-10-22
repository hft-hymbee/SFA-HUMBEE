"""The end-of-day route close job body."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from humbee_sfa.modules.routes.service import RouteService

SWEEP_JOB_NAME = "routes.end_of_day_sweep"


def run_end_of_day_sweep(
    connection: Connection, run_id: str, *, tenant_id: str, business_date: date, now: datetime
) -> int:
    del run_id
    with Session(bind=connection, autoflush=False, expire_on_commit=False) as session:
        return RouteService(session).close_day(
            tenant_id=tenant_id, business_date=business_date, now=now
        )

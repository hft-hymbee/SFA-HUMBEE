"""Background end-of-day sweep trigger for routes.

Closes every business date up to the due date that has no successful run, plus any earlier date still
holding open visits or plans, so days missed while the app was down, a run failed or work synced late
are caught up on the next tick.
"""

from __future__ import annotations

import threading
from datetime import date, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from humbee_sfa.core.business_date import to_business_date
from humbee_sfa.core.clock import Clock, SystemClock
from humbee_sfa.modules.routes.models.route_plan import RoutePlan
from humbee_sfa.modules.routes.models.route_visit import RouteVisit
from humbee_sfa.modules.routes.repository import OPEN_PLAN_STATES
from humbee_sfa.platform.models.sweep_run import SweepRun
from humbee_sfa.platform.scheduler import SupervisedJobRunner

from .sweep import SWEEP_JOB_NAME, run_end_of_day_sweep

logger = structlog.get_logger("humbee_sfa.routes.sweep_worker")

DEFAULT_POLL_INTERVAL_SECONDS = 30.0
CATCH_UP_WINDOW_DAYS = 7


def _due_business_date(
    now_utc: datetime,
    *,
    day_boundary_hour_ist: int,
    sweep_grace_minutes: int,
) -> date:
    due_at = now_utc - timedelta(minutes=sweep_grace_minutes)
    return to_business_date(due_at, day_boundary_hour=day_boundary_hour_ist) - timedelta(days=1)


class EndOfDaySweepWorker:
    """Triggers the routes sweep job for each due business date without a successful run."""

    def __init__(
        self,
        engine: Engine,
        session_factory: sessionmaker[Session],
        *,
        tenant_id: str,
        day_boundary_hour_ist: int,
        sweep_grace_minutes: int,
        clock: Clock | None = None,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    ) -> None:
        self._tenant_id = tenant_id
        self._session_factory = session_factory
        self._runner = SupervisedJobRunner(engine, session_factory, clock=clock)
        self._clock = clock or SystemClock()
        self._day_boundary_hour_ist = day_boundary_hour_ist
        self._sweep_grace_minutes = sweep_grace_minutes
        self._poll_interval_seconds = poll_interval_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop, name="routes-end-of-day-sweep-worker", daemon=True
        )
        self._thread.start()
        logger.info(
            "route_sweep_worker_started",
            sweep_grace_minutes=self._sweep_grace_minutes,
        )

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self._poll_interval_seconds * 2)
            self._thread = None
        logger.info("route_sweep_worker_stopped")

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._run_due_sweep()
            except Exception:
                logger.exception("route_sweep_worker_tick_failed")
            self._stop_event.wait(self._poll_interval_seconds)

    def _run_due_sweep(self) -> None:
        due_date = _due_business_date(
            self._clock.now_utc(),
            day_boundary_hour_ist=self._day_boundary_hour_ist,
            sweep_grace_minutes=self._sweep_grace_minutes,
        )
        for business_date, rerun_succeeded in self._dates_to_sweep(due_date):
            try:
                self._runner.run(
                    job_name=SWEEP_JOB_NAME,
                    tenant_id=self._tenant_id,
                    business_date=business_date,
                    rerun_succeeded=rerun_succeeded,
                    body=lambda connection, run_id, day=business_date: run_end_of_day_sweep(
                        connection,
                        run_id,
                        tenant_id=self._tenant_id,
                        business_date=day,
                        now=self._clock.now_utc(),
                    ),
                )
            except Exception:
                logger.exception(
                    "route_sweep_worker_date_failed", business_date=business_date.isoformat()
                )

    def _dates_to_sweep(self, due_date: date) -> list[tuple[date, bool]]:
        """`(business_date, rerun_succeeded)` pairs. A date still holding open visits or plans is
        swept even if an earlier run succeeded — work synced late lands on the day it occurred."""

        with self._session_factory() as session:
            open_dates = {
                business_date
                for model in (RouteVisit, RoutePlan)
                for business_date in session.scalars(
                    select(model.business_date)
                    .where(
                        model.tenant_id == self._tenant_id,
                        model.state.in_(OPEN_PLAN_STATES),
                        model.is_active.is_(True),
                        model.business_date <= due_date,
                    )
                    .distinct()
                )
            }
            window = [
                due_date - timedelta(days=offset)
                for offset in range(CATCH_UP_WINDOW_DAYS - 1, -1, -1)
            ]
            succeeded = set(
                session.scalars(
                    select(SweepRun.business_date).where(
                        SweepRun.tenant_id == self._tenant_id,
                        SweepRun.sweep_type == SWEEP_JOB_NAME,
                        SweepRun.status == "succeeded",
                        SweepRun.business_date.in_(window),
                    )
                )
            )
        dates = open_dates | {day for day in window if day not in succeeded}
        return [(day, day in open_dates) for day in sorted(dates)]

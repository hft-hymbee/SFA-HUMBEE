"""Background end-of-day sweep trigger for routes.

Closes every business date up to the due date that has no successful run, plus any earlier date still
holding open visits or plans, so days missed while the app was down, a run failed or work synced late
are caught up on the next tick.

Follow-up jobs (passed in by `main.py`, e.g. reporting's business-profiler day close) run for a
date only after that date's sweep has succeeded (the sweep closes the day's open visits), and again
once each time the sweep reruns successfully after them (late work), each with its own run record,
so one failing does not block the sweep and is retried on its own.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from datetime import date, datetime, timedelta

import structlog
from sqlalchemy import Connection, select
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
# `(job_name, body(connection, run_id, business_date) -> rows_affected)`.
FollowUpJob = tuple[str, Callable[[Connection, str, date], int]]
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
        follow_up_jobs: Sequence[FollowUpJob] = (),
    ) -> None:
        self._tenant_id = tenant_id
        self._follow_up_jobs = tuple(follow_up_jobs)
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
        for business_date, rerun_succeeded in self._dates_to_sweep(due_date, SWEEP_JOB_NAME):

            def sweep_body(connection: Connection, run_id: str, day: date = business_date) -> int:
                return run_end_of_day_sweep(
                    connection,
                    run_id,
                    tenant_id=self._tenant_id,
                    business_date=day,
                    now=self._clock.now_utc(),
                )

            try:
                self._runner.run(
                    job_name=SWEEP_JOB_NAME,
                    tenant_id=self._tenant_id,
                    business_date=business_date,
                    rerun_succeeded=rerun_succeeded,
                    body=sweep_body,
                )
            except Exception:
                logger.exception(
                    "route_sweep_worker_date_failed", business_date=business_date.isoformat()
                )
        for job_name, job_body in self._follow_up_jobs:
            for business_date, rerun_succeeded in self._follow_up_dates(due_date, job_name):

                def follow_up_body(
                    connection: Connection,
                    run_id: str,
                    day: date = business_date,
                    body: Callable[[Connection, str, date], int] = job_body,
                ) -> int:
                    return body(connection, run_id, day)

                try:
                    self._runner.run(
                        job_name=job_name,
                        tenant_id=self._tenant_id,
                        business_date=business_date,
                        rerun_succeeded=rerun_succeeded,
                        body=follow_up_body,
                    )
                except Exception:
                    logger.exception(
                        "route_sweep_follow_up_failed",
                        job_name=job_name,
                        business_date=business_date.isoformat(),
                    )

    def _follow_up_dates(self, due_date: date, job_name: str) -> list[tuple[date, bool]]:
        """`(business_date, rerun_succeeded)` for catch-up window dates whose sweep succeeded and
        `job_name` either has not succeeded yet, or last succeeded before the sweep's latest
        successful run finished (late work the sweep picked up): at most one rerun per sweep run."""

        window = _catch_up_window(due_date)
        with self._session_factory() as session:
            rows = session.execute(
                select(SweepRun.sweep_type, SweepRun.business_date, SweepRun.completed_at).where(
                    SweepRun.tenant_id == self._tenant_id,
                    SweepRun.sweep_type.in_((SWEEP_JOB_NAME, job_name)),
                    SweepRun.status == "succeeded",
                    SweepRun.business_date.in_(window),
                )
            ).all()
        swept = {day: done_at for job, day, done_at in rows if job == SWEEP_JOB_NAME}
        done = {day: done_at for job, day, done_at in rows if job == job_name}
        result = []
        for day in window:
            if day not in swept:
                continue
            if day not in done:
                result.append((day, False))
            elif swept[day] and done[day] and swept[day] > done[day]:
                result.append((day, True))
        return result

    def _dates_to_sweep(self, due_date: date, job_name: str) -> list[tuple[date, bool]]:
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
            window = _catch_up_window(due_date)
            succeeded = set(
                session.scalars(
                    select(SweepRun.business_date).where(
                        SweepRun.tenant_id == self._tenant_id,
                        SweepRun.sweep_type == job_name,
                        SweepRun.status == "succeeded",
                        SweepRun.business_date.in_(window),
                    )
                )
            )
        dates = open_dates | {day for day in window if day not in succeeded}
        return [(day, day in open_dates) for day in sorted(dates)]


def _catch_up_window(due_date: date) -> list[date]:
    return [due_date - timedelta(days=offset) for offset in range(CATCH_UP_WINDOW_DAYS - 1, -1, -1)]

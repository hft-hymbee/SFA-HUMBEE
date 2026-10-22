"""Background worker that periodically drains reporting domain events into fact tables.

`projector_job.py`'s own docstring says this job is "shaped for `platform/scheduler.py`'s
`SupervisedJobRunner`," but that runner claims a run once per `(tenant_id, sweep_type,
business_date)` and skips any later call for the same business date — correct for a once-daily
sweep, wrong for a projector meant to drain events every few hours within the same day. This
worker instead reuses only `SupervisedJobRunner`'s advisory-lock leader election
(`advisory_lock_key` + `pg_try_advisory_lock`), so at most one process in the cluster runs a tick
at a time, without borrowing the once-per-day claim semantics that don't fit here.
"""

from __future__ import annotations

import threading

import structlog
from sqlalchemy import text
from sqlalchemy.engine import Engine

from humbee_sfa.modules.reporting.projector_job import run_reporting_projector
from humbee_sfa.platform.scheduler import advisory_lock_key

logger = structlog.get_logger("humbee_sfa.reporting.projector_worker")

_JOB_NAME = "reporting_projector"
DEFAULT_INTERVAL_SECONDS = 12 * 60 * 60.0


class ReportingProjectorWorker:
    """Ticks `run_reporting_projector` on a fixed interval under leader election.

    The first tick runs immediately on `start()` (not after the first wait), so a fresh deploy
    drains any backlog right away instead of leaving fact tables stale for up to a full interval.
    """

    def __init__(self, engine: Engine, *, interval_seconds: float = DEFAULT_INTERVAL_SECONDS) -> None:
        self._engine = engine
        self._interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop, name="reporting-projector-worker", daemon=True
        )
        self._thread.start()
        logger.info("reporting_projector_worker_started", interval_seconds=self._interval_seconds)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=min(self._interval_seconds, 30.0))
            self._thread = None
        logger.info("reporting_projector_worker_stopped")

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._run_tick()
            except Exception:
                logger.exception("reporting_projector_worker_tick_failed")
            self._stop_event.wait(self._interval_seconds)

    def _run_tick(self) -> None:
        lock_key = advisory_lock_key(_JOB_NAME)
        with self._engine.connect() as lock_connection:
            acquired = lock_connection.execute(
                text("SELECT pg_try_advisory_lock(CAST(:key AS bigint))"), {"key": lock_key}
            ).scalar()
            if not acquired:
                logger.info("reporting_projector_tick_skipped_lock_held")
                return
            try:
                with self._engine.begin() as work_connection:
                    processed = run_reporting_projector(work_connection)
                logger.info("reporting_projector_tick_succeeded", events_processed=processed)
            finally:
                lock_connection.execute(
                    text("SELECT pg_advisory_unlock(CAST(:key AS bigint))"), {"key": lock_key}
                )

"""Generic supervised scheduled-job execution. Backend-foundation infra.

Leader election is a session-scoped Postgres advisory lock (`pg_try_advisory_lock`) keyed by job
name, so at most one process in the cluster runs a given job at a time. The run itself is claimed
idempotently in `platform_sweep_runs` (unique on `tenant_id, sweep_type, business_date`): a run that
already succeeded for that business date is skipped, a run left `running` by a crashed process is
retried, and a failed run records `failure_reason` and is retried on the next tick.

Feature-specific jobs (outbox drain, DP SLA timers, end-of-day sweep, rollup projection) register
onto this runner from their own module; this file owns none of that business logic.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import date

import structlog
from sqlalchemy import select, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker

from humbee_sfa.core.clock import Clock, SystemClock
from humbee_sfa.platform.models import SweepRun

logger = structlog.get_logger("humbee_sfa.platform.scheduler")

# A `running` row older than this is assumed to belong to a crashed process, not a live one —
# the advisory lock already guarantees no other live process is running this job concurrently.
STALE_RUNNING_THRESHOLD_SECONDS = 3600


def advisory_lock_key(job_name: str) -> int:
    """Deterministic signed 64-bit lock key for `pg_advisory_lock`, stable across processes."""

    digest = hashlib.sha256(job_name.encode("utf-8")).digest()[:8]
    return int.from_bytes(digest, "big", signed=True)


class SupervisedJobRunner:
    def __init__(
        self,
        engine: Engine,
        session_factory: sessionmaker[Session],
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._session_factory = session_factory
        self._clock = clock or SystemClock()

    def run(
        self,
        *,
        job_name: str,
        tenant_id: str,
        business_date: date,
        body: Callable[[Connection, str], int],
        rerun_succeeded: bool = False,
    ) -> None:
        """Run `body` under cluster-wide leader election and idempotent run-claiming.

        `rerun_succeeded` lets a date that already succeeded run again, for work that arrived
        after the earlier run.

        `body` receives a `Connection` owning its own transaction plus the claimed
        `SweepRun.id`, and returns the number of rows/units affected, recorded on the sweep run
        for observability. The run id is threaded through so a job that writes its own audit
        trail (e.g. `routes.end_of_day_sweep` -> `MissedVisitAudit.sweep_run_id`) can stamp the
        FK without a second query.
        """

        lock_key = advisory_lock_key(job_name)
        with self._engine.connect() as lock_connection:
            acquired = lock_connection.execute(
                text("SELECT pg_try_advisory_lock(CAST(:key AS bigint))"), {"key": lock_key}
            ).scalar()
            if not acquired:
                logger.info("scheduled_job_skipped_lock_held", job_name=job_name)
                return
            try:
                self._run_claimed(
                    job_name=job_name,
                    tenant_id=tenant_id,
                    business_date=business_date,
                    body=body,
                    rerun_succeeded=rerun_succeeded,
                )
            finally:
                lock_connection.execute(
                    text("SELECT pg_advisory_unlock(CAST(:key AS bigint))"), {"key": lock_key}
                )

    def _run_claimed(
        self,
        *,
        job_name: str,
        tenant_id: str,
        business_date: date,
        body: Callable[[Connection, str], int],
        rerun_succeeded: bool,
    ) -> None:
        with self._session_factory() as session:
            run_row = self._claim(
                session,
                job_name=job_name,
                tenant_id=tenant_id,
                business_date=business_date,
                rerun_succeeded=rerun_succeeded,
            )
            if run_row is None:
                return
            run_id = run_row.id

        try:
            with self._engine.begin() as work_connection:
                rows_affected = body(work_connection, run_id)
        except Exception as exc:
            logger.error(
                "scheduled_job_failed",
                job_name=job_name,
                business_date=business_date.isoformat(),
                error=str(exc),
            )
            self._mark_completed(run_id, status="failed", rows_affected=None, failure_reason=str(exc)[:2000])
            raise

        logger.info(
            "scheduled_job_succeeded",
            job_name=job_name,
            business_date=business_date.isoformat(),
            rows_affected=rows_affected,
        )
        self._mark_completed(run_id, status="succeeded", rows_affected=rows_affected, failure_reason=None)

    def _claim(
        self,
        session: Session,
        *,
        job_name: str,
        tenant_id: str,
        business_date: date,
        rerun_succeeded: bool,
    ) -> SweepRun | None:
        now = self._clock.now_utc()
        existing = session.execute(
            select(SweepRun)
            .where(
                SweepRun.tenant_id == tenant_id,
                SweepRun.sweep_type == job_name,
                SweepRun.business_date == business_date,
            )
            .with_for_update()
        ).scalar_one_or_none()

        if existing is not None and existing.status == "succeeded" and not rerun_succeeded:
            logger.info(
                "scheduled_job_skipped_already_succeeded",
                job_name=job_name,
                business_date=business_date.isoformat(),
            )
            return None

        if existing is not None and existing.status == "running":
            age_seconds = (now - existing.started_at).total_seconds()
            if age_seconds < STALE_RUNNING_THRESHOLD_SECONDS:
                logger.warning(
                    "scheduled_job_skipped_run_in_progress",
                    job_name=job_name,
                    business_date=business_date.isoformat(),
                    age_seconds=age_seconds,
                )
                return None
            logger.warning(
                "scheduled_job_reclaimed_stale_running",
                job_name=job_name,
                business_date=business_date.isoformat(),
                stale_seconds=age_seconds,
            )

        if existing is None:
            existing = SweepRun(
                tenant_id=tenant_id,
                sweep_type=job_name,
                business_date=business_date,
                started_at=now,
                status="running",
            )
            session.add(existing)
        else:
            existing.started_at = now
            existing.status = "running"
            existing.completed_at = None
            existing.rows_affected = None
            existing.failure_reason = None
        session.commit()
        return existing

    def _mark_completed(
        self,
        run_id: str,
        *,
        status: str,
        rows_affected: int | None,
        failure_reason: str | None,
    ) -> None:
        with self._session_factory() as session:
            run_row = session.get(SweepRun, run_id)
            if run_row is None:
                return
            run_row.status = status
            run_row.completed_at = self._clock.now_utc()
            run_row.rows_affected = rows_affected
            run_row.failure_reason = failure_reason
            session.commit()

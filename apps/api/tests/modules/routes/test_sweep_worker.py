from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session, sessionmaker
from tests.conftest import NOW
from tests.fixtures import seed

from humbee_sfa.modules.reporting.business_profiler import DAY_CLOSE_JOB_NAME
from humbee_sfa.modules.routes.sweep import SWEEP_JOB_NAME
from humbee_sfa.modules.routes.sweep_worker import EndOfDaySweepWorker
from humbee_sfa.platform.models import SweepRun

DUE = date(2026, 10, 19)


def test_follow_up_runs_after_each_successful_sweep(db_session: Session) -> None:
    worker = EndOfDaySweepWorker(
        db_session.get_bind(),
        sessionmaker(bind=db_session.connection(), join_transaction_mode="create_savepoint"),
        tenant_id=seed.tenant_id(),
        day_boundary_hour_ist=0,
        sweep_grace_minutes=0,
    )

    def run(job: str, day: date, status: str, completed_at: datetime | None = None) -> None:
        db_session.add(
            SweepRun(
                tenant_id=seed.tenant_id(),
                sweep_type=job,
                business_date=day,
                started_at=NOW,
                completed_at=completed_at or NOW,
                status=status,
            )
        )
        db_session.flush()

    swept, failed, closed, reswept = (DUE - timedelta(days=offset) for offset in (1, 2, 3, 4))
    later = NOW + timedelta(hours=1)
    run(SWEEP_JOB_NAME, swept, "succeeded")
    run(SWEEP_JOB_NAME, failed, "failed")
    run(SWEEP_JOB_NAME, closed, "succeeded")
    run(DAY_CLOSE_JOB_NAME, closed, "succeeded", completed_at=later)  # ran after the sweep
    run(SWEEP_JOB_NAME, reswept, "succeeded", completed_at=later)  # the sweep reran after the job
    run(DAY_CLOSE_JOB_NAME, reswept, "succeeded")

    # The swept date runs for the first time, the reswept one reruns once; never a failed or unswept
    # date, nor one whose job already ran after its latest sweep.
    assert worker._follow_up_dates(DUE, DAY_CLOSE_JOB_NAME) == [(reswept, True), (swept, False)]

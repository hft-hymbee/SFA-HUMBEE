"""Reporting projector scheduled job. Epic 05 Story 5.1 checkbox 1.

Wires the producer rollups onto the generic engine (`projector.py`) and exposes a body function
shaped for `platform/scheduler.py`'s `SupervisedJobRunner` (`Callable[[Connection], int]`) — the
existing idempotent, leader-elected job primitive from epic 00, reused here rather than building a
second scheduling mechanism. This file owns no fold logic of its own, only the stream/handler
registration; wiring the job into a running scheduler loop is out of scope for Story 5.1 (no such
loop exists yet — `partition_maintenance.py`'s job is in the same unwired state).

Story 5.1 ships a single partition (0) per stream, matching the default `partition` argument on
`DomainEventPublisher.publish`; multi-partition fan-out is future scaling work, not a correctness
requirement here.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from humbee_sfa.core.settings import get_settings
from humbee_sfa.modules.reporting import dim_employee_sync, projector
from humbee_sfa.modules.reporting.producers import (
    attendance_rollup,
    leave_rollup,
    orders_rollup,
    org_dim_employee_rollup,
    routes_rollup,
    targets_rollup,
)

_PARTITION = 0
_REPLAYABLE_REASONS = ("employee_dimension_missing", "handler_failed")
# `org` runs first: every other producer's `upsert_fact_employee_day` needs a current
# `dim_employee` row already in place (see `org_dim_employee_rollup`'s module docstring).
_PRODUCERS = (
    (org_dim_employee_rollup.STREAM, org_dim_employee_rollup.apply),
    (leave_rollup.STREAM, leave_rollup.apply),
    (attendance_rollup.STREAM, attendance_rollup.apply),
    (routes_rollup.STREAM, routes_rollup.apply),
    (orders_rollup.STREAM, orders_rollup.apply),
    (targets_rollup.STREAM, targets_rollup.apply),
)


def run_reporting_projector(connection: Connection) -> int:
    processed = 0
    with Session(bind=connection) as session:
        # Seeds employees that already existed before this projector shipped — their
        # `employee_created` events predate the lateness window and will never replay through
        # `_PRODUCERS` above. Cheap and idempotent: a no-op once every employee has a row.
        dim_employee_sync.backfill_missing(session, tenant_id=get_settings().tenant_id)
        # This `Session` is a plain `Session(bind=connection)`, not `core/db.py`'s sessionmaker, so
        # it defaults to autoflush — this flush is belt-and-suspenders to guarantee the backfill's
        # pending inserts are visible to `process_stream`'s queries in this same transaction.
        session.flush()
        for stream, handler in _PRODUCERS:
            while True:
                batch = projector.process_stream(session, stream=stream, partition=_PARTITION, handler=handler)
                processed += batch
                if batch < projector.BATCH_SIZE:
                    break
            # Heals events quarantined on an earlier tick for a since-resolved dimension gap
            # (e.g. the backfill above just seeded the employee they were waiting on) or a
            # since-fixed handler; each reason replays at most one batch per tick.
            for reason in _REPLAYABLE_REASONS:
                processed += projector.replay_quarantined(
                    session, stream=stream, handler=handler, reason=reason
                )
    return processed

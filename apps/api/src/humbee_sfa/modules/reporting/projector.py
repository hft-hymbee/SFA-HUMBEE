"""Generic reporting projector engine: projector semantics, late-arriving events and
replay/recompute.

This module owns the durable-log bookkeeping shared by every producer rollup: cursor advance
against `platform_domain_events`, at-least-once dedup by `event_seq`, lateness quarantine, the
`fact_employee_day` upsert-and-recompute primitive, and operator replay/health. Producers (see
`producers/`) only supply the per-event-type fold logic for the columns their stream owns.

Recompute, never increment: `upsert_fact_employee_day` always *sets* the columns a
producer passes it from that event's own payload, never `+= 1`s a counter. Replaying the same
event any number of times converges on the same row, which is what makes catch-up, late-event
healing and full replay all safe to run against live traffic without a shadow-table swap.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from humbee_sfa.core.business_date import to_business_date
from humbee_sfa.core.clock import Clock, SystemClock
from humbee_sfa.core.settings import get_settings
from humbee_sfa.modules.reporting.models import (
    DimEmployee,
    FactEmployeeDay,
    FactEmployeeManufacturerDay,
    FactEmployeeOutletDay,
    ProjectorOffset,
)
from humbee_sfa.platform.models import DomainEvent, EventQuarantine

logger = structlog.get_logger("humbee_sfa.modules.reporting.projector")

# Bumped when a KPI formula changes; see `fact_employee_day.formula_version`. This ships the
# first formula generation only — a version bump and its recompute-queue drain are
# out of scope here.
FORMULA_VERSION = 1

EventHandler = Callable[[Session, DomainEvent], None]

BATCH_SIZE = 500


class DimensionNotReady(Exception):
    """Raised by a producer when the employee's current `dim_employee` row does not exist yet.

    The `org` -> `dim_employee` SCD2 projector is not built here (org's published events carry
    only ids/codes today, not the display/geography shape `dim_employee` needs). Until that lands, any producer event for an
    employee with no dimension row is quarantined with this reason and heals via operator replay
    once the dimension exists, instead of failing the FK write or fabricating a placeholder row.
    """


def process_stream(
    session: Session,
    *,
    stream: str,
    partition: int,
    handler: EventHandler,
    clock: Clock | None = None,
    batch_size: int = BATCH_SIZE,
) -> int:
    """Fold new events on `stream`/`partition` through `handler`, advancing the offset.

    Events are applied in `event_seq` order; the offset advances past every event in the batch
    whether it was applied, quarantined for lateness, or quarantined for a handler failure — an
    event is never retried automatically, only via explicit operator replay. A failing
    handler's partial writes are rolled back to a savepoint so one bad event cannot corrupt or
    stall the rest of the batch. Caller owns the outer transaction/commit (same contract as
    `platform/scheduler.py` job bodies).
    """

    active_clock = clock or SystemClock()
    settings = get_settings()
    offset = _get_or_create_offset(session, stream=stream, partition=partition, clock=active_clock)

    events = (
        session.execute(
            select(DomainEvent)
            .where(
                DomainEvent.stream == stream,
                DomainEvent.partition == partition,
                DomainEvent.event_seq > offset.last_event_seq,
            )
            .order_by(DomainEvent.event_seq)
            .limit(batch_size)
        )
        .scalars()
        .all()
    )

    today = to_business_date(active_clock.now_utc(), settings.day_boundary_hour_ist)
    lateness_floor = today - timedelta(days=settings.reporting_projector_lateness_window_days)

    for event in events:
        if event.business_date < lateness_floor:
            _quarantine(session, event, reason="beyond_lateness_window", clock=active_clock)
        else:
            savepoint = session.begin_nested()
            try:
                handler(session, event)
                session.flush()
            except DimensionNotReady as exc:
                savepoint.rollback()
                _quarantine(
                    session, event, reason="employee_dimension_missing", detail=str(exc), clock=active_clock
                )
            except Exception as exc:  # noqa: BLE001 - one bad event must not stall the stream
                savepoint.rollback()
                logger.error(
                    "reporting_projector_event_quarantined",
                    stream=stream,
                    partition=partition,
                    event_seq=event.event_seq,
                    event_type=event.event_type,
                    error=str(exc),
                )
                _quarantine(session, event, reason="handler_failed", detail=str(exc)[:2000], clock=active_clock)
            else:
                savepoint.commit()

        offset.last_event_seq = event.event_seq
        offset.updated_at = active_clock.now_utc()
        # Releases the savepoint SQLAlchemy joined this session to (it was bound to a connection
        # already inside a transaction — see `projector_job.py`), so this event's work survives
        # even if a later event in the batch raises something `process_stream` does not catch.
        # It does not commit the caller's outer transaction; that stays the caller's job.
        session.commit()

    return len(events)


def replay_quarantined(
    session: Session,
    *,
    stream: str,
    handler: EventHandler,
    reason: str,
    clock: Clock | None = None,
    limit: int = BATCH_SIZE,
) -> int:
    """Re-applies up to `limit` quarantined events on `stream` whose quarantine `reason` can
    resolve itself over time — `employee_dimension_missing`: once `dim_employee` gets
    a row for the employee, the exact same event that failed before will now fold cleanly; and
    `handler_failed`, once the handler is fixed. `process_stream` never retries automatically
    (its offset already advanced past the event), so this is the only path back for an event
    quarantined that way.

    Never call this with `reason="beyond_lateness_window"` — that rejection is permanent by design
    (don't silently rewrite an old month), not a transient gap to heal.
    """

    active_clock = clock or SystemClock()
    rows = session.execute(
        select(EventQuarantine, DomainEvent)
        .join(DomainEvent, DomainEvent.id == EventQuarantine.domain_event_id)
        .where(
            EventQuarantine.reason == reason,
            EventQuarantine.released_at.is_(None),
            DomainEvent.stream == stream,
        )
        .order_by(DomainEvent.event_seq)
        .limit(limit)
    ).all()

    released = 0
    for quarantine_row, event in rows:
        savepoint = session.begin_nested()
        try:
            handler(session, event)
            session.flush()
        except DimensionNotReady:
            savepoint.rollback()
            continue
        except Exception as exc:  # noqa: BLE001 - one bad replay must not stall the rest
            savepoint.rollback()
            logger.error(
                "reporting_projector_replay_failed",
                stream=stream,
                event_seq=event.event_seq,
                error=str(exc),
            )
            continue
        else:
            savepoint.commit()
        quarantine_row.released_at = active_clock.now_utc()
        released += 1
        session.commit()
    return released


def upsert_fact_employee_day(
    session: Session,
    *,
    tenant_id: str,
    employee_id: str,
    business_date: date,
    last_event_at: datetime | None,
    fields: dict[str, object],
    clock: Clock | None = None,
) -> FactEmployeeDay:
    """Recompute-and-write the columns in `fields` on one `fact_employee_day` row.

    A caller only ever passes the columns its own stream owns, so two producers
    folding the same row never clobber each other's counters. `revision` increments on every
    write, proving a recompute happened (never a counter of business events).

    `last_event_at` is the occurred-at of the event being folded. A backfill recomputing from
    current state is not folding an event and passes `None`, which leaves the marker alone —
    stamping it with wall-clock time would claim an event this row never saw.

    Raises `DimensionNotReady` if the employee has no current `dim_employee` row yet.
    """

    active_clock = clock or SystemClock()
    row = session.get(FactEmployeeDay, (tenant_id, employee_id, business_date))
    if row is None:
        employee_key = session.execute(
            select(DimEmployee.employee_key).where(
                DimEmployee.tenant_id == tenant_id,
                DimEmployee.employee_id == employee_id,
                DimEmployee.valid_to.is_(None),
            )
        ).scalar_one_or_none()
        if employee_key is None:
            raise DimensionNotReady(f"no current dim_employee row for tenant={tenant_id} employee={employee_id}")
        row = FactEmployeeDay(
            tenant_id=tenant_id,
            employee_id=employee_id,
            business_date=business_date,
            employee_key=employee_key,
            revision=0,
            formula_version=FORMULA_VERSION,
            computed_at=active_clock.now_utc(),
        )
        session.add(row)

    for column, value in fields.items():
        setattr(row, column, value)

    row.revision += 1
    if last_event_at is not None:
        row.last_event_at = max(ts for ts in (row.last_event_at, last_event_at) if ts is not None)
    row.computed_at = active_clock.now_utc()
    return row


def upsert_fact_employee_outlet_day(
    session: Session,
    *,
    tenant_id: str,
    employee_id: str,
    business_date: date,
    humbee_outlet_id: str,
    fields: dict[str, object],
    clock: Clock | None = None,
) -> FactEmployeeOutletDay:
    """Recompute-and-write the columns in `fields` on one `fact_employee_outlet_day` row.

    A caller only ever passes the columns its own stream owns. Each producer owns its outlet-grain
    columns entirely (e.g., routes producer owns visit counts; orders producer owns order counts).

    Returns the row after update. No dimension check needed — outlet IDs are external Humbee
    identifiers, not local dimension keys.
    """

    active_clock = clock or SystemClock()
    row = session.get(FactEmployeeOutletDay, (tenant_id, employee_id, business_date, humbee_outlet_id))
    if row is None:
        row = FactEmployeeOutletDay(
            tenant_id=tenant_id,
            employee_id=employee_id,
            business_date=business_date,
            humbee_outlet_id=humbee_outlet_id,
            computed_at=active_clock.now_utc(),
        )
        session.add(row)

    for column, value in fields.items():
        setattr(row, column, value)

    row.computed_at = active_clock.now_utc()
    return row


def upsert_fact_employee_manufacturer_day(
    session: Session,
    *,
    tenant_id: str,
    employee_id: str,
    business_date: date,
    humbee_manufacturer_id: str,
    fields: dict[str, object],
    manufacturer_label: str | None = None,
    clock: Clock | None = None,
) -> FactEmployeeManufacturerDay:
    """Recompute-and-write the columns in `fields` on one `fact_employee_manufacturer_day` row.

    A caller only ever passes the columns its own stream owns. Omitted columns are preserved
    (field-merge, same as `upsert_fact_employee_outlet_day`). `manufacturer_label` is NOT NULL
    on create — pass it as an argument and/or in `fields`.
    """

    active_clock = clock or SystemClock()
    row = session.get(
        FactEmployeeManufacturerDay,
        (tenant_id, employee_id, business_date, humbee_manufacturer_id),
    )
    if row is None:
        label = manufacturer_label if manufacturer_label is not None else fields.get("manufacturer_label")
        row = FactEmployeeManufacturerDay(
            tenant_id=tenant_id,
            employee_id=employee_id,
            business_date=business_date,
            humbee_manufacturer_id=humbee_manufacturer_id,
            manufacturer_label=label,
            computed_at=active_clock.now_utc(),
        )
        session.add(row)

    for column, value in fields.items():
        setattr(row, column, value)

    row.computed_at = active_clock.now_utc()
    return row


def drop_stale_manufacturer_days(
    session: Session,
    *,
    tenant_id: str,
    employee_id: str,
    business_date: date,
    keep_manufacturer_ids: set[str],
) -> None:
    """Delete `fact_employee_manufacturer_day` rows the day's recompute no longer produces.

    A full-day recompute owns the whole grain, not just the rows it writes: a
    manufacturer whose only order was cancelled must lose its row, or its money outlives the
    order it came from. FEMD exists solely because of orders, so deleting is correct here.
    """

    rows = (
        session.execute(
            select(FactEmployeeManufacturerDay).where(
                FactEmployeeManufacturerDay.tenant_id == tenant_id,
                FactEmployeeManufacturerDay.employee_id == employee_id,
                FactEmployeeManufacturerDay.business_date == business_date,
            )
        )
        .scalars()
        .all()
    )
    for row in rows:
        if row.humbee_manufacturer_id not in keep_manufacturer_ids:
            session.delete(row)


def clear_stale_outlet_day_orders(
    session: Session,
    *,
    tenant_id: str,
    employee_id: str,
    business_date: date,
    keep_outlet_ids: set[str],
) -> None:
    """Zero the order columns on `fact_employee_outlet_day` rows the day no longer orders for.

    The row itself stays — `routes_rollup` owns its visit columns and a visit without an order
    is a real row. Only the columns the orders stream owns are reset.
    """

    rows = (
        session.execute(
            select(FactEmployeeOutletDay).where(
                FactEmployeeOutletDay.tenant_id == tenant_id,
                FactEmployeeOutletDay.employee_id == employee_id,
                FactEmployeeOutletDay.business_date == business_date,
            )
        )
        .scalars()
        .all()
    )
    for row in rows:
        if row.humbee_outlet_id in keep_outlet_ids:
            continue
        if not (row.orders_count or row.net_value_paise or row.lines_count):
            continue
        row.orders_count = 0
        row.net_value_paise = 0
        row.lines_count = 0


def _get_or_create_offset(
    session: Session, *, stream: str, partition: int, clock: Clock
) -> ProjectorOffset:
    offset = session.get(ProjectorOffset, (stream, partition))
    if offset is None:
        offset = ProjectorOffset(
            stream=stream, partition=partition, last_event_seq=0, updated_at=clock.now_utc()
        )
        session.add(offset)
        session.flush()
    return offset


def _quarantine(
    session: Session,
    event: DomainEvent,
    *,
    reason: str,
    clock: Clock,
    detail: str | None = None,
) -> None:
    session.add(
        EventQuarantine(
            tenant_id=event.tenant_id,
            domain_event_id=event.id,
            reason=reason,
            detail=detail,
            quarantined_at=clock.now_utc(),
            released_at=None,
        )
    )

"""Attendance producer rollup — stream `attendance`.

Recomputes `fact_employee_day`'s attendance columns from the `attendance` stream's own event log
(`platform_domain_events`) on every punch/official-work event — never by importing
`attendance.models` (forbidden by `pyproject.toml`'s "Modules must not import each other's
internals" contract; cross-module reads go through the owning module's event stream, not its
tables) and never a `+= 1` counter: every fold re-derives the full day's value
from that day's events, so replay and out-of-order arrival converge on the same row.

Confirmed payload shapes (verified against `attendance/service.py`, not guessed):
`punched_in`/`punched_out` carry `{employee_id, business_date, is_late}` only — no duration field,
so `on_duty_seconds` is derived from the punch events' own `occurred_at` timestamps.
`official_work_started` carries `{employee_id, work_type, business_date}` — no numeric field to
fold. `official_work_logged` carries `{employee_id, work_type, duration_seconds, business_date}` —
no task-count field, so `official_work_task_count` is derived by counting that day's
`official_work_logged` events.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from humbee_sfa.modules.reporting.producers.event_log import employee_day_events
from humbee_sfa.modules.reporting.projector import upsert_fact_employee_day
from humbee_sfa.platform.models import DomainEvent

STREAM = "attendance"
PUNCHED_IN = "punched_in"
PUNCHED_OUT = "punched_out"
OFFICIAL_WORK_STARTED = "official_work_started"
OFFICIAL_WORK_LOGGED = "official_work_logged"


def apply(session: Session, event: DomainEvent) -> None:
    """Fold attendance events into fact_employee_day by recomputing from the day's own event log."""

    if event.event_type == PUNCHED_IN:
        _handle_punch_in(session, event)
    elif event.event_type == PUNCHED_OUT:
        _handle_punch_out(session, event)
    elif event.event_type == OFFICIAL_WORK_LOGGED:
        _handle_official_work_logged(session, event)
    # OFFICIAL_WORK_STARTED carries no foldable numeric field (confirmed) — nothing to recompute
    # until the matching official_work_logged event closes the session.


def _handle_punch_in(session: Session, event: DomainEvent) -> None:
    payload = event.payload
    employee_id: str = payload["employee_id"]
    occurred_at = event.occurred_at
    business_date = event.business_date

    upsert_fact_employee_day(
        session,
        tenant_id=event.tenant_id,
        employee_id=employee_id,
        business_date=business_date,
        last_event_at=occurred_at,
        fields={
            "punched_in": True,
            "first_punch_in_at": occurred_at,
            "is_late_punch_in": bool(payload.get("is_late", False)),
        },
    )


def _handle_punch_out(session: Session, event: DomainEvent) -> None:
    payload = event.payload
    employee_id: str = payload["employee_id"]
    occurred_at = event.occurred_at
    business_date = event.business_date

    punch_ins = employee_day_events(
        session,
        stream=STREAM,
        tenant_id=event.tenant_id,
        employee_id=employee_id,
        business_date=business_date,
        event_type=PUNCHED_IN,
    )
    on_duty_seconds = 0
    if punch_ins:
        on_duty_seconds = max(0, int((occurred_at - punch_ins[0].occurred_at).total_seconds()))

    upsert_fact_employee_day(
        session,
        tenant_id=event.tenant_id,
        employee_id=employee_id,
        business_date=business_date,
        last_event_at=occurred_at,
        fields={
            "punched_in": False,
            "last_punch_out_at": occurred_at,
            "on_duty_seconds": on_duty_seconds,
        },
    )


def _handle_official_work_logged(session: Session, event: DomainEvent) -> None:
    payload = event.payload
    employee_id: str = payload["employee_id"]
    occurred_at = event.occurred_at
    business_date = event.business_date

    day_logged = employee_day_events(
        session,
        stream=STREAM,
        tenant_id=event.tenant_id,
        employee_id=employee_id,
        business_date=business_date,
        event_type=OFFICIAL_WORK_LOGGED,
    )
    official_work_seconds = sum(int(row.payload.get("duration_seconds", 0)) for row in day_logged)

    upsert_fact_employee_day(
        session,
        tenant_id=event.tenant_id,
        employee_id=employee_id,
        business_date=business_date,
        last_event_at=occurred_at,
        fields={
            "official_work_seconds": official_work_seconds,
            "official_work_task_count": len(day_logged),
        },
    )

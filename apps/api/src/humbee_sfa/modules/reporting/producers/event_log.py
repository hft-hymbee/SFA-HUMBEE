from __future__ import annotations

from datetime import date

from sqlalchemy import String, literal_column, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from humbee_sfa.platform.models import DomainEvent


def payload_text(key: str) -> ColumnElement[str]:
    return DomainEvent.payload.op("->>", return_type=String)(literal_column(f"'{key}'"))


def _employee_events(
    session: Session,
    *,
    tenant_id: str,
    stream: str,
    event_type: str,
    employee_id: str,
    day_filter: ColumnElement[bool],
) -> list[DomainEvent]:
    return list(
        session.execute(
            select(DomainEvent)
            .where(
                DomainEvent.tenant_id == tenant_id,
                DomainEvent.stream == stream,
                DomainEvent.event_type == event_type,
                payload_text("employee_id") == employee_id,
                day_filter,
            )
            .order_by(DomainEvent.event_seq)
        )
        .scalars()
        .all()
    )


def employee_day_events(
    session: Session,
    *,
    tenant_id: str,
    stream: str,
    event_type: str,
    employee_id: str,
    business_date: date,
) -> list[DomainEvent]:
    return _employee_events(
        session,
        tenant_id=tenant_id,
        stream=stream,
        event_type=event_type,
        employee_id=employee_id,
        day_filter=DomainEvent.business_date == business_date,
    )


def latest_payload_day_events(
    session: Session,
    *,
    tenant_id: str,
    stream: str,
    event_type: str,
    employee_id: str,
    business_date: date,
) -> list[DomainEvent]:
    events = _employee_events(
        session,
        tenant_id=tenant_id,
        stream=stream,
        event_type=event_type,
        employee_id=employee_id,
        day_filter=payload_text("business_date") == business_date.isoformat(),
    )
    return list({event.aggregate_id: event for event in events}.values())

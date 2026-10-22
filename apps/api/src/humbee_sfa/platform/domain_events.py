"""Helpers for writing append-only domain events."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from humbee_sfa.core.business_date import to_business_date
from humbee_sfa.core.clock import Clock, SystemClock
from humbee_sfa.core.settings import get_settings
from humbee_sfa.platform.models import DomainEvent


class DomainEventPublisher:
    def __init__(self, session: Session, clock: Clock | None = None) -> None:
        self._session = session
        self._clock = clock or SystemClock()

    def publish(
        self,
        *,
        tenant_id: str,
        stream: str,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict[str, Any],
        partition: int = 0,
        actor_employee_id: str | None = None,
        on_behalf_of_employee_id: str | None = None,
        request_id: str | None = None,
        occurred_at: datetime | None = None,
    ) -> DomainEvent:
        event_time = occurred_at or self._clock.now_utc()
        row = DomainEvent(
            tenant_id=tenant_id,
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
            occurred_at=event_time,
            received_at=self._clock.now_utc(),
            business_date=to_business_date(event_time, get_settings().day_boundary_hour_ist),
            created_by_employee_id=actor_employee_id,
            on_behalf_of_employee_id=on_behalf_of_employee_id,
            request_id=request_id,
            stream=stream,
            partition=partition,
        )
        self._session.add(row)
        return row

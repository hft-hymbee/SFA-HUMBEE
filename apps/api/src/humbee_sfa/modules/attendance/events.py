"""Attendance domain event names and publish helper — M09 §3.7, §5.2, §5.6.

`fact_employee_day` (reporting) already carries the columns these events feed
(`punched_in`, `official_work_seconds`, ...) — epic 05 Story 5.1 has not built the attendance
producer rollup yet, but the event log is durable and at-least-once, so these events preserve the
inputs that producer will consume. Names follow the shared domain-event convention (snake_case,
module-prefixed).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from humbee_sfa.platform.domain_events import DomainEventPublisher

STREAM = "attendance"
AGGREGATE_ATTENDANCE_DAY = "attendance_day"
AGGREGATE_OFFICIAL_WORK_SESSION = "official_work_session"

PUNCHED_IN = "punched_in"
PUNCHED_OUT = "punched_out"
OFFICIAL_WORK_STARTED = "official_work_started"
OFFICIAL_WORK_LOGGED = "official_work_logged"


def publish_attendance_event(
    publisher: DomainEventPublisher,
    *,
    tenant_id: str,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict[str, Any],
    actor_employee_id: str | None = None,
    occurred_at: datetime | None = None,
) -> None:
    publisher.publish(
        tenant_id=tenant_id,
        stream=STREAM,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=payload,
        actor_employee_id=actor_employee_id,
        occurred_at=occurred_at,
    )

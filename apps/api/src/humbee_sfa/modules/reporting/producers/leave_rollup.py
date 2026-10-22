"""Leave producer rollup — stream `leave` (M11 §3b.2, epic 05 Story 5.1 checkbox 2).

Folds `leave_granted` / `leave_rejected` / `leave_withdrawn` (published by
`modules/leave/adapter.py` through the approvals decision transaction) into
`fact_employee_day.is_leave_day` / `leave_type` for every business date the leave request covers.

Each event is a terminal outcome for its own request and carries the full date range and type in
its payload (see `LeaveAdapter._event`), so folding it is a plain set, not an increment: replaying
the same event any number of times, in any order relative to itself, converges on the same value
(M11 §3b.3 rule 2). A later decision on a different, overlapping request for the same employee/day
simply overwrites — `fact_employee_day` models at most one leave per employee/day, matching the
leave module's own no-overlap invariant.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from humbee_sfa.modules.reporting.projector import upsert_fact_employee_day
from humbee_sfa.platform.models import DomainEvent

STREAM = "leave"

GRANTED = "leave_granted"
REJECTED = "leave_rejected"
WITHDRAWN = "leave_withdrawn"

_IS_LEAVE_DAY = {GRANTED: True, REJECTED: False, WITHDRAWN: False}


def apply(session: Session, event: DomainEvent) -> None:
    if event.event_type not in _IS_LEAVE_DAY:
        return

    payload = event.payload
    is_leave_day = _IS_LEAVE_DAY[event.event_type]
    from_date = date.fromisoformat(payload["from_date"])
    to_date = date.fromisoformat(payload["to_date"])

    day = from_date
    while day <= to_date:
        upsert_fact_employee_day(
            session,
            tenant_id=event.tenant_id,
            employee_id=payload["employee_id"],
            business_date=day,
            last_event_at=event.occurred_at,
            fields={
                "is_leave_day": is_leave_day,
                "leave_type": payload["leave_type"] if is_leave_day else None,
            },
        )
        day += timedelta(days=1)

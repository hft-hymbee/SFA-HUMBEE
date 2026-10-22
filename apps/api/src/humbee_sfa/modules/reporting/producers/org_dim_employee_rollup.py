"""Org employee producer rollup — stream `org`.

Every other producer in this package needs a current `dim_employee` row before it can write
anything (`upsert_fact_employee_day` raises `DimensionNotReady` otherwise), so this one runs first
in `projector_job.py`'s `_PRODUCERS`. It does not fold `payload` fields directly — none of the four
event payloads carry the columns `dim_employee` needs (confirmed against `org/service.py`: e.g.
`employee_updated` carries only the *names* of changed fields, never their values) — so every event
here just re-reads the employee's current state from `org.service` and versions the dimension if
anything tracked actually changed. See `dim_employee_sync.py` for the fold/versioning logic itself
and why the geography columns are always left empty.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from humbee_sfa.modules.reporting.dim_employee_sync import sync_employee
from humbee_sfa.platform.models import DomainEvent

STREAM = "org"

EMPLOYEE_CREATED = "employee_created"
EMPLOYEE_UPDATED = "employee_updated"
EMPLOYEE_MOVED = "employee_moved"
EMPLOYEE_DEACTIVATED = "employee_deactivated"

_TRACKED_EVENT_TYPES = (EMPLOYEE_CREATED, EMPLOYEE_UPDATED, EMPLOYEE_MOVED, EMPLOYEE_DEACTIVATED)


def apply(session: Session, event: DomainEvent) -> None:
    """Fold employee lifecycle events into `dim_employee` by re-reading current state."""

    if event.event_type not in _TRACKED_EVENT_TYPES:
        return

    employee_id: str = event.payload["employee_id"]
    sync_employee(
        session,
        tenant_id=event.tenant_id,
        employee_id=employee_id,
        occurred_at=event.occurred_at,
    )

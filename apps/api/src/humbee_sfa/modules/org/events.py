"""Org domain event names and publish helper.

`EmployeeMoved` is the contract downstream modules act on (M03 §5.5): `approvals` re-routes open
requests to the new parent, `reporting` invalidates tree rollups. Geography scope belongs to the
employee and needs no re-parenting (R-ORG-40) — only its visibility changes, which follows scope.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from humbee_sfa.platform.domain_events import DomainEventPublisher

STREAM = "org"
AGGREGATE_EMPLOYEE = "employee"

EMPLOYEE_CREATED = "employee_created"
EMPLOYEE_UPDATED = "employee_updated"
EMPLOYEE_MOVED = "employee_moved"
EMPLOYEE_DEACTIVATED = "employee_deactivated"


def publish_org_event(
    publisher: DomainEventPublisher,
    *,
    tenant_id: str,
    event_type: str,
    aggregate_id: str,
    payload: dict[str, Any],
    aggregate_type: str = AGGREGATE_EMPLOYEE,
    actor_employee_id: str | None = None,
    request_id: str | None = None,
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
        request_id=request_id,
        occurred_at=occurred_at,
    )

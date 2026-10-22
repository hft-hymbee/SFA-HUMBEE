"""Orders domain event names and publish helper.

`order_submitted` is published when an order is successfully created (accepted into the cart).
This event feeds the reporting rollups.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from humbee_sfa.platform.domain_events import DomainEventPublisher

STREAM = "orders"
AGGREGATE_ORDER = "order"

ORDER_SUBMITTED = "order_submitted"
DP_ORDER_APPROVED = "dp_order_approved"


def publish_order_event(
    publisher: DomainEventPublisher,
    *,
    tenant_id: str,
    event_type: str,
    aggregate_id: str,
    payload: dict[str, Any],
    actor_employee_id: str | None = None,
    occurred_at: datetime | None = None,
) -> None:
    publisher.publish(
        tenant_id=tenant_id,
        stream=STREAM,
        event_type=event_type,
        aggregate_type=AGGREGATE_ORDER,
        aggregate_id=aggregate_id,
        payload=payload,
        actor_employee_id=actor_employee_id,
        occurred_at=occurred_at,
    )

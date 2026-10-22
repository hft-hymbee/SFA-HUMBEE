from __future__ import annotations

from sqlalchemy.orm import Session

from humbee_sfa.modules.reporting.projector import upsert_fact_employee_day
from humbee_sfa.modules.targets.service import count_leads_for_employee_day
from humbee_sfa.platform.models import DomainEvent

STREAM = "targets"

LEAD_CAPTURED = "lead_captured"


def apply(session: Session, event: DomainEvent) -> None:
    if event.event_type != LEAD_CAPTURED:
        return

    employee_id = event.payload["captured_by_employee_id"]
    upsert_fact_employee_day(
        session,
        tenant_id=event.tenant_id,
        employee_id=employee_id,
        business_date=event.business_date,
        last_event_at=event.occurred_at,
        fields={
            "leads_captured_count": count_leads_for_employee_day(
                session,
                tenant_id=event.tenant_id,
                employee_id=employee_id,
                business_date=event.business_date,
            )
        },
    )

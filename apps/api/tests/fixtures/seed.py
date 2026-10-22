from __future__ import annotations

import itertools
from datetime import date

from sqlalchemy.orm import Session

from humbee_sfa.core.conventions import generate_ulid
from humbee_sfa.core.settings import get_settings
from humbee_sfa.modules.org import schemas as org_schemas
from humbee_sfa.modules.org.models import Employee
from humbee_sfa.modules.org.scope import maintenance_scope
from humbee_sfa.modules.org.service import OrgService

_sequence = itertools.count(1)

DEFAULT_DESIGNATION = {
    "sales_person": "network_officer_salesperson",
    "manager": "area_sales_manager",
    "admin": "admin",
}


def tenant_id() -> str:
    return get_settings().tenant_id


def employee(
    db: Session,
    role: str,
    *,
    manager: Employee | None = None,
    designation: str | None = None,
    full_name: str | None = None,
    joined_on: date = date(2025, 1, 1),
) -> Employee:
    n = next(_sequence)
    body = org_schemas.CreateEmployeeBody(
        employee_code=f"E{n:05d}",
        full_name=full_name or f"{role.replace('_', ' ').title()} {n}",
        phone_e164=f"+9198{n:08d}",
        role_code=role,
        designation_code=designation or DEFAULT_DESIGNATION[role],
        manager_employee_id=manager.id if manager is not None else None,
        joined_on=joined_on,
    )
    _, payload = OrgService(db)._create_employee(
        scope=maintenance_scope(tenant_id()),
        body=body,
        endpoint="tests/seed",
        idempotency_key=generate_ulid(),
        raw_body=body.model_dump_json().encode(),
        request_id=None,
    )
    return db.get(Employee, payload["id"])


def phone_of(row: Employee) -> str:
    return f"+9198{int(row.employee_code[1:]):08d}"

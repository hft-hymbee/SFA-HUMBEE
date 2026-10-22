from __future__ import annotations

import itertools
from collections.abc import Sequence
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.fakes.humbee import FakeHumbee

from humbee_sfa.core.conventions import generate_ulid
from humbee_sfa.core.db import transaction
from humbee_sfa.core.security import decrypt_phone
from humbee_sfa.core.settings import get_settings
from humbee_sfa.modules.beats.models import Beat, BeatOutlet, BeatVersion
from humbee_sfa.modules.beats.repository import build_geo_scope_json
from humbee_sfa.modules.org import schemas as org_schemas
from humbee_sfa.modules.org.models import Employee
from humbee_sfa.modules.org.scope import maintenance_scope
from humbee_sfa.modules.org.service import OrgService
from humbee_sfa.modules.outlets.models import Outlet

_sequence = itertools.count(1)
_beat_sequence = itertools.count(1)

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
    return decrypt_phone(row.phone_e164_enc)


def projected_outlet(db: Session, humbee: FakeHumbee, outlet_ref: str, district_id: str, now: datetime) -> Outlet:
    fake = humbee.outlets.get(outlet_ref) or humbee.add_outlet(outlet_ref, district_id=district_id)
    row = db.execute(
        select(Outlet).where(Outlet.tenant_id == tenant_id(), Outlet.humbee_outlet_id == outlet_ref)
    ).scalar_one_or_none()
    if row is None:
        row = Outlet(
            tenant_id=tenant_id(),
            humbee_outlet_id=outlet_ref,
            name=fake.name,
            humbee_shop_category_id=fake.shop_category_id,
            humbee_district_id=fake.district_id,
            as_of=now,
            fetched_at=now,
        )
        db.add(row)
        db.flush()
    return row


def approved_beat(
    db: Session,
    owner: Employee,
    outlet_ids: Sequence[str],
    *,
    humbee: FakeHumbee,
    frequency: str = "weekly",
    visit_days: Sequence[int] = (1, 4),
    district_id: str = "100",
) -> Beat:
    n = next(_beat_sequence)
    now = datetime.now(UTC)
    code = f"BEAT-{n:04d}"
    name = f"Beat {n}"
    state_id = humbee.districts[district_id].state_id
    with transaction(db):
        outlets = [projected_outlet(db, humbee, ref, district_id, now) for ref in outlet_ids]
        beat = Beat(
            tenant_id=tenant_id(),
            code=code,
            display_name=name,
            owner_employee_id=owner.id,
            lifecycle_state="approved",
            activation_state="active",
            current_version_id=generate_ulid(),
            created_by_employee_id=owner.id,
        )
        db.add(beat)
        db.flush()
        version = BeatVersion(
            id=beat.current_version_id,
            tenant_id=tenant_id(),
            beat_id=beat.id,
            version_no=1,
            state="approved",
            display_name=name,
            code=code,
            geo_scope=build_geo_scope_json(
                zones=[humbee.states[state_id].zone_id],
                states=[state_id],
                districts=[district_id],
                cats=[],
                as_of=now,
            ),
            frequency={
                "frequency": frequency,
                "visit_days": [] if frequency == "daily" else list(visit_days),
                "week_cycle": [],
            },
            outlet_count=len(outlets),
            approved_at=now,
            approved_by_employee_id=owner.manager_employee_id,
            created_by_employee_id=owner.id,
        )
        db.add(version)
        db.flush()
        db.add_all(
            BeatOutlet(
                tenant_id=tenant_id(),
                beat_version_id=version.id,
                outlet_id=outlet.id,
                sequence_hint=position,
                created_by_employee_id=owner.id,
            )
            for position, outlet in enumerate(outlets, start=1)
        )
    return beat

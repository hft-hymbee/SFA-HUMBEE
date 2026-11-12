from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.fixtures import seed
from tests.fixtures.auth import login, request_otp, verify_otp
from tests.fixtures.flows import error_code

from humbee_sfa.core.conventions import generate_ulid
from humbee_sfa.modules.identity.models import Session as IdentitySession
from humbee_sfa.platform.models import AuditLog

EMPLOYEES = "/api/v1/org/employees"
NEW_PHONE = "+919000000001"


def _phone(employee_id: str) -> str:
    return f"{EMPLOYEES}/{employee_id}/phone"


def test_phone_change_moves_login_to_new_number(
    api_client: TestClient, db_session: Session
) -> None:
    admin = login(api_client, seed.employee(db_session, "admin"))
    sp = seed.employee(db_session, "sales_person")
    old_phone = seed.phone_of(sp)
    sp_client = login(api_client, sp)
    pending = request_otp(api_client, old_phone, device_id="other")
    assert pending.status_code == 200, pending.text

    changed = admin.post(_phone(sp.id), {"phone_e164": NEW_PHONE})

    assert changed.status_code == 200, changed.text
    assert changed.json()["phone_e164"] == NEW_PHONE
    assert sp_client.get("/api/v1/me").status_code == 401
    reasons = db_session.scalars(
        select(IdentitySession.revocation_reason).where(IdentitySession.employee_id == sp.id)
    ).all()
    assert reasons == ["admin_revoke"]
    stale = verify_otp(api_client, pending.json()["challenge_id"], device_id="other")
    assert (stale.status_code, error_code(stale)) == (409, "challenge_expired")
    old = request_otp(api_client, old_phone)
    assert (old.status_code, error_code(old)) == (404, "phone_not_registered")
    db_session.refresh(sp)
    assert login(api_client, sp).get("/api/v1/me").status_code == 200

    audit = db_session.scalars(
        select(AuditLog.change_payload).where(
            AuditLog.entity_id == sp.id, AuditLog.change_payload["fields"].astext == '["phone"]'
        )
    ).one()
    assert audit["phone_last4"] == {"from": old_phone[-4:], "to": NEW_PHONE[-4:]}
    assert old_phone not in str(audit) and NEW_PHONE not in str(audit)


def test_inactive_employee_frees_reused_sim(api_client: TestClient, db_session: Session) -> None:
    admin = login(api_client, seed.employee(db_session, "admin"))
    manager = seed.employee(db_session, "manager")
    leaver = seed.employee(db_session, "sales_person", manager=manager)
    joiner = seed.employee(db_session, "sales_person", manager=manager)
    sim = seed.phone_of(leaver)
    assert admin.post(f"{EMPLOYEES}/{leaver.id}/deactivate", {}).status_code == 200

    blocked = admin.post(_phone(joiner.id), {"phone_e164": sim})
    assert (blocked.status_code, error_code(blocked)) == (409, "phone_already_registered")
    assert admin.post(_phone(leaver.id), {"phone_e164": "+919000000002"}).status_code == 200
    moved = admin.post(_phone(joiner.id), {"phone_e164": sim})
    assert moved.status_code == 200, moved.text
    assert moved.json()["phone_e164"] == sim


def test_phone_change_rejections(api_client: TestClient, db_session: Session) -> None:
    admin_row = seed.employee(db_session, "admin")
    admin = login(api_client, admin_row)
    other_admin = seed.employee(db_session, "admin")
    manager = seed.employee(db_session, "manager")
    sp = seed.employee(db_session, "sales_person", manager=manager)
    other = seed.employee(db_session, "sales_person", manager=manager)

    rejected = [
        (admin, sp.id, {"phone_e164": seed.phone_of(other)}, 409, "phone_already_registered"),
        (admin, sp.id, {"phone_e164": seed.phone_of(sp)}, 422, "phone_unchanged"),
        (admin, other_admin.id, {"phone_e164": NEW_PHONE}, 403, "admin_phone_change_forbidden"),
        (admin, admin_row.id, {"phone_e164": NEW_PHONE}, 403, "admin_phone_change_forbidden"),
        (login(api_client, manager), sp.id, {"phone_e164": NEW_PHONE}, 403, "forbidden"),
    ]
    for actor, employee_id, body, status, code in rejected:
        response = actor.post(_phone(employee_id), body)
        assert (response.status_code, error_code(response)) == (status, code), body
    for bad in ("+14155550123", "9000000001", "+9190000000"):
        assert admin.post(_phone(sp.id), {"phone_e164": bad}).status_code == 422, bad


def test_phone_change_idempotency(api_client: TestClient, db_session: Session) -> None:
    admin = login(api_client, seed.employee(db_session, "admin"))
    manager = seed.employee(db_session, "manager")
    key = generate_ulid()

    first = admin.post(_phone(manager.id), {"phone_e164": NEW_PHONE}, key=key)
    replay = admin.post(_phone(manager.id), {"phone_e164": NEW_PHONE}, key=key)
    conflict = admin.post(_phone(manager.id), {"phone_e164": "+919000000003"}, key=key)

    assert first.status_code == replay.status_code == 200
    assert replay.json() == first.json()
    assert (conflict.status_code, error_code(conflict)) == (409, "idempotency_conflict")

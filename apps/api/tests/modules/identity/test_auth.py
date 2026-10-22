from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.fixtures import seed
from tests.fixtures.auth import OTP, request_otp, verify_otp
from tests.fixtures.flows import error_code

from humbee_sfa.core.conventions import generate_ulid
from humbee_sfa.core.settings import get_settings
from humbee_sfa.modules.identity.models import AuthAuditEvent, OtpChallenge
from humbee_sfa.modules.identity.models import Session as IdentitySession
from humbee_sfa.modules.org import repository as org_repository
from humbee_sfa.modules.org.models import Employee
from humbee_sfa.modules.org.scope import maintenance_scope

WRONG_CODE = "654321"


def _deactivate(db: Session, employee: Employee) -> None:
    org_repository.deactivate_employee(
        db,
        scope=maintenance_scope(get_settings().tenant_id),
        employee=employee,
        at=datetime.now(UTC),
    )


def _sessions(db: Session, employee: Employee) -> list[IdentitySession]:
    return list(
        db.scalars(select(IdentitySession).where(IdentitySession.employee_id == employee.id))
    )


def _challenge_id(client: TestClient, employee: Employee) -> str:
    response = request_otp(client, seed.phone_of(employee))
    assert response.status_code == 200, response.text
    return response.json()["challenge_id"]


def test_login_refresh_logout(api_client: TestClient, db_session: Session) -> None:
    employee = seed.employee(db_session, "sales_person")

    verified = verify_otp(api_client, _challenge_id(api_client, employee))
    assert verified.status_code == 200, verified.text
    first = verified.json()
    assert first["expires_in"] == 900
    me = api_client.get("/api/v1/me", headers={"Authorization": f"Bearer {first['access_token']}"})
    assert (me.json()["id"], me.json()["role"]) == (employee.id, "sales_person")

    refreshed = api_client.post(
        "/api/v1/auth/token/refresh",
        headers={"Idempotency-Key": generate_ulid()},
        json={"refresh_token": first["refresh_token"], "client_device_id": "device-1"},
    )
    assert refreshed.status_code == 200, refreshed.text
    second = refreshed.json()
    assert second["refresh_token"] != first["refresh_token"]
    bearer = {"Authorization": f"Bearer {second['access_token']}"}
    assert api_client.get("/api/v1/me", headers=bearer).status_code == 200

    stale = api_client.post(
        "/api/v1/auth/token/refresh",
        headers={"Idempotency-Key": generate_ulid()},
        json={"refresh_token": first["refresh_token"], "client_device_id": "device-1"},
    )
    assert (stale.status_code, error_code(stale)) == (401, "refresh_invalid")

    logout = api_client.post("/api/v1/auth/logout", json={"refresh_token": second["refresh_token"]})
    assert logout.status_code == 204
    after = api_client.get("/api/v1/me", headers=bearer)
    assert (after.status_code, error_code(after)) == (401, "refresh_invalid")

    sessions = _sessions(db_session, employee)
    assert [row.revocation_reason for row in sessions] == ["user_logout"]


def test_wrong_code_exhausts_challenge(api_client: TestClient, db_session: Session) -> None:
    employee = seed.employee(db_session, "sales_person")
    challenge_id = _challenge_id(api_client, employee)

    for remaining in (2, 1):
        wrong = verify_otp(api_client, challenge_id, code=WRONG_CODE)
        assert (wrong.status_code, error_code(wrong)) == (400, "invalid_code")
        assert wrong.json()["error"]["details"]["attempts_remaining"] == remaining

    last = verify_otp(api_client, challenge_id, code=WRONG_CODE)
    assert (last.status_code, error_code(last)) == (409, "challenge_expired")
    correct = verify_otp(api_client, challenge_id, code=OTP)
    assert (correct.status_code, error_code(correct)) == (409, "challenge_expired")

    failed = db_session.scalar(
        select(func.count())
        .select_from(AuthAuditEvent)
        .where(AuthAuditEvent.employee_id == employee.id, AuthAuditEvent.event_type == "otp_failed")
    )
    assert failed == 3
    assert _sessions(db_session, employee) == []


def test_who_cannot_log_in(api_client: TestClient, db_session: Session) -> None:
    unknown = request_otp(api_client, "+919111111111")
    assert (unknown.status_code, error_code(unknown)) == (404, "phone_not_registered")

    manager = seed.employee(db_session, "manager", full_name="Meera Manager")
    inactive = seed.employee(db_session, "sales_person", manager=manager)
    _deactivate(db_session, inactive)
    blocked = request_otp(api_client, seed.phone_of(inactive))
    assert (blocked.status_code, error_code(blocked)) == (403, "account_deactivated")
    contact = api_client.get(
        "/api/v1/auth/manager-contact",
        params={"challenge_id": blocked.json()["error"]["details"]["challenge_id"]},
    )
    assert contact.status_code == 200, contact.text
    assert contact.json() == {
        "manager_name": "Meera Manager",
        "manager_phone_e164": seed.phone_of(manager),
    }

    late = seed.employee(db_session, "sales_person", manager=manager)
    challenge_id = _challenge_id(api_client, late)
    _deactivate(db_session, late)
    verified = verify_otp(api_client, challenge_id)
    assert (verified.status_code, error_code(verified)) == (404, "employee_not_found")
    assert _sessions(db_session, late) == []


def test_otp_request_idempotency(api_client: TestClient, db_session: Session) -> None:
    employee = seed.employee(db_session, "sales_person")
    key = generate_ulid()

    first = request_otp(api_client, seed.phone_of(employee), key=key)
    replay = request_otp(api_client, seed.phone_of(employee), key=key)
    assert first.status_code == replay.status_code == 200
    assert replay.json()["challenge_id"] == first.json()["challenge_id"]
    challenges = db_session.scalar(
        select(func.count())
        .select_from(OtpChallenge)
        .where(OtpChallenge.employee_id == employee.id)
    )
    assert challenges == 1

    conflict = request_otp(api_client, seed.phone_of(employee), device_id="device-2", key=key)
    assert (conflict.status_code, error_code(conflict)) == (409, "idempotency_conflict")


def test_verify_rate_limited_per_phone(api_client: TestClient, db_session: Session) -> None:
    employee = seed.employee(db_session, "sales_person")

    for wrong_attempts in (2, 2, 1):
        challenge_id = _challenge_id(api_client, employee)
        for _ in range(wrong_attempts):
            wrong = verify_otp(api_client, challenge_id, code=WRONG_CODE)
            assert (wrong.status_code, error_code(wrong)) == (400, "invalid_code")

    sixth = verify_otp(api_client, challenge_id, code=OTP)
    assert (sixth.status_code, error_code(sixth)) == (429, "otp_rate_limited")
    assert _sessions(db_session, employee) == []

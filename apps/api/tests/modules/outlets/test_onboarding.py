from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.fakes.humbee import FakeHumbee
from tests.fakes.humbee_onboarding import (
    FIRM_ROLE_ID,
    LOCATION_ID,
    MANUFACTURER_ID,
    PINCODE,
    install_onboarding,
)
from tests.fixtures import seed
from tests.fixtures.auth import OTP, Authed, login
from tests.fixtures.flows import error_code, team

from humbee_sfa.core.conventions import generate_ulid
from humbee_sfa.modules.outlets.models import OutletOnboardingCandidate

ONBOARDING = "/api/v1/outlets/onboarding"
VERIFY_PHONE = "/sfa/v1/verify/phone-number"
ONBOARD = "/sfa/v1/onboard"
OWNER_PHONE = "+917000000001"
GSTIN = "29ABCDE1234F1Z5"


@pytest.fixture(autouse=True)
def onboarding_masters(humbee: FakeHumbee) -> None:
    install_onboarding(humbee)


def _request_otp(sp: Authed, phone: str = OWNER_PHONE) -> Any:
    return sp.post(f"{ONBOARDING}/owner-otp/request", {"phone_e164": phone})


def _verify(sp: Authed, challenge_id: str) -> None:
    verified = sp.post(f"{ONBOARDING}/owner-otp/verify", {"challenge_id": challenge_id, "code": OTP})
    assert verified.status_code == 200, verified.text
    assert verified.json()["verified"] is True


def _verified_challenge(sp: Authed, phone: str = OWNER_PHONE) -> str:
    requested = _request_otp(sp, phone)
    assert requested.status_code == 200, requested.text
    _verify(sp, requested.json()["challenge_id"])
    return requested.json()["challenge_id"]


def _address(**extra: str) -> dict[str, Any]:
    return {
        "company_address": {"address_line_1": "12 MG Road", "address_line_2": "Shivajinagar"},
        "state_id": "10",
        "state_name": "Karnataka",
        "district_id": "100",
        "district_name": "Bengaluru Urban",
        **extra,
    }


def _candidate_body(challenge_id: str, phone: str = OWNER_PHONE, **overrides: Any) -> dict[str, Any]:
    return {
        "challenge_id": challenge_id,
        "phone_number": phone,
        "company_name": "Sri Lakshmi Traders",
        "company_gstin": GSTIN,
        "registered_address": _address(),
        "operational_address": _address(location_id=LOCATION_ID, pincode=PINCODE),
        "date_of_birth": "1980-05-17",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "roles": [{"manufacturer_id": MANUFACTURER_ID, "firm_role_id": FIRM_ROLE_ID}],
        **overrides,
    }


def _capture(sp: Authed, phone: str = OWNER_PHONE) -> dict[str, Any]:
    created = sp.post(f"{ONBOARDING}/candidates", _candidate_body(_verified_challenge(sp, phone), phone))
    assert created.status_code == 201, created.text
    return created.json()


def _candidate(sp: Authed, candidate_id: str) -> dict[str, Any]:
    response = sp.get(f"{ONBOARDING}/candidates/{candidate_id}")
    assert response.status_code == 200, response.text
    return response.json()


def _candidate_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(OutletOnboardingCandidate))


def test_capture_and_manager_approval_onboards_to_humbee(
    api_client: TestClient, db_session: Session, humbee: FakeHumbee
) -> None:
    sp, manager = team(db_session, api_client)

    challenge_id = _request_otp(sp).json()["challenge_id"]
    refused = sp.post(f"{ONBOARDING}/candidates", _candidate_body(challenge_id))
    assert refused.status_code == 409
    assert error_code(refused) == "owner_phone_not_verified"

    _verify(sp, challenge_id)
    too_young = sp.post(f"{ONBOARDING}/candidates", _candidate_body(challenge_id, date_of_birth="2013-01-01"))
    assert too_young.status_code == 422
    assert error_code(too_young) == "date_of_birth_invalid"

    key = generate_ulid()
    body = _candidate_body(challenge_id)
    created = sp.post(f"{ONBOARDING}/candidates", body, key=key)
    assert created.status_code == 201, created.text
    candidate = created.json()
    assert candidate["status"] == "pending_approval"

    phone_checks = len(humbee.calls_to("GET", VERIFY_PHONE))
    replayed = sp.post(f"{ONBOARDING}/candidates", body, key=key)
    assert replayed.status_code == 201, replayed.text
    assert replayed.json()["id"] == candidate["id"]
    assert len(humbee.calls_to("GET", VERIFY_PHONE)) == phone_checks

    duplicate = sp.post(f"{ONBOARDING}/candidates", body)
    assert duplicate.status_code == 409
    assert error_code(duplicate) == "candidate_already_captured"
    assert _candidate_count(db_session) == 1

    inbox = manager.get("/api/v1/approvals", subject_type="outlet").json()["items"]
    assert [(i["id"], i["subject_id"], i["assigned_approver_id"], i["routing_reason"]) for i in inbox] == [
        (candidate["approval_request_id"], candidate["id"], manager.employee.id, "direct_parent")
    ]
    assert humbee.calls_to("POST", ONBOARD) == []

    approved = manager.post(f"/api/v1/approvals/{candidate['approval_request_id']}/approve", {})
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    submitted = _candidate(sp, candidate["id"])
    assert submitted["status"] == "submitted"
    assert submitted["humbee_company_id"] == "9001"
    assert submitted["submission_error"] is None
    [onboard_call] = humbee.calls_to("POST", ONBOARD)
    assert onboard_call.json == {
        "phone_number": "7000000001",
        "registered_address": {
            "company_address": {"address_line_1": "12 MG Road", "address_line_2": "Shivajinagar"},
            "state_id": "10",
            "district_id": "100",
        },
        "operational_address": {
            "company_address": {"address_line_1": "12 MG Road", "address_line_2": "Shivajinagar"},
            "state_id": "10",
            "district_id": "100",
            "location_id": LOCATION_ID,
            "pincode": PINCODE,
        },
        "onboarded_by": sp.employee.id,
        "roles": [{"manufacturer_id": MANUFACTURER_ID, "firm_role_id": FIRM_ROLE_ID}],
        "industries": [],
        "company_name": "Sri Lakshmi Traders",
        "company_gstin": GSTIN,
        "date_of_birth": "1980-05-17",
        "latitude": 12.9716,
        "longitude": 77.5946,
    }


def test_owner_phone_already_on_humbee_is_refused(
    api_client: TestClient, db_session: Session, humbee: FakeHumbee
) -> None:
    sp, _ = team(db_session, api_client)

    humbee.fail("GET", VERIFY_PHONE, "088")
    blocked = _request_otp(sp)
    assert blocked.status_code == 409
    assert error_code(blocked) == "owner_already_on_humbee"

    challenge_id = _verified_challenge(sp)
    humbee.fail("GET", VERIFY_PHONE, "088")
    refused = sp.post(f"{ONBOARDING}/candidates", _candidate_body(challenge_id))
    assert refused.status_code == 409
    assert error_code(refused) == "owner_already_on_humbee"
    assert _candidate_count(db_session) == 0


def test_humbee_refusing_onboard_marks_submission_failed(
    api_client: TestClient, db_session: Session, humbee: FakeHumbee
) -> None:
    sp, manager = team(db_session, api_client)
    candidate = _capture(sp)

    humbee.fail("POST", ONBOARD, "088")
    approved = manager.post(f"/api/v1/approvals/{candidate['approval_request_id']}/approve", {})
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    failed = _candidate(sp, candidate["id"])
    assert failed["status"] == "submission_failed"
    assert failed["submission_error"] == "Owner phone is already registered on Humbee."
    assert failed["humbee_company_id"] is None
    assert len(humbee.calls_to("POST", ONBOARD)) == 1


def test_manager_rejection_releases_the_owner_phone(
    api_client: TestClient, db_session: Session, humbee: FakeHumbee
) -> None:
    sp, manager = team(db_session, api_client)
    candidate = _capture(sp)

    rejected = manager.post(
        f"/api/v1/approvals/{candidate['approval_request_id']}/reject", {"reason": "Shop is closed down"}
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"
    assert _candidate(sp, candidate["id"])["status"] == "rejected"
    assert humbee.calls_to("POST", ONBOARD) == []

    recaptured = _capture(sp)
    assert recaptured["id"] != candidate["id"]
    assert recaptured["status"] == "pending_approval"


def test_admin_may_see_and_decide_outlet_verification(
    api_client: TestClient, db_session: Session, humbee: FakeHumbee
) -> None:
    sp, _ = team(db_session, api_client)
    admin = login(api_client, seed.employee(db_session, "admin"))
    candidate = _capture(sp)
    approval_id = candidate["approval_request_id"]

    inbox = admin.get("/api/v1/approvals", subject_type="outlet").json()
    assert inbox["pending_count"] == 1
    assert [(i["id"], i["can_decide"]) for i in inbox["items"]] == [(approval_id, True)]
    assert admin.get("/api/v1/approvals/summary").json()["pending_by_filter"]["outlet"] == 1
    assert admin.get(f"/api/v1/approvals/{approval_id}").status_code == 200

    approved = admin.post(f"/api/v1/approvals/{approval_id}/approve", {})
    assert approved.status_code == 200, approved.text
    assert approved.json()["decided_by_id"] == admin.employee.id

    submitted = _candidate(sp, candidate["id"])
    assert submitted["status"] == "submitted"
    assert submitted["humbee_company_id"] == "9001"

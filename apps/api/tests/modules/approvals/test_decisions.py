from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.conftest import NOW
from tests.fixtures import seed
from tests.fixtures.auth import Authed, login
from tests.fixtures.flows import error_code

from humbee_sfa.core.conventions import generate_ulid
from humbee_sfa.modules.approvals import repository as approvals_repository
from humbee_sfa.modules.org.models import Employee


def _file_leave(sp: Authed) -> str:
    response = sp.post(
        "/api/v1/leave/requests",
        {"leave_type": "casual", "from_date": "2026-10-21", "to_date": "2026-10-23"},
    )
    assert response.status_code == 201, response.text
    return response.json()["approval_request_id"]


def _pending(db: Session, *, subject_type: str, requester: Employee, approver: Employee) -> None:
    approvals_repository.insert_request(
        db,
        tenant_id=seed.tenant_id(),
        subject_type=subject_type,
        subject_id=generate_ulid(),
        requester_id=requester.id,
        requester_manager_id=approver.id,
        assigned_approver_id=approver.id,
        routing_reason="direct_parent",
        escalated_from_id=None,
        escalation_depth=0,
        status="pending",
        title=subject_type,
        subtitle=subject_type,
        amount_paise=None,
        submitted_at=NOW,
        submitted_business_date=date(2026, 10, 19),
    )
    db.flush()


def test_decision_rules_on_a_leave_request(api_client: TestClient, db_session: Session) -> None:
    manager = seed.employee(db_session, "manager")
    sp_row = seed.employee(db_session, "sales_person", manager=manager)
    other = login(api_client, seed.employee(db_session, "manager"))
    admin = login(api_client, seed.employee(db_session, "admin"))
    sp = login(api_client, sp_row)
    boss = login(api_client, manager)
    approval_id = _file_leave(sp)

    inbox = boss.get("/api/v1/approvals").json()
    assert inbox["pending_count"] == 1
    [item] = inbox["items"]
    assert (item["id"], item["assigned_approver_id"], item["routing_reason"], item["can_decide"]) == (
        approval_id,
        manager.id,
        "direct_parent",
        True,
    )

    assert other.get("/api/v1/approvals").json()["pending_count"] == 0
    stranger = other.post(f"/api/v1/approvals/{approval_id}/approve", {})
    assert (stranger.status_code, error_code(stranger)) == (403, "not_the_assigned_approver")

    admin_inbox = admin.get("/api/v1/approvals").json()
    assert (admin_inbox["pending_count"], admin_inbox["items"]) == (0, [])
    admin_read = admin.get(f"/api/v1/approvals/{approval_id}")
    assert (admin_read.status_code, error_code(admin_read)) == (404, "approval_not_found")

    stale = boss.post(f"/api/v1/approvals/{approval_id}/approve", {}, headers={"If-Match": "9"})
    assert (stale.status_code, error_code(stale)) == (412, "subject_changed")
    blank = boss.post(f"/api/v1/approvals/{approval_id}/reject", {"reason": "   "})
    assert (blank.status_code, error_code(blank)) == (422, "reason_required")

    key = generate_ulid()
    approved = boss.post(f"/api/v1/approvals/{approval_id}/approve", {}, key=key)
    assert approved.status_code == 200, approved.text
    assert (approved.json()["status"], approved.json()["decided_by_id"]) == ("approved", manager.id)
    replay = boss.post(f"/api/v1/approvals/{approval_id}/approve", {}, key=key)
    assert (replay.status_code, replay.json()) == (200, approved.json())

    again = boss.post(f"/api/v1/approvals/{approval_id}/approve", {})
    assert (again.status_code, error_code(again)) == (409, "approval_already_decided")
    withdraw = sp.post(f"/api/v1/approvals/{approval_id}/withdraw", {})
    assert (withdraw.status_code, error_code(withdraw)) == (409, "approval_already_decided")

    leave = sp.get("/api/v1/leave/requests/mine").json()["items"]
    assert [row["status"] for row in leave] == ["approved"]


def test_summary_counts_pending_per_filter(api_client: TestClient, db_session: Session) -> None:
    manager = seed.employee(db_session, "manager")
    sp_row = seed.employee(db_session, "sales_person", manager=manager)
    _file_leave(login(api_client, sp_row))
    _pending(db_session, subject_type="beat_create", requester=sp_row, approver=manager)
    _pending(db_session, subject_type="dp_order", requester=sp_row, approver=manager)

    summary = login(api_client, manager).get("/api/v1/approvals/summary")
    assert summary.status_code == 200, summary.text
    assert summary.json() == {
        "pending_total": 3,
        "pending_by_filter": {"order": 1, "beat": 1, "leave": 1, "outlet": 0},
    }


def test_decisions_notify_the_other_party_once(api_client: TestClient, db_session: Session) -> None:
    manager = seed.employee(db_session, "manager")
    sp = login(api_client, seed.employee(db_session, "sales_person", manager=manager))
    boss = login(api_client, manager)
    approval_id = _file_leave(sp)

    boss_feed = boss.get("/api/v1/notifications").json()
    assert boss_feed["unread_count"] == 1
    [submitted] = boss_feed["items"]
    assert (submitted["kind"], submitted["source_request_id"]) == ("submitted", approval_id)
    assert sp.get("/api/v1/notifications").json()["items"] == []

    key = generate_ulid()
    assert boss.post(f"/api/v1/approvals/{approval_id}/approve", {}, key=key).status_code == 200
    assert boss.post(f"/api/v1/approvals/{approval_id}/approve", {}, key=key).status_code == 200

    sp_feed = sp.get("/api/v1/notifications").json()
    assert [(row["kind"], row["deep_link_type"]) for row in sp_feed["items"]] == [("approved", "leave")]
    approved_id = sp_feed["items"][0]["id"]
    assert sp.get("/api/v1/notifications/unread-count").json() == {"count": 1}

    first = sp.post(f"/api/v1/notifications/{approved_id}/read").json()
    assert (first["changed"], first["unread_count"]) == (True, 0)
    second = sp.post(f"/api/v1/notifications/{approved_id}/read").json()
    assert (second["changed"], second["read_at"]) == (False, first["read_at"])
    assert sp.get("/api/v1/notifications/unread-count").json() == {"count": 0}

    assert boss.post("/api/v1/notifications/read-all").json() == {"marked": 1, "unread_count": 0}
    assert boss.post("/api/v1/notifications/read-all").json() == {"marked": 0, "unread_count": 0}

    foreign = sp.get(f"/api/v1/notifications/{submitted['id']}")
    assert (foreign.status_code, error_code(foreign)) == (404, "notification_not_found")
    foreign_read = sp.post(f"/api/v1/notifications/{submitted['id']}/read")
    assert (foreign_read.status_code, error_code(foreign_read)) == (404, "notification_not_found")

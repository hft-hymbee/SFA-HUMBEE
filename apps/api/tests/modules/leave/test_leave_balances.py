from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.fixtures import seed
from tests.fixtures.auth import Authed, login
from tests.fixtures.flows import error_code, team


def _casual(user: Authed) -> dict[str, Any]:
    response = user.get("/api/v1/leave/balances/me")
    assert response.status_code == 200, response.text
    return next(item for item in response.json()["items"] if item["leave_type"] == "casual")


def _file(user: Authed, leave_type: str, from_date: str, to_date: str) -> dict[str, Any]:
    response = user.post(
        "/api/v1/leave/requests",
        {"leave_type": leave_type, "from_date": from_date, "to_date": to_date},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _decide(user: Authed, approval_id: str, action: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    response = user.post(f"/api/v1/approvals/{approval_id}/{action}", body or {})
    assert response.status_code == 200, response.text
    return response.json()


def test_balance_lifecycle_through_approve_reject_withdraw(api_client: TestClient, db_session: Session) -> None:
    sp, boss = team(db_session, api_client)

    balances = sp.get("/api/v1/leave/balances/me").json()
    assert balances["period_year"] == 2026
    assert {item["leave_type"]: item["available_days"] for item in balances["items"]} == {
        "privileged": 12,
        "casual": 6,
        "sick": 6,
    }

    preview = sp.get("/api/v1/leave/preview", leave_type="casual", from_date="2026-10-21", to_date="2026-10-23")
    assert preview.status_code == 200, preview.text
    assert (preview.json()["day_count"], preview.json()["balance_after"]) == (3, 3)

    first = _file(sp, "casual", "2026-10-21", "2026-10-23")
    assert (first["status"], first["day_count"]) == ("pending", 3)
    casual = _casual(sp)
    assert (casual["pending_days"], casual["available_days"]) == (3, 3)

    assert _decide(boss, first["approval_request_id"], "approve")["status"] == "approved"
    casual = _casual(sp)
    assert (casual["consumed_days"], casual["pending_days"], casual["available_days"]) == (3, 0, 3)

    overlapping = sp.post(
        "/api/v1/leave/requests", {"leave_type": "sick", "from_date": "2026-10-23", "to_date": "2026-10-23"}
    )
    assert overlapping.status_code == 409
    assert error_code(overlapping) == "overlapping_leave"

    weekend = _file(sp, "casual", "2026-10-24", "2026-10-25")
    assert weekend["day_count"] == 2
    assert _casual(sp)["available_days"] == 1
    assert _decide(boss, weekend["approval_request_id"], "reject", {"reason": "Stock count"})["status"] == "rejected"
    casual = _casual(sp)
    assert (casual["pending_days"], casual["available_days"]) == (0, 3)

    third = _file(sp, "casual", "2026-10-26", "2026-10-26")
    assert _casual(sp)["pending_days"] == 1
    assert _decide(sp, third["approval_request_id"], "withdraw")["status"] == "withdrawn"
    casual = _casual(sp)
    assert (casual["consumed_days"], casual["pending_days"], casual["available_days"]) == (3, 0, 3)

    mine = sp.get("/api/v1/leave/requests/mine").json()["items"]
    assert sorted(item["status"] for item in mine) == ["approved", "rejected", "withdrawn"]

    inverted = sp.post(
        "/api/v1/leave/requests", {"leave_type": "casual", "from_date": "2026-10-30", "to_date": "2026-10-29"}
    )
    assert inverted.status_code == 422
    assert error_code(inverted) == "invalid_date_range"


def test_over_balance_is_advisory(api_client: TestClient, db_session: Session) -> None:
    sp, _ = team(db_session, api_client)

    preview = sp.get("/api/v1/leave/preview", leave_type="casual", from_date="2026-10-21", to_date="2026-10-28")
    assert preview.status_code == 200, preview.text
    assert preview.json()["day_count"] == 8
    assert preview.json()["balance_after"] == -2
    assert preview.json()["exceeds_balance"] is True

    request = _file(sp, "casual", "2026-10-21", "2026-10-28")
    assert request["status"] == "pending"
    assert request["balance_after_projected"] == -2
    casual = _casual(sp)
    assert (casual["pending_days"], casual["available_days"]) == (8, -2)


def test_top_of_hierarchy_leave_is_auto_approved(api_client: TestClient, db_session: Session) -> None:
    top = login(api_client, seed.employee(db_session, "manager"))

    request = _file(top, "sick", "2026-10-21", "2026-10-22")
    assert request["status"] == "auto_approved"
    sick = next(
        item for item in top.get("/api/v1/leave/balances/me").json()["items"] if item["leave_type"] == "sick"
    )
    assert (sick["consumed_days"], sick["pending_days"], sick["available_days"]) == (2, 0, 4)
    assert top.get("/api/v1/approvals/summary").json()["pending_total"] == 0


def test_team_leave_is_scoped_to_own_tree(api_client: TestClient, db_session: Session) -> None:
    manager_a = seed.employee(db_session, "manager")
    manager_b = seed.employee(db_session, "manager")
    sp_a = login(api_client, seed.employee(db_session, "sales_person", manager=manager_a))
    sp_b = login(api_client, seed.employee(db_session, "sales_person", manager=manager_b))
    own = _file(sp_a, "casual", "2026-10-21", "2026-10-21")
    _file(sp_b, "casual", "2026-10-21", "2026-10-21")

    team = login(api_client, manager_a).get("/api/v1/leave/team")
    assert team.status_code == 200, team.text
    assert [(item["id"], item["employee_id"]) for item in team.json()["items"]] == [
        (own["id"], sp_a.employee.id)
    ]

    refused = sp_a.get("/api/v1/leave/team")
    assert refused.status_code == 403
    assert error_code(refused) == "forbidden"

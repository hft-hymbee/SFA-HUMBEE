from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.fakes.humbee import FakeHumbee
from tests.fakes.humbee_targets import install_target_manufacturers
from tests.fixtures import seed
from tests.fixtures.auth import login
from tests.fixtures.flows import error_code

from humbee_sfa.core.conventions import generate_ulid
from humbee_sfa.modules.targets.models import Lead, Target

MONTH = "2026-10-01"


@pytest.fixture(autouse=True)
def manufacturers(humbee: FakeHumbee) -> None:
    install_target_manufacturers(
        humbee,
        {
            "501": ("Aashirvaad Foods", "amount"),
            "502": ("Shakti Cement", "volume"),
            "503": ("Sunrise Spices", "amount"),
        },
    )


def _sales(employee_id: str, lines: list[tuple[str, int]], period_month: str = MONTH) -> dict[str, object]:
    return {
        "employee_id": employee_id,
        "target_type": "sales",
        "period_month": period_month,
        "lines": [{"manufacturer_id": m, "line_value": v} for m, v in lines],
    }


def test_set_change_and_remove_sales_target(api_client: TestClient, db_session: Session) -> None:
    manager = seed.employee(db_session, "manager")
    sp = seed.employee(db_session, "sales_person", manager=manager)
    as_manager = login(api_client, manager)

    created = as_manager.post("/api/v1/targets", _sales(sp.id, [("501", 5_000_000), ("502", 40), ("503", 2_500_000)]))
    assert created.status_code == 201, created.text
    target = created.json()
    assert target["target_value_amount_paise"] == 7_500_000
    assert target["target_value_volume_units"] == 40
    assert target["target_value"] is None
    assert target["version"] == 1
    assert {(line["manufacturer_id"], line["line_basis"], line["uom_label"]) for line in target["lines"]} == {
        ("501", "amount", "₹"),
        ("502", "volume", "Ton"),
        ("503", "amount", "₹"),
    }

    again = as_manager.post("/api/v1/targets", _sales(sp.id, [("501", 1)]))
    assert (again.status_code, error_code(again)) == (409, "target_already_set")

    path = f"/api/v1/targets/{target['id']}"
    update = {"target_type": "sales", "version": 1, "lines": [{"manufacturer_id": "502", "line_value": 15}]}
    updated = as_manager.put(path, update)
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2
    assert updated.json()["target_value_amount_paise"] is None
    assert updated.json()["target_value_volume_units"] == 15

    stale = as_manager.put(path, update)
    assert (stale.status_code, error_code(stale)) == (409, "target_version_conflict")

    retyped = as_manager.put(path, {"target_type": "leads", "version": 2, "target_value": 5})
    assert (retyped.status_code, error_code(retyped)) == (422, "target_type_immutable")

    listed = as_manager.get("/api/v1/targets", employee_id=sp.id, period_month=MONTH)
    assert [(t["id"], len(t["lines"])) for t in listed.json()["targets"]] == [(target["id"], 1)]

    removed = as_manager.delete(path)
    assert removed.status_code == 200, removed.text
    assert removed.json()["status"] == "removed"
    assert removed.json()["removed_by"] == manager.id

    after_removal = as_manager.put(path, {**update, "version": 3})
    assert (after_removal.status_code, error_code(after_removal)) == (409, "target_removed")
    assert as_manager.get("/api/v1/targets", employee_id=sp.id, period_month=MONTH).json()["targets"] == []

    reset = as_manager.post("/api/v1/targets", _sales(sp.id, [("503", 900)]))
    assert reset.status_code == 201, reset.text
    assert reset.json()["target_value_amount_paise"] == 900


def test_who_may_set_a_target_and_for_when(api_client: TestClient, db_session: Session) -> None:
    manager = seed.employee(db_session, "manager")
    sp = seed.employee(db_session, "sales_person", manager=manager)
    other_manager = seed.employee(db_session, "manager")
    other_sp = seed.employee(db_session, "sales_person", manager=other_manager)
    admin = seed.employee(db_session, "admin")
    as_manager = login(api_client, manager)

    by_sp = login(api_client, sp).post("/api/v1/targets", _sales(sp.id, [("501", 100)]))
    assert (by_sp.status_code, error_code(by_sp)) == (403, "forbidden")

    out_of_tree = as_manager.post("/api/v1/targets", _sales(other_sp.id, [("501", 100)]))
    assert (out_of_tree.status_code, error_code(out_of_tree)) == (404, "employee_not_found")

    for_admin = login(api_client, admin).post("/api/v1/targets", _sales(admin.id, [("501", 100)]))
    assert (for_admin.status_code, error_code(for_admin)) == (422, "target_subject_not_hierarchy_member")

    past = as_manager.post("/api/v1/targets", _sales(sp.id, [("501", 100)], "2026-09-01"))
    assert (past.status_code, error_code(past)) == (422, "period_in_the_past")

    mid_month = as_manager.post("/api/v1/targets", _sales(sp.id, [("501", 100)], "2026-10-15"))
    assert (mid_month.status_code, error_code(mid_month)) == (422, "period_not_month_start")

    unknown = as_manager.post("/api/v1/targets", _sales(sp.id, [("501", 100), ("999", 5)]))
    assert (unknown.status_code, error_code(unknown)) == (422, "manufacturer_not_found")

    outlets = {"employee_id": sp.id, "target_type": "outlets", "period_month": MONTH, "target_value": 12}
    for scope in (None, "pharmacy"):
        body = outlets if scope is None else {**outlets, "outlet_category_scope": scope}
        refused = as_manager.post("/api/v1/targets", body)
        assert (refused.status_code, error_code(refused)) == (422, "validation_error")
    accepted = as_manager.post("/api/v1/targets", {**outlets, "outlet_category_scope": "grocery"})
    assert accepted.status_code == 201, accepted.text
    assert (accepted.json()["target_value"], accepted.json()["outlet_category_scope"]) == (12, "grocery")

    assert db_session.scalar(select(func.count()).select_from(Target)) == 1


def test_target_roster_lists_own_tree(api_client: TestClient, db_session: Session) -> None:
    manager = seed.employee(db_session, "manager")
    with_target = seed.employee(db_session, "sales_person", manager=manager, full_name="Asha Rao")
    without_target = seed.employee(db_session, "sales_person", manager=manager, full_name="Bala Iyer")
    other_manager = seed.employee(db_session, "manager")
    seed.employee(db_session, "sales_person", manager=other_manager)
    as_manager = login(api_client, manager)
    assert as_manager.post("/api/v1/targets", _sales(with_target.id, [("501", 100)])).status_code == 201

    roster = as_manager.get("/api/v1/targets/roster")
    assert roster.status_code == 200, roster.text
    body = roster.json()
    assert (body["period_month"], body["total"], body["with_target"]) == (MONTH, 2, 1)
    assert [(m["employee_id"], m["active_target_count"]) for m in body["members"]] == [
        (with_target.id, 1),
        (without_target.id, 0),
    ]

    by_sp = login(api_client, with_target).get("/api/v1/targets/roster")
    assert (by_sp.status_code, error_code(by_sp)) == (403, "forbidden")


def test_reused_lead_id_conflicts(api_client: TestClient, db_session: Session) -> None:
    sp = seed.employee(db_session, "sales_person", manager=seed.employee(db_session, "manager"))
    as_sp = login(api_client, sp)
    body = {
        "id": generate_ulid(),
        "name": "Ravi Kumar",
        "mobile": "+91 98450 12345",
        "email": "ravi@example.com",
        "company_name": "Kumar Traders",
        "associated_manufacturers": ["Acme Oils"],
    }

    captured = as_sp.post("/api/v1/leads", body)
    assert captured.status_code == 201, captured.text

    reused = as_sp.post("/api/v1/leads", {**body, "company_name": "Other Traders"})
    assert (reused.status_code, error_code(reused)) == (409, "lead_id_taken")
    assert db_session.scalar(select(func.count()).select_from(Lead)) == 1

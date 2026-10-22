from __future__ import annotations

import itertools
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.fixtures import seed
from tests.fixtures.auth import Authed, login
from tests.fixtures.flows import error_code

from humbee_sfa.core.conventions import generate_ulid
from humbee_sfa.core.settings import get_settings
from humbee_sfa.modules.identity.models import Session as IdentitySession
from humbee_sfa.modules.org.models import Employee, GeographyScopeAssignment, HierarchyEdge
from humbee_sfa.platform.models import AuditLog

EMPLOYEES = "/api/v1/org/employees"
_numbers = itertools.count(90001)


def _body(role: str, *, manager_id: str | None = None, **overrides: Any) -> dict[str, Any]:
    n = next(_numbers)
    return {
        "employee_code": f"E{n:05d}",
        "full_name": f"Created {n}",
        "phone_e164": f"+9198{n:08d}",
        "role_code": role,
        "designation_code": seed.DEFAULT_DESIGNATION[role],
        "manager_employee_id": manager_id,
        **overrides,
    }


def _create(admin: Authed, role: str, *, manager_id: str | None = None) -> str:
    response = admin.post(EMPLOYEES, _body(role, manager_id=manager_id))
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _edges(db: Session, *employee_ids: str) -> set[tuple[str, str, int]]:
    rows = db.execute(
        select(
            HierarchyEdge.ancestor_employee_id,
            HierarchyEdge.descendant_employee_id,
            HierarchyEdge.depth,
        ).where(HierarchyEdge.descendant_employee_id.in_(employee_ids))
    )
    return {(ancestor, descendant, depth) for ancestor, descendant, depth in rows}


def _audits(db: Session, entity_id: str, transition: str) -> int:
    return db.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.entity_id == entity_id,
            AuditLog.change_payload["transition"].astext == transition,
        )
    )


def _employee_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Employee))


def test_build_move_and_scope(api_client: TestClient, db_session: Session) -> None:
    admin = login(api_client, seed.employee(db_session, "admin"))
    a = _create(admin, "manager")
    b = _create(admin, "manager")
    sp = _create(admin, "sales_person", manager_id=a)
    assert _edges(db_session, a, b, sp) == {(a, a, 0), (b, b, 0), (a, sp, 1), (sp, sp, 0)}

    as_a = login(api_client, db_session.get(Employee, a))
    as_b = login(api_client, db_session.get(Employee, b))
    assert sp in {item["id"] for item in as_a.get(EMPLOYEES).json()["items"]}
    hidden = as_b.get(f"{EMPLOYEES}/{sp}")
    assert (hidden.status_code, error_code(hidden)) == (404, "employee_not_found")

    moved = admin.post(f"{EMPLOYEES}/{sp}/move", {"new_manager_employee_id": b})
    assert moved.status_code == 200, moved.text
    assert moved.json()["manager_employee_id"] == b
    assert _edges(db_session, a, b, sp) == {(a, a, 0), (b, b, 0), (b, sp, 1), (sp, sp, 0)}
    assert as_a.get(f"{EMPLOYEES}/{sp}").status_code == 404
    assert as_b.get(f"{EMPLOYEES}/{sp}").status_code == 200
    assert _audits(db_session, sp, "employee_moved") == 1

    cycle = admin.post(f"{EMPLOYEES}/{b}/move", {"new_manager_employee_id": sp})
    assert (cycle.status_code, error_code(cycle)) == (409, "cycle_detected")

    same = admin.post(f"{EMPLOYEES}/{sp}/move", {"new_manager_employee_id": b})
    assert same.status_code == 200
    assert _audits(db_session, sp, "employee_moved") == 1
    assert _edges(db_session, a, b, sp) == {(a, a, 0), (b, b, 0), (b, sp, 1), (sp, sp, 0)}


def test_create_validation(api_client: TestClient, db_session: Session) -> None:
    admin = login(api_client, seed.employee(db_session, "admin"))
    manager = seed.employee(db_session, "manager")
    sp = seed.employee(db_session, "sales_person", manager=manager)
    before = _employee_count(db_session)

    rejected = [
        (
            admin,
            _body("sales_person", designation_code="area_sales_manager"),
            422,
            "designation_role_mismatch",
        ),
        (
            admin,
            _body("sales_person", phone_e164=seed.phone_of(sp)),
            409,
            "phone_already_registered",
        ),
        (admin, _body("sales_person", employee_code=sp.employee_code), 409, "employee_code_taken"),
        (admin, _body("sales_person", manager_id=sp.id), 422, "invalid_manager"),
        (
            login(api_client, manager),
            _body("sales_person", manager_id=manager.id),
            403,
            "forbidden",
        ),
    ]
    for actor, body, status, code in rejected:
        response = actor.post(EMPLOYEES, body)
        assert (response.status_code, error_code(response)) == (status, code), body

    assert _employee_count(db_session) == before


def test_deactivation_ends_access(api_client: TestClient, db_session: Session) -> None:
    admin_row = seed.employee(db_session, "admin")
    admin = login(api_client, admin_row)
    manager = seed.employee(db_session, "manager")
    sp = seed.employee(db_session, "sales_person", manager=manager)
    sp_web = login(api_client, sp, device_id="web")
    sp_phone = login(api_client, sp, device_id="phone")

    demote = admin.patch(
        f"{EMPLOYEES}/{manager.id}",
        {"role_code": "sales_person", "designation_code": "network_officer_salesperson"},
    )
    assert (demote.status_code, error_code(demote)) == (409, "employee_has_reports")

    deactivated = admin.post(f"{EMPLOYEES}/{sp.id}/deactivate", {"reason": "left"})
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["status"] == "inactive"

    for client in (sp_web, sp_phone):
        me = client.get("/api/v1/me")
        assert (me.status_code, error_code(me)) == (403, "account_deactivated")
    reasons = db_session.scalars(
        select(IdentitySession.revocation_reason).where(IdentitySession.employee_id == sp.id)
    ).all()
    assert reasons == ["deactivated", "deactivated"]

    again = admin.post(f"{EMPLOYEES}/{sp.id}/deactivate", {"reason": "left"})
    assert again.status_code == 200
    assert _audits(db_session, sp.id, "employee_deactivated") == 1

    itself = admin.post(f"{EMPLOYEES}/{admin_row.id}/deactivate", {})
    assert (itself.status_code, error_code(itself)) == (409, "self_deactivation_forbidden")


def test_admin_bootstrap(api_client: TestClient, db_session: Session) -> None:
    body = {
        key: value
        for key, value in _body("admin").items()
        if key not in ("role_code", "designation_code", "manager_employee_id")
    }

    wrong = api_client.post(
        "/api/v1/org/admins",
        headers={"api-key": "wrong-key", "Idempotency-Key": generate_ulid()},
        json=body,
    )
    assert (wrong.status_code, error_code(wrong)) == (401, "invalid_api_key")
    assert _employee_count(db_session) == 0

    created = api_client.post(
        "/api/v1/org/admins",
        headers={"api-key": get_settings().humbee_api_key, "Idempotency-Key": generate_ulid()},
        json=body,
    )
    assert created.status_code == 201, created.text
    payload = created.json()
    assert (payload["role_code"], payload["designation_code"], payload["manager_employee_id"]) == (
        "admin",
        "admin",
        None,
    )
    me = login(api_client, db_session.get(Employee, payload["id"])).get("/api/v1/me")
    assert me.json()["role"] == "admin"


def test_geography_scope(api_client: TestClient, db_session: Session) -> None:
    admin = login(api_client, seed.employee(db_session, "admin"))
    manager_row = seed.employee(db_session, "manager")
    sp = seed.employee(db_session, "sales_person", manager=manager_row)
    scope_path = f"{EMPLOYEES}/{sp.id}/geography-scope"
    karnataka = {"zones": ["1"], "states": ["10"], "districts": ["100", "101"]}

    assigned = admin.put(scope_path, karnataka)
    assert assigned.status_code == 200, assigned.text
    read = admin.get(scope_path).json()
    assert {key: read[key] for key in karnataka} == karnataka
    assert read["geo_labels"] == {
        "zones": [{"id": "1", "name": "South"}],
        "states": [{"id": "10", "name": "Karnataka"}],
        "districts": [
            {"id": "100", "name": "Bengaluru Urban", "state_id": "10", "state_name": "Karnataka"},
            {"id": "101", "name": "Mysuru", "state_id": "10", "state_name": "Karnataka"},
        ],
    }
    assert _audits(db_session, _assignment_id(db_session, sp.id), "geo_scope_assigned") == 1

    orphan = admin.put(scope_path, {"zones": ["1"], "states": ["10"], "districts": ["100", "200"]})
    assert (orphan.status_code, error_code(orphan)) == (422, "geography_unknown_identifier")
    assert orphan.json()["error"]["details"]["unknown"] == ["200"]
    assert admin.get(scope_path).json()["districts"] == ["100", "101"]

    manager = login(api_client, manager_row)
    denied = manager.put(scope_path, karnataka)
    assert (denied.status_code, error_code(denied)) == (403, "forbidden")

    unassigned = admin.get(f"{EMPLOYEES}/{manager_row.id}/geography-scope")
    assert (unassigned.status_code, error_code(unassigned)) == (404, "geography_scope_not_assigned")


def _assignment_id(db: Session, employee_id: str) -> str:
    return db.scalar(
        select(GeographyScopeAssignment.id).where(
            GeographyScopeAssignment.employee_id == employee_id
        )
    )


def _shape(node: dict[str, Any]) -> tuple[str, int, list[Any]]:
    return node["id"], node["depth"], [_shape(child) for child in node["children"]]


def test_tree_with_two_roots(api_client: TestClient, db_session: Session) -> None:
    admin = login(api_client, seed.employee(db_session, "admin"))
    first = seed.employee(db_session, "manager", full_name="Anil Root")
    second = seed.employee(db_session, "manager", full_name="Bina Root")
    middle = seed.employee(db_session, "manager", manager=first, full_name="Chetan Middle")
    leaf = seed.employee(db_session, "sales_person", manager=middle, full_name="Deepa Leaf")
    other = seed.employee(db_session, "sales_person", manager=second, full_name="Esha Other")

    own = login(api_client, first).get("/api/v1/org/tree").json()["roots"]
    assert [_shape(root) for root in own] == [(first.id, 0, [(middle.id, 1, [(leaf.id, 2, [])])])]
    assert own[0]["is_actor"] is True

    forest = admin.get("/api/v1/org/tree").json()["roots"]
    assert [_shape(root) for root in forest] == [
        (first.id, 0, [(middle.id, 1, [(leaf.id, 2, [])])]),
        (second.id, 0, [(other.id, 1, [])]),
    ]

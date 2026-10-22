from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import pytest
import time_machine
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.conftest import NOW
from tests.fakes.humbee import FakeHumbee
from tests.fakes.humbee_commerce import FakeCommerce, Product, Seller, install_commerce
from tests.fixtures import seed
from tests.fixtures.auth import Authed, login
from tests.fixtures.flows import check_in, error_code, punch, punch_in

from humbee_sfa.core.conventions import generate_ulid
from humbee_sfa.modules.org.models import Employee
from humbee_sfa.modules.reporting.models import FactEmployeeDay
from humbee_sfa.modules.reporting.projector_job import run_reporting_projector

DAY = date(2026, 10, 19)
MFR = "MFR-1"
LINES = [{"product_id": "PA", "qty": 3}, {"product_id": "PB", "qty": 2}]
DIRECT = Seller("SEL-1", "Direct Dealer")
APPROVAL = Seller("SEL-2", "Approval Dealer", manager_approval_required=True)

FACT_COLUMNS = (
    "planned_outlets",
    "visited_planned_outlets",
    "unplanned_visits",
    "visits_total",
    "productive_visits",
    "outlet_seconds",
    "punched_in",
    "on_duty_seconds",
    "orders_submitted_count",
    "orders_approved_count",
    "orders_rejected_count",
    "order_net_value_paise",
)


@pytest.fixture()
def commerce(humbee: FakeHumbee) -> FakeCommerce:
    shop = install_commerce(humbee)
    shop.add_manufacturer(MFR, "Ultra Cement")
    shop.add_product(Product("PA", "Product A", 10_000, 1_800, 500))
    shop.add_product(Product("PB", "Product B", 25_050, 500, 0))
    shop.scheme_discount_paise = 1_000
    shop.scheme_label = "Diwali"
    return shop


def _project(db: Session) -> None:
    db.flush()
    run_reporting_projector(db.connection())
    db.expire_all()


def _fact(db: Session, employee: Employee, day: date = DAY) -> FactEmployeeDay | None:
    return db.get(FactEmployeeDay, (seed.tenant_id(), employee.id, day))


def _facts(db: Session, employee: Employee) -> dict[str, object]:
    row = _fact(db, employee)
    assert row is not None
    return {column: getattr(row, column) for column in FACT_COLUMNS}


def _totals(body: dict, window: str) -> dict[str, int]:
    return body[window]["totals"]


def _start_beat(sp: Authed, beat_id: str) -> dict[str, str]:
    started = sp.post("/api/v1/route-plans/switch-beat", {"beat_id": beat_id})
    assert started.status_code == 200, started.text
    return {
        outlet["outlet_ref"]: outlet["visit_id"]
        for group in started.json()["outlet_groups"]
        if group["beat_id"]
        for outlet in group["outlets"]
    }


def _enter(sp: Authed, visit_id: str, **body: Any) -> None:
    entered = check_in(sp, visit_id, **body)
    assert entered.status_code == 200, entered.text


def _no_order(sp: Authed, visit_id: str) -> None:
    logged = sp.post(f"/api/v1/visits/{visit_id}/outcome", {"reason": "stock_full"})
    assert (logged.status_code, logged.json()["state"]) == (200, "visited_no_order"), logged.text


def _check_out(sp: Authed, visit_id: str) -> None:
    closed = sp.post(f"/api/v1/visits/{visit_id}/check-out")
    assert (closed.status_code, closed.json()["state"]) == (200, "visited_with_order"), closed.text


def _order(sp: Authed, visit_id: str, outlet_ref: str, seller: Seller) -> tuple[str, dict[str, Any]]:
    created = sp.post(
        "/api/v1/carts",
        {"visit_id": visit_id, "outlet_id": outlet_ref, "manufacturer_id": MFR, "seller_id": seller.seller_id},
    )
    assert created.status_code == 201, created.text
    cart_id = created.json()["id"]
    priced = sp.put(f"/api/v1/carts/{cart_id}/lines", {"lines": LINES})
    assert priced.status_code == 200, priced.text
    submitted = sp.post("/api/v1/orders", {"cart_id": cart_id})
    assert submitted.status_code == 202, submitted.text
    return cart_id, submitted.json()


def _approval_id(manager: Authed, cart_id: str) -> str:
    items = manager.get("/api/v1/approvals", status="pending").json()["items"]
    return next(item["id"] for item in items if item["subject_id"] == cart_id)


def _visited_with_order(sp: Authed, visit_id: str, outlet_ref: str) -> None:
    _enter(sp, visit_id)
    _order(sp, visit_id, outlet_ref, DIRECT)
    _check_out(sp, visit_id)


def _decide(user: Authed, approval_id: str, action: str, body: dict[str, Any] | None = None) -> None:
    decided = user.post(f"/api/v1/approvals/{approval_id}/{action}", body or {})
    assert decided.status_code == 200, decided.text


def test_field_day_projects_into_facts_and_kpis(
    api_client: TestClient,
    db_session: Session,
    humbee: FakeHumbee,
    commerce: FakeCommerce,
    travel: time_machine.Coordinates,
) -> None:
    manager_row = seed.employee(db_session, "manager")
    sp_row = seed.employee(db_session, "sales_person", manager=manager_row)
    beat = seed.approved_beat(db_session, sp_row, ["O-1", "O-2", "O-3"], humbee=humbee)
    humbee.add_outlet("O-9")
    commerce.link_seller("O-1", MFR, DIRECT)
    commerce.link_seller("O-1", MFR, APPROVAL)
    sp = login(api_client, sp_row)
    manager = login(api_client, manager_row)

    def at(minutes: int, seconds: int = 0) -> datetime:
        moment = NOW + timedelta(minutes=minutes, seconds=seconds)
        travel.move_to(moment)
        return moment

    punch_in(sp, at=NOW)
    stops = _start_beat(sp, beat.id)

    _enter(sp, stops["O-1"], at=at(1))
    edited_cart, _ = _order(sp, stops["O-1"], "O-1", APPROVAL)
    _, direct = _order(sp, stops["O-1"], "O-1", DIRECT)
    assert (direct["status"], direct["gross_total_paise"]) == ("dp_created", 85_137)
    humbee.fail("POST", "/sfa/v1/orders", "002")
    _, failed = _order(sp, stops["O-1"], "O-1", DIRECT)
    assert failed["status"] == "submission_failed"
    pending_cart, pending = _order(sp, stops["O-1"], "O-1", APPROVAL)
    assert pending["status"] == "pending_approval"
    withdrawn_cart, _ = _order(sp, stops["O-1"], "O-1", APPROVAL)
    _decide(sp, _approval_id(manager, withdrawn_cart), "withdraw")

    approval_id = _approval_id(manager, edited_cart)
    fields = manager.get(f"/api/v1/approvals/{approval_id}/editable-fields").json()["items"]
    line_b = next(field["key"] for field in fields if field["label"] == "Product B")
    edited = manager.post(
        f"/api/v1/approvals/{approval_id}/edit-and-approve", {"patch": {line_b: 1}}, headers={"If-Match": "1"}
    )
    assert (edited.status_code, edited.json()["status"]) == (200, "approved_with_edits"), edited.text
    at(9)
    _check_out(sp, stops["O-1"])

    _enter(sp, stops["O-2"], at=at(9, 30))
    at(11, 30)
    _no_order(sp, stops["O-2"])

    unplanned = generate_ulid()
    _enter(sp, unplanned, at=at(12), outlet_ref="O-9")
    at(14)
    _no_order(sp, unplanned)

    off_duty_at = at(80)
    sp = login(api_client, sp_row)
    manager = login(api_client, manager_row)
    punched_out = punch(sp, "out", off_duty_at)
    assert punched_out.status_code == 201, punched_out.text

    _project(db_session)

    expected = {
        "planned_outlets": 3,
        "visited_planned_outlets": 2,
        "unplanned_visits": 1,
        "visits_total": 3,
        "productive_visits": 1,
        "outlet_seconds": 720,
        "punched_in": False,
        "on_duty_seconds": 4800,
        "orders_submitted_count": 3,
        "orders_approved_count": 2,
        "orders_rejected_count": 0,
        "order_net_value_paise": 144_038,
    }
    assert _facts(db_session, sp_row) == expected

    calls = sp.get("/api/v1/reporting/kpis/calls/self")
    assert calls.status_code == 200, calls.text
    assert _totals(calls.json(), "today") == {"tc": 3, "pc": 1, "sc": 3, "utc": 3}
    assert _totals(calls.json(), "mtd") == {"tc": 3, "pc": 1, "sc": 3, "utc": 3}

    surface = sp.get("/api/v1/reporting/kpi-surfaces/sp-dashboard")
    assert surface.status_code == 200, surface.text
    cards = {card["code"]: card for group in surface.json()["groups"] for card in group["items"]}
    assert (cards["COV"]["value"], cards["PROD"]["value"]) == ("75%", "33%")

    retried = sp.post(f"/api/v1/orders/{failed['id']}/retry-submission")
    assert (retried.status_code, retried.json()["status"]) == (202, "dp_created"), retried.text
    _decide(manager, _approval_id(manager, pending_cart), "reject", {"reason": "Over stock"})
    _project(db_session)

    settled = {
        **expected,
        "orders_submitted_count": 4,
        "orders_approved_count": 3,
        "orders_rejected_count": 1,
        "order_net_value_paise": 229_175,
    }
    assert _facts(db_session, sp_row) == settled
    revision = _fact(db_session, sp_row).revision

    _project(db_session)

    assert _facts(db_session, sp_row) == settled
    assert _fact(db_session, sp_row).revision == revision


def test_team_rollup_sums_only_own_tree(
    api_client: TestClient, db_session: Session, humbee: FakeHumbee, commerce: FakeCommerce
) -> None:
    manager_a = seed.employee(db_session, "manager")
    manager_b = seed.employee(db_session, "manager")
    sp1 = seed.employee(db_session, "sales_person", manager=manager_a)
    sp2 = seed.employee(db_session, "sales_person", manager=manager_a)
    sp3 = seed.employee(db_session, "sales_person", manager=manager_b)
    for outlet_ref in ("O-1", "O-5", "O-7", "O-8"):
        commerce.link_seller(outlet_ref, MFR, DIRECT)
    beats = {
        sp1.id: seed.approved_beat(db_session, sp1, ["O-1", "O-2"], humbee=humbee),
        sp2.id: seed.approved_beat(db_session, sp2, ["O-5"], humbee=humbee),
        sp3.id: seed.approved_beat(db_session, sp3, ["O-7", "O-8", "O-9", "O-10"], humbee=humbee),
    }

    def field_day(row: Employee, productive: list[str], no_order: list[str], unplanned: list[str]) -> None:
        sp = login(api_client, row)
        punch_in(sp)
        stops = _start_beat(sp, beats[row.id].id)
        for outlet_ref in productive:
            _visited_with_order(sp, stops[outlet_ref], outlet_ref)
        for outlet_ref in no_order:
            _enter(sp, stops[outlet_ref])
            _no_order(sp, stops[outlet_ref])
        for outlet_ref in unplanned:
            visit_id = generate_ulid()
            _enter(sp, visit_id, outlet_ref=outlet_ref)
            _no_order(sp, visit_id)

    field_day(sp1, productive=["O-1"], no_order=["O-2"], unplanned=[])
    field_day(sp2, productive=["O-5"], no_order=[], unplanned=["O-2"])
    field_day(sp3, productive=["O-7", "O-8"], no_order=["O-9"], unplanned=[])
    _project(db_session)

    team = login(api_client, manager_a).get("/api/v1/reporting/kpis/calls/team")
    assert team.status_code == 200, team.text
    body = team.json()
    rows = {row["employee_id"]: (row["tc"], row["pc"], row["sc"], row["utc"]) for row in body["mtd"]["items"]}
    assert rows == {sp1.id: (2, 1, 2, 2), sp2.id: (2, 1, 1, 2)}
    assert _totals(body, "mtd") == {"tc": 4, "pc": 2, "sc": 3, "utc": 3}
    assert _totals(body, "today") == {"tc": 4, "pc": 2, "sc": 3, "utc": 3}

    sp_client = login(api_client, sp3)
    assert sp_client.get("/api/v1/reporting/kpis/calls/org").status_code == 403
    assert sp_client.get("/api/v1/reporting/kpis/calls/team").status_code == 403


def test_leave_days_follow_approval_decisions(api_client: TestClient, db_session: Session) -> None:
    manager_row = seed.employee(db_session, "manager")
    sp_row = seed.employee(db_session, "sales_person", manager=manager_row)
    sp = login(api_client, sp_row)
    manager = login(api_client, manager_row)

    def file(from_date: str, to_date: str) -> str:
        filed = sp.post("/api/v1/leave/requests", {"leave_type": "casual", "from_date": from_date, "to_date": to_date})
        assert (filed.status_code, filed.json()["status"]) == (201, "pending"), filed.text
        return filed.json()["approval_request_id"]

    def leave(*days: date) -> list[tuple[bool, str | None] | None]:
        rows = [_fact(db_session, sp_row, day) for day in days]
        return [(row.is_leave_day, row.leave_type) if row else None for row in rows]

    granted = file("2026-10-21", "2026-10-22")
    refused = file("2026-10-26", "2026-10-27")
    _decide(manager, granted, "approve")
    _project(db_session)

    assert leave(date(2026, 10, 21), date(2026, 10, 22)) == [(True, "casual"), (True, "casual")]
    assert leave(date(2026, 10, 23), date(2026, 10, 26), date(2026, 10, 27)) == [None, None, None]

    _decide(manager, refused, "reject", {"reason": "Stock count"})
    _project(db_session)

    assert leave(date(2026, 10, 21), date(2026, 10, 22)) == [(True, "casual"), (True, "casual")]
    assert leave(date(2026, 10, 26), date(2026, 10, 27)) == [(False, None), (False, None)]


def test_surface_and_export_gates(api_client: TestClient, db_session: Session) -> None:
    callers = {role: login(api_client, seed.employee(db_session, role)) for role in ("sales_person", "manager", "admin")}
    attendance = "/api/v1/reporting/admin/reports/attendance"
    gates = [
        ("sales_person", "/api/v1/reporting/kpi-surfaces/manager-dashboard", {}),
        ("manager", "/api/v1/reporting/kpi-surfaces/sp-home", {}),
        ("admin", "/api/v1/reporting/kpi-surfaces/sp-dashboard", {}),
        ("manager", attendance, {"from_date": DAY, "to_date": DAY}),
    ]
    for role, path, params in gates:
        response = callers[role].get(path, **params)
        assert (response.status_code, error_code(response)) == (403, "forbidden"), (role, path)

    def export(from_date: str, to_date: str) -> tuple[int, str | None]:
        response = callers["admin"].get(attendance, from_date=from_date, to_date=to_date)
        return response.status_code, error_code(response) if response.status_code >= 400 else None

    assert export("2026-10-19", "2026-10-18") == (400, "invalid_range")
    assert export("2026-06-19", "2026-10-19") == (400, "range_too_large")
    assert export("2026-06-19", "2026-10-18") == (200, None)

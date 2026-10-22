from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.fakes.humbee import FakeHumbee, HumbeeCall
from tests.fakes.humbee_commerce import (
    FakeCommerce,
    Product,
    PurchaseOrder,
    Seller,
    ShipTo,
    install_commerce,
)
from tests.fixtures import seed
from tests.fixtures.auth import Authed, login
from tests.fixtures.flows import check_in, error_code, punch_in, team

from humbee_sfa.core.conventions import generate_ulid
from humbee_sfa.main import app
from humbee_sfa.modules.orders.models.cart_draft import CartDraft
from humbee_sfa.modules.orders.models.order import Order
from humbee_sfa.modules.orders.models.submission_attempt import SubmissionAttempt

OUTLET = "OUT-1"
MFR = "MFR-1"
CANONICAL_LINES = [{"product_id": "PA", "qty": 3}, {"product_id": "PB", "qty": 2}]


@dataclass
class Field:
    sp: Authed
    manager: Authed
    visit_id: str


@pytest.fixture()
def commerce(humbee: FakeHumbee) -> FakeCommerce:
    shop = install_commerce(humbee)
    humbee.add_outlet(OUTLET)
    shop.add_manufacturer(MFR, "Ultra Cement")
    shop.add_product(Product("PA", "Product A", 10_000, 1_800, 500))
    shop.add_product(Product("PB", "Product B", 25_050, 500, 0))
    shop.scheme_discount_paise = 1_000
    shop.scheme_label = "Diwali"
    return shop


def _check_in(sp: Authed) -> str:
    punch_in(sp)
    visit_id = generate_ulid()
    checked_in = check_in(sp, visit_id, outlet_ref=OUTLET)
    assert checked_in.status_code == 200, checked_in.text
    return visit_id


def _field(api_client: TestClient, db_session: Session) -> Field:
    sp, manager = team(db_session, api_client)
    return Field(sp=sp, manager=manager, visit_id=_check_in(sp))


def _cart(sp: Authed, visit_id: str, lines: list[dict[str, Any]] | None = None) -> str:
    created = sp.post("/api/v1/carts", {"visit_id": visit_id, "outlet_id": OUTLET, "manufacturer_id": MFR})
    assert created.status_code == 201, created.text
    cart_id = created.json()["id"]
    if lines:
        priced = sp.put(f"/api/v1/carts/{cart_id}/lines", {"lines": lines})
        assert priced.status_code == 200, priced.text
    return cart_id


def _place(sp: Authed, visit_id: str, lines: list[dict[str, Any]] = CANONICAL_LINES) -> dict[str, Any]:
    submitted = sp.post("/api/v1/orders", {"cart_id": _cart(sp, visit_id, lines)})
    assert submitted.status_code == 202, submitted.text
    return submitted.json()


def _pending_approval(manager: Authed, cart_id: str) -> dict[str, Any]:
    items = manager.get("/api/v1/approvals", status="pending").json()["items"]
    return next(item for item in items if item["subject_id"] == cart_id)


def _attempts(db: Session, order_id: str) -> list[SubmissionAttempt]:
    return list(
        db.scalars(
            select(SubmissionAttempt)
            .where(SubmissionAttempt.order_id == order_id)
            .order_by(SubmissionAttempt.attempt_no)
        )
    )


def _order_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Order))


def _registered_quantities(call: HumbeeCall) -> list[tuple[str, int]]:
    return sorted(
        (p["product_id"], p["quantity"]["quantity_in_uom"])
        for p in call.json["order_products_delivery"][0]["products_info"]
    )


def test_direct_order_is_priced_registered_with_humbee_and_closes_the_visit(
    api_client: TestClient, db_session: Session, humbee: FakeHumbee, commerce: FakeCommerce
) -> None:
    commerce.link_seller(OUTLET, MFR, Seller("SEL-1", "Direct Dealer"))
    day = _field(api_client, db_session)
    sp = day.sp

    body = {"visit_id": day.visit_id, "outlet_id": OUTLET, "manufacturer_id": MFR}
    created = sp.post("/api/v1/carts", body)
    assert created.status_code == 201
    resumed = sp.post("/api/v1/carts", body)
    assert resumed.status_code == 200
    cart_id = created.json()["id"]
    assert resumed.json()["id"] == cart_id

    cart = sp.put(f"/api/v1/carts/{cart_id}/lines", {"lines": CANONICAL_LINES}).json()
    assert {line["product_id"]: (line["line_net_paise"], line["line_gst_amount_paise"]) for line in cart["lines"]} == {
        "PA": (30_000, 5_063),
        "PB": (50_100, 2_474),
    }
    assert (
        cart["subtotal_net_paise"], cart["product_discount_paise"], cart["scheme_discount_paise"],
        cart["taxable_base_paise"], cart["gst_amount_paise"], cart["gross_total_paise"],
    ) == (80_100, 1_500, 1_000, 77_600, 7_537, 85_137)

    key = generate_ulid()
    submitted = sp.post("/api/v1/orders", {"cart_id": cart_id}, key=key)
    assert submitted.status_code == 202, submitted.text
    order = submitted.json()
    assert order["status"] == "dp_created"
    assert order["downstream_dp_order_ref"] == "DP-0001"
    assert order["gross_total_paise"] == 85_137
    assert [a.attempt_no for a in _attempts(db_session, order["id"])] == [1]
    [registered] = humbee.calls_to("POST", "/sfa/v1/orders")
    assert registered.headers["Idempotency-Key"] == order["order_number"]
    assert registered.json["buyer_esi_id"] == "ESI-OUT-1"
    assert _registered_quantities(registered) == [("PA", 3), ("PB", 2)]

    replay = sp.post("/api/v1/orders", {"cart_id": cart_id}, key=key)
    assert replay.status_code == 202
    assert replay.json() == order
    assert _order_count(db_session) == 1
    assert len(_attempts(db_session, order["id"])) == 1
    assert len(humbee.calls_to("POST", "/sfa/v1/orders")) == 1

    checked_out = sp.post(f"/api/v1/visits/{day.visit_id}/check-out")
    assert checked_out.status_code == 200
    assert checked_out.json()["state"] == "visited_with_order"

    assert db_session.get(CartDraft, cart_id).status == "converted"
    locked = sp.put(f"/api/v1/carts/{cart_id}/lines", {"lines": [{"product_id": "PA", "qty": 1}]})
    assert (locked.status_code, error_code(locked)) == (409, "cart_not_open")


def test_manager_edits_and_approves_an_approval_seller_order(
    api_client: TestClient, db_session: Session, humbee: FakeHumbee, commerce: FakeCommerce
) -> None:
    commerce.link_seller(OUTLET, MFR, Seller("SEL-2", "Approval Dealer", manager_approval_required=True))
    day = _field(api_client, db_session)

    order = _place(day.sp, day.visit_id)
    assert order["status"] == "pending_approval"
    assert humbee.calls_to("POST", "/sfa/v1/orders") == []
    cart_id = db_session.get(Order, order["id"]).cart_draft_id
    approval = _pending_approval(day.manager, cart_id)
    assert approval["assigned_approver_id"] == day.manager.employee.id

    fields = day.manager.get(f"/api/v1/approvals/{approval['id']}/editable-fields").json()["items"]
    line_b = next(f["key"] for f in fields if f["label"] == "Product B")
    path = f"/api/v1/approvals/{approval['id']}/edit-and-approve"

    too_many = day.manager.post(path, {"patch": {line_b: 3}}, headers={"If-Match": "1"})
    assert (too_many.status_code, error_code(too_many)) == (422, "subject_edit_rejected")

    decided = day.manager.post(path, {"patch": {line_b: 1}}, headers={"If-Match": "1"})
    assert decided.status_code == 200, decided.text
    assert (decided.json()["status"], decided.json()["subject_version"]) == ("approved_with_edits", 2)

    final = day.sp.get(f"/api/v1/orders/{order['id']}").json()
    assert final["status"] == "dp_created"
    assert final["gross_total_paise"] == 58_901
    assert datetime.fromisoformat(final["dp_sla_deadline_at"]) == datetime.fromisoformat(
        final["approved_at"]
    ) + timedelta(hours=1)
    [registered] = humbee.calls_to("POST", "/sfa/v1/orders")
    assert _registered_quantities(registered) == [("PA", 3), ("PB", 1)]


def test_rejected_and_withdrawn_orders_never_reach_humbee(
    api_client: TestClient, db_session: Session, humbee: FakeHumbee, commerce: FakeCommerce
) -> None:
    commerce.link_seller(OUTLET, MFR, Seller("SEL-2", "Approval Dealer", manager_approval_required=True))
    day = _field(api_client, db_session)

    rejected = _place(day.sp, day.visit_id)
    approval = _pending_approval(day.manager, db_session.get(Order, rejected["id"]).cart_draft_id)
    assert day.manager.post(f"/api/v1/approvals/{approval['id']}/reject", {"reason": "Over stock"}).status_code == 200
    assert day.sp.get(f"/api/v1/orders/{rejected['id']}").json()["status"] == "rejected"

    withdrawn = _place(day.sp, day.visit_id)
    approval = _pending_approval(day.manager, db_session.get(Order, withdrawn["id"]).cart_draft_id)
    assert day.sp.post(f"/api/v1/approvals/{approval['id']}/withdraw", {}).status_code == 200
    assert day.sp.get(f"/api/v1/orders/{withdrawn['id']}").json()["status"] == "cancelled"

    assert humbee.calls_to("POST", "/sfa/v1/orders") == []


def test_submission_failures_classify_and_gate_manual_retry(
    api_client: TestClient, db_session: Session, humbee: FakeHumbee, commerce: FakeCommerce
) -> None:
    commerce.link_seller(OUTLET, MFR, Seller("SEL-1", "Direct Dealer"))
    day = _field(api_client, db_session)
    sp = day.sp

    def retry(order_id: str) -> httpx.Response:
        return sp.post(f"/api/v1/orders/{order_id}/retry-submission")

    humbee.fail("POST", "/sfa/v1/orders", "999", times=2)
    timed_out = _place(sp, day.visit_id)
    assert timed_out["status"] == "submission_failed"
    assert [(a.outcome, a.failure_class) for a in _attempts(db_session, timed_out["id"])] == [("timeout", "timeout")]
    blocked = retry(timed_out["id"])
    assert (blocked.status_code, error_code(blocked)) == (409, "retry_not_allowed")

    humbee.fail("POST", "/sfa/v1/orders", "002")
    terminal = _place(sp, day.visit_id)
    assert [(a.outcome, a.failure_class) for a in _attempts(db_session, terminal["id"])] == [
        ("failed_terminal", "failed_terminal")
    ]
    retried = retry(terminal["id"])
    assert retried.status_code == 202
    assert retried.json()["status"] == "dp_created"
    assert [(a.attempt_no, a.trigger, a.outcome) for a in _attempts(db_session, terminal["id"])] == [
        (1, "outbox_auto", "failed_terminal"),
        (2, "manual_sp_retry", "success"),
    ]

    humbee.fail("POST", "/sfa/v1/orders", "002", times=2)
    twice = _place(sp, day.visit_id)
    assert retry(twice["id"]).json()["status"] == "submission_failed"
    limited = retry(twice["id"])
    assert (limited.status_code, error_code(limited)) == (429, "retry_rate_limited")

    humbee.fail("POST", "/sfa/v1/orders", "030")
    inactive = _place(sp, day.visit_id)
    assert [a.failure_class for a in _attempts(db_session, inactive["id"])] == ["outlet_inactive"]
    assert error_code(retry(inactive["id"])) == "retry_not_allowed"


def test_registration_transport_timeout_is_recorded_as_timeout(
    api_client: TestClient, db_session: Session, humbee: FakeHumbee, commerce: FakeCommerce
) -> None:
    commerce.link_seller(OUTLET, MFR, Seller("SEL-1", "Direct Dealer"))
    commerce.registration_timeouts = 2
    day = _field(api_client, db_session)

    stalled = _place(day.sp, day.visit_id)

    assert stalled["status"] == "submission_failed"
    assert stalled["downstream_dp_order_ref"] is None
    assert [(a.outcome, a.failure_class) for a in _attempts(db_session, stalled["id"])] == [("timeout", "timeout")]
    assert len(humbee.calls_to("POST", "/sfa/v1/orders")) == 2
    assert commerce.registration_timeouts == 0


def test_po_backed_cart_is_capped_by_the_purchase_order(
    api_client: TestClient, db_session: Session, commerce: FakeCommerce
) -> None:
    commerce.link_seller(
        OUTLET, MFR,
        Seller("SEL-3", "PO Dealer", requires_purchase_order=True, manager_approval_required=True),
    )
    commerce.purchase_orders.append(
        PurchaseOrder("PO-1", max_dp_quantity=10, available_quantity=6, line_balances={"PA": 4, "PB": 10})
    )
    day = _field(api_client, db_session)
    sp = day.sp
    cart_id = _cart(sp, day.visit_id, [{"product_id": "PA", "qty": 3}])

    no_po = sp.post("/api/v1/orders", {"cart_id": cart_id})
    assert (no_po.status_code, error_code(no_po)) == (422, "po_required")

    selected = sp.patch(f"/api/v1/carts/{cart_id}", {"source_po_id": "PO-1"})
    assert selected.status_code == 200, selected.text
    assert (selected.json()["po_cap_qty"], selected.json()["po_cap_source"]) == (6, "available_quantity")

    over_line = sp.put(f"/api/v1/carts/{cart_id}/lines", {"lines": [{"product_id": "PA", "qty": 5}]})
    assert (over_line.status_code, error_code(over_line)) == (422, "po_line_quantity_exceeded")

    over_cap = sp.put(f"/api/v1/carts/{cart_id}/lines", {"lines": [{"product_id": "PB", "qty": 4}]})
    assert (over_cap.status_code, error_code(over_cap)) == (422, "po_quantity_exceeded")

    at_cap = sp.put(f"/api/v1/carts/{cart_id}/lines", {"lines": [{"product_id": "PB", "qty": 3}]})
    assert at_cap.status_code == 200
    assert _order_count(db_session) == 0


def test_humbee_down_refuses_with_503_and_creates_no_order(
    api_client: TestClient, db_session: Session, humbee: FakeHumbee, commerce: FakeCommerce
) -> None:
    commerce.link_seller(
        OUTLET, MFR,
        Seller("SEL-3", "PO Dealer", requires_purchase_order=True, manager_approval_required=True),
    )
    commerce.purchase_orders.append(PurchaseOrder("PO-1", max_dp_quantity=10, available_quantity=10))
    commerce.ship_to.append(ShipTo("DEALER-9", "ESI-D-9", "Dealer Nine"))
    day = _field(api_client, db_session)
    sp = day.sp

    def down(method: str, template: str) -> None:
        humbee.fail(method, template, "999", times=2)

    def unavailable(response: httpx.Response) -> tuple[int, str]:
        return response.status_code, error_code(response)

    context = {"visit_id": day.visit_id, "outlet_id": OUTLET, "manufacturer_id": MFR}
    assert sp.get("/api/v1/orders/context", **context).status_code == 200
    for method, template in [
        ("GET", "/sfa/v1/outlets/{outlet_id}/sellers"),
        ("GET", "/sfa/v1/manufacturers"),
        ("GET", "/sfa/v1/sellers/ship-to-options"),
        ("GET", "/sfa/v1/purchase-orders"),
    ]:
        down(method, template)
        assert unavailable(sp.get("/api/v1/orders/context", **context)) == (503, "upstream_unavailable"), template

    cart_id = _cart(sp, day.visit_id, [{"product_id": "PA", "qty": 2}])
    down("GET", "/sfa/v1/purchase-orders")
    assert unavailable(sp.patch(f"/api/v1/carts/{cart_id}", {"source_po_id": "PO-1"})) == (503, "upstream_unavailable")
    down("GET", "/sfa/v1/sellers/ship-to-options")
    dealer = {"ship_to_type": "dealer", "ship_to_outlet_id": "DEALER-9", "ship_to_esi_id": "ESI-D-9"}
    assert unavailable(sp.patch(f"/api/v1/carts/{cart_id}", dealer)) == (503, "upstream_unavailable")
    assert sp.patch(f"/api/v1/carts/{cart_id}", {"source_po_id": "PO-1"}).status_code == 200

    for method, template in [
        ("GET", "/sfa/v1/outlets/{outlet_id}/sellers"),
        ("GET", "/sfa/v1/purchase-orders"),
        ("GET", "/sfa/v1/manufacturers"),
    ]:
        down(method, template)
        assert unavailable(sp.post("/api/v1/orders", {"cart_id": cart_id})) == (503, "upstream_unavailable"), template

    assert _order_count(db_session) == 0
    assert db_session.get(CartDraft, cart_id).status == "open"
    assert sp.post("/api/v1/orders", {"cart_id": cart_id}).json()["status"] == "pending_approval"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Listing open purchase orders while Humbee is down must refuse with 503 upstream_unavailable "
        "like every other commerce read; GET /orders/purchase-orders is not wrapped in "
        "_commerce_upstream and returns 500 "
        "internal_error"
    ),
)
def test_purchase_order_list_refuses_with_503_when_humbee_is_down(
    api_client: TestClient, db_session: Session, humbee: FakeHumbee, commerce: FakeCommerce
) -> None:
    commerce.link_seller(
        OUTLET, MFR,
        Seller("SEL-3", "PO Dealer", requires_purchase_order=True, manager_approval_required=True),
    )
    commerce.purchase_orders.append(PurchaseOrder("PO-1", max_dp_quantity=10, available_quantity=10))
    sp, _ = team(db_session, api_client)
    query = {"outlet_id": OUTLET, "manufacturer_id": MFR, "outlet_esi_id": "ESI-OUT-1"}
    listed = sp.get("/api/v1/orders/purchase-orders", **query)
    assert listed.status_code == 200, listed.text
    assert [po["po_id"] for po in listed.json()["purchase_orders"]] == ["PO-1"]

    humbee.fail("GET", "/sfa/v1/purchase-orders", "999", times=2)
    lenient = TestClient(app, raise_server_exceptions=False, client=("127.0.0.1", 50000))
    refused = Authed(lenient, sp.token, sp.employee).get("/api/v1/orders/purchase-orders", **query)

    assert (refused.status_code, error_code(refused)) == (503, "upstream_unavailable")


def test_order_reads_are_scoped_to_self_and_own_tree(
    api_client: TestClient, db_session: Session, commerce: FakeCommerce
) -> None:
    commerce.link_seller(OUTLET, MFR, Seller("SEL-1", "Direct Dealer"))
    manager = seed.employee(db_session, "manager")
    other_manager = seed.employee(db_session, "manager")
    first = login(api_client, seed.employee(db_session, "sales_person", manager=manager))
    second = login(api_client, seed.employee(db_session, "sales_person", manager=manager))
    mine = _place(first, _check_in(first))["id"]
    theirs = _place(second, _check_in(second))["id"]

    def listed(client: Authed) -> set[str]:
        return {item["id"] for item in client.get("/api/v1/orders").json()["items"]}

    assert listed(first) == {mine}
    assert first.get(f"/api/v1/orders/{theirs}").status_code == 404
    assert listed(login(api_client, manager)) == {mine, theirs}
    outsider = login(api_client, other_manager)
    assert listed(outsider) == set()
    hidden = outsider.get(f"/api/v1/orders/{mine}")
    assert (hidden.status_code, error_code(hidden)) == (404, "order_not_found")

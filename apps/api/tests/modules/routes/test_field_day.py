from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.conftest import NOW
from tests.fakes.humbee import FakeHumbee
from tests.fixtures import seed
from tests.fixtures.auth import login
from tests.fixtures.flows import check_in, error_code, punch_in
from tests.fixtures.seed import approved_beat

from humbee_sfa.core.conventions import generate_ulid
from humbee_sfa.core.db import transaction
from humbee_sfa.modules.orders.models import Order
from humbee_sfa.modules.org.models import Employee
from humbee_sfa.modules.routes.models.route_missed_visit_audit import RouteMissedVisitAudit
from humbee_sfa.modules.routes.models.route_plan import RoutePlan
from humbee_sfa.modules.routes.models.route_stop import RouteStop
from humbee_sfa.modules.routes.models.route_visit import RouteVisit
from humbee_sfa.modules.routes.models.route_visit_outcome import RouteVisitOutcome
from humbee_sfa.modules.routes.service import RouteService
from humbee_sfa.platform.models.domain_event import DomainEvent

MONDAY = date(2026, 10, 19)


def _stops(day: dict) -> list[dict]:
    return [outlet for group in day["outlet_groups"] if group["beat_id"] for outlet in group["outlets"]]


def _order_on(db: Session, visit_id: str, employee: Employee, outlet_ref: str) -> Order:
    now = datetime.now(UTC)
    order = Order(
        tenant_id=seed.tenant_id(),
        order_number=f"ORD-{generate_ulid()}",
        order_path="direct",
        seller_type_snapshot="R1",
        status="submitted",
        employee_id=employee.id,
        visit_id=visit_id,
        humbee_outlet_id=outlet_ref,
        outlet_name_snapshot=f"Outlet {outlet_ref}",
        humbee_manufacturer_id="M-1",
        manufacturer_name_snapshot="Maker",
        humbee_seller_id="S-1",
        seller_name_snapshot="Seller",
        snapshot_taken_at=now,
        snapshot_source_as_of=now,
        requires_approval=False,
        subtotal_net_paise=10_000,
        taxable_base_paise=10_000,
        gst_amount_paise=500,
        gross_total_paise=10_500,
        idempotency_key=generate_ulid(),
        occurred_at=now,
        received_at=now,
        business_date=MONDAY,
        created_by_employee_id=employee.id,
    )
    with transaction(db):
        db.add(order)
    return order


def _route_day(db: Session, employee: Employee, states: Sequence[str]) -> list[RouteVisit]:
    now = datetime.now(UTC)
    plan = RoutePlan(
        id=generate_ulid(),
        tenant_id=seed.tenant_id(),
        employee_id=employee.id,
        business_date=MONDAY,
        beat_id=generate_ulid(),
        beat_version_id=generate_ulid(),
        state="in_progress",
        started_at=now,
        created_by_employee_id=employee.id,
    )
    stops: list[RouteStop] = []
    visits: list[RouteVisit] = []
    for sequence_no, state in enumerate(states, start=1):
        outlet_ref = f"{employee.employee_code}-{sequence_no}"
        visit = RouteVisit(
            id=generate_ulid(),
            tenant_id=seed.tenant_id(),
            employee_id=employee.id,
            route_plan_id=plan.id,
            humbee_outlet_id=outlet_ref,
            state=state,
            origin="planned",
            visit_type="physical",
            planned_for_date=MONDAY,
            checked_in_at=None if state == "scheduled" else now,
            checked_out_at=now if state.startswith("visited") else None,
            occurred_at=now,
            received_at=now,
            business_date=MONDAY,
            created_by_employee_id=employee.id,
        )
        stop = RouteStop(
            id=generate_ulid(),
            tenant_id=seed.tenant_id(),
            route_plan_id=plan.id,
            humbee_outlet_id=outlet_ref,
            sequence_no=sequence_no,
            beat_id=plan.beat_id,
            beat_version_id=plan.beat_version_id,
            run_origin="assigned_beat",
            snapshot_name=f"Outlet {outlet_ref}",
            snapshot_as_of=now,
            visit_id=visit.id,
            created_by_employee_id=employee.id,
        )
        visit.route_stop_id = stop.id
        stops.append(stop)
        visits.append(visit)
    with transaction(db):
        db.add_all([plan, *stops, *visits])
    return visits


def test_full_route_day(
    api_client: TestClient, db_session: Session, humbee: FakeHumbee, travel
) -> None:
    manager = seed.employee(db_session, "manager")
    sp_row = seed.employee(db_session, "sales_person", manager=manager)
    beat = approved_beat(db_session, sp_row, ["O-1", "O-2", "O-3"], humbee=humbee, visit_days=(1, 4))
    humbee.add_outlet("O-9")
    sp = login(api_client, sp_row)

    blocked = sp.post("/api/v1/route-plans/switch-beat", {"beat_id": beat.id})
    assert (blocked.status_code, error_code(blocked)) == (403, "not_punched_in")

    punch_in(sp)
    started = sp.post("/api/v1/route-plans/switch-beat", {"beat_id": beat.id})
    assert started.status_code == 200, started.text
    stops = _stops(started.json())
    assert [s["outlet_ref"] for s in stops] == ["O-1", "O-2", "O-3"]
    assert {s["visit_state"] for s in stops} == {"scheduled"}
    assert {s["run_origin"] for s in stops} == {"assigned_beat"}
    first, second, _third = (s["visit_id"] for s in stops)

    checked_in = check_in(sp, first)
    assert (checked_in.status_code, checked_in.json()["state"]) == (200, "in_progress")
    busy = check_in(sp, second)
    assert (busy.status_code, error_code(busy)) == (409, "visit_already_in_progress")

    no_outcome = sp.post(f"/api/v1/visits/{first}/check-out")
    assert (no_outcome.status_code, error_code(no_outcome)) == (422, "outcome_required")
    logged = sp.post(f"/api/v1/visits/{first}/outcome", {"reason": "shop_closed"})
    assert (logged.status_code, logged.json()["state"]) == (200, "visited_no_order")
    again = sp.post(f"/api/v1/visits/{first}/check-out")
    assert (again.status_code, again.json()["state"]) == (200, "visited_no_order")

    entered_at = NOW + timedelta(minutes=1)
    travel.move_to(entered_at)
    assert check_in(sp, second, at=entered_at).status_code == 200
    order = _order_on(db_session, second, sp_row, "O-2")
    travel.move_to(entered_at + timedelta(seconds=750))
    closed = sp.post(f"/api/v1/visits/{second}/check-out")
    assert (closed.status_code, closed.json()["state"]) == (200, "visited_with_order")
    completed = db_session.execute(
        select(DomainEvent).where(
            DomainEvent.aggregate_id == second, DomainEvent.event_type == "visit_completed"
        )
    ).scalar_one()
    assert completed.payload["outlet_seconds"] == 750
    assert completed.payload["order_ids"] == [order.id]

    unplanned_id = generate_ulid()
    unplanned = check_in(sp, unplanned_id, outlet_ref="O-9")
    assert unplanned.status_code == 200, unplanned.text
    assert (unplanned.json()["origin"], unplanned.json()["route_stop_id"]) == ("unplanned", None)
    assert sp.post(f"/api/v1/visits/{unplanned_id}/outcome", {"reason": "no_requirement"}).status_code == 200

    day = sp.get("/api/v1/route-plans/current").json()
    assert {
        key: day[key]
        for key in (
            "planned_stop_count",
            "planned_visited_count",
            "unplanned_visit_count",
            "visited_count",
            "coverage_pct",
        )
    } == {
        "planned_stop_count": 3,
        "planned_visited_count": 2,
        "unplanned_visit_count": 1,
        "visited_count": 3,
        "coverage_pct": 75,
    }


def test_off_day_beat_and_gps_rule(
    api_client: TestClient, db_session: Session, humbee: FakeHumbee, travel
) -> None:
    travel.move_to(NOW + timedelta(days=1))
    manager = seed.employee(db_session, "manager")
    sp_row = seed.employee(db_session, "sales_person", manager=manager)
    beat = approved_beat(db_session, sp_row, ["T-1", "T-2"], humbee=humbee, visit_days=(1, 4))
    sp = login(api_client, sp_row)
    punch_in(sp)

    started = sp.post("/api/v1/route-plans/switch-beat", {"beat_id": beat.id})
    assert started.status_code == 200, started.text
    stops = _stops(started.json())
    assert {s["run_origin"] for s in stops} == {"unplanned_beat"}

    visit_id = stops[0]["visit_id"]
    no_gps = check_in(sp, visit_id, gps=None)
    assert (no_gps.status_code, error_code(no_gps)) == (424, "gps_required")
    assert db_session.get(RouteVisit, visit_id).state == "scheduled"

    phoned = check_in(sp, visit_id, gps=None, visit_type="telephonic")
    assert phoned.status_code == 200, phoned.text
    assert (phoned.json()["state"], phoned.json()["visit_type"]) == ("in_progress", "telephonic")


def test_end_of_day_sweep(api_client: TestClient, db_session: Session) -> None:
    manager_row = seed.employee(db_session, "manager")
    sp_a = seed.employee(db_session, "sales_person", manager=manager_row)
    sp_b = seed.employee(db_session, "sales_person", manager=manager_row)
    done, scheduled, open_no_order = _route_day(
        db_session, sp_a, ["visited_no_order", "scheduled", "in_progress"]
    )
    (open_with_order,) = _route_day(db_session, sp_b, ["in_progress"])
    order = _order_on(db_session, open_with_order.id, sp_b, open_with_order.humbee_outlet_id)

    swept_at = datetime.now(UTC)
    service = RouteService(db_session)
    with transaction(db_session):
        assert service.close_day(tenant_id=seed.tenant_id(), business_date=MONDAY, now=swept_at) == 2

    for visit in (scheduled, open_no_order):
        db_session.refresh(visit)
        assert (visit.state, visit.missed_at) == ("missed", swept_at)
    db_session.refresh(open_with_order)
    assert open_with_order.state == "visited_with_order"
    outcome = db_session.execute(
        select(RouteVisitOutcome).where(RouteVisitOutcome.visit_id == open_with_order.id)
    ).scalar_one()
    assert outcome.order_ids == [order.id]
    db_session.refresh(done)
    assert done.state == "visited_no_order"

    def audits_by_visit() -> dict[str, int]:
        rows = db_session.execute(
            select(RouteMissedVisitAudit.visit_id, func.count())
            .where(RouteMissedVisitAudit.business_date == MONDAY)
            .group_by(RouteMissedVisitAudit.visit_id)
        ).all()
        return dict(rows)

    assert audits_by_visit() == {scheduled.id: 1, open_no_order.id: 1}
    plans = db_session.execute(
        select(RoutePlan.state, RoutePlan.closed_at).where(
            RoutePlan.employee_id.in_([sp_a.id, sp_b.id])
        )
    ).all()
    assert [tuple(plan) for plan in plans] == [("closed", swept_at), ("closed", swept_at)]

    with transaction(db_session):
        assert service.close_day(tenant_id=seed.tenant_id(), business_date=MONDAY, now=datetime.now(UTC)) == 0
    assert audits_by_visit() == {scheduled.id: 1, open_no_order.id: 1}
    db_session.refresh(scheduled)
    assert scheduled.missed_at == swept_at

    missed = login(api_client, sp_a).get("/api/v1/missed-visits").json()
    assert {item["visit_id"] for item in missed["items"]} == {scheduled.id, open_no_order.id}
    assert missed["summary"] == {"missed": 2, "visited": 1, "adherence_pct": 33}

    manager = login(api_client, manager_row)
    refused = manager.post(f"/api/v1/admin/jobs/end-of-day-sweep?business_date={MONDAY}")
    assert (refused.status_code, error_code(refused)) == (403, "forbidden")


def test_team_route_reads(api_client: TestClient, db_session: Session) -> None:
    manager_row = seed.employee(db_session, "manager")
    on_route_row = seed.employee(db_session, "sales_person", manager=manager_row)
    idle_row = seed.employee(db_session, "sales_person", manager=manager_row)
    other_manager = seed.employee(db_session, "manager")
    outsider_row = seed.employee(db_session, "sales_person", manager=other_manager)
    _route_day(db_session, on_route_row, ["scheduled", "scheduled"])
    _route_day(db_session, outsider_row, ["scheduled"])
    for row in (on_route_row, idle_row, outsider_row):
        punch_in(login(api_client, row))
    manager = login(api_client, manager_row)

    own = manager.get("/api/v1/route-plans/current", employee_id=on_route_row.id)
    assert (own.status_code, own.json()["planned_stop_count"]) == (200, 2)

    coverage = manager.get("/api/v1/coverage/team", business_date=MONDAY.isoformat()).json()
    rows = {row["employee_id"]: row for row in coverage["items"]}
    assert set(rows) == {on_route_row.id, idle_row.id}
    assert rows[idle_row.id]["on_duty"] is True
    assert (coverage["on_route"], coverage["planned"], coverage["on_route_total"]) == (1, 2, 2)


def test_manager_cannot_see_other_tree_route_day(api_client: TestClient, db_session: Session) -> None:
    manager_row = seed.employee(db_session, "manager")
    seed.employee(db_session, "sales_person", manager=manager_row)
    outsider_row = seed.employee(db_session, "sales_person", manager=seed.employee(db_session, "manager"))
    _route_day(db_session, outsider_row, ["scheduled"])

    response = login(api_client, manager_row).get("/api/v1/route-plans/current", employee_id=outsider_row.id)
    assert (response.status_code, error_code(response)) == (403, "forbidden")

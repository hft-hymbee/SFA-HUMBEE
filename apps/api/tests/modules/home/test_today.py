from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.fakes.humbee import FakeHumbee
from tests.fixtures import seed
from tests.fixtures.auth import login
from tests.fixtures.flows import check_in, error_code, punch, punch_in
from tests.fixtures.seed import approved_beat


def test_today_composition_around_duty(api_client: TestClient, db_session: Session, humbee: FakeHumbee) -> None:
    sp = seed.employee(db_session, "sales_person", manager=seed.employee(db_session, "manager"))
    beat = approved_beat(db_session, sp, ["OUT-1"], humbee=humbee, frequency="daily")
    me = login(api_client, sp)
    for offset in range(4):
        day = (date(2026, 10, 26) + timedelta(days=offset)).isoformat()
        submitted = me.post("/api/v1/leave/requests", {"leave_type": "casual", "from_date": day, "to_date": day})
        assert submitted.status_code == 201, submitted.text

    before = me.get("/api/v1/home/today").json()
    assert before["business_date"] == "2026-10-19"
    assert before["attendance"]["data"]["has_punched_in"] is False
    assert before["targets"] == {"status": "unavailable", "reason": "capability_not_released", "retryable": False, "as_of": None}
    requests = before["requests"]["data"]
    assert [item["status"] for item in requests["items"]] == ["pending"] * 3
    assert requests["pending_count"] == 4

    punch_in(me)
    switched = me.post("/api/v1/route-plans/switch-beat", {"beat_id": beat.id})
    assert switched.status_code == 200, switched.text

    on_duty = me.get("/api/v1/home/today").json()
    assert on_duty["attendance"]["data"]["has_punched_in"] is True
    assert on_duty["attendance"]["data"]["locked"] is False
    assert on_duty["route"]["status"] == "available"
    assert (on_duty["route"]["data"]["beat_id"], on_duty["route"]["data"]["planned_stop_count"]) == (beat.id, 1)

    assert punch(me, "out").status_code == 201
    after = me.get("/api/v1/home/today").json()
    assert after["attendance"]["data"]["locked"] is True


def test_route_writes_gated_until_punch_in(api_client: TestClient, db_session: Session, humbee: FakeHumbee) -> None:
    humbee.add_outlet("OUT-1")
    me = login(api_client, seed.employee(db_session, "sales_person", manager=seed.employee(db_session, "manager")))

    today = me.get("/api/v1/home/today").json()
    assert today["attendance"]["data"]["has_punched_in"] is False
    assert today["route"]["status"] == "available"

    blocked = check_in(me, outlet_ref="OUT-1")
    assert (blocked.status_code, error_code(blocked)) == (403, "not_punched_in")

    punch_in(me)
    checked_in = check_in(me, outlet_ref="OUT-1")
    assert (checked_in.status_code, checked_in.json()["state"]) == (200, "in_progress")

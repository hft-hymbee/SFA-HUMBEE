from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.fakes.humbee import FakeHumbee
from tests.fixtures import seed
from tests.fixtures.auth import login
from tests.fixtures.flows import check_in, punch_in
from tests.fixtures.seed import approved_beat

from humbee_sfa.core.conventions import generate_ulid
from humbee_sfa.modules.outlets.models import Outlet

URL = "/api/v1/route-plans/current/business-profiler"
BUSINESS_PROFILER = "/sfa/v1/outlets/business-profiler"


def _by_ref(response) -> dict[str, dict]:
    assert response.status_code == 200, response.text
    return {item["outlet_ref"]: item for item in response.json()["outlets"]}


def test_live_values_for_every_outlet_on_the_route(
    api_client: TestClient, db_session: Session, humbee: FakeHumbee
) -> None:
    sp_row = seed.employee(db_session, "sales_person", manager=seed.employee(db_session, "manager"))
    beat = approved_beat(db_session, sp_row, ["O-1", "O-2"], humbee=humbee)
    humbee.outlets["O-1"].business_profiler_pct = 70
    humbee.add_outlet("O-9", business_profiler_pct=40)
    sp = login(api_client, sp_row)
    punch_in(sp)
    assert sp.post("/api/v1/route-plans/switch-beat", {"beat_id": beat.id}).status_code == 200
    assert check_in(sp, generate_ulid(), outlet_ref="O-9").status_code == 200

    items = _by_ref(sp.get(URL))

    assert {ref: (i["business_profiler_pct"], i["is_live"]) for ref, i in items.items()} == {
        "O-1": (70, True),
        "O-2": (0, True),
        "O-9": (40, True),
    }
    assert len(humbee.calls_to("POST", BUSINESS_PROFILER)) == 1
    stored = db_session.execute(select(Outlet).where(Outlet.humbee_outlet_id == "O-1")).scalar_one()
    assert stored.business_profiler_pct == 70


def test_falls_back_to_last_known_when_humbee_fails(
    api_client: TestClient, db_session: Session, humbee: FakeHumbee
) -> None:
    sp_row = seed.employee(db_session, "sales_person", manager=seed.employee(db_session, "manager"))
    beat = approved_beat(db_session, sp_row, ["O-1", "O-2"], humbee=humbee)
    humbee.outlets["O-1"].business_profiler_pct = 70
    sp = login(api_client, sp_row)
    punch_in(sp)
    assert sp.post("/api/v1/route-plans/switch-beat", {"beat_id": beat.id}).status_code == 200
    # Only O-1 gets a stored value, through outlet detail.
    assert sp.get("/api/v1/outlets/O-1").json()["business_profiler_pct"] == 70

    humbee.fail("POST", BUSINESS_PROFILER, "999")
    items = _by_ref(sp.get(URL))

    assert {ref: (i["business_profiler_pct"], i["is_live"]) for ref, i in items.items()} == {"O-1": (70, False)}


def test_outlet_humbee_does_not_know_is_omitted(
    api_client: TestClient, db_session: Session, humbee: FakeHumbee
) -> None:
    sp_row = seed.employee(db_session, "sales_person", manager=seed.employee(db_session, "manager"))
    beat = approved_beat(db_session, sp_row, ["O-1", "O-2"], humbee=humbee)
    del humbee.outlets["O-2"]
    sp = login(api_client, sp_row)
    punch_in(sp)
    assert sp.post("/api/v1/route-plans/switch-beat", {"beat_id": beat.id}).status_code == 200

    assert set(_by_ref(sp.get(URL))) == {"O-1"}


def test_no_route_today_makes_no_humbee_call(
    api_client: TestClient, db_session: Session, humbee: FakeHumbee
) -> None:
    sp_row = seed.employee(db_session, "sales_person", manager=seed.employee(db_session, "manager"))

    assert _by_ref(login(api_client, sp_row).get(URL)) == {}
    assert humbee.calls_to("POST", BUSINESS_PROFILER) == []

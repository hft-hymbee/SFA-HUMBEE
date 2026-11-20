from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.fakes.humbee import FakeHumbee
from tests.fixtures import seed
from tests.fixtures.auth import login
from tests.fixtures.flows import assign_districts

GEO = {"zones": ["1"], "states": ["10"], "districts": ["100"], "cats": []}
WEEKLY = {"frequency": "weekly", "visit_days": [1, 4], "week_cycle": []}


def test_outlet_identity_on_the_beat_outlet_picker_only(
    db_session: Session, api_client: TestClient, humbee: FakeHumbee
) -> None:
    humbee.add_outlet("O1", "Shree Ganesh", gstin="29ABCDE1234F1Z5", pan="ABCDE1234F", manufacturers="DBC,TAG")
    humbee.add_outlet("O2", "Shree Ganesh", pan="ZZZZZ9999Z")
    humbee.add_outlet("O3", "Shree Ganesh")
    humbee.outlet_page_size = 100  # the fake otherwise caps every page at 2
    manager = seed.employee(db_session, "manager")
    sales_person = seed.employee(db_session, "sales_person", manager=manager)
    assign_districts(login(api_client, seed.employee(db_session, "admin")), sales_person, humbee, "100")
    sp = login(api_client, sales_person)
    district_name = humbee.districts["100"].name

    beat_id = sp.post("/api/v1/beats", {}).json()["id"]
    patched = sp.patch(
        f"/api/v1/beats/{beat_id}/draft",
        {"display_name": "Beat", "code": "B-1", "geo_scope": GEO, "frequency": WEEKLY},
    )
    assert patched.status_code == 200, patched.text

    expected = {
        "O1": ("29ABCDE1234F1Z5", district_name, "DBC,TAG"),
        "O2": ("ZZZZZ9999Z", district_name, None),
        "O3": (None, district_name, None),
    }

    def identity(items: list[dict]) -> dict[str, tuple]:
        return {i["outlet_ref"]: (i["gstin_pan"], i["district_name"], i["manufacturer_names"]) for i in items}

    scope = sp.get(f"/api/v1/beats/{beat_id}/scope-outlets")
    assert scope.status_code == 200, scope.text
    assert identity(scope.json()["items"]) == expected

    by_gstin = sp.get(f"/api/v1/beats/{beat_id}/scope-outlets", q="29abcde")
    assert [i["outlet_ref"] for i in by_gstin.json()["items"]] == ["O1"]

    # Once picked, a beat's outlets carry none of it.
    placed = sp.put(f"/api/v1/beats/{beat_id}/draft/outlets", {"outlet_refs": ["O1", "O2", "O3"]})
    assert placed.status_code == 200, placed.text
    detail = sp.get(f"/api/v1/beats/{beat_id}/draft")
    assert detail.status_code == 200, detail.text
    for outlets in (placed.json()["outlets"], detail.json()["outlets"]):
        assert len(outlets) == 3
        assert not any({"gstin_pan", "district_name", "manufacturer_names"} & outlet.keys() for outlet in outlets)

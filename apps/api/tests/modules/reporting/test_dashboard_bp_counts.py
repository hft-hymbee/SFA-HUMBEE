from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.conftest import NOW
from tests.fakes.humbee import FakeHumbee
from tests.fakes.humbee_commerce import install_commerce
from tests.fakes.humbee_targets import install_target_manufacturers
from tests.fixtures import seed
from tests.fixtures.auth import login
from tests.fixtures.flows import check_in, punch_in


def _visit(sp, visit_id: str) -> None:
    assert check_in(sp, visit_id).status_code == 200
    assert sp.post(f"/api/v1/visits/{visit_id}/outcome", {"reason": "stock_full"}).status_code == 200


def test_manager_and_admin_dashboards_count_bp_over_visited_outlets(
    api_client: TestClient, db_session: Session, humbee: FakeHumbee
) -> None:
    manager_row = seed.employee(db_session, "manager")
    sp_row = seed.employee(db_session, "sales_person", manager=manager_row)
    other_manager_row = seed.employee(db_session, "manager")
    admin_row = seed.employee(db_session, "admin")
    beat = seed.approved_beat(db_session, sp_row, ["O-1", "O-2", "O-3"], humbee=humbee)
    for ref, pct in {"O-1": 90, "O-2": 40, "O-3": 85}.items():
        humbee.outlets[ref].business_profiler_pct = pct
    install_commerce(humbee).add_manufacturer("1", "Ultra Cement")
    install_target_manufacturers(humbee, {"1": ("Ultra Cement", "amount")})
    sp = login(api_client, sp_row)

    punch_in(sp, at=NOW)
    started = sp.post("/api/v1/route-plans/switch-beat", {"beat_id": beat.id})
    assert started.status_code == 200, started.text
    stops = {
        outlet["outlet_ref"]: outlet["visit_id"]
        for group in started.json()["outlet_groups"]
        if group["beat_id"]
        for outlet in group["outlets"]
    }
    _visit(sp, stops["O-1"])
    _visit(sp, stops["O-2"])  # O-3 is never visited, so it is not counted.

    def bp(row, path: str, key: str, **params: object) -> tuple[int, int]:
        response = login(api_client, row).get(f"/api/v1/reporting/dashboards/{path}", **params)
        assert response.status_code == 200, response.text
        metrics = response.json()[key]
        return metrics["bp_filled"], metrics["bp_not_filled"]

    for period in ("today", "mtd"):
        assert bp(manager_row, "manager", "team_metrics", period=period) == (1, 1)
        assert bp(admin_row, "admin", "org_metrics", period=period) == (1, 1)
    # Outside the manager's tree nothing counts; the admin filters do not narrow the counts.
    assert bp(other_manager_row, "manager", "team_metrics", period="today") == (0, 0)
    assert bp(admin_row, "admin", "org_metrics", period="today", manufacturer_id="1") == (1, 1)

    # The per-outlet flag uses the same threshold (80) as the counts.
    route = sp.get("/api/v1/route-plans/current/business-profiler")
    assert route.status_code == 200, route.text
    flags = {item["outlet_ref"]: item["is_filled"] for item in route.json()["outlets"]}
    assert flags == {"O-1": True, "O-2": False, "O-3": True}
    detail = sp.get("/api/v1/outlets/O-2")
    assert detail.status_code == 200, detail.text
    assert (detail.json()["business_profiler_pct"], detail.json()["is_filled"]) == (40, False)

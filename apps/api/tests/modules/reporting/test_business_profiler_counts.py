from __future__ import annotations

import io
from datetime import date, datetime, timedelta

import time_machine
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.conftest import NOW
from tests.fakes.humbee import FakeHumbee
from tests.fakes.humbee_commerce import install_commerce
from tests.fakes.humbee_targets import install_target_manufacturers
from tests.fixtures import seed
from tests.fixtures.auth import login
from tests.fixtures.flows import check_in, punch_in

from humbee_sfa.core.db import transaction
from humbee_sfa.core.settings import get_settings
from humbee_sfa.modules.outlets.models.business_profiler_history import (
    OutletBusinessProfilerHistory,
)
from humbee_sfa.modules.outlets.service import OutletReadService
from humbee_sfa.modules.reporting.business_profiler import DAY_CLOSE_JOB_NAME
from humbee_sfa.modules.reporting.business_profiler_close import run_business_profiler_day_close
from humbee_sfa.modules.reporting.models import FactEmployeeDay, FactEmployeeOutletDay
from humbee_sfa.modules.reporting.projector_job import run_reporting_projector
from humbee_sfa.modules.routes.service import RouteService
from humbee_sfa.platform.models import SweepRun

DAY = date(2026, 10, 19)  # NOW is 10:00 IST on DAY; the day ends 2026-10-19T18:30Z.
PUSH = "/api/v1/integrations/humbee/business-profiler"
BP_FETCH = "/sfa/v1/outlets/business-profiler"


def _push(
    client: TestClient, outlet_id: str, pct: int | None, changed_at: datetime, key: str | None = None
) -> int:
    response = client.post(
        PUSH,
        json={"outlets": [{"outlet_id": outlet_id, "business_profiler_pct": pct, "changed_at": changed_at.isoformat()}]},
        headers={"api-key": key or get_settings().humbee_api_key},
    )
    return response.status_code


def _visit(sp, visit_id: str) -> None:
    entered = check_in(sp, visit_id)
    assert entered.status_code == 200, entered.text
    logged = sp.post(f"/api/v1/visits/{visit_id}/outcome", {"reason": "stock_full"})
    assert logged.status_code == 200, logged.text


def _bp(body: dict, window: str = "today") -> tuple[int, int]:
    totals = body[window]["totals"]
    return totals["bp_filled"], totals["bp_not_filled"]


def test_push_auth(api_client: TestClient) -> None:
    assert _push(api_client, "O-1", 90, NOW, key="wrong") == 401
    assert api_client.post(PUSH, json={"outlets": []}, headers={"api-key": get_settings().humbee_api_key}).status_code == 422


def test_counts_use_each_outlets_current_pct(
    api_client: TestClient,
    db_session: Session,
    humbee: FakeHumbee,
    travel: time_machine.Coordinates,
) -> None:
    manager_row = seed.employee(db_session, "manager")
    sp_row = seed.employee(db_session, "sales_person", manager=manager_row)
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
    _visit(sp, stops["O-2"])  # O-3 is never visited: it is not part of the BP base.

    def team_calls(**params: object) -> dict:
        response = login(api_client, manager_row).get("/api/v1/reporting/kpis/calls/team", **params)
        assert response.status_code == 200, response.text
        return response.json()

    # Live today: check-in fetched O-1 (90) and O-2 (40).
    assert _bp(team_calls()) == (1, 1)
    row = team_calls()["today"]["items"][0]
    assert (row["bp_filled"], row["bp_not_filled"]) == (1, 1)

    # The retailer fills O-2's profile; Humbee's push makes today's count move without a visit.
    assert _push(api_client, "O-2", 95, NOW + timedelta(hours=1)) == 204
    assert _push(api_client, "O-2", 95, NOW + timedelta(hours=1)) == 204  # replay is harmless
    assert _bp(team_calls()) == (2, 0)
    sp_today = sp.get("/api/v1/reporting/dashboards/sales-person", period="today").json()["metrics"]
    assert (sp_today["bp_filled"], sp_today["bp_not_filled"]) == (2, 0)

    # During the day O-1 drops to 50 in Humbee and that push is lost. After midnight O-2 drops to
    # 30 (pushed at 00:02 IST) before the day-close pull at 00:10 IST.
    humbee.outlets["O-1"].business_profiler_pct = 50
    after_midnight = datetime(2026, 10, 19, 18, 32, tzinfo=NOW.tzinfo)
    travel.move_to(after_midnight)
    humbee.outlets["O-2"].business_profiler_pct = 30
    assert _push(api_client, "O-2", 30, after_midnight) == 204

    travel.move_to(datetime(2026, 10, 19, 18, 40, tzinfo=NOW.tzinfo))
    db_session.flush()
    run_reporting_projector(db_session.connection())
    with transaction(db_session):
        RouteService(db_session).close_day(tenant_id=seed.tenant_id(), business_date=DAY, now=datetime.now(NOW.tzinfo))
    run_business_profiler_day_close(db_session.connection(), "bp", tenant_id=seed.tenant_id(), business_date=DAY)
    db_session.add(
        SweepRun(
            tenant_id=seed.tenant_id(),
            sweep_type=DAY_CLOSE_JOB_NAME,
            business_date=DAY,
            started_at=datetime.now(NOW.tzinfo),
            status="succeeded",
        )
    )
    db_session.flush()
    db_session.expire_all()

    # The sweep still freezes the day's end: O-1 = 50 (the pull repaired the lost push), O-2 = 95 (the
    # post-midnight change does not leak back into the day). No count reads these facts.
    fact = db_session.get(FactEmployeeDay, (seed.tenant_id(), sp_row.id, DAY))
    assert fact is not None and fact.business_profiler_filled_outlet_count == 1
    outlets = {
        ref: (row.business_profiler_pct, row.business_profiler_filled)
        for ref in ("O-1", "O-2")
        if (row := db_session.get(FactEmployeeOutletDay, (seed.tenant_id(), sp_row.id, DAY, ref)))
    }
    assert outlets == {"O-1": (50, False), "O-2": (95, True)}
    # The day's count uses each outlet's current %: O-1 = 50, O-2 = 30.
    assert _bp(team_calls(business_date=DAY.isoformat())) == (0, 2)

    # A later projector replay of the frozen day keeps the same answer.
    run_reporting_projector(db_session.connection())
    db_session.expire_all()
    assert db_session.get(FactEmployeeDay, (seed.tenant_id(), sp_row.id, DAY)).business_profiler_filled_outlet_count == 1

    admin = login(api_client, admin_row)
    report = admin.get("/api/v1/reporting/admin/reports/attendance", from_date=DAY.isoformat(), to_date=DAY.isoformat())
    assert report.status_code == 200, report.text
    sheet = load_workbook(io.BytesIO(report.content)).active
    rows = list(sheet.iter_rows(values_only=True))
    headers = rows[0]
    record = dict(zip(headers, next(r for r in rows[1:] if r[1] == sp_row.full_name), strict=True))
    assert {
        key: record[key]
        for key in (
            "Total Visits", "Physical Visits", "Telephonic Visits", "Productive Visits", "Missed Visits",
            "BP Filled Outlets", "BP Not Filled Outlets",
        )
    } == {
        "Total Visits": 2,
        "Physical Visits": 2,
        "Telephonic Visits": 0,
        "Productive Visits": 0,
        "Missed Visits": 1,
        "BP Filled Outlets": 0,
        "BP Not Filled Outlets": 2,
    }

    # The next day O-1 is filled again: the past day's count and month-to-date move with it.
    assert _push(api_client, "O-1", 95, datetime(2026, 10, 20, 6, 0, tzinfo=NOW.tzinfo)) == 204
    travel.move_to(datetime(2026, 10, 20, 6, 30, tzinfo=NOW.tzinfo))
    assert _bp(team_calls(business_date=DAY.isoformat())) == (1, 1)
    assert _bp(team_calls(), "mtd") == (1, 1)
    sp_mtd = login(api_client, sp_row).get("/api/v1/reporting/dashboards/sales-person", period="mtd").json()["metrics"]
    assert (sp_mtd["bp_filled"], sp_mtd["bp_not_filled"]) == (1, 1)


def test_current_pct_falls_back_to_humbee_once(db_session: Session, humbee: FakeHumbee) -> None:
    humbee.add_outlet("N-1", business_profiler_pct=90)  # N-2 is unknown to Humbee
    service = OutletReadService(db_session)
    fetches = lambda: len(humbee.calls_to("POST", BP_FETCH))

    # Humbee down: the outlets are absent (counted not filled) and nothing is recorded.
    humbee.fail("POST", BP_FETCH, "999")
    assert service.current_business_profiler(tenant_id=seed.tenant_id(), outlet_ids=["N-1", "N-2"], timeout_s=3) == {}
    assert db_session.scalars(select(OutletBusinessProfilerHistory)).all() == []

    # Humbee answers: N-1 is recorded as fetched, N-2 (left out) as having no %.
    assert service.current_business_profiler(
        tenant_id=seed.tenant_id(), outlet_ids=["N-1", "N-2"], timeout_s=3
    ) == {"N-1": 90, "N-2": None}
    recorded = {row.humbee_outlet_id: (row.pct, row.source) for row in db_session.scalars(select(OutletBusinessProfilerHistory))}
    assert recorded == {"N-1": (90, "fetch"), "N-2": (None, "fetch")}

    # Later reads use the history: no further Humbee call.
    calls = fetches()
    assert service.current_business_profiler(
        tenant_id=seed.tenant_id(), outlet_ids=["N-1", "N-2"], timeout_s=3
    ) == {"N-1": 90, "N-2": None}
    assert fetches() == calls == 2

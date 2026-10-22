from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.fakes.humbee import FakeHumbee
from tests.fixtures import seed
from tests.fixtures.auth import Authed, login
from tests.fixtures.flows import check_in, error_code, punch

from humbee_sfa.core.business_date import IST_ZONE
from humbee_sfa.modules.attendance.models.gps_fix import GpsFix
from humbee_sfa.modules.attendance.models.punch_event import PunchEvent


def ist(hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(2026, 10, 19, hour, minute, second, tzinfo=IST_ZONE)


def start_official_work(authed: Authed, at: datetime) -> object:
    return authed.post(
        "/api/v1/official-work/sessions",
        {"work_type": "meeting", "occurred_at": at.isoformat(), "purpose": "Distributor review"},
    )


def test_one_duty_cycle(api_client: TestClient, db_session: Session, travel) -> None:
    travel.move_to(ist(12, 0))
    sp = seed.employee(db_session, "sales_person", manager=seed.employee(db_session, "manager"))
    me = login(api_client, sp)

    punched_in = punch(
        me, "in", ist(9, 30),
        latitude=28.6139, longitude=77.209, accuracy_m=2500.0, provider="network", is_mock_location=True,
    )
    assert punched_in.status_code == 201, punched_in.text
    assert punched_in.json()["on_duty"] is True
    assert me.get("/api/v1/attendance/today").json()["on_duty"] is True

    fix = db_session.execute(
        select(GpsFix).join(PunchEvent, PunchEvent.gps_fix_id == GpsFix.id).where(PunchEvent.employee_id == sp.id)
    ).scalar_one()
    assert (fix.latitude, fix.longitude, fix.accuracy_m) == (Decimal("28.613900"), Decimal("77.209000"), Decimal("2500.00"))
    assert fix.is_mock_location is True

    again = punch(me, "in", ist(9, 35))
    assert (again.status_code, error_code(again)) == (409, "already_punched_in")

    work = start_official_work(me, ist(9, 45))
    assert work.status_code == 201, work.text

    blocked = punch(me, "out", ist(10, 0))
    assert (blocked.status_code, error_code(blocked)) == (409, "official_work_running")

    ended = me.post(f"/api/v1/official-work/sessions/{work.json()['id']}/end", {"occurred_at": ist(10, 30).isoformat()})
    assert ended.status_code == 200, ended.text
    assert ended.json()["duration_seconds"] == 2700

    punched_out = punch(me, "out", ist(11, 0))
    assert punched_out.status_code == 201, punched_out.text
    today = me.get("/api/v1/attendance/today").json()
    assert today["on_duty"] is False
    assert today["punched_out_at"] is not None

    second_cycle = punch(me, "in", ist(11, 30))
    assert (second_cycle.status_code, error_code(second_cycle)) == (409, "punch_sequence_conflict")

    history = me.get("/api/v1/attendance/history", month="2026-10").json()
    assert history["summary"] == {"present": 0, "late": 1, "absent": 0, "leave": 0}
    assert [day["status"] for day in history["days"]] == ["late"]


def test_late_boundary(api_client: TestClient, db_session: Session) -> None:
    manager = seed.employee(db_session, "manager")
    for at, expected in [(ist(8, 59, 59), "present"), (ist(9, 0, 0), "present"), (ist(9, 0, 1), "late")]:
        me = login(api_client, seed.employee(db_session, "sales_person", manager=manager))
        assert punch(me, "in", at).status_code == 201
        history = me.get("/api/v1/attendance/history", month="2026-10").json()
        assert [day["status"] for day in history["days"]] == [expected], at


def test_team_counts(api_client: TestClient, db_session: Session) -> None:
    manager = seed.employee(db_session, "manager")
    early, late, on_leave, absent = (seed.employee(db_session, "sales_person", manager=manager) for _ in range(4))
    other_sp = seed.employee(db_session, "sales_person", manager=seed.employee(db_session, "manager"))
    boss = login(api_client, manager)

    assert punch(login(api_client, early), "in", ist(8, 50)).status_code == 201
    assert punch(login(api_client, late), "in", ist(9, 20)).status_code == 201
    assert punch(login(api_client, other_sp), "in", ist(9, 40)).status_code == 201

    leave = login(api_client, on_leave).post(
        "/api/v1/leave/requests", {"leave_type": "casual", "from_date": "2026-10-19", "to_date": "2026-10-19"}
    )
    assert leave.status_code == 201, leave.text
    approved = boss.post(f"/api/v1/approvals/{leave.json()['approval_request_id']}/approve", {})
    assert approved.status_code == 200, approved.text

    team = boss.get("/api/v1/attendance/team", business_date="2026-10-19").json()
    assert (team["on_duty_count"], team["after_9am_count"], team["on_leave_count"], team["no_punch_in_count"]) == (2, 1, 1, 1)
    assert team["total"] == 4
    assert {row["employee_id"] for row in team["items"]} == {early.id, late.id, on_leave.id, absent.id}

    forbidden = login(api_client, absent).get("/api/v1/attendance/team", business_date="2026-10-19")
    assert forbidden.status_code == 403


def test_field_mutex(api_client: TestClient, db_session: Session, humbee: FakeHumbee) -> None:
    humbee.add_outlet("OUT-1")
    manager = seed.employee(db_session, "manager")
    visiting = login(api_client, seed.employee(db_session, "sales_person", manager=manager))
    working = login(api_client, seed.employee(db_session, "sales_person", manager=manager))

    assert punch(visiting, "in", ist(9, 30)).status_code == 201
    visit = check_in(visiting, at=ist(9, 40), outlet_ref="OUT-1")
    assert visit.status_code == 200, visit.text
    assert visit.json()["state"] == "in_progress"

    out = punch(visiting, "out", ist(9, 55))
    assert (out.status_code, error_code(out)) == (409, "visit_in_progress")
    work = start_official_work(visiting, ist(9, 55))
    assert (work.status_code, error_code(work)) == (409, "visit_in_progress")

    assert punch(working, "in", ist(9, 30)).status_code == 201
    assert start_official_work(working, ist(9, 40)).status_code == 201
    blocked = check_in(working, outlet_ref="OUT-1")
    assert (blocked.status_code, error_code(blocked)) == (409, "official_work_running")

from __future__ import annotations

from datetime import timedelta
from typing import Any

import time_machine
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.conftest import NOW
from tests.fixtures import seed
from tests.fixtures.auth import Authed, login

from humbee_sfa.core.conventions import generate_ulid
from humbee_sfa.modules.targets import repository
from humbee_sfa.modules.targets.models import Lead


def _lead_body(**overrides: Any) -> dict[str, Any]:
    return {
        "name": "Ravi Kumar",
        "mobile": "+919845012345",
        "email": "ravi@example.com",
        "company_name": "Kumar Oils",
        **overrides,
    }


def test_capture_stores_company_as_the_single_manufacturer(
    api_client: TestClient, db_session: Session
) -> None:
    sp = seed.employee(db_session, "sales_person", manager=seed.employee(db_session, "manager"))
    resp = login(api_client, sp).post("/api/v1/leads", _lead_body(associated_manufacturers=["A", "B"]))
    assert resp.status_code == 201, resp.text
    assert "associated_manufacturers" not in resp.json()
    lead = db_session.scalars(select(Lead)).one()
    assert lead.associated_manufacturer_names == ["Kumar Oils"]


def test_capture_rejects_manufacturer_name_over_120(
    api_client: TestClient, db_session: Session
) -> None:
    sp = seed.employee(db_session, "sales_person", manager=seed.employee(db_session, "manager"))
    resp = login(api_client, sp).post("/api/v1/leads", _lead_body(company_name="X" * 121))
    assert resp.status_code == 422


def _capture(client: Authed, company: str, **overrides: Any) -> str:
    resp = client.post("/api/v1/leads", _lead_body(company_name=company, **overrides))
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


class _Org:
    def __init__(self, api_client: TestClient, db: Session) -> None:
        self.admin = seed.employee(db, "admin")
        self.m1 = seed.employee(db, "manager")
        self.m2 = seed.employee(db, "manager", manager=self.m1)
        self.so1 = seed.employee(db, "sales_person", manager=self.m1)
        self.so2 = seed.employee(db, "sales_person", manager=self.m2)
        self.m3 = seed.employee(db, "manager")
        self.so3 = seed.employee(db, "sales_person", manager=self.m3)
        self.c = {
            e.id: login(api_client, e)
            for e in (self.admin, self.m1, self.so1, self.so2, self.m3, self.so3)
        }
        self.lead = {
            "so1": _capture(self.c[self.so1.id], "Alpha Foods"),
            "so2": _capture(self.c[self.so2.id], "Beta Foods"),
            "m1": _capture(self.c[self.m1.id], "Gamma Foods"),
            "so3": _capture(self.c[self.so3.id], "Delta Foods"),
        }


def _ids(resp: Any) -> set[str]:
    assert resp.status_code == 200, resp.text
    return {i["id"] for i in resp.json()["items"]}


def test_list_scope_by_role(api_client: TestClient, db_session: Session) -> None:
    o = _Org(api_client, db_session)
    L = o.lead

    so = o.c[o.so1.id].get("/api/v1/leads")
    assert _ids(so) == {L["so1"]}
    item = so.json()["items"][0]
    assert item["captured_by"] == {"id": o.so1.id, "name": o.so1.full_name}
    assert so.json()["total"] == 1

    mgr = o.c[o.m1.id].get("/api/v1/leads")
    assert _ids(mgr) == {L["so1"], L["so2"], L["m1"]}
    assert mgr.json()["total"] == 3

    adm = o.c[o.admin.id].get("/api/v1/leads")
    assert _ids(adm) == set(L.values())
    assert adm.json()["total"] == 4


def test_list_other_tenant_never_visible(api_client: TestClient, db_session: Session) -> None:
    o = _Org(api_client, db_session)
    repository.insert_lead(
        db_session,
        lead_id=generate_ulid(),
        tenant_id="other-tenant",
        captured_by_employee_id=o.so1.id,
        prospect_name="Ghost",
        contact_designation=None,
        contact_mobile_hmac="x" * 64,
        contact_mobile_enc=b"x",
        contact_mobile_last4="0000",
        contact_email="g@example.com",
        company_name="Ghost Co",
        associated_manufacturer_names=["Ghost Co"],
        annual_turnover_cr=None,
        head_office_location=None,
        notes=None,
        occurred_at=NOW,
        received_at=NOW,
        business_date=NOW.date(),
    )
    db_session.commit()
    resp = o.c[o.admin.id].get("/api/v1/leads")
    assert _ids(resp) == set(o.lead.values())
    assert resp.json()["total"] == 4


def test_employee_filter_scope(api_client: TestClient, db_session: Session) -> None:
    o = _Org(api_client, db_session)
    L = o.lead
    m1 = o.c[o.m1.id]
    assert _ids(m1.get("/api/v1/leads", employee_id=o.so2.id)) == {L["so2"]}
    assert _ids(m1.get("/api/v1/leads", employee_id=o.m1.id)) == {L["m1"]}
    assert m1.get("/api/v1/leads", employee_id=o.so3.id).status_code == 404
    so1 = o.c[o.so1.id]
    assert _ids(so1.get("/api/v1/leads", employee_id=o.so1.id)) == {L["so1"]}
    assert so1.get("/api/v1/leads", employee_id=o.so2.id).status_code == 404


def test_date_range(api_client: TestClient, db_session: Session, travel: time_machine.Coordinates) -> None:
    sp = seed.employee(db_session, "sales_person", manager=seed.employee(db_session, "manager"))
    c = login(api_client, sp)
    day1 = _capture(c, "Day One Co")
    travel.move_to(NOW + timedelta(days=3))
    c = login(api_client, sp)
    day2 = _capture(c, "Day Two Co")
    d1 = NOW.date().isoformat()
    d2 = (NOW + timedelta(days=3)).date().isoformat()

    assert _ids(c.get("/api/v1/leads", **{"from": d1, "to": d1})) == {day1}
    assert _ids(c.get("/api/v1/leads", **{"from": d2})) == {day2}
    assert _ids(c.get("/api/v1/leads", **{"from": d1, "to": d2})) == {day1, day2}
    bad = c.get("/api/v1/leads", **{"from": d2, "to": d1})
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "invalid_date_range"


def test_search_matches_manufacturer_contact_email(
    api_client: TestClient, db_session: Session
) -> None:
    sp = seed.employee(db_session, "sales_person", manager=seed.employee(db_session, "manager"))
    c = login(api_client, sp)
    lid = _capture(c, "Zephyr Spices", name="Quentin Blake", email="qb@mailer.test")
    _capture(c, "Other Co", name="Someone Else", email="else@example.com")
    for q in ("zephyr", "QUENTIN", "mailer.TEST"):
        assert _ids(c.get("/api/v1/leads", q=q)) == {lid}, q


def test_search_is_literal(api_client: TestClient, db_session: Session) -> None:
    sp = seed.employee(db_session, "sales_person", manager=seed.employee(db_session, "manager"))
    c = login(api_client, sp)
    first = _capture(c, "100% Pure Oils")
    _capture(c, "1000 Pure Oils")
    assert _ids(c.get("/api/v1/leads", q="100%")) == {first}


def test_cursor_paging_is_stable_on_ties(api_client: TestClient, db_session: Session) -> None:
    sp = seed.employee(db_session, "sales_person", manager=seed.employee(db_session, "manager"))
    c = login(api_client, sp)
    with time_machine.travel(NOW, tick=False):
        for n in range(5):
            _capture(c, f"Tie Co {n}")
        seen: list[str] = []
        cursor: str | None = None
        for _ in range(5):
            params: dict[str, Any] = {"limit": 2}
            if cursor:
                params["cursor"] = cursor
            resp = c.get("/api/v1/leads", **params)
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["total"] == 5
            seen += [i["id"] for i in body["items"]]
            cursor = body["next_cursor"]
            if cursor is None:
                assert len(body["items"]) == 1
                break
    assert len(seen) == 5 and len(set(seen)) == 5
    assert cursor is None


def test_invalid_cursor_is_422(api_client: TestClient, db_session: Session) -> None:
    sp = seed.employee(db_session, "sales_person", manager=seed.employee(db_session, "manager"))
    for bad in ("garbage", "2026-10-19T04:30:00+00:00", "nope|01ABC"):
        resp = login(api_client, sp).get("/api/v1/leads", cursor=bad)
        assert resp.status_code == 422, bad
        assert resp.json()["error"]["code"] == "invalid_cursor"

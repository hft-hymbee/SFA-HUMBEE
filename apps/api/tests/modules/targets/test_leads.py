from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.fixtures import seed
from tests.fixtures.auth import login

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

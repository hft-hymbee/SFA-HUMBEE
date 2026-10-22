from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.fakes.humbee import FakeHumbee
from tests.fixtures import seed
from tests.fixtures.auth import Authed, login

from humbee_sfa.core.conventions import generate_ulid
from humbee_sfa.modules.org.models import Employee

VISIT_GPS = {"lat": 12.9716, "lng": 77.5946, "accuracy_m": 8.0, "provider": "gps", "is_mock": False}


def error_code(response: httpx.Response) -> str:
    return response.json()["error"]["code"]


def team(db: Session, client: TestClient) -> tuple[Authed, Authed]:
    manager = seed.employee(db, "manager")
    sales_person = seed.employee(db, "sales_person", manager=manager)
    return login(client, sales_person), login(client, manager)


def punch(authed: Authed, direction: str, at: datetime | None = None, **gps: Any) -> httpx.Response:
    occurred_at = (at or datetime.now(UTC)).isoformat()
    fix = {
        "latitude": 12.9716,
        "longitude": 77.5946,
        "accuracy_m": 8.0,
        "provider": "gps",
        "captured_at": occurred_at,
        **gps,
    }
    return authed.post(
        "/api/v1/attendance/punches",
        {"direction": direction, "occurred_at": occurred_at, "gps_fix": fix, "resolved_address": "MG Road"},
    )


def punch_in(authed: Authed, at: datetime | None = None) -> None:
    response = punch(authed, "in", at)
    assert response.status_code == 201, response.text


def check_in(
    authed: Authed, visit_id: str | None = None, *, at: datetime | None = None, **body: Any
) -> httpx.Response:
    payload = {
        "occurred_at": (at or datetime.now(UTC)).isoformat(),
        "visit_type": "physical",
        "gps": VISIT_GPS,
        **body,
    }
    return authed.post(f"/api/v1/visits/{visit_id or generate_ulid()}/check-in", payload)


def assign_districts(admin: Authed, employee: Employee, humbee: FakeHumbee, *district_ids: str) -> None:
    state_ids = list(dict.fromkeys(humbee.districts[d].state_id for d in district_ids))
    zone_ids = list(dict.fromkeys(humbee.states[s].zone_id for s in state_ids))
    response = admin.put(
        f"/api/v1/org/employees/{employee.id}/geography-scope",
        {"zones": zone_ids, "states": state_ids, "districts": list(district_ids)},
    )
    assert response.status_code == 200, response.text

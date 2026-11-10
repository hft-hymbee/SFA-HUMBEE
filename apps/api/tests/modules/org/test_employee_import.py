from __future__ import annotations

import itertools

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.fixtures import seed
from tests.fixtures.auth import Authed, login
from tests.fixtures.flows import error_code

from humbee_sfa.core.conventions import generate_ulid
from humbee_sfa.modules.org import employee_import
from humbee_sfa.modules.org.models import Employee, HierarchyEdge
from humbee_sfa.platform.models import AuditLog

IMPORT = "/api/v1/org/employees/import"
TEMPLATE = "/api/v1/org/employees/import/template"
HEADER = ",".join(employee_import.REQUIRED_COLUMNS)
_numbers = itertools.count(70001)
_AUTO = "auto"


def _phone() -> str:
    return f"98{next(_numbers):08d}"


def _csv(*rows: str, header: str = HEADER) -> bytes:
    return ("\n".join((header, *rows)) + "\n").encode()


def _row(
    code: str, phone: str, role: str = "sales_person", manager_code: str = "", **kw: str
) -> str:
    designation = kw.get("designation", seed.DEFAULT_DESIGNATION.get(role, "admin"))
    return f"{code},Name {code},{phone},{role},{designation},{manager_code}"


def _upload(
    actor: Authed, data: bytes, *, dry_run: bool = False, key: str | None = _AUTO
) -> httpx.Response:
    headers = {"Authorization": f"Bearer {actor.token}"}
    if key is not None:
        headers["Idempotency-Key"] = generate_ulid() if key == _AUTO else key
    return actor.client.post(
        IMPORT,
        params={"dry_run": str(dry_run).lower()},
        files={"file": ("employees.csv", data, "text/csv")},
        headers=headers,
    )


def _employee_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Employee))


def _by_code(db: Session, code: str) -> Employee:
    return db.scalars(select(Employee).where(Employee.employee_code == code)).one()


def _edges(db: Session, employee_id: str) -> set[tuple[str, int]]:
    rows = db.execute(
        select(HierarchyEdge.ancestor_employee_id, HierarchyEdge.depth).where(
            HierarchyEdge.descendant_employee_id == employee_id
        )
    )
    return {(ancestor, depth) for ancestor, depth in rows}


def test_import_is_admin_only(api_client: TestClient, db_session: Session) -> None:
    manager = seed.employee(db_session, "manager")
    sp = seed.employee(db_session, "sales_person", manager=manager)
    before = _employee_count(db_session)

    for actor in (login(api_client, manager), login(api_client, sp)):
        response = _upload(actor, _csv(_row("X-1", _phone())))
        assert (response.status_code, error_code(response)) == (403, "forbidden")
        template = actor.get(TEMPLATE)
        assert (template.status_code, error_code(template)) == (403, "forbidden")
    assert _employee_count(db_session) == before


def test_import_builds_hierarchy_managers_first(
    api_client: TestClient, db_session: Session
) -> None:
    admin = login(api_client, seed.employee(db_session, "admin"))
    existing_manager = seed.employee(db_session, "manager")
    sp1_phone, sp2_phone, sp3_phone = _phone(), _phone(), _phone()
    header = HEADER + ",login_enabled,joined_on"
    data = _csv(
        # The report is listed before its manager; the import must still write the manager first.
        _row("SP-1", f"+91{sp1_phone}", manager_code="MGR-1") + ",false,2026-10-01",
        _row("MGR-1", _phone(), role="manager") + ",,",
        _row("SP-2", f"91{sp2_phone}", manager_code="MGR-1") + ",,",
        _row("SP-3", sp3_phone, manager_code=existing_manager.employee_code) + ",,",
        header=header,
    )

    response = _upload(admin, data)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["dry_run"] is False and body["row_count"] == 4
    assert [row["row"] for row in body["employees"]] == [2, 3, 4, 5]
    manager, sp1, sp2, sp3 = (_by_code(db_session, c) for c in ("MGR-1", "SP-1", "SP-2", "SP-3"))
    assert manager.manager_employee_id is None
    assert sp1.manager_employee_id == sp2.manager_employee_id == manager.id
    assert sp3.manager_employee_id == existing_manager.id
    assert _edges(db_session, manager.id) == {(manager.id, 0)}
    assert _edges(db_session, sp1.id) == {(sp1.id, 0), (manager.id, 1)}
    assert (existing_manager.id, 1) in _edges(db_session, sp3.id)
    assert [seed.phone_of(e) for e in (sp1, sp2, sp3)] == [
        f"+91{sp1_phone}",
        f"+91{sp2_phone}",
        f"+91{sp3_phone}",
    ]
    assert sp1.login_enabled is False and str(sp1.joined_on) == "2026-10-01"
    created_audits = db_session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.entity_id.in_([manager.id, sp1.id, sp2.id, sp3.id]),
            AuditLog.change_payload["transition"].astext == "employee_created",
        )
    )
    assert created_audits == 4


def test_import_is_all_or_nothing_and_reports_every_row(
    api_client: TestClient, db_session: Session
) -> None:
    admin = login(api_client, seed.employee(db_session, "admin"))
    manager = seed.employee(db_session, "manager")
    sp = seed.employee(db_session, "sales_person", manager=manager)
    inactive = seed.employee(db_session, "manager")
    assert (
        admin.post(
            f"/api/v1/org/employees/{inactive.id}/deactivate", {"reason": "left"}
        ).status_code
        == 200
    )
    before = _employee_count(db_session)

    rows = [
        _row("OK-1", _phone()),  # 2: valid, but nothing may be written
        _row("OK-1", _phone()),  # 3
        _row("C-4", seed.phone_of(sp)),  # 4
        _row(sp.employee_code, _phone()),  # 5
        _row("C-6", _phone(), manager_code="NO-SUCH-CODE"),  # 6
        _row("C-7", _phone(), manager_code=inactive.employee_code),  # 7
        _row("C-8", _phone(), manager_code=sp.employee_code),  # 8
        _row("C-9", _phone()),  # 9: valid
        _row("C-10", _phone(), manager_code="C-9"),  # 10
        _row("C-11", _phone(), manager_code="C-11"),  # 11
        _row("C-12", _phone(), role="admin"),  # 12
        _row("C-13", _phone(), designation="area_sales_manager"),  # 13
        _row("C-14", "12345"),  # 14
        _row("C-15", _phone(), role="manager", manager_code="C-16"),  # 15
        _row("C-16", _phone(), role="manager", manager_code="C-15"),  # 16
        _row("C-17", _phone()) + ",maybe",  # 17
    ]
    response = _upload(admin, _csv(*rows, header=HEADER + ",login_enabled"))

    assert (response.status_code, error_code(response)) == (422, "csv_validation_failed")
    details = response.json()["error"]["details"]
    assert details["row_count"] == 16
    assert {(e["row"], e["code"]) for e in details["errors"]} == {
        (3, "duplicate_in_file"),
        (4, "phone_already_registered"),
        (5, "employee_code_taken"),
        (6, "manager_not_found"),
        (7, "manager_not_found"),
        (8, "invalid_manager"),
        (10, "invalid_manager"),
        (11, "self_manager"),
        (12, "role_not_allowed"),
        (13, "designation_role_mismatch"),
        (14, "invalid_phone"),
        (15, "manager_cycle"),
        (16, "manager_cycle"),
        (17, "invalid_value"),
    }
    assert _employee_count(db_session) == before


def test_file_level_errors(api_client: TestClient, db_session: Session) -> None:
    admin = login(api_client, seed.employee(db_session, "admin"))
    too_many = _csv(*(_row(f"R-{i}", f"97{i:08d}") for i in range(employee_import.MAX_ROWS + 1)))
    cases = [
        (b"", 422, "csv_empty"),
        (_csv(), 422, "csv_empty"),
        (b"employee_code,phone\nA,9800000000\n", 422, "csv_missing_columns"),
        (_csv(header=HEADER + ",email"), 422, "csv_unknown_columns"),
        (_csv(header=HEADER + ",phone"), 422, "csv_duplicate_columns"),
        (HEADER.encode() + b"\n\xff\xfe\n", 422, "csv_invalid_encoding"),
        (too_many, 422, "csv_too_many_rows"),
        (b"x" * (employee_import.MAX_BYTES + 1), 413, "file_too_large"),
    ]
    for data, status, code in cases:
        response = _upload(admin, data)
        assert (response.status_code, error_code(response)) == (status, code), code


def test_dry_run_validates_without_writing(api_client: TestClient, db_session: Session) -> None:
    admin = login(api_client, seed.employee(db_session, "admin"))
    before = _employee_count(db_session)

    response = _upload(
        admin,
        _csv(
            _row("D-1", _phone(), role="manager"),
            _row("D-2", _phone(), manager_code="D-1"),
        ),
        dry_run=True,
        key=None,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["dry_run"] is True and body["row_count"] == 2
    assert all(row["id"] is None for row in body["employees"])
    assert _employee_count(db_session) == before


def test_import_idempotency(api_client: TestClient, db_session: Session) -> None:
    admin = login(api_client, seed.employee(db_session, "admin"))
    data = _csv(_row("I-1", _phone()), _row("I-2", _phone()))
    before = _employee_count(db_session)
    key = generate_ulid()

    first = _upload(admin, data, key=key)
    replay = _upload(admin, data, key=key)
    assert first.status_code == replay.status_code == 201, first.text
    assert replay.json() == first.json()
    assert _employee_count(db_session) == before + 2

    conflict = _upload(admin, _csv(_row("I-3", _phone())), key=key)
    assert (conflict.status_code, error_code(conflict)) == (409, "idempotency_conflict")
    missing = _upload(admin, _csv(_row("I-4", _phone())), key=None)
    assert (missing.status_code, error_code(missing)) == (422, "idempotency_key_required")


def test_template_round_trip(api_client: TestClient, db_session: Session) -> None:
    admin = login(api_client, seed.employee(db_session, "admin"))

    template = admin.get(TEMPLATE)
    assert template.status_code == 200
    assert template.headers["content-type"].startswith("text/csv")

    response = _upload(admin, template.content)
    assert response.status_code == 201, response.text
    manager_row, sp_row = response.json()["employees"]
    assert sp_row["manager_employee_id"] == manager_row["id"]


def test_normalize_phone_and_manager_ordering() -> None:
    assert employee_import.normalize_phone("98765 43210") == "+919876543210"
    assert employee_import.normalize_phone("919876543210") == "+919876543210"
    assert employee_import.normalize_phone("+919876543210") == "+919876543210"
    assert employee_import.normalize_phone("+14155550123") == "+14155550123"
    assert employee_import.normalize_phone("12345") is None

    rows, errors = employee_import.parse_csv(
        _csv(
            _row("L3", "9000000003", manager_code="L2"),
            _row("L2", "9000000002", role="manager", manager_code="L1"),
            _row("L1", "9000000001", role="manager"),
        )
    )
    ordered, cycle_errors = employee_import.order_managers_first(rows)
    assert errors == cycle_errors == []
    assert [row.employee_code for row in ordered] == ["L1", "L2", "L3"]

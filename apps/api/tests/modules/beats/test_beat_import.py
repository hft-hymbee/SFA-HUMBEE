from __future__ import annotations

import io
from typing import Any

import httpx
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.fakes.humbee import FakeHumbee
from tests.fixtures import seed
from tests.fixtures.auth import Authed, login
from tests.fixtures.flows import assign_districts, error_code

from humbee_sfa.core.conventions import generate_ulid
from humbee_sfa.modules.beats import beat_import
from humbee_sfa.modules.beats.models import Beat, BeatOutlet, BeatVersion
from humbee_sfa.modules.org.models import Employee
from humbee_sfa.modules.outlets.models import Outlet
from humbee_sfa.platform.models import AuditLog

IMPORT = "/api/v1/beats/import"
TEMPLATE = "/api/v1/beats/import/template"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
CONFIG = beat_import.CONFIG_SHEET
OUTLETS = beat_import.OUTLETS_SHEET
_AUTO = "auto"


def _beat(
    name: str,
    owner: Employee | str,
    *,
    freq: str = "weekly",
    days: str = "Mon, Thu",
    weeks: str = "",
    cats: str = "",
    zones: Any = "1",
    states: Any = "10",
    districts: Any = "100",
) -> list[Any]:
    code = owner if isinstance(owner, str) else owner.employee_code
    return [name, code, freq, days, weeks, cats, zones, states, districts]


def _xlsx(
    beats: list[list[Any]],
    outlets: list[list[Any]],
    *,
    config_header: list[str] | None = None,
    sheets: tuple[str, ...] = (CONFIG, OUTLETS),
) -> bytes:
    workbook = Workbook()
    workbook.remove(workbook.active)  # type: ignore[arg-type]
    if CONFIG in sheets:
        config = workbook.create_sheet(CONFIG)
        config.append(config_header or list(beat_import.CONFIG_COLUMNS.values()))
        for row in beats:
            config.append(row)
    if OUTLETS in sheets:
        sheet = workbook.create_sheet(OUTLETS)
        sheet.append(list(beat_import.OUTLET_COLUMNS.values()))
        for row in outlets:
            sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _upload(
    actor: Authed, data: bytes, *, dry_run: bool = False, key: str | None = _AUTO
) -> httpx.Response:
    headers = {"Authorization": f"Bearer {actor.token}"}
    if key is not None:
        headers["Idempotency-Key"] = generate_ulid() if key == _AUTO else key
    return actor.client.post(
        IMPORT,
        params={"dry_run": str(dry_run).lower()},
        files={"file": ("beats.xlsx", data, XLSX)},
        headers=headers,
    )


def _beat_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Beat))


def _by_name(db: Session, name: str) -> Beat:
    return db.scalars(select(Beat).where(Beat.display_name == name)).one()


def _sequence(db: Session, beat: Beat) -> list[str]:
    rows = db.execute(
        select(Outlet.humbee_outlet_id)
        .join(BeatOutlet, BeatOutlet.outlet_id == Outlet.id)
        .where(BeatOutlet.beat_version_id == beat.current_version_id)
        .order_by(BeatOutlet.sequence_hint)
    )
    return [ref for (ref,) in rows]


def _codes(response: httpx.Response) -> set[tuple[str, int, str]]:
    return {(e["sheet"], e["row"], e["code"]) for e in response.json()["error"]["details"]["errors"]}


def _setup(db: Session, api_client: TestClient, humbee: FakeHumbee) -> tuple[Authed, Employee, Employee]:
    admin = login(api_client, seed.employee(db, "admin"))
    manager = seed.employee(db, "manager")
    south = seed.employee(db, "sales_person", manager=manager)
    west = seed.employee(db, "sales_person", manager=manager)
    assign_districts(admin, south, humbee, "100", "101")
    assign_districts(admin, west, humbee, "200")
    return admin, south, west


def test_import_creates_approved_beats(
    db_session: Session, api_client: TestClient, humbee: FakeHumbee
) -> None:
    admin, south, west = _setup(db_session, api_client, humbee)
    humbee.add_outlet("O1", district_id="100", shop_category_id="CATEGORY_C")
    humbee.add_outlet("O2", district_id="100")
    humbee.add_outlet("O3", district_id="101", shop_category_id="CATEGORY_B")
    humbee.add_outlet("O4", district_id="200")
    humbee.outlet_page_size = 10_000  # the fake otherwise caps every page at 2
    data = _xlsx(
        [
            _beat("Indiranagar", south),  # no categories: any category in the district
            _beat("Mysuru F", south, freq="Fortnightly", days="tue", weeks="1, 3", cats="category_b",
                  districts="101"),
            # Ids typed as numbers come back from Excel as floats.
            _beat("Pune Daily", west, freq="daily", days="", zones=2, states=20.0, districts=200.0),
        ],
        [["Indiranagar", "O2"], ["indiranagar", "O1"], ["Mysuru F", "O3"], ["Pune Daily", "O4"]],
    )

    response = _upload(admin, data)

    assert response.status_code == 201, response.text
    # One outlet search for the whole file, across all three beats' districts, at Humbee's
    # maximum page size and with categories checked locally.
    (search,) = humbee.calls_to("GET", "/sfa/v1/outlets")
    assert search.params.get_list("district_ids") == ["100", "101", "200"]
    assert search.params["limit"] == "10000" and "shop_category_ids" not in search.params
    body = response.json()
    assert body["dry_run"] is False and body["beat_count"] == 3
    assert [(b["row"], b["outlet_count"]) for b in body["beats"]] == [(2, 2), (3, 1), (4, 1)]
    indiranagar, mysuru, pune = (_by_name(db_session, n) for n in ("Indiranagar", "Mysuru F", "Pune Daily"))
    for beat in (indiranagar, mysuru, pune):
        assert (beat.lifecycle_state, beat.activation_state) == ("approved", "active")
        assert beat.current_version_id is not None and beat.draft_version_id is None
        assert beat.code == beat.display_name
    assert indiranagar.owner_employee_id == south.id and pune.owner_employee_id == west.id
    assert _sequence(db_session, indiranagar) == ["O2", "O1"]

    mysuru_version = db_session.get(BeatVersion, mysuru.current_version_id)
    assert mysuru_version.frequency == {"frequency": "fortnightly", "visit_days": [2], "week_cycle": [1, 3]}
    assert mysuru_version.geo_scope["cats"] == ["CATEGORY_B"]
    assert mysuru_version.geo_scope["labels"]["districts"] == [
        {"id": "101", "name": "Mysuru", "state_id": "10", "state_name": "Karnataka"}
    ]
    pune_version = db_session.get(BeatVersion, pune.current_version_id)
    assert pune_version.frequency == {"frequency": "daily", "visit_days": [], "week_cycle": []}
    assert pune_version.geo_scope["districts"] == ["200"]

    submitted = db_session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.entity_id.in_([indiranagar.id, mysuru.id, pune.id]),
            AuditLog.change_payload["transition"].astext == "beat_submitted",
        )
    )
    assert submitted == 3
    listed = admin.get("/api/v1/beats", params={"status": "approved"})
    assert {"Indiranagar", "Mysuru F", "Pune Daily"} <= {b["display_name"] for b in listed.json()["items"]}


def test_import_is_admin_only(db_session: Session, api_client: TestClient, humbee: FakeHumbee) -> None:
    _, south, _ = _setup(db_session, api_client, humbee)
    manager = db_session.get(Employee, south.manager_employee_id)
    for actor in (login(api_client, manager), login(api_client, south)):
        response = _upload(actor, _xlsx([_beat("X", south)], [["X", "O1"]]))
        assert (response.status_code, error_code(response)) == (403, "forbidden")
        template = actor.get(TEMPLATE)
        assert (template.status_code, error_code(template)) == (403, "forbidden")


def test_import_reports_every_error_and_writes_nothing(
    db_session: Session, api_client: TestClient, humbee: FakeHumbee
) -> None:
    admin, south, west = _setup(db_session, api_client, humbee)
    for n in range(1, 14):
        humbee.add_outlet(f"P{n}", district_id="100")
    humbee.add_outlet("Q1", district_id="101")
    existing = _upload(admin, _xlsx([_beat("Existing", south)], [["Existing", "P12"]]))
    assert existing.status_code == 201, existing.text

    manager = db_session.get(Employee, south.manager_employee_id)
    inactive = seed.employee(db_session, "sales_person", manager=manager)
    assign_districts(admin, inactive, humbee, "100")
    assert admin.post(f"/api/v1/org/employees/{inactive.id}/deactivate", {"reason": "left"}).status_code == 200
    unassigned = seed.employee(db_session, "sales_person", manager=manager)
    before = _beat_count(db_session)

    beats = [
        _beat("Good", south),  # 2: valid, but nothing may be written
        _beat("GOOD", south),  # 3
        _beat("existing", south),  # 4
        _beat("Ghost", "NO-SUCH-CODE"),  # 5
        _beat("Gone", inactive),  # 6
        _beat("Boss", manager),  # 7
        _beat("Loose", unassigned),  # 8
        _beat("BadZone", south, zones="1, 9"),  # 9
        _beat("WrongState", south, districts="100, 200"),  # 10
        _beat("NotMine", south, zones="1, 2", states="10, 20", districts="100, 200"),  # 11
        _beat("Freq", south, days=""),  # 12
        _beat("BadDay", south, days="Funday"),  # 13
        _beat("BadCat", south, cats="CATEGORY_Z"),  # 14
        _beat("Empty", south),  # 15
        _beat("OutDistrict", south),  # 16
        _beat("OutCat", south, cats="CATEGORY_B"),  # 17
        _beat("TakenOutlet", south),  # 18
        _beat("Pune", west, zones="2", states="20", districts="200"),  # 19
    ]
    outlets = [
        ["Good", "P1"],  # 2
        ["Existing", "P2"],  # 3
        ["Ghost", "P3"],  # 4
        ["Gone", "P4"],  # 5
        ["Boss", "P5"],  # 6
        ["Loose", "P6"],  # 7
        ["BadZone", "P7"],  # 8
        ["WrongState", "P8"],  # 9
        ["NotMine", "P9"],  # 10
        ["Freq", "P10"],  # 11
        ["BadDay", "P11"],  # 12
        ["BadCat", "P13"],  # 13
        ["OutDistrict", "Q1"],  # 14: Q1 is in 101
        ["OutCat", "NO-SUCH-OUTLET"],  # 15
        ["TakenOutlet", "P12"],  # 16: already on "Existing"
        ["Nope", "X1"],  # 17
        ["Good", "P1"],  # 18
        ["Pune", "P1"],  # 19
        ["Pune", ""],  # 20
    ]
    response = _upload(admin, _xlsx(beats, outlets))

    assert (response.status_code, error_code(response)) == (422, "xlsx_validation_failed"), response.text
    details = response.json()["error"]["details"]
    assert (details["beat_count"], details["outlet_row_count"]) == (17, 19)
    assert _codes(response) == {
        (CONFIG, 3, "duplicate_in_file"),
        (CONFIG, 4, "beat_name_taken"),
        (CONFIG, 5, "employee_not_found"),
        (CONFIG, 6, "employee_inactive"),
        (CONFIG, 7, "owner_not_sales_person"),
        (CONFIG, 8, "geo_scope_not_assigned"),
        (CONFIG, 9, "unknown_zone"),
        (CONFIG, 10, "district_not_in_state"),
        (CONFIG, 11, "zone_not_assigned"),
        (CONFIG, 11, "state_not_assigned"),
        (CONFIG, 11, "district_not_assigned"),
        (CONFIG, 12, "frequency_incomplete"),
        (CONFIG, 13, "invalid_value"),
        (CONFIG, 14, "invalid_value"),
        (CONFIG, 15, "no_outlets_selected"),
        (CONFIG, 19, "no_outlets_selected"),  # both of its outlet rows were rejected
        (OUTLETS, 14, "outlet_out_of_scope"),
        (OUTLETS, 15, "outlet_out_of_scope"),
        (OUTLETS, 16, "outlet_already_on_beat"),
        (OUTLETS, 17, "unknown_beat"),
        (OUTLETS, 18, "duplicate_in_file"),
        (OUTLETS, 19, "duplicate_in_file"),
        (OUTLETS, 20, "invalid_value"),
    }
    assert _beat_count(db_session) == before


def test_category_filter_applies_only_when_given(
    db_session: Session, api_client: TestClient, humbee: FakeHumbee
) -> None:
    admin, south, _ = _setup(db_session, api_client, humbee)
    humbee.add_outlet("C1", district_id="100", shop_category_id="CATEGORY_D")

    rejected = _upload(admin, _xlsx([_beat("Cat", south, cats="CATEGORY_A")], [["Cat", "C1"]]))
    assert _codes(rejected) == {(OUTLETS, 2, "outlet_out_of_scope")}
    accepted = _upload(admin, _xlsx([_beat("Cat", south)], [["Cat", "C1"]]))
    assert accepted.status_code == 201, accepted.text


def test_file_level_errors(db_session: Session, api_client: TestClient, humbee: FakeHumbee) -> None:
    admin, south, _ = _setup(db_session, api_client, humbee)
    header = list(beat_import.CONFIG_COLUMNS.values())
    too_many = [_beat(f"B{i}", south) for i in range(beat_import.MAX_BEATS + 1)]
    cases = [
        (b"not a workbook", 422, "xlsx_invalid"),
        (_xlsx([], [], sheets=(CONFIG,)), 422, "xlsx_missing_sheet"),
        (_xlsx([], []), 422, "xlsx_empty"),
        (_xlsx([], [], config_header=header[:-1]), 422, "xlsx_missing_columns"),
        (_xlsx([], [], config_header=[*header, "Notes"]), 422, "xlsx_unknown_columns"),
        (_xlsx([], [], config_header=[*header, "Beat Name"]), 422, "xlsx_duplicate_columns"),
        (_xlsx(too_many, []), 422, "xlsx_too_many_rows"),
        (b"x" * (beat_import.MAX_BYTES + 1), 413, "file_too_large"),
    ]
    for data, status, code in cases:
        response = _upload(admin, data)
        assert (response.status_code, error_code(response)) == (status, code), code


def test_dry_run_and_idempotency(db_session: Session, api_client: TestClient, humbee: FakeHumbee) -> None:
    admin, south, _ = _setup(db_session, api_client, humbee)
    humbee.add_outlet("D1", district_id="100")
    humbee.add_outlet("D2", district_id="101")
    data = _xlsx([_beat("Dry", south)], [["Dry", "D1"]])
    before = _beat_count(db_session)

    preview = _upload(admin, data, dry_run=True, key=None)
    assert preview.status_code == 200, preview.text
    assert preview.json()["dry_run"] is True and preview.json()["beats"][0]["id"] is None
    assert _beat_count(db_session) == before

    key = generate_ulid()
    first = _upload(admin, data, key=key)
    replay = _upload(admin, data, key=key)
    assert first.status_code == replay.status_code == 201, first.text
    assert replay.json() == first.json()
    assert _beat_count(db_session) == before + 1

    other = _xlsx([_beat("Other", south, districts="101")], [["Other", "D2"]])
    conflict = _upload(admin, other, key=key)
    assert (conflict.status_code, error_code(conflict)) == (409, "idempotency_conflict")
    missing = _upload(admin, other, key=None)
    assert (missing.status_code, error_code(missing)) == (422, "idempotency_key_required")


def test_template_parses_cleanly(db_session: Session, api_client: TestClient, humbee: FakeHumbee) -> None:
    admin, _, _ = _setup(db_session, api_client, humbee)
    template = admin.get(TEMPLATE)
    assert template.status_code == 200
    assert template.headers["content-type"] == XLSX

    beats, outlet_rows, errors = beat_import.parse_workbook(template.content)
    assert errors == [] and outlet_rows == 3
    assert [(b.name, b.outlet_refs) for b in beats] == [
        ("Indiranagar Mon-Thu", ["1001", "1002"]),
        ("Mysuru Fortnightly", ["2001"]),
    ]

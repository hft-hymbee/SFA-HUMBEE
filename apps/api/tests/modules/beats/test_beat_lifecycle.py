from __future__ import annotations

from typing import Any

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.fakes.humbee import FakeHumbee
from tests.fixtures import seed
from tests.fixtures.auth import Authed, login
from tests.fixtures.flows import assign_districts, error_code

from humbee_sfa.modules.approvals.models import Request
from humbee_sfa.modules.beats.models.beat import Beat
from humbee_sfa.modules.beats.models.beat_edit_request import BeatEditRequest
from humbee_sfa.modules.beats.models.beat_version import BeatVersion

WEEKLY_MON_THU = {"frequency": "weekly", "visit_days": [1, 4], "week_cycle": []}


def _geo(*districts: str) -> dict[str, Any]:
    return {"zones": ["1"], "states": ["10"], "districts": list(districts), "cats": []}


def _draft(owner: Authed, *, code: str, outlets: list[str], districts: tuple[str, ...] = ("100",)) -> str:
    created = owner.post("/api/v1/beats", {})
    assert created.status_code == 201, created.text
    beat_id = created.json()["id"]
    patched = owner.patch(
        f"/api/v1/beats/{beat_id}/draft",
        {"display_name": f"Beat {code}", "code": code, "geo_scope": _geo(*districts), "frequency": WEEKLY_MON_THU},
    )
    assert patched.status_code == 200, patched.text
    placed = owner.put(f"/api/v1/beats/{beat_id}/draft/outlets", {"outlet_refs": outlets})
    assert placed.status_code == 200, placed.text
    return beat_id


def _submitted(owner: Authed, *, code: str, outlets: list[str]) -> tuple[str, str]:
    beat_id = _draft(owner, code=code, outlets=outlets)
    submitted = owner.post(f"/api/v1/beats/{beat_id}/submit")
    assert submitted.status_code == 202, submitted.text
    return beat_id, submitted.json()["approval_request_id"]


def _team(db: Session, api_client: TestClient, humbee: FakeHumbee) -> tuple[Authed, Authed, Authed]:
    manager = seed.employee(db, "manager")
    sales_person = seed.employee(db, "sales_person", manager=manager)
    admin = login(api_client, seed.employee(db, "admin"))
    assign_districts(admin, sales_person, humbee, "100")
    return admin, login(api_client, manager), login(api_client, sales_person)


def _row(db: Session, model: type, row_id: str) -> Any:
    return db.get(model, row_id, populate_existing=True)


def test_create_submit_and_approve(db_session: Session, api_client: TestClient, humbee: FakeHumbee) -> None:
    for outlet_id in ("O1", "O2", "O3"):
        humbee.add_outlet(outlet_id, district_id="100")
    _, manager, sp = _team(db_session, api_client, humbee)

    created = sp.post("/api/v1/beats", {})
    assert created.status_code == 201, created.text
    beat_id = created.json()["id"]
    assert created.json()["lifecycle_state"] == "draft"

    def submit() -> httpx.Response:
        return sp.post(f"/api/v1/beats/{beat_id}/submit")

    unnamed = submit()
    assert (unnamed.status_code, error_code(unnamed)) == (422, "beat_not_named")

    named = sp.patch(
        f"/api/v1/beats/{beat_id}/draft",
        {"display_name": "Indiranagar Mon/Thu", "code": "BLR-IND-01", "geo_scope": _geo("100")},
    )
    assert named.status_code == 200, named.text
    no_outlets = submit()
    assert (no_outlets.status_code, error_code(no_outlets)) == (422, "no_outlets_selected")

    placed = sp.put(f"/api/v1/beats/{beat_id}/draft/outlets", {"outlet_refs": ["O1", "O2", "O3"]})
    assert placed.status_code == 200, placed.text
    assert placed.json()["outlet_count"] == 3
    no_days = submit()
    assert (no_days.status_code, error_code(no_days)) == (422, "frequency_incomplete")

    scheduled = sp.patch(f"/api/v1/beats/{beat_id}/draft", {"frequency": WEEKLY_MON_THU})
    assert scheduled.status_code == 200, scheduled.text
    submitted = submit()
    assert submitted.status_code == 202, submitted.text
    assert submitted.json()["lifecycle_state"] == "pending_approval"
    approval_id = submitted.json()["approval_request_id"]
    assert _row(db_session, Request, approval_id).assigned_approver_id == manager.employee.id

    locked = sp.patch(f"/api/v1/beats/{beat_id}/draft", {"display_name": "Renamed"})
    assert (locked.status_code, error_code(locked)) == (409, "draft_locked")

    approved = manager.post(f"/api/v1/approvals/{approval_id}/approve", {})
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    detail = sp.get(f"/api/v1/beats/{beat_id}")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert (body["lifecycle_state"], body["activation_state"], body["display_status"]) == ("approved", "active", "active")
    assert (body["code"], body["display_name"]) == ("BLR-IND-01", "Indiranagar Mon/Thu")
    assert body["version_state"] == "approved"
    assert body["frequency"] == WEEKLY_MON_THU
    assert body["outlet_count"] == 3
    assert sorted(outlet["outlet_ref"] for outlet in body["outlets"]) == ["O1", "O2", "O3"]
    beat = _row(db_session, Beat, beat_id)
    assert (beat.current_version_id, beat.draft_version_id) == (body["version_id"], None)


def test_reject_releases_and_withdraw_reopens(db_session: Session, api_client: TestClient, humbee: FakeHumbee) -> None:
    humbee.add_outlet("O1", district_id="100")
    humbee.add_outlet("O2", district_id="100")
    _, manager, sp = _team(db_session, api_client, humbee)

    rejected_id, rejected_approval = _submitted(sp, code="BLR-01", outlets=["O1"])
    blank = manager.post(f"/api/v1/approvals/{rejected_approval}/reject", {"reason": "   "})
    assert (blank.status_code, error_code(blank)) == (422, "reason_required")
    rejected = manager.post(f"/api/v1/approvals/{rejected_approval}/reject", {"reason": "Overlaps Koramangala"})
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"

    beat = _row(db_session, Beat, rejected_id)
    assert (beat.lifecycle_state, beat.is_active, beat.code, beat.draft_version_id) == ("rejected", False, rejected_id, None)
    assert sp.get(f"/api/v1/beats/{rejected_id}").status_code == 404

    second_id, second_approval = _submitted(sp, code="BLR-01", outlets=["O1"])
    withdrawn = sp.post(f"/api/v1/approvals/{second_approval}/withdraw", {})
    assert withdrawn.status_code == 200, withdrawn.text
    assert withdrawn.json()["status"] == "withdrawn"

    draft = sp.get(f"/api/v1/beats/{second_id}/draft")
    assert draft.status_code == 200, draft.text
    assert (draft.json()["lifecycle_state"], draft.json()["version_state"]) == ("draft", "draft")
    edited = sp.put(f"/api/v1/beats/{second_id}/draft/outlets", {"outlet_refs": ["O1", "O2"]})
    assert edited.status_code == 200, edited.text
    assert edited.json()["outlet_count"] == 2
    resubmitted = sp.post(f"/api/v1/beats/{second_id}/submit")
    assert resubmitted.status_code == 202, resubmitted.text
    assert resubmitted.json()["approval_request_id"] != second_approval


def test_outlet_exclusivity_and_scope(db_session: Session, api_client: TestClient, humbee: FakeHumbee) -> None:
    humbee.add_outlet("O1", district_id="100")
    humbee.add_outlet("O2", district_id="100")
    humbee.add_outlet("M1", district_id="101")
    _, _, sp = _team(db_session, api_client, humbee)

    holder_id = _draft(sp, code="BLR-01", outlets=["O1"])
    contender_id = _draft(sp, code="BLR-02", outlets=["O1", "O2"])
    assert sp.post(f"/api/v1/beats/{holder_id}/submit").status_code == 202

    clash = sp.post(f"/api/v1/beats/{contender_id}/submit")
    assert (clash.status_code, error_code(clash)) == (409, "outlet_already_on_beat")
    assert clash.json()["error"]["details"] == {"outlets": ["O1"]}
    re_add = sp.put(f"/api/v1/beats/{contender_id}/draft/outlets", {"outlet_refs": ["O1", "O2"]})
    assert (re_add.status_code, error_code(re_add)) == (409, "outlet_already_on_beat")

    foreign = sp.put(f"/api/v1/beats/{contender_id}/draft/outlets", {"outlet_refs": ["O2", "M1"]})
    assert (foreign.status_code, error_code(foreign)) == (422, "outlet_out_of_scope")
    assert foreign.json()["error"]["details"] == {"outlets": ["M1"]}

    narrowed = sp.put(f"/api/v1/beats/{contender_id}/draft/outlets", {"outlet_refs": ["O2"]})
    assert narrowed.status_code == 200, narrowed.text
    assert sp.post(f"/api/v1/beats/{contender_id}/submit").status_code == 202


def test_edit_request_and_deactivation(db_session: Session, api_client: TestClient, humbee: FakeHumbee) -> None:
    for outlet_id in ("O1", "O2", "O3"):
        humbee.add_outlet(outlet_id, district_id="100")
    admin, manager, sp = _team(db_session, api_client, humbee)
    beat_id, approval_id = _submitted(sp, code="BLR-01", outlets=["O1", "O2"])
    assert manager.post(f"/api/v1/approvals/{approval_id}/approve", {}).status_code == 200
    base_version_id = _row(db_session, Beat, beat_id).current_version_id

    branch = sp.post(f"/api/v1/beats/{beat_id}/edit-requests")
    assert branch.status_code == 200, branch.text
    proposed_version_id = branch.json()["proposed_version_id"]
    assert branch.json()["base_version_id"] == base_version_id
    changed = sp.put(f"/api/v1/beats/{beat_id}/draft/outlets", {"outlet_refs": ["O2", "O3"]})
    assert changed.status_code == 200, changed.text
    submitted = sp.post(f"/api/v1/beats/{beat_id}/edit-requests/submit")
    assert submitted.status_code == 202, submitted.text

    second = sp.post(f"/api/v1/beats/{beat_id}/edit-requests")
    assert (second.status_code, error_code(second)) == (409, "edit_already_pending")

    live = sp.get(f"/api/v1/beats/{beat_id}").json()
    assert live["display_status"] == "edit_pending"
    assert sorted(outlet["outlet_ref"] for outlet in live["outlets"]) == ["O1", "O2"]
    edit_approval_id = live["pending_edit"]["approval_request_id"]
    outlet_diff = next(line for line in live["pending_edit"]["diff"] if line["field"] == "outlets")
    assert [o["outlet_ref"] for o in outlet_diff["added"]] == ["O3"]
    assert [o["outlet_ref"] for o in outlet_diff["removed"]] == ["O1"]

    assert manager.post(f"/api/v1/approvals/{edit_approval_id}/approve", {}).status_code == 200
    applied = sp.get(f"/api/v1/beats/{beat_id}").json()
    assert (applied["version_id"], applied["version_state"], applied["display_status"]) == (proposed_version_id, "approved", "active")
    assert sorted(outlet["outlet_ref"] for outlet in applied["outlets"]) == ["O2", "O3"]
    assert applied["pending_edit"] is None
    assert _row(db_session, BeatVersion, base_version_id).state == "superseded"

    assert sp.post(f"/api/v1/beats/{beat_id}/edit-requests").status_code == 200
    assert sp.patch(f"/api/v1/beats/{beat_id}/draft", {"display_name": "Indiranagar East"}).status_code == 200
    pending = sp.post(f"/api/v1/beats/{beat_id}/edit-requests/submit")
    assert pending.status_code == 202, pending.text
    pending_approval_id = sp.get(f"/api/v1/beats/{beat_id}").json()["pending_edit"]["approval_request_id"]
    pending_version_id = _row(db_session, Beat, beat_id).draft_version_id

    deactivated = admin.post(f"/api/v1/beats/{beat_id}/deactivate", {"reason": "Territory merged"})
    assert deactivated.status_code == 200, deactivated.text
    assert (deactivated.json()["display_status"], deactivated.json()["deactivation_reason"]) == ("inactive", "Territory merged")
    assert deactivated.json()["pending_edit"] is None
    assert _row(db_session, Request, pending_approval_id).status == "withdrawn"
    assert _row(db_session, BeatVersion, pending_version_id).state == "withdrawn"
    edit_request = db_session.execute(
        select(BeatEditRequest).where(BeatEditRequest.proposed_version_id == pending_version_id)
    ).scalar_one()
    assert edit_request.state == "withdrawn"
    late = manager.post(f"/api/v1/approvals/{pending_approval_id}/approve", {})
    assert (late.status_code, error_code(late)) == (409, "approval_already_decided")

    reactivated = admin.post(f"/api/v1/beats/{beat_id}/reactivate")
    assert reactivated.status_code == 200, reactivated.text
    body = reactivated.json()
    assert (body["activation_state"], body["display_status"], body["display_name"]) == ("active", "active", "Beat BLR-01")
    assert (body["deactivation_reason"], body["deactivated_at"]) == (None, None)


def test_top_of_hierarchy_submissions_approve_immediately(
    db_session: Session, api_client: TestClient, humbee: FakeHumbee
) -> None:
    humbee.add_outlet("O1", district_id="100")
    humbee.add_outlet("O2", district_id="100")
    admin = login(api_client, seed.employee(db_session, "admin"))
    root_manager = seed.employee(db_session, "manager")
    root_sales_person = seed.employee(db_session, "sales_person")
    assign_districts(admin, root_manager, humbee, "100")
    assign_districts(admin, root_sales_person, humbee, "100")

    manager = login(api_client, root_manager)
    own_id = _draft(manager, code="MGR-01", outlets=["O1"])
    own = manager.post(f"/api/v1/beats/{own_id}/submit")
    assert own.status_code == 200, own.text
    assert (own.json()["lifecycle_state"], own.json()["version_state"], own.json()["approval_request_id"]) == ("approved", "approved", None)
    assert db_session.execute(select(Request).where(Request.subject_id == own_id)).first() is None

    sp = login(api_client, root_sales_person)
    beat_id = _draft(sp, code="SP-01", outlets=["O2"])
    submitted = sp.post(f"/api/v1/beats/{beat_id}/submit")
    assert submitted.status_code == 202, submitted.text
    assert (submitted.json()["lifecycle_state"], submitted.json()["version_state"]) == ("approved", "approved")
    request = _row(db_session, Request, submitted.json()["approval_request_id"])
    assert (request.status, request.routing_reason, request.assigned_approver_id) == ("auto_approved", "auto_top_of_hierarchy", None)
    assert _row(db_session, Beat, beat_id).current_version_id == submitted.json()["version_id"]

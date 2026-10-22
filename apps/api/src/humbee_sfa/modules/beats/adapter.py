"""`BeatCreateAdapter` / `BeatEditAdapter` — beats' implementation of the M06
`ApprovalSubjectAdapter` contract for `beat_create` and `beat_edit` (M07 §3a.2 transitions #3–#12).

Both use the **beat id** as `subject_id` — not the version or edit-request id — because
`deep_link()`/`notification()` get no `session` (M06 contract) and S-BEAT5 is the one screen either
outcome lands on. At most one pending version and one pending edit request can exist per beat at a
time (`uq_beats_versions_one_pending`, `uq_beats_edit_one_pending`), so this is unambiguous.

These callbacks run **inside** the engine's decision transaction on its own session (R-AP-16): they
must never commit, roll back, or open a session of their own — exactly the `LeaveAdapter` contract.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.modules.approvals.contracts import (
    Actor,
    ApprovalAdvisory,
    ApprovalStatus,
    DeepLink,
    EditableField,
    EditResult,
    NotificationSpec,
    SubjectDetailBlock,
    SubjectDetailBlocks,
    SubjectEditRejected,
    SubjectEvent,
    SubjectSummary,
    SubjectType,
)
from humbee_sfa.modules.approvals.models import Request
from humbee_sfa.modules.beats import repository
from humbee_sfa.modules.beats.models.beat import Beat
from humbee_sfa.modules.beats.models.beat_edit_request import BeatEditRequest
from humbee_sfa.modules.beats.models.beat_version import BeatVersion
from humbee_sfa.modules.org import service as org_service
from humbee_sfa.modules.outlets.service import OutletReadService

STREAM = "beats"
AGGREGATE_BEAT = "beat"

_CREATE_TITLES: dict[str, str] = {
    ApprovalStatus.APPROVED: "Beat approved",
    ApprovalStatus.APPROVED_WITH_EDITS: "Beat approved",
    ApprovalStatus.AUTO_APPROVED: "Beat auto-approved",
    ApprovalStatus.REJECTED: "Beat rejected",
    ApprovalStatus.WITHDRAWN: "Beat submission withdrawn",
}
_EDIT_TITLES: dict[str, str] = {
    ApprovalStatus.APPROVED: "Beat edit approved",
    ApprovalStatus.APPROVED_WITH_EDITS: "Beat edit approved",
    ApprovalStatus.AUTO_APPROVED: "Beat edit auto-approved",
    ApprovalStatus.REJECTED: "Beat edit rejected",
    ApprovalStatus.WITHDRAWN: "Beat edit withdrawn",
}


def _frequency_label(freq: dict[str, Any]) -> str:
    label = str(freq.get("frequency") or "").capitalize()
    days = len(freq.get("visit_days") or [])
    return f"{label} ({days} day/wk)" if days else label


def _beat(session: Session, *, tenant_id: str, beat_id: str) -> Beat:
    beat = repository.get_beat_by_id(session, tenant_id=tenant_id, beat_id=beat_id)
    if beat is None:
        raise ApiError(404, "beat_not_found", "Beat was not found.")
    return beat


def _version(session: Session, *, tenant_id: str, version_id: str | None) -> BeatVersion:
    version = (
        repository.get_version(session, tenant_id=tenant_id, version_id=version_id)
        if version_id
        else None
    )
    if version is None:
        raise ApiError(404, "beat_version_not_found", "Beat version was not found.")
    return version


def _pending_edit(session: Session, *, tenant_id: str, beat_id: str) -> BeatEditRequest:
    edit_request = repository.get_pending_edit_request(session, tenant_id=tenant_id, beat_id=beat_id)
    if edit_request is None:
        raise ApiError(404, "beat_edit_not_found", "Beat edit request was not found.")
    return edit_request


def _event(event_type: str, *, beat_id: str, version_id: str) -> SubjectEvent:
    return SubjectEvent(
        stream=STREAM, event_type=event_type, aggregate_type=AGGREGATE_BEAT, aggregate_id=beat_id,
        payload={"beat_id": beat_id, "version_id": version_id},
    )


def apply_create_approved(
    session: Session, *, tenant_id: str, beat_id: str, approved_at: datetime, approved_by_id: str | None
) -> SubjectEvent:
    beat = _beat(session, tenant_id=tenant_id, beat_id=beat_id)
    version = _version(session, tenant_id=tenant_id, version_id=beat.draft_version_id)
    version.state = "approved"
    version.approved_at = approved_at
    version.approved_by_employee_id = approved_by_id
    beat.lifecycle_state = "approved"
    beat.current_version_id = version.id
    beat.draft_version_id = None
    beat.display_name = version.display_name
    beat.code = version.code
    session.flush()
    return _event("beat_approved", beat_id=beat.id, version_id=version.id)


def apply_edit_approved(
    session: Session, *, tenant_id: str, beat_id: str, approved_at: datetime, approved_by_id: str | None
) -> SubjectEvent:
    """Transition #10 — the proposed version becomes current; the old one is superseded, never
    deleted (R-BEAT-14, R-BEAT-19)."""

    beat = _beat(session, tenant_id=tenant_id, beat_id=beat_id)
    edit_request = _pending_edit(session, tenant_id=tenant_id, beat_id=beat.id)
    current = _version(session, tenant_id=tenant_id, version_id=beat.current_version_id)
    proposed = _version(session, tenant_id=tenant_id, version_id=edit_request.proposed_version_id)
    # `uq_beats_versions_one_approved` is a non-deferrable partial unique index (R-BEAT-15):
    # the old version must stop being `approved` in its own flush before the proposed one
    # becomes `approved`, or the two UPDATEs can be ordered either way within the transaction.
    current.state = "superseded"
    session.flush()
    proposed.state = "approved"
    proposed.approved_at = approved_at
    proposed.approved_by_employee_id = approved_by_id
    beat.current_version_id = proposed.id
    beat.draft_version_id = None
    beat.display_name = proposed.display_name
    beat.code = proposed.code
    repository.resolve_edit_request(
        session, edit_request=edit_request, state="applied", resolved_at=approved_at
    )
    session.flush()
    return _event("beat_version_applied", beat_id=beat.id, version_id=proposed.id)


class BeatCreateAdapter:
    """Transitions #3, #5, #6, #7 — a beat's first-time submission."""

    subject_type = SubjectType.BEAT_CREATE

    def summary(self, session: Session, *, subject_id: str, viewer: Actor) -> SubjectSummary:
        beat = _beat(session, tenant_id=viewer.tenant_id, beat_id=subject_id)
        version = _version(session, tenant_id=viewer.tenant_id, version_id=beat.draft_version_id)
        owner = org_service.get_employee(
            session, tenant_id=viewer.tenant_id, employee_id=beat.owner_employee_id
        )
        return SubjectSummary(
            title=f"Beat: {version.display_name}",
            subtitle=(
                f"{owner.full_name} · {version.outlet_count} outlets · "
                f"{_frequency_label(version.frequency)}"
            ),
            icon_key="Calendar",
            requester_id=beat.owner_employee_id,
        )

    def detail(self, session: Session, *, subject_id: str, viewer: Actor) -> SubjectDetailBlocks:
        beat = repository.get_beat_by_id(session, tenant_id=viewer.tenant_id, beat_id=subject_id)
        if beat is None:
            return SubjectDetailBlocks(blocks=())
        version = _version(
            session, tenant_id=viewer.tenant_id,
            version_id=beat.draft_version_id or beat.current_version_id,
        )
        memberships = repository.list_memberships_for_versions(session, version_ids=[version.id])
        # Local projection reads only, never Humbee — the same call `beats/service.py` already
        # makes for this version, so listing outlets here costs nothing extra.
        outlets = OutletReadService(session).get_projected_outlets(
            tenant_id=viewer.tenant_id,
            outlet_ids=[membership.outlet_id for membership in memberships],
            ids_are_local=True,
        )
        return SubjectDetailBlocks(
            blocks=(
                SubjectDetailBlock(
                    kind="key_values", label="Beat",
                    payload={
                        "Code": version.code,
                        "Districts": ", ".join(repository.read_districts(version.geo_scope)) or "—",
                        "Shop categories": ", ".join(version.geo_scope.get("cats") or []) or "All categories",
                        "Frequency": _frequency_label(version.frequency),
                        "Visit days": sorted(version.frequency.get("visit_days") or []),
                        "Week cycle": sorted(version.frequency.get("week_cycle") or []),
                        "Outlets": version.outlet_count,
                    },
                ),
                SubjectDetailBlock(
                    kind="line_items", label="Outlets",
                    payload={
                        "lines": [
                            {"label": outlet.record.name, "locality": outlet.record.locality}
                            for outlet in outlets
                        ]
                    },
                ),
            )
        )

    def editable_fields(self, session: Session, *, subject_id: str) -> list[EditableField]:
        return []

    def apply_edit(
        self, session: Session, *, subject_id: str, patch: dict[str, Any], actor: Actor
    ) -> EditResult:
        raise SubjectEditRejected("Beats cannot be edited during approval.")

    def on_approved(self, session: Session, *, request: Request) -> list[SubjectEvent]:
        return [
            apply_create_approved(
                session, tenant_id=request.tenant_id, beat_id=request.subject_id,
                approved_at=request.decided_at, approved_by_id=request.decided_by_id,
            )
        ]

    def on_rejected(
        self, session: Session, *, request: Request, reason: str
    ) -> list[SubjectEvent]:
        beat = _beat(session, tenant_id=request.tenant_id, beat_id=request.subject_id)
        version = _version(session, tenant_id=request.tenant_id, version_id=beat.draft_version_id)
        version.state = "rejected"
        beat.lifecycle_state = "rejected"
        beat.draft_version_id = None
        beat.is_active = False
        beat.deactivated_at = request.decided_at
        beat.deactivated_by = request.decided_by_id
        beat.code = beat.id
        session.flush()
        return [_event("beat_rejected", beat_id=beat.id, version_id=version.id)]

    def on_withdrawn(self, session: Session, *, request: Request) -> list[SubjectEvent]:
        """Transition #7."""

        beat = _beat(session, tenant_id=request.tenant_id, beat_id=request.subject_id)
        version = _version(session, tenant_id=request.tenant_id, version_id=beat.draft_version_id)
        version.state = "draft"
        beat.lifecycle_state = "draft"
        session.flush()
        return [_event("beat_submission_withdrawn", beat_id=beat.id, version_id=version.id)]

    def advisories(self, session: Session, *, subject_id: str) -> list[ApprovalAdvisory]:
        return []

    def notification(
        self, request: Request, outcome: ApprovalStatus, *, occurred_at: datetime
    ) -> NotificationSpec:
        return NotificationSpec(
            kind=str(outcome),
            title=_CREATE_TITLES.get(str(outcome), request.title),
            subtitle=request.title,
            recipient_id=request.requester_id,
            dedupe_key=f"approval:{request.id}:{outcome}",
        )

    def deep_link(self, request: Request, viewer: Actor) -> DeepLink:
        if request.status == ApprovalStatus.REJECTED:
            return DeepLink(target_type="approval_request", target_id=request.id)
        return DeepLink(target_type="beat", target_id=request.subject_id)


class BeatEditAdapter:
    """Transitions #9, #10, #11, #12 — an edit to an already-approved, still-live beat."""

    subject_type = SubjectType.BEAT_EDIT

    def summary(self, session: Session, *, subject_id: str, viewer: Actor) -> SubjectSummary:
        beat = _beat(session, tenant_id=viewer.tenant_id, beat_id=subject_id)
        edit_request = _pending_edit(session, tenant_id=viewer.tenant_id, beat_id=subject_id)
        proposed = _version(
            session, tenant_id=viewer.tenant_id, version_id=edit_request.proposed_version_id
        )
        owner = org_service.get_employee(
            session, tenant_id=viewer.tenant_id, employee_id=beat.owner_employee_id
        )
        return SubjectSummary(
            title=f"Edit: {beat.display_name}",
            subtitle=(
                f"{owner.full_name} · {proposed.outlet_count} outlets · "
                f"{len(edit_request.diff)} change(s)"
            ),
            icon_key="Calendar",
            requester_id=beat.owner_employee_id,
        )

    def detail(self, session: Session, *, subject_id: str, viewer: Actor) -> SubjectDetailBlocks:
        edit_request = repository.get_pending_edit_request(
            session, tenant_id=viewer.tenant_id, beat_id=subject_id
        )
        if edit_request is None:
            return SubjectDetailBlocks(blocks=())
        return SubjectDetailBlocks(
            blocks=(
                SubjectDetailBlock(
                    kind="line_items", label="Requested changes", payload={"diff": edit_request.diff}
                ),
            )
        )

    def editable_fields(self, session: Session, *, subject_id: str) -> list[EditableField]:
        return []

    def apply_edit(
        self, session: Session, *, subject_id: str, patch: dict[str, Any], actor: Actor
    ) -> EditResult:
        raise SubjectEditRejected("Beat edits cannot be edited during approval.")

    def on_approved(self, session: Session, *, request: Request) -> list[SubjectEvent]:
        return [
            apply_edit_approved(
                session, tenant_id=request.tenant_id, beat_id=request.subject_id,
                approved_at=request.decided_at, approved_by_id=request.decided_by_id,
            )
        ]

    def on_rejected(
        self, session: Session, *, request: Request, reason: str
    ) -> list[SubjectEvent]:
        """Transition #11 — `current_version_id` is untouched; the beat keeps running (R-BEAT-14)."""

        beat = _beat(session, tenant_id=request.tenant_id, beat_id=request.subject_id)
        edit_request = _pending_edit(session, tenant_id=request.tenant_id, beat_id=beat.id)
        proposed = _version(
            session, tenant_id=request.tenant_id, version_id=edit_request.proposed_version_id
        )
        proposed.state = "rejected"
        beat.draft_version_id = None
        repository.resolve_edit_request(
            session, edit_request=edit_request, state="rejected", resolved_at=request.decided_at
        )
        session.flush()
        return [_event("beat_edit_rejected", beat_id=beat.id, version_id=proposed.id)]

    def on_withdrawn(self, session: Session, *, request: Request) -> list[SubjectEvent]:
        """Transition #12 — reached either by the SP's own withdraw or by
        `approvals.service.withdraw_for_subject` when Admin deactivates the beat (R-BEAT-28).
        Idempotent: an already-resolved edit (no pending row left) is a no-op."""

        beat = _beat(session, tenant_id=request.tenant_id, beat_id=request.subject_id)
        edit_request = repository.get_pending_edit_request(
            session, tenant_id=request.tenant_id, beat_id=beat.id
        )
        if edit_request is None:
            return []
        proposed = _version(
            session, tenant_id=request.tenant_id, version_id=edit_request.proposed_version_id
        )
        proposed.state = "withdrawn"
        beat.draft_version_id = None
        repository.resolve_edit_request(
            session, edit_request=edit_request, state="withdrawn", resolved_at=request.decided_at
        )
        session.flush()
        return [_event("beat_edit_withdrawn", beat_id=beat.id, version_id=proposed.id)]

    def advisories(self, session: Session, *, subject_id: str) -> list[ApprovalAdvisory]:
        return []

    def notification(
        self, request: Request, outcome: ApprovalStatus, *, occurred_at: datetime
    ) -> NotificationSpec:
        return NotificationSpec(
            kind=str(outcome),
            title=_EDIT_TITLES.get(str(outcome), request.title),
            subtitle=request.title,
            recipient_id=request.requester_id,
            dedupe_key=f"approval:{request.id}:{outcome}",
        )

    def deep_link(self, request: Request, viewer: Actor) -> DeepLink:
        return DeepLink(target_type="beat", target_id=request.subject_id)


__all__ = ["BeatCreateAdapter", "BeatEditAdapter"]

"""`OutletVerificationAdapter` — outlets' implementation of the M06 `ApprovalSubjectAdapter`.

Humbee has no candidate stage and no approver: ON-3 creates a real firm, organization and owner
login immediately. So the approval cannot wrap the Humbee call — it gates it. This adapter is the
only place `OutletOnboardingCandidate.status` moves out of `pending_approval`, and the grant path
makes the Humbee call inline, inside the engine's decision transaction.

That call cannot fail the decision: `submit_candidate_to_humbee` never raises, writing the outcome
onto the candidate instead, so a manager's approval commits whether or not Humbee answered.

Reads use `internal_routing_scope` for the same reason `LeaveAdapter` does: the engine has already
resolved who may see the request, and the deciding actor is the *manager*, whose own row scope does
not cover the sales person's submission.

Routing is the engine's default — the requester's direct manager. M14 R-OUT-14 specifies Admin
instead, and honouring that would mean changing `approvals/routing.py`, not this file; manager
approval is the behaviour asked for and the deviation is recorded in epic 08.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from humbee_sfa.core.clock import SystemClock
from humbee_sfa.core.security import decrypt_phone
from humbee_sfa.core.settings import get_settings
from humbee_sfa.integration.humbee.onboarding import (
    HumbeeError,
    HumbeeOnboardingProvider,
    OnboardingUnavailable,
)
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
from humbee_sfa.modules.outlets import repository
from humbee_sfa.modules.outlets.models import OutletOnboardingCandidate
from humbee_sfa.modules.outlets.service import (
    display_name,
    submit_candidate_to_humbee,
)

STREAM = "outlets"
AGGREGATE_CANDIDATE = "outlet_onboarding_candidate"

CANDIDATE_APPROVED = "outlet_candidate_approved"
CANDIDATE_REJECTED = "outlet_candidate_rejected"
CANDIDATE_WITHDRAWN = "outlet_candidate_withdrawn"

_TITLE_MAX = 120
_SUBTITLE_MAX = 200

_OUTCOME_TITLES: dict[str, str] = {
    ApprovalStatus.APPROVED: "Outlet onboarding approved",
    ApprovalStatus.APPROVED_WITH_EDITS: "Outlet onboarding approved",
    ApprovalStatus.AUTO_APPROVED: "Outlet onboarding auto-approved",
    ApprovalStatus.REJECTED: "Outlet onboarding rejected",
    ApprovalStatus.WITHDRAWN: "Outlet onboarding withdrawn",
}

def _clip(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"


class OutletVerificationAdapter:
    subject_type = SubjectType.OUTLET_VERIFICATION

    # -- rendering ------------------------------------------------------------

    def summary(self, session: Session, *, subject_id: str, viewer: Actor) -> SubjectSummary:
        candidate = repository.require_candidate(
            session, tenant_id=viewer.tenant_id, candidate_id=subject_id
        )
        document = candidate.company_gstin or candidate.pancard_no
        role_count = len(candidate.payload.get("roles", []))
        locality = candidate.payload.get("operational_address", {}).get("pincode") or None
        subtitle = " · ".join(
            part
            for part in (
                document,
                f"{role_count} role{'' if role_count == 1 else 's'}" if role_count else None,
                locality,
            )
            if part
        )
        return SubjectSummary(
            title=_clip(f"Onboard: {display_name(candidate)}", _TITLE_MAX),
            subtitle=_clip(subtitle, _SUBTITLE_MAX),
            icon_key="Store",
            requester_id=candidate.captured_by_employee_id,
            amount_paise=None,  # onboarding a firm carries no money
        )

    def detail(self, session: Session, *, subject_id: str, viewer: Actor) -> SubjectDetailBlocks:
        candidate = repository.require_candidate(
            session, tenant_id=viewer.tenant_id, candidate_id=subject_id
        )
        payload = candidate.payload
        operational = payload.get("operational_address", {})
        registered = payload.get("registered_address", {})
        labels = _display_labels(payload)
        return SubjectDetailBlocks(
            blocks=(
                SubjectDetailBlock(
                    kind="key_values",
                    label="Firm",
                    payload={
                        "Name": display_name(candidate),
                        "GSTIN": candidate.company_gstin or "—",
                        "PAN": candidate.pancard_no or "—",
                        "Owner phone": decrypt_phone(candidate.owner_phone_enc),
                    },
                ),
                SubjectDetailBlock(
                    kind="key_values",
                    label="Registered address",
                    payload=_address_block(registered, labels=labels),
                ),
                SubjectDetailBlock(
                    kind="key_values",
                    label="Operational address",
                    payload=_address_block(operational, labels=labels, include_location=True)
                    | {"Pincode": operational.get("pincode") or "—"},
                ),
                SubjectDetailBlock(
                    kind="line_items",
                    label="Roles requested",
                    payload={
                        "lines": _role_lines(
                            payload.get("roles", []),
                            labels=labels,
                        )
                    },
                ),
                SubjectDetailBlock(
                    kind="line_items",
                    label="Industries requested",
                    payload={"lines": _industry_lines(payload.get("industries", []))},
                ),
            )
        )

    # -- editing --------------------------------------------------------------

    def editable_fields(self, session: Session, *, subject_id: str) -> list[EditableField]:
        # A manager approves or rejects the firm as captured. Editing a GSTIN or an address here
        # would send Humbee something the sales person never saw and the owner never confirmed.
        return []

    def apply_edit(
        self, session: Session, *, subject_id: str, patch: dict[str, Any], actor: Actor
    ) -> EditResult:
        # Unreachable while `editable_fields` is empty; loud rather than silent if that changes.
        raise SubjectEditRejected("An onboarding candidate cannot be edited during approval.")

    # -- outcome callbacks (all inside the engine's decision transaction) -----

    def on_approved(self, session: Session, *, request: Request) -> list[SubjectEvent]:
        """Grant: onboard the firm at Humbee now, and record how far it got.

        `approved` is the intermediate the submission moves off immediately — a committed candidate
        is `submitted` or `submission_failed`, never left at `approved`.
        """

        candidate = self._transition(session, request=request, status="approved")
        if candidate is None:
            return []
        submit_candidate_to_humbee(session, candidate=candidate, clock=SystemClock())
        return [self._event(CANDIDATE_APPROVED, candidate)]

    def on_rejected(self, session: Session, *, request: Request, reason: str) -> list[SubjectEvent]:
        candidate = self._transition(session, request=request, status="rejected")
        if candidate is None:
            return []
        # The document claim is released with the rejection, so another sales person may capture
        # the same firm — that is the partial unique index's `status` predicate doing its job.
        return [self._event(CANDIDATE_REJECTED, candidate, reason=reason or None)]

    def on_withdrawn(self, session: Session, *, request: Request) -> list[SubjectEvent]:
        candidate = self._transition(session, request=request, status="withdrawn")
        if candidate is None:
            return []
        return [self._event(CANDIDATE_WITHDRAWN, candidate)]

    # -- advisory + notification ----------------------------------------------

    def advisories(self, session: Session, *, subject_id: str) -> list[ApprovalAdvisory]:
        candidate = session.get(OutletOnboardingCandidate, subject_id)
        if candidate is None:
            return []
        if candidate.status != "submission_failed" or not candidate.submission_error:
            return []
        return [
            ApprovalAdvisory(
                code="outlet_onboarding_failed",
                severity="warning",
                message=f"Humbee onboarding failed: {candidate.submission_error}",
            )
        ]

    def notification(
        self, request: Request, outcome: ApprovalStatus, *, occurred_at: datetime
    ) -> NotificationSpec:
        return NotificationSpec(
            kind=str(outcome),
            title=_OUTCOME_TITLES.get(str(outcome), request.title),
            subtitle=(
                f"{request.title} · see comment"
                if outcome == ApprovalStatus.REJECTED
                else request.title
            ),
            recipient_id=request.requester_id,
            dedupe_key=f"approval:{request.id}:{outcome}",
        )

    def deep_link(self, request: Request, viewer: Actor) -> DeepLink:
        # The requester tracks the captured candidate; approvers act on the approval request.
        # Neither side links to a Humbee outlet id that may never be minted.
        if viewer.employee_id == request.requester_id:
            return DeepLink(target_type="outlet", target_id=request.subject_id)
        return DeepLink(target_type="approval_request", target_id=request.id)

    # -- internals ------------------------------------------------------------

    @staticmethod
    def _transition(
        session: Session, *, request: Request, status: str
    ) -> OutletOnboardingCandidate | None:
        """Move a still-pending candidate, or report that there is nothing to move.

        `None` rather than an error: `withdraw_for_subject` can fire from a system path, and the
        engine may redeliver an outcome for a candidate that already left `pending_approval`.
        """

        candidate = repository.get_candidate(
            session, tenant_id=request.tenant_id, candidate_id=request.subject_id
        )
        if candidate is None or candidate.status != "pending_approval":
            return None
        candidate.status = status
        candidate.version += 1
        session.flush()
        return candidate

    @staticmethod
    def _event(
        event_type: str, candidate: OutletOnboardingCandidate, *, reason: str | None = None
    ) -> SubjectEvent:
        payload: dict[str, Any] = {
            "candidate_id": candidate.id,
            "captured_by_employee_id": candidate.captured_by_employee_id,
            "status": candidate.status,
            "has_gstin": candidate.company_gstin is not None,
        }
        if reason:
            payload["reason"] = reason
        return SubjectEvent(
            stream=STREAM,
            event_type=event_type,
            aggregate_type=AGGREGATE_CANDIDATE,
            aggregate_id=candidate.id,
            payload=payload,
        )


def _display_labels(payload: dict[str, Any]) -> dict[str, dict[str, str]]:
    labels: dict[str, dict[str, str]] = {
        "states": {},
        "districts": {},
        "locations": {},
        "manufacturers": {},
        "roles": {},
    }
    try:
        provider = HumbeeOnboardingProvider(get_settings())
        labels["states"] = {
            state.state_id: state.state_name
            for state in provider.list_firm_address_states()
        }
        state_ids = {
            address.get("state_id")
            for address in (
                payload.get("registered_address", {}),
                payload.get("operational_address", {}),
            )
            if isinstance(address, dict) and address.get("state_id")
        }
        for state_id in state_ids:
            labels["districts"].update({
                district.district_id: district.district_name
                for district in provider.list_firm_address_districts(state_id=str(state_id))
            })

        operational = payload.get("operational_address", {})
        if isinstance(operational, dict) and operational.get("district_id"):
            options = provider.list_firm_address_options(
                district_id=str(operational["district_id"]),
                pincode=operational.get("pincode"),
                location_id=operational.get("location_id"),
            )
            labels["locations"] = {
                location.location_id: location.location_name
                for location in options.locations
            }

        for manufacturer in provider.list_manufacturer_roles():
            labels["manufacturers"][manufacturer.manufacturer_id] = manufacturer.name
            for role in (*manufacturer.vcp_roles, *manufacturer.influencer_roles):
                labels["roles"][role.role_id] = role.role_name
    except (RuntimeError, HumbeeError, OnboardingUnavailable):
        return labels
    return labels


def _display_value(labels: dict[str, dict[str, str]], bucket: str, value: Any) -> str:
    if value is None:
        return "—"
    key = str(value)
    return labels.get(bucket, {}).get(key) or key


def _address_block(
    address: dict[str, Any],
    *,
    labels: dict[str, dict[str, str]],
    include_location: bool = False,
) -> dict[str, Any]:
    lines = address.get("company_address", {})
    block = {
        "Line 1": lines.get("address_line_1") or "—",
        "Line 2": lines.get("address_line_2") or "—",
        "Line 3": lines.get("address_line_3") or "—",
        "State": _display_value(labels, "states", address.get("state_id")),
        "District": _display_value(labels, "districts", address.get("district_id")),
    }
    if include_location:
        block["Locality"] = _display_value(labels, "locations", address.get("location_id"))
    return block


def _role_lines(
    roles: list[dict[str, Any]],
    *,
    labels: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    lines = []
    for role in roles:
        if not isinstance(role, dict):
            continue
        manufacturer_id = role.get("manufacturer_id")
        lines.append(
            {
                "label": _display_value(labels, "roles", role.get("firm_role_id")),
                "manufacturer": _display_value(labels, "manufacturers", manufacturer_id),
            }
        )
    return lines


def _industry_lines(industries: list[dict[str, Any]]) -> list[dict[str, str]]:
    lines = []
    for industry in industries:
        if not isinstance(industry, dict):
            continue
        lines.append(
            {
                "primary": str(industry.get("primary_industry_name") or "—"),
                "secondary": str(industry.get("secondary_industry") or "—"),
                "role": str(industry.get("role_name") or "—"),
            }
        )
    return lines


__all__ = [
    "CANDIDATE_APPROVED",
    "CANDIDATE_REJECTED",
    "CANDIDATE_WITHDRAWN",
    "OutletVerificationAdapter",
]

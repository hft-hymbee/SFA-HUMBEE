"""`LeaveAdapter` — M12's implementation of the M06 `ApprovalSubjectAdapter` contract (§3.7).

This file is the **only** place `LeaveRequest.status` is written (R-LV-09) and the only place the
balance reservation is converted or released (R-LV-12). Leave has no `approve()`, no state machine
and no decision endpoint of its own (R-LV-01): the three callbacks below run inside M06's decision
transaction, on M06's session, and mirror whatever the engine already decided.

Reads and writes here use `internal_routing_scope` (tenant-only, no actor) on purpose. Visibility
of the approval request was already resolved by the engine before it called us, and the deciding
actor is the *approver*, whose own row scope would not cover the requester's leave.

`LeaveGranted` / `LeaveRejected` / `LeaveWithdrawn` (M12 §10, cross-module interfaces) are returned
as `SubjectEvent`s rather than published here — `ApprovalService._run_callbacks_and_publish` writes
them through `platform/domain_events.py` inside the same transaction.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
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
from humbee_sfa.modules.leave import repository
from humbee_sfa.modules.leave.leave_type import LeaveType
from humbee_sfa.modules.leave.models import LeaveRequest
from humbee_sfa.modules.org import service as org_service
from humbee_sfa.modules.org.scope import internal_routing_scope

STREAM = "leave"
AGGREGATE_REQUEST = "leave_request"

# Named in M12 §10 as `LeaveGranted` / `LeaveRejected` / `LeaveWithdrawn`; snake-cased to match the
# shared domain-event naming convention.
LEAVE_GRANTED = "leave_granted"
LEAVE_REJECTED = "leave_rejected"
LEAVE_WITHDRAWN = "leave_withdrawn"

TYPE_LABELS: dict[LeaveType, str] = {
    LeaveType.CASUAL: "Casual leave",
    LeaveType.SICK: "Sick leave",
    LeaveType.PRIVILEGED: "Privileged leave",
}


def _type_label(leave_type: str) -> str:
    return TYPE_LABELS[LeaveType(leave_type)]

_OUTCOME_TITLES: dict[str, str] = {
    ApprovalStatus.APPROVED: "Leave approved",
    ApprovalStatus.APPROVED_WITH_EDITS: "Leave approved",
    ApprovalStatus.AUTO_APPROVED: "Leave auto-approved",
    ApprovalStatus.REJECTED: "Leave request rejected",
    ApprovalStatus.WITHDRAWN: "Leave request withdrawn",
}


# ---------------------------------------------------------------------------
# Display derivations (M12 §8) — used for the strings M06 denormalises at write time
# ---------------------------------------------------------------------------


def date_range_label(from_date: date, to_date: date) -> str:
    """`"08 Jul"` · `"22–23 Jul"` · `"30 Jul – 02 Aug"` · cross-year appends the year."""

    if from_date == to_date:
        return from_date.strftime("%d %b")
    if from_date.year != to_date.year:
        return f"{from_date.strftime('%d %b %Y')} – {to_date.strftime('%d %b %Y')}"
    if from_date.month == to_date.month:
        return f"{from_date.strftime('%d')}–{to_date.strftime('%d %b')}"
    return f"{from_date.strftime('%d %b')} – {to_date.strftime('%d %b')}"


def day_count_label(day_count: Decimal) -> str:
    if day_count == Decimal("0.5"):
        return "Half day"
    return f"{day_count:g} day" if day_count == 1 else f"{day_count:g} days"


# ---------------------------------------------------------------------------
# The adapter
# ---------------------------------------------------------------------------


class LeaveAdapter:
    subject_type = SubjectType.LEAVE

    # -- rendering ---------------------------------------------------------

    def summary(self, session: Session, *, subject_id: str, viewer: Actor) -> SubjectSummary:
        row = self._row(session, tenant_id=viewer.tenant_id, subject_id=subject_id)
        employee = org_service.get_employee(
            session, tenant_id=viewer.tenant_id, employee_id=row.employee_id
        )
        return SubjectSummary(
            title=f"Leave: {date_range_label(row.from_date, row.to_date)}",
            subtitle=(
                f"{employee.full_name} · {_type_label(row.leave_type)} · "
                f"{day_count_label(row.day_count)}"
            ),
            icon_key="Calendar",
            requester_id=row.employee_id,
            amount_paise=None,  # leave has no money
        )

    def detail(self, session: Session, *, subject_id: str, viewer: Actor) -> SubjectDetailBlocks:
        row = self._row(session, tenant_id=viewer.tenant_id, subject_id=subject_id)
        return SubjectDetailBlocks(
            blocks=(
                SubjectDetailBlock(
                    kind="date_range",
                    label="Dates",
                    payload={
                        "from_date": row.from_date.isoformat(),
                        "to_date": row.to_date.isoformat(),
                        "day_count": float(row.day_count),
                        "is_half_day": row.is_half_day,
                    },
                ),
                SubjectDetailBlock(
                    kind="key_values",
                    label="Leave",
                    payload={
                        "Type": _type_label(row.leave_type),
                        "Reason": row.reason or "—",
                        "Balance before": float(row.balance_before),
                        "Balance after": float(row.balance_after_projected),
                    },
                ),
            )
        )

    # -- editing -----------------------------------------------------------

    def editable_fields(self, session: Session, *, subject_id: str) -> list[EditableField]:
        # v1 has no partial approval of leave (M12 §3.7), so S-AP2 hides the Edit button (R-AP-13).
        return []

    def apply_edit(
        self, session: Session, *, subject_id: str, patch: dict[str, Any], actor: Actor
    ) -> EditResult:
        # Unreachable: the engine calls `policies.require_editable([])` first. Present so the
        # Protocol is satisfied structurally, and so a future edit path fails loudly, not silently.
        raise SubjectEditRejected("Leave requests cannot be edited during approval.")

    # -- outcome callbacks (all run inside M06's decision transaction) -----

    def on_approved(self, session: Session, *, request: Request) -> list[SubjectEvent]:
        """Grant: mirror the status and convert the reservation into consumption (R-LV-12)."""

        row = self._mirror(session, request=request)
        self._move_balance(
            session,
            row=row,
            tenant_id=request.tenant_id,
            consumed_delta=row.day_count,
            pending_delta=-row.day_count,
        )
        return [self._event(LEAVE_GRANTED, row)]

    def on_rejected(
        self, session: Session, *, request: Request, reason: str
    ) -> list[SubjectEvent]:
        """Rejection: release the reservation, never debit."""

        row = self._mirror(session, request=request, decision_note=reason or None)
        self._move_balance(
            session, row=row, tenant_id=request.tenant_id, pending_delta=-row.day_count
        )
        return [self._event(LEAVE_REJECTED, row)]

    def on_withdrawn(self, session: Session, *, request: Request) -> list[SubjectEvent]:
        """Withdrawal (R-LV-13): release the reservation, never debit."""

        row = self._mirror(session, request=request)
        self._move_balance(
            session, row=row, tenant_id=request.tenant_id, pending_delta=-row.day_count
        )
        return [self._event(LEAVE_WITHDRAWN, row)]

    # -- advisory + notification -------------------------------------------

    def advisories(self, session: Session, *, subject_id: str) -> list[ApprovalAdvisory]:
        # No leave advisory is specified yet (M12 §12 Q5 is open). The hook stays empty rather than
        # inventing copy the approver would learn to ignore.
        return []

    def notification(
        self, request: Request, outcome: ApprovalStatus, *, occurred_at: datetime
    ) -> NotificationSpec:
        """Materialised outcome copy (R-AP-22). No `session` here by contract, so the strings come
        from the request's own denormalised `title` (`"Leave: 22–23 Jul"`), which M06 wrote from
        `summary()` at submission. Deep-link fields stay unset so the engine resolves them per
        recipient through `deep_link()`."""

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
        # The requester lands on their own leave row (S-LV2); anyone else on the request (S-AP2).
        if viewer.employee_id == request.requester_id:
            return DeepLink(target_type="leave", target_id=request.subject_id)
        return DeepLink(target_type="approval_request", target_id=request.id)

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _row(session: Session, *, tenant_id: str, subject_id: str) -> LeaveRequest:
        row = repository.get_request(
            session, scope=internal_routing_scope(tenant_id), leave_request_id=subject_id
        )
        if row is None:
            raise ApiError(404, "leave_request_not_found", "Leave request was not found.")
        return row

    def _mirror(
        self, session: Session, *, request: Request, decision_note: str | None = None
    ) -> LeaveRequest:
        """The single write path for `LeaveRequest.status` in the whole codebase (R-LV-09).

        The status mirrored is `request.status` verbatim — the engine has already applied its own
        outcome by the time it calls us, so `auto_approved` and `approved` land as themselves and
        S-LV3's separate filter buckets stay implementable (M12 §3.4).
        """

        row = self._row(session, tenant_id=request.tenant_id, subject_id=request.subject_id)
        repository.set_request_status(
            session,
            scope=internal_routing_scope(request.tenant_id),
            request=row,
            status=request.status,
            decided_at=request.decided_at,
            decision_note=decision_note or request.decision_note,
        )
        return row

    @staticmethod
    def _move_balance(
        session: Session,
        *,
        row: LeaveRequest,
        tenant_id: str,
        consumed_delta: Decimal = Decimal(0),
        pending_delta: Decimal = Decimal(0),
    ) -> None:
        scope = internal_routing_scope(tenant_id)
        balance = repository.get_balance(
            session,
            scope=scope,
            employee_id=row.employee_id,
            leave_type=row.leave_type,
            # §12 Q14: a range straddling the year boundary is attributed by `from_date` in v1,
            # which is the same attribution submission used to reserve.
            period_year=row.from_date.year,
        )
        if balance is None:
            # Unreachable: submission creates the row before it reserves. Raising keeps a silently
            # un-debited grant from becoming a reachable state (M12 §11.3).
            raise ApiError(
                409,
                "leave_balance_missing",
                "No leave balance exists for this request's type and period.",
            )
        repository.apply_balance_delta(
            session,
            scope=scope,
            balance=balance,
            consumed_delta=consumed_delta,
            pending_delta=pending_delta,
        )

    @staticmethod
    def _event(event_type: str, row: LeaveRequest) -> SubjectEvent:
        return SubjectEvent(
            stream=STREAM,
            event_type=event_type,
            aggregate_type=AGGREGATE_REQUEST,
            aggregate_id=row.id,
            payload={
                "leave_request_id": row.id,
                "employee_id": row.employee_id,
                "leave_type": row.leave_type,
                "from_date": row.from_date.isoformat(),
                "to_date": row.to_date.isoformat(),
                "day_count": float(row.day_count),
                "is_half_day": row.is_half_day,
                "status": row.status,
            },
        )


__all__ = [
    "LEAVE_GRANTED",
    "LEAVE_REJECTED",
    "LEAVE_WITHDRAWN",
    "TYPE_LABELS",
    "LeaveAdapter",
    "date_range_label",
    "day_count_label",
]

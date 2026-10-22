"""Who may *act* on an approval request.

This is not scope. `org.scope.ScopeResolver` decides the actor's organisational boundary. The checks
below decide what they can **do** inside it: assigned approvers may decide their requests, and Admin
may decide beat and outlet-verification requests even when they are not assigned. Admin is
explicitly excluded from leave approvals.
"""

from __future__ import annotations

from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.modules.approvals.contracts import (
    TERMINAL_STATUSES,
    Actor,
    ApprovalStatus,
    EditableField,
    SubjectType,
)
from humbee_sfa.modules.approvals.models import Request

_ADMIN_ROLE = "admin"
_ADMIN_OVERRIDE_SUBJECT_TYPES = frozenset(
    {
        SubjectType.BEAT_CREATE.value,
        SubjectType.BEAT_EDIT.value,
        SubjectType.OUTLET_VERIFICATION.value,
    }
)
_ADMIN_EXCLUDED_SUBJECT_TYPES = frozenset({SubjectType.LEAVE.value})


def _is_admin(actor: Actor) -> bool:
    return actor.role.strip().casefold() == _ADMIN_ROLE


def additional_decision_subject_types(actor: Actor) -> frozenset[str]:
    """Subject types this actor may decide without being the assigned approver."""

    return _ADMIN_OVERRIDE_SUBJECT_TYPES if _is_admin(actor) else frozenset()


def excluded_subject_types(actor: Actor) -> frozenset[str]:
    """Subject types this actor may not read or decide through approvals."""

    return _ADMIN_EXCLUDED_SUBJECT_TYPES if _is_admin(actor) else frozenset()


def _has_decision_rights(actor: Actor, request: Request) -> bool:
    if request.subject_type in excluded_subject_types(actor):
        return False
    return request.assigned_approver_id == actor.employee_id or (
        request.subject_type in additional_decision_subject_types(actor)
    )


def is_terminal(request: Request) -> bool:
    return request.status in TERMINAL_STATUSES


def can_decide(actor: Actor, request: Request) -> bool:
    """Assigned approver, plus Admin for beat and outlet-verification requests, while pending."""

    return request.status == ApprovalStatus.PENDING and _has_decision_rights(actor, request)


def can_withdraw(actor: Actor, request: Request) -> bool:
    """Only the requester, and only while pending."""

    return request.status == ApprovalStatus.PENDING and request.requester_id == actor.employee_id


def require_decision_rights(actor: Actor, request: Request) -> None:
    """Decision-rights check first, then already-decided.

    Order matters: a non-approver must not learn a request's decision state by probing an endpoint,
    so they get `403` whatever the status. A permitted actor gets the actionable `409`.
    """

    if not _has_decision_rights(actor, request):
        raise ApiError(
            403,
            "not_the_assigned_approver",
            "Only the assigned approver can decide this request, except Admin may decide beat and outlet approvals.",
        )
    if is_terminal(request):
        raise ApiError(
            409,
            "approval_already_decided",
            f"This request was already {request.status}.",
            details={
                "status": request.status,
                "decided_by_id": request.decided_by_id,
                "decided_at": request.decided_at.isoformat() if request.decided_at else None,
            },
        )


def require_withdraw_rights(actor: Actor, request: Request) -> None:
    if request.requester_id != actor.employee_id:
        raise ApiError(403, "not_the_requester", "Only the requester can withdraw this request.")
    if is_terminal(request):
        raise ApiError(
            409,
            "approval_already_decided",
            f"This request was already {request.status}.",
            details={"status": request.status, "decided_by_id": request.decided_by_id},
        )


def require_editable(fields: list[EditableField]) -> None:
    """A subject type that declares no editable fields cannot be edit-and-approved."""

    if not fields:
        raise ApiError(
            422, "not_editable", "This request type cannot be edited before approval."
        )


def require_reason(reason: str | None) -> str:
    """Rejection requires a non-empty reason after trimming, whatever the UI does."""

    trimmed = (reason or "").strip()
    if not trimmed:
        raise ApiError(422, "reason_required", "Add a reason — the requester will see this.")
    return trimmed


def require_subject_version(request: Request, if_match: int | None, *, required: bool) -> None:
    """`If-Match: <subject_version>` guards edit-and-approve; a mismatch means a
    concurrent edit moved the subject under the client."""

    if if_match is None:
        if required:
            raise ApiError(
                428,
                "if_match_required",
                "Send If-Match with the subject_version you are deciding on.",
            )
        return
    if if_match != request.subject_version:
        raise ApiError(
            412,
            "subject_changed",
            "This request changed since you loaded it. Reload and try again.",
            details={"subject_version": request.subject_version},
        )

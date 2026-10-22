"""Approvals persistence. Thin, no business decisions.

Two kinds of function live here, and the difference is deliberate:

* **Actor-facing reads** take a resolved `ScopeContext` from `org.scope` (the inbox, my requests,
  the detail read). Scope is applied here and nowhere else, so a new endpoint cannot forget it.
  Approval requests are activity data, so callers resolve `OrgResource.ACTIVITY_DATA`.
* **Engine operations** — insert, row lock, status write, decision append — take `tenant_id`
  only. These have no human actor to scope against: the engine owns
  `approvals_requests`, and *who may act* is decided by `policies.can_decide` before they are
  reached (scope decides what you can see, the policy decides what you can act on).
  Naming them `tenant_id` rather than passing a fake scope keeps each call site greppable.

Visibility predicate for the actor-facing reads: the scope predicate applies to
`requester_id` — "requests raised inside my tree" — OR'd with `assigned_approver_id == actor`. The
second arm matters after a hierarchy move: a request may still be assigned to an approver whose
tree the requester has since left, and it must not vanish from that approver's inbox.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import DateTime, Select, and_, func, literal, or_, select, tuple_
from sqlalchemy.orm import Session

from humbee_sfa.modules.approvals.contracts import ApprovalStatus
from humbee_sfa.modules.approvals.models import Decision, Request
from humbee_sfa.modules.org.scope import ScopeContext, employee_scope_condition

# ---------------------------------------------------------------------------
# Scoped reads
# ---------------------------------------------------------------------------


def _visible_conditions(scope: ScopeContext) -> tuple[Any, ...]:
    return (
        Request.tenant_id == scope.tenant_id,
        Request.is_active.is_(True),
        or_(
            employee_scope_condition(scope, Request.requester_id),
            Request.assigned_approver_id == scope.actor_employee_id,
        ),
    )


def _visible(scope: ScopeContext) -> Select[tuple[Request]]:
    return select(Request).where(*_visible_conditions(scope))


def _visible_condition_count(scope: ScopeContext) -> Select[tuple[int]]:
    return select(func.count()).select_from(Request).where(*_visible_conditions(scope))


def _decision_rights_condition(
    employee_id: str, additional_decision_subject_types: frozenset[str]
) -> Any:
    decision_rights = Request.assigned_approver_id == employee_id
    if additional_decision_subject_types:
        return or_(
            decision_rights,
            Request.subject_type.in_(additional_decision_subject_types),
        )
    return decision_rights


def _apply_filters(
    stmt: Select[Any],
    *,
    statuses: tuple[str, ...] | None,
    subject_types: tuple[str, ...] | None,
    assigned_approver_id: str | None,
    requester_id: str | None,
    actionable_by_employee_id: str | None,
    additional_decision_subject_types: frozenset[str],
    excluded_subject_types: frozenset[str],
    decided_from: datetime | None,
    decided_before: datetime | None,
) -> Select[Any]:
    if statuses:
        stmt = stmt.where(Request.status.in_(statuses))
    if subject_types:
        stmt = stmt.where(Request.subject_type.in_(subject_types))
    if excluded_subject_types:
        stmt = stmt.where(Request.subject_type.not_in(excluded_subject_types))
    if assigned_approver_id is not None:
        stmt = stmt.where(Request.assigned_approver_id == assigned_approver_id)
    if requester_id is not None:
        stmt = stmt.where(Request.requester_id == requester_id)
    if actionable_by_employee_id is not None:
        stmt = stmt.where(
            _decision_rights_condition(
                actionable_by_employee_id, additional_decision_subject_types
            )
        )
    if decided_from is not None:
        stmt = stmt.where(Request.decided_at >= decided_from)
    if decided_before is not None:
        stmt = stmt.where(Request.decided_at < decided_before)

    return stmt


def get_visible(
    session: Session,
    *,
    scope: ScopeContext,
    request_id: str,
    excluded_subject_types: frozenset[str] = frozenset(),
) -> Request | None:
    """Out-of-scope and non-existent are indistinguishable by design — the caller turns
    `None` into `404 APPROVAL_NOT_FOUND` rather than leaking existence."""

    stmt = _visible(scope).where(Request.id == request_id)
    if excluded_subject_types:
        stmt = stmt.where(Request.subject_type.not_in(excluded_subject_types))
    return session.execute(stmt).scalar_one_or_none()


def list_visible(
    session: Session,
    *,
    scope: ScopeContext,
    statuses: tuple[str, ...] | None = None,
    subject_types: tuple[str, ...] | None = None,
    assigned_approver_id: str | None = None,
    requester_id: str | None = None,
    actionable_by_employee_id: str | None = None,
    additional_decision_subject_types: frozenset[str] = frozenset(),
    excluded_subject_types: frozenset[str] = frozenset(),
    decided_from: datetime | None = None,
    decided_before: datetime | None = None,
    cursor: tuple[datetime, str] | None = None,
    limit: int,
) -> list[Request]:
    """Keyset page, newest first, served by `ix_approvals_inbox` / `ix_approvals_mine`.

    Filtering is a server-side parameter, never a client-side array filter over a paginated list.
    """

    stmt = _apply_filters(
        _visible(scope),
        statuses=statuses,
        subject_types=subject_types,
        assigned_approver_id=assigned_approver_id,
        requester_id=requester_id,
        actionable_by_employee_id=actionable_by_employee_id,
        additional_decision_subject_types=additional_decision_subject_types,
        excluded_subject_types=excluded_subject_types,
        decided_from=decided_from,
        decided_before=decided_before,
    ).order_by(Request.submitted_at.desc(), Request.id.desc())
    if cursor is not None:
        stmt = stmt.where(tuple_(Request.submitted_at, Request.id) < cursor)
    return list(session.execute(stmt.limit(limit)).scalars().all())


def count_visible(
    session: Session,
    *,
    scope: ScopeContext,
    statuses: tuple[str, ...] | None = None,
    subject_types: tuple[str, ...] | None = None,
    assigned_approver_id: str | None = None,
    requester_id: str | None = None,
    actionable_by_employee_id: str | None = None,
    additional_decision_subject_types: frozenset[str] = frozenset(),
    excluded_subject_types: frozenset[str] = frozenset(),
    decided_from: datetime | None = None,
    decided_before: datetime | None = None,
) -> int:
    """The count comes from the *same* scoped predicate as the rows (the dashboard, the
    inbox summary bar and the bell badge must never disagree)."""

    stmt = _apply_filters(
        _visible_condition_count(scope),
        statuses=statuses,
        subject_types=subject_types,
        assigned_approver_id=assigned_approver_id,
        requester_id=requester_id,
        actionable_by_employee_id=actionable_by_employee_id,
        additional_decision_subject_types=additional_decision_subject_types,
        excluded_subject_types=excluded_subject_types,
        decided_from=decided_from,
        decided_before=decided_before,
    )
    return int(session.execute(stmt).scalar_one())


def count_pending_by_subject_type(
    session: Session,
    *,
    scope: ScopeContext,
    actionable_by_employee_id: str | None = None,
    additional_decision_subject_types: frozenset[str] = frozenset(),
    excluded_subject_types: frozenset[str] = frozenset(),
) -> dict[str, int]:
    """Chip counts for the inbox and the dashboard exception row, in one query."""

    stmt = _apply_filters(
        select(Request.subject_type, func.count()).where(*_visible_conditions(scope)),
        statuses=(ApprovalStatus.PENDING,),
        subject_types=None,
        assigned_approver_id=None,
        requester_id=None,
        actionable_by_employee_id=actionable_by_employee_id,
        additional_decision_subject_types=additional_decision_subject_types,
        excluded_subject_types=excluded_subject_types,
        decided_from=None,
        decided_before=None,
    )
    stmt = stmt.group_by(Request.subject_type)
    return {row[0]: row[1] for row in session.execute(stmt).all()}


def latency_summary(
    session: Session,
    *,
    scope: ScopeContext,
    decided_from: datetime,
    decided_before: datetime,
    as_of: datetime,
) -> tuple[float | None, float | None, float | None, int, int]:
    """One scoped aggregate: decided latency (median, p90) in the window, pending age, counts.

    Seconds, not hours — the service converts. Scope is `_visible_conditions`, the same predicate
    `list_visible` / `count_pending_by_subject_type` use. Does not write `sla_due_at`.
    """

    decided_in_window = and_(
        Request.decided_at.is_not(None),
        Request.decided_at >= decided_from,
        Request.decided_at < decided_before,
    )
    is_pending = Request.status == ApprovalStatus.PENDING
    decided_seconds = func.extract("epoch", Request.decided_at - Request.submitted_at)
    pending_seconds = func.extract(
        "epoch", literal(as_of, type_=DateTime(timezone=True)) - Request.submitted_at
    )
    stmt = select(
        func.percentile_cont(0.5).within_group(decided_seconds).filter(decided_in_window),
        func.percentile_cont(0.9).within_group(decided_seconds).filter(decided_in_window),
        func.percentile_cont(0.5).within_group(pending_seconds).filter(is_pending),
        func.count().filter(decided_in_window),
        func.count().filter(is_pending),
    ).where(*_visible_conditions(scope))
    median, p90, pending_median, decided_count, pending_count = session.execute(stmt).one()
    return (
        float(median) if median is not None else None,
        float(p90) if p90 is not None else None,
        float(pending_median) if pending_median is not None else None,
        int(decided_count or 0),
        int(pending_count or 0),
    )


def list_decisions(session: Session, *, tenant_id: str, request_id: str) -> list[Decision]:
    """The append-only trail, ordered — the input to the timeline projection.

    `Decision` carries no `tenant_id` of its own, so this joins `Request` to scope by tenant —
    defense-in-depth alongside the caller's own `_load_visible` scope check, matching this
    module's convention of tenant-scoping every read.
    """

    stmt = (
        select(Decision)
        .join(Request, Request.id == Decision.request_id)
        .where(
            Decision.request_id == request_id,
            Decision.is_active.is_(True),
            Request.tenant_id == tenant_id,
        )
        .order_by(Decision.sequence)
    )
    return list(session.execute(stmt).scalars().all())


# ---------------------------------------------------------------------------
# Engine operations (no actor; see module docstring)
# ---------------------------------------------------------------------------


def pending_for_subject(
    session: Session, *, tenant_id: str, subject_type: str, subject_id: str
) -> Request | None:
    """The one-pending-per-subject friendly pre-check. The partial unique index
    `uq_approvals_one_pending_per_subject` is what actually makes a double submit race-safe."""

    stmt = select(Request).where(
        Request.tenant_id == tenant_id,
        Request.subject_type == subject_type,
        Request.subject_id == subject_id,
        Request.status == ApprovalStatus.PENDING,
    )
    return session.execute(stmt).scalar_one_or_none()


def lock_request(session: Session, *, tenant_id: str, request_id: str) -> Request | None:
    """`SELECT ... FOR UPDATE` on the request row — the same approver on two devices must not both
    decide."""

    stmt = (
        select(Request)
        .where(
            Request.tenant_id == tenant_id,
            Request.id == request_id,
            Request.is_active.is_(True),
        )
        .with_for_update()
    )
    return session.execute(stmt).scalar_one_or_none()


def insert_request(
    session: Session,
    *,
    tenant_id: str,
    subject_type: str,
    subject_id: str,
    requester_id: str,
    requester_manager_id: str | None,
    assigned_approver_id: str | None,
    routing_reason: str,
    escalated_from_id: str | None,
    escalation_depth: int,
    status: str,
    title: str,
    subtitle: str,
    amount_paise: int | None,
    submitted_at: datetime,
    submitted_business_date: date,
    decided_at: datetime | None = None,
    decided_by_id: str | None = None,
    actor_employee_id: str | None = None,
) -> Request:
    row = Request(
        tenant_id=tenant_id,
        subject_type=subject_type,
        subject_id=subject_id,
        subject_version=1,
        requester_id=requester_id,
        requester_manager_id=requester_manager_id,
        assigned_approver_id=assigned_approver_id,
        routing_reason=routing_reason,
        escalated_from_id=escalated_from_id,
        escalation_depth=escalation_depth,
        status=status,
        title=title[:120],
        subtitle=subtitle[:200],
        amount_paise=amount_paise,
        submitted_at=submitted_at,
        submitted_business_date=submitted_business_date,
        decided_at=decided_at,
        decided_by_id=decided_by_id,
        edit_applied=False,
        created_by_employee_id=actor_employee_id,
    )
    session.add(row)
    session.flush()
    return row


def append_decision(
    session: Session,
    *,
    tenant_id: str,
    request_id: str,
    action: str,
    occurred_at: datetime,
    actor_id: str | None = None,
    actor_role: str | None = None,
    note: str | None = None,
    edit_patch: dict[str, Any] | None = None,
) -> Decision:
    """Every state transition appends exactly one row here. Never updated, never deleted.

    `sequence` is derived under the caller's `FOR UPDATE` lock on the request (or, at creation,
    while the request row is still uncommitted), so `uq_approvals_decisions_seq` cannot be raced.
    """

    next_sequence = (
        session.execute(
            select(func.coalesce(func.max(Decision.sequence), 0)).where(
                Decision.request_id == request_id
            )
        ).scalar_one()
        + 1
    )
    row = Decision(
        tenant_id=tenant_id,
        request_id=request_id,
        sequence=next_sequence,
        action=action,
        actor_id=actor_id,
        actor_role=actor_role,
        note=note,
        edit_patch=edit_patch,
        occurred_at=occurred_at,
        created_by_employee_id=actor_id,
    )
    session.add(row)
    session.flush()
    return row


def apply_decision_outcome(
    session: Session,
    *,
    request: Request,
    status: str,
    decided_at: datetime,
    decided_by_id: str | None,
    decision_note: str | None = None,
    edit_applied: bool | None = None,
) -> None:
    request.status = status
    request.decided_at = decided_at
    request.decided_by_id = decided_by_id
    if decision_note is not None:
        request.decision_note = decision_note
    if edit_applied is not None:
        request.edit_applied = edit_applied
    session.flush()


def apply_edit_result(
    session: Session,
    *,
    request: Request,
    subject_version: int,
    title: str,
    subtitle: str,
    amount_paise: int | None,
) -> None:
    """Refresh the denormalised summary after `adapter.apply_edit` (the request's
    `amount_paise` must be updated in the same transaction as the subject's)."""

    request.subject_version = subject_version
    request.title = title[:120]
    request.subtitle = subtitle[:200]
    request.amount_paise = amount_paise
    session.flush()

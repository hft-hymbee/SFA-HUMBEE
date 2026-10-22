"""Leave persistence — M12 §3.1/§3.3. Thin, scoped, no business decisions.

Every function takes a resolved `ScopeContext` from `org.scope` (M12 §9: "scope is applied in
`leave/repository.py` via the shared `ScopeResolver`"), so a caller cannot forget the tenant
predicate. Leave rows are activity data, so callers resolve `OrgResource.ACTIVITY_DATA`; the
system-routing oracle path uses `internal_routing_scope` (tenant-only, no actor).

Nothing here computes `day_count`, reserves balance or moves status: those are decisions and live
in `service.py` (day count) or in the M06 approval engine (status).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Select, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from humbee_sfa.core.conventions import generate_ulid
from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.modules.leave.leave_type import LeaveType
from humbee_sfa.modules.leave.models import LeaveBalance, LeaveRequest
from humbee_sfa.modules.org.scope import ScopeContext, apply_scope

# M12 §3.4 / R-LV-19. `GRANTED_STATUSES` is exactly the predicate of the partial index
# `ix_leave_on_leave_oracle`; changing one without the other silently deoptimises the hot path.
GRANTED_STATUSES: tuple[str, ...] = ("approved", "auto_approved")
# R-LV-08: the statuses the exclusion constraint treats as occupying a date range.
LIVE_OR_GRANTED_STATUSES: tuple[str, ...] = ("pending", *GRANTED_STATUSES)


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------


def _require_own_leave_write(scope: ScopeContext, employee_id: str) -> None:
    """M12 §9: nobody applies for leave on behalf of anybody else — not even an Admin.

    A row that does not exist yet cannot be scope-tested, so the target employee is compared
    against the actor directly. The no-actor system scope is allowed because that path only ever
    mirrors an M06 decision back onto an existing subject.
    """

    if scope.is_authentication:
        return
    if scope.actor_employee_id != employee_id:
        raise ApiError(403, "forbidden", "Leave can only be recorded for the acting employee.")


def _scoped_requests(scope: ScopeContext) -> Select[tuple[LeaveRequest]]:
    return apply_scope(
        select(LeaveRequest),
        scope,
        tenant_column=LeaveRequest.tenant_id,
        employee_id_column=LeaveRequest.employee_id,
    )


# ---------------------------------------------------------------------------
# Leave request reads
# ---------------------------------------------------------------------------


def get_request(
    session: Session, *, scope: ScopeContext, leave_request_id: str
) -> LeaveRequest | None:
    stmt = _scoped_requests(scope).where(LeaveRequest.id == leave_request_id)
    return session.execute(stmt).scalar_one_or_none()


def get_leave_types(
    session: Session, *, tenant_id: str, leave_request_ids: list[str]
) -> dict[str, str]:
    """`leave_type` per request id, tenant-scoped, for the admin attendance report — attendance
    holds only a logical `leave_request_id` pointer, never the type itself."""

    if not leave_request_ids:
        return {}
    stmt = select(LeaveRequest.id, LeaveRequest.leave_type).where(
        LeaveRequest.tenant_id == tenant_id, LeaveRequest.id.in_(leave_request_ids)
    )
    return {row.id: row.leave_type for row in session.execute(stmt).all()}


def get_request_by_approval_request(
    session: Session, *, scope: ScopeContext, approval_request_id: str
) -> LeaveRequest | None:
    """The M06 → M12 mirror lookup (R-LV-09). Unique per `uq_leave_approval_request`."""

    stmt = _scoped_requests(scope).where(
        LeaveRequest.approval_request_id == approval_request_id
    )
    return session.execute(stmt).scalar_one_or_none()


def list_requests_for_employee(
    session: Session,
    *,
    scope: ScopeContext,
    employee_id: str,
    statuses: tuple[str, ...] | None = None,
    limit: int,
    offset: int = 0,
) -> list[LeaveRequest]:
    """S-LV2 history — newest `from_date` first, served by `ix_leave_mine`."""

    stmt = (
        _scoped_requests(scope)
        .where(LeaveRequest.employee_id == employee_id)
        .order_by(LeaveRequest.from_date.desc(), LeaveRequest.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if statuses:
        stmt = stmt.where(LeaveRequest.status.in_(statuses))
    return list(session.execute(stmt).scalars().all())


def list_requests_in_scope(
    session: Session,
    *,
    scope: ScopeContext,
    statuses: tuple[str, ...] | None = None,
    limit: int,
    offset: int = 0,
) -> list[LeaveRequest]:
    """S-LV3 team leave — every leave row the actor's resolved scope allows, newest `from_date`
    first. The scope (Manager → own tree, Admin → org) is entirely `apply_scope`'s decision;
    nothing here widens or narrows it (R-LV-16).
    """

    stmt = (
        _scoped_requests(scope)
        .order_by(LeaveRequest.from_date.desc(), LeaveRequest.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if statuses:
        stmt = stmt.where(LeaveRequest.status.in_(statuses))
    return list(session.execute(stmt).scalars().all())


def list_requests_overlapping(
    session: Session,
    *,
    scope: ScopeContext,
    from_date: date,
    to_date: date,
    employee_id: str | None = None,
    statuses: tuple[str, ...] = GRANTED_STATUSES,
) -> list[LeaveRequest]:
    """Requests whose inclusive IST date range intersects `[from_date, to_date]`.

    Both bounds are IST business dates (R-LV-06). Overlap, not containment: a leave from 30 Jul
    to 02 Aug is returned for a July window and for an August one.
    """

    stmt = (
        _scoped_requests(scope)
        .where(
            LeaveRequest.status.in_(statuses),
            LeaveRequest.from_date <= to_date,
            LeaveRequest.to_date >= from_date,
        )
        .order_by(LeaveRequest.from_date, LeaveRequest.id)
    )
    if employee_id is not None:
        stmt = stmt.where(LeaveRequest.employee_id == employee_id)
    return list(session.execute(stmt).scalars().all())


def granted_leave_exists_on(
    session: Session, *, scope: ScopeContext, employee_id: str, on_date: date
) -> bool:
    """The `is_on_leave()` oracle query — M12 §5.4 step 2.

    Shaped deliberately to be answered by `ix_leave_on_leave_oracle`
    `(tenant_id, employee_id, from_date, to_date) WHERE status IN ('approved','auto_approved')`:
    an `EXISTS` over the four indexed columns and nothing else. No `LeaveDay` expansion, no ORM
    object graph, and no extra predicate (an `is_active` filter would fall outside the index and
    leave rows are append-only anyway — R-LV-25).

    Called on every approval submission system-wide, so keep it boring.
    """

    stmt = (
        select(LeaveRequest.id)
        .where(
            LeaveRequest.tenant_id == scope.tenant_id,
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status.in_(GRANTED_STATUSES),
            LeaveRequest.from_date <= on_date,
            LeaveRequest.to_date >= on_date,
        )
        .limit(1)
    )
    return session.execute(select(stmt.exists())).scalar_one()


# ---------------------------------------------------------------------------
# Leave request writes
# ---------------------------------------------------------------------------


def insert_request(
    session: Session,
    *,
    scope: ScopeContext,
    employee_id: str,
    leave_type: LeaveType,
    from_date: date,
    to_date: date,
    day_count: Decimal,
    is_half_day: bool,
    reason: str | None,
    status: str,
    approval_request_id: str,
    balance_before: Decimal,
    balance_after_projected: Decimal,
    applied_at: datetime,
    applied_business_date: date,
    leave_request_id: str | None = None,
) -> LeaveRequest:
    """Insert one leave application. `day_count` is supplied, never derived here (R-LV-05).

    `leave_request_id` accepts the client-generated ULID (M12 §3.1) so a retried submit is
    provably the same request.
    """

    _require_own_leave_write(scope, employee_id)
    row = LeaveRequest(
        tenant_id=scope.tenant_id,
        employee_id=employee_id,
        leave_type=leave_type,
        from_date=from_date,
        to_date=to_date,
        day_count=day_count,
        is_half_day=is_half_day,
        reason=reason,
        status=status,
        approval_request_id=approval_request_id,
        balance_before=balance_before,
        balance_after_projected=balance_after_projected,
        applied_at=applied_at,
        applied_business_date=applied_business_date,
        created_by_employee_id=scope.actor_employee_id,
    )
    if leave_request_id is not None:
        row.id = leave_request_id
    session.add(row)
    session.flush()
    return row


def link_approval_request(
    session: Session, *, request: LeaveRequest, approval_request_id: str
) -> None:
    """Point the leave row at its M06 request once the engine has minted it.

    Submission is a chicken-and-egg: the engine needs the leave row to exist before it can render
    the request's denormalised summary, and the leave row's `approval_request_id` is NOT NULL. So
    the insert self-references and this closes the link, in the same transaction — a leave row whose
    `approval_request_id` is not a real M06 request is never visible outside it (M12 §11.3).
    """

    request.approval_request_id = approval_request_id
    session.flush()


def set_request_status(
    session: Session,
    *,
    scope: ScopeContext,
    request: LeaveRequest,
    status: str,
    decided_at: datetime | None = None,
    decision_note: str | None = None,
) -> None:
    """Mirror an M06 outcome onto the leave row (R-LV-09).

    This is a projection write, not a decision: the caller must already be inside the approval
    engine's decision transaction. M12 owns no status transitions of its own (R-LV-01).
    """

    request.status = status
    if decided_at is not None:
        request.decided_at = decided_at
    if decision_note is not None:
        request.decision_note = decision_note
    session.flush()


# ---------------------------------------------------------------------------
# Leave balances
# ---------------------------------------------------------------------------


def _balance_stmt(
    scope: ScopeContext, *, employee_id: str, leave_type: LeaveType, period_year: int
) -> Select[tuple[LeaveBalance]]:
    return apply_scope(
        select(LeaveBalance),
        scope,
        tenant_column=LeaveBalance.tenant_id,
        employee_id_column=LeaveBalance.employee_id,
    ).where(
        LeaveBalance.employee_id == employee_id,
        LeaveBalance.leave_type == leave_type,
        LeaveBalance.period_year == period_year,
    )


def get_balance(
    session: Session,
    *,
    scope: ScopeContext,
    employee_id: str,
    leave_type: LeaveType,
    period_year: int,
) -> LeaveBalance | None:
    stmt = _balance_stmt(
        scope, employee_id=employee_id, leave_type=leave_type, period_year=period_year
    )
    return session.execute(stmt).scalar_one_or_none()


def list_balances(
    session: Session, *, scope: ScopeContext, employee_id: str, period_year: int
) -> list[LeaveBalance]:
    stmt = (
        apply_scope(
            select(LeaveBalance),
            scope,
            tenant_column=LeaveBalance.tenant_id,
            employee_id_column=LeaveBalance.employee_id,
        )
        .where(
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.period_year == period_year,
        )
        .order_by(LeaveBalance.leave_type)
    )
    return list(session.execute(stmt).scalars().all())


def insert_balance(
    session: Session,
    *,
    scope: ScopeContext,
    employee_id: str,
    leave_type: LeaveType,
    period_year: int,
    entitled_days: Decimal,
) -> LeaveBalance:
    row = LeaveBalance(
        tenant_id=scope.tenant_id,
        employee_id=employee_id,
        leave_type=leave_type,
        period_year=period_year,
        entitled_days=entitled_days,
        consumed_days=Decimal(0),
        pending_days=Decimal(0),
        created_by_employee_id=scope.actor_employee_id,
    )
    session.add(row)
    session.flush()
    return row


def insert_balance_if_absent(
    session: Session,
    *,
    scope: ScopeContext,
    employee_id: str,
    leave_type: LeaveType,
    period_year: int,
    entitled_days: Decimal,
) -> LeaveBalance:
    """Open a ledger row unless a concurrent transaction already has, then return whichever row
    `uq_leave_balances` kept. `ON CONFLICT DO NOTHING` makes the loser wait and skip instead of
    failing the submission."""

    session.execute(
        pg_insert(LeaveBalance)
        .values(
            id=generate_ulid(),
            tenant_id=scope.tenant_id,
            employee_id=employee_id,
            leave_type=leave_type,
            period_year=period_year,
            entitled_days=entitled_days,
            consumed_days=Decimal(0),
            pending_days=Decimal(0),
            created_by_employee_id=scope.actor_employee_id,
        )
        .on_conflict_do_nothing(
            index_elements=["tenant_id", "employee_id", "leave_type", "period_year"]
        )
    )
    stmt = _balance_stmt(
        scope, employee_id=employee_id, leave_type=leave_type, period_year=period_year
    )
    return session.execute(stmt).scalar_one()


def apply_balance_delta(
    session: Session,
    *,
    scope: ScopeContext,
    balance: LeaveBalance,
    consumed_delta: Decimal = Decimal(0),
    pending_delta: Decimal = Decimal(0),
) -> None:
    """Conditional UPDATE of the ledger columns (R-LV-12: reserve → consume → release).

    Written as a database-side arithmetic update rather than read-modify-write so two concurrent
    reservations cannot lose one another. `leave_balances_nonneg_chk` is the backstop; a delta that
    would drive a column negative raises rather than clamping.
    """

    session.execute(
        update(LeaveBalance)
        .where(
            LeaveBalance.tenant_id == scope.tenant_id,
            LeaveBalance.id == balance.id,
        )
        .values(
            consumed_days=LeaveBalance.consumed_days + consumed_delta,
            pending_days=LeaveBalance.pending_days + pending_delta,
        )
    )
    session.expire(balance)

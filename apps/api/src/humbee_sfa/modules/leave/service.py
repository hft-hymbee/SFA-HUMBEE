"""Leave availability and derivations.

This module is the public face of `leave` for other modules. `is_on_leave()` and
`granted_leave_dates()` expose granted-leave availability to attendance and route planning.
Submission hands decision lifecycle ownership to the approval engine; leave owns no separate state
machine.

`LeaveService` at the bottom is the HTTP-facing half: the leave screen reads plus submission, which
creates the leave row and then hands routing and the whole decision lifecycle to
`approvals.service.create`. Nothing in this file writes `LeaveRequest.status` — that is
`leave/adapter.py`'s exclusive job.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import structlog
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from humbee_sfa.core.business_date import to_business_date
from humbee_sfa.core.clock import Clock, SystemClock
from humbee_sfa.core.conventions import generate_ulid
from humbee_sfa.core.db import transaction
from humbee_sfa.core.deps import AccessTokenClaims
from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.core.settings import Settings, get_settings
from humbee_sfa.modules.approvals import service as approvals_service
from humbee_sfa.modules.approvals.contracts import ApprovalStatus
from humbee_sfa.modules.leave import repository, schemas
from humbee_sfa.modules.leave.leave_type import LeaveType
from humbee_sfa.modules.leave.models import LeaveBalance, LeaveRequest
from humbee_sfa.modules.org import service as org_service
from humbee_sfa.modules.org.scope import (
    OrgResource,
    Scope,
    ScopeContext,
    ScopeResolver,
    internal_routing_scope,
)
from humbee_sfa.platform.idempotency import IdempotencyService

logger = structlog.get_logger("humbee_sfa.leave")

HALF_DAY_COUNT = Decimal("0.5")
WHOLE_DAY = Decimal(1)
MAX_LEAVE_DAYS = 364
UNKNOWN_EMPLOYEE_NAME = "Former employee"


# ---------------------------------------------------------------------------
# Business-date derivation
# ---------------------------------------------------------------------------


def current_business_date(clock: Clock, *, settings: Settings | None = None) -> date:
    """Today's IST business date, from the injected clock — never from server-local time.

    Every leave date in this module is one of these. Callers that already hold a business date pass
    it through unchanged; callers that only have "now" come through here.
    """

    resolved = settings or get_settings()
    return to_business_date(clock.now_utc(), resolved.day_boundary_hour_ist)


def _prorated_entitlement(*, annual_days: Decimal, remaining_months_inclusive: int) -> Decimal:
    prorated = (annual_days * Decimal(remaining_months_inclusive)) / Decimal(12)
    return prorated.quantize(WHOLE_DAY, rounding=ROUND_HALF_UP)


def _yearly_default_days(settings: Settings) -> dict[LeaveType, Decimal]:
    return {
        LeaveType.PRIVILEGED: Decimal(settings.leave_default_yearly_privileged_days),
        LeaveType.CASUAL: Decimal(settings.leave_default_yearly_casual_days),
        LeaveType.SICK: Decimal(settings.leave_default_yearly_sick_days),
    }


def provision_employee_join_year_balances(
    session: Session,
    *,
    scope: ScopeContext,
    employee_id: str,
    joined_on: date | None,
    privileged_leave_days: Decimal | None,
    casual_leave_days: Decimal | None,
    sick_leave_days: Decimal | None,
    clock: Clock,
    settings: Settings | None = None,
) -> None:
    """Create the join-year leave ledger rows if absent.

    Entitlements provided at employee creation are yearly values and are prorated for the join
    year, rounded to whole days. Missing values use yearly defaults, prorated by the same rule
    (remaining months in the join year, inclusive). Every later year opens at the full yearly
    default — see `LeaveService._ensure_balance`.
    """

    resolved_settings = settings or get_settings()
    join_date = joined_on or current_business_date(clock, settings=resolved_settings)
    remaining_months_inclusive = 12 - join_date.month + 1
    period_year = join_date.year

    explicit: dict[LeaveType, Decimal | None] = {
        LeaveType.PRIVILEGED: privileged_leave_days,
        LeaveType.CASUAL: casual_leave_days,
        LeaveType.SICK: sick_leave_days,
    }
    for leave_type, annual_default in _yearly_default_days(resolved_settings).items():
        explicit_days = explicit[leave_type]
        existing = repository.get_balance(
            session,
            scope=scope,
            employee_id=employee_id,
            leave_type=leave_type,
            period_year=period_year,
        )
        if existing is not None:
            continue

        annual_days = explicit_days if explicit_days is not None else annual_default
        entitled_days = _prorated_entitlement(
            annual_days=annual_days,
            remaining_months_inclusive=remaining_months_inclusive,
        )
        repository.insert_balance(
            session,
            scope=scope,
            employee_id=employee_id,
            leave_type=leave_type,
            period_year=period_year,
            entitled_days=entitled_days,
        )


def _require_business_date(value: date, *, field: str) -> date:
    """Reject a `datetime` masquerading as a business date.

    `datetime` is a subclass of `date`, so an accidental `utc_now()` would otherwise sail through
    and be compared against IST `DATE` columns as its UTC calendar day — wrong for every instant
    between 18:30 UTC and midnight. That is a caller bug, not a runtime condition, so it raises
    `TypeError` rather than an `ApiError`.
    """

    if isinstance(value, datetime):
        raise TypeError(
            f"{field} must be an IST business date (datetime.date), not a datetime; "
            "derive it via leave.service.current_business_date or the caller's business date."
        )
    return value


# ---------------------------------------------------------------------------
# Day count
# ---------------------------------------------------------------------------


def compute_day_count(
    *, from_date: date, to_date: date, is_half_day: bool = False
) -> Decimal:
    """Inclusive IST calendar day count — the value that gets **stored** on the request.

    `(to_date - from_date).days + 1`; `0.5` for a half day. v1 counts calendar days: weekends and
    public holidays are included because no holiday master exists. The result is
    persisted at submission precisely so a later holiday policy cannot rewrite historical leave
    — nothing may recompute it on a read path.
    """

    _require_business_date(from_date, field="from_date")
    _require_business_date(to_date, field="to_date")
    if to_date < from_date:
        raise ApiError(422, "invalid_date_range", "To date cannot be before from date.")
    if is_half_day:
        if from_date != to_date:
            raise ApiError(
                422, "half_day_range_invalid", "A half day must start and end on the same date."
            )
        return HALF_DAY_COUNT
    day_count = (to_date - from_date).days + 1
    if day_count > MAX_LEAVE_DAYS:
        raise ApiError(
            422,
            "leave_range_too_long",
            f"A leave request can cover at most {MAX_LEAVE_DAYS} days.",
        )
    return Decimal(day_count)


# ---------------------------------------------------------------------------
# The availability oracle
# ---------------------------------------------------------------------------


def leave_types_by_ids(
    session: Session, *, tenant_id: str, leave_request_ids: list[str]
) -> dict[str, str]:
    """`leave_type` per leave request id, for `attendance.list_attendance_for_report` — the
    module boundary a caller outside `leave` must go through instead of its repository."""

    return repository.get_leave_types(
        session, tenant_id=tenant_id, leave_request_ids=leave_request_ids
    )


def is_on_leave(session: Session, *, tenant_id: str, employee_id: str, on_date: date) -> bool:
    """Whether `employee_id` is on granted leave for IST business date `on_date`.

    True only for requests in `approved` or `auto_approved` that cover `on_date` inclusively;
    pending/rejected/withdrawn/expired never count. `on_date` must be a business `date` (not
    `datetime`). The lookup is tenant- and employee-scoped via `internal_routing_scope`.
    If leave availability cannot be read, this fails closed with
    `ApiError(503, "leave_availability_unavailable")`.
    """

    _require_business_date(on_date, field="on_date")
    scope: ScopeContext = internal_routing_scope(tenant_id)
    try:
        return repository.granted_leave_exists_on(
            session, scope=scope, employee_id=employee_id, on_date=on_date
        )
    except SQLAlchemyError as exc:
        # WARN, not ERROR: the caller's request fails retryably and nothing is left inconsistent.
        logger.warning("leave_availability_unavailable", tenant_id=tenant_id)
        raise ApiError(
            503,
            "leave_availability_unavailable",
            "Leave availability cannot be determined right now. Please retry.",
        ) from exc


def granted_leave_dates(
    session: Session,
    *,
    tenant_id: str,
    employee_id: str,
    from_date: date,
    to_date: date,
) -> set[date]:
    """Every IST business date in `[from_date, to_date]` on which the employee has granted leave.

    The set form of `is_on_leave` for callers that need a whole window at once (attendance
    distinguishing "on leave" from "no punch-in"; route planning suppressing missed-visit
    audit). Same status filter, same business-date semantics, same fail-closed behaviour: a
    partially computed set is never returned.
    """

    _require_business_date(from_date, field="from_date")
    _require_business_date(to_date, field="to_date")
    if to_date < from_date:
        raise ApiError(422, "invalid_date_range", "To date cannot be before from date.")

    scope = internal_routing_scope(tenant_id)
    try:
        rows = repository.list_requests_overlapping(
            session,
            scope=scope,
            employee_id=employee_id,
            from_date=from_date,
            to_date=to_date,
        )
    except SQLAlchemyError as exc:
        logger.warning("leave_availability_unavailable", tenant_id=tenant_id)
        raise ApiError(
            503,
            "leave_availability_unavailable",
            "Leave availability cannot be determined right now. Please retry.",
        ) from exc

    covered: set[date] = set()
    for row in rows:
        start = max(row.from_date, from_date)
        end = min(row.to_date, to_date)
        covered.update(
            start + timedelta(days=offset) for offset in range((end - start).days + 1)
        )
    return covered


def employees_on_leave(session: Session, *, tenant_id: str, on_date: date) -> set[str]:
    """Every employee in the tenant on granted leave for IST business date `on_date`.

    The roster form of `is_on_leave` for team views that split "on leave" from "no punch-in".
    Same status filter and the same fail-closed behaviour.
    """

    _require_business_date(on_date, field="on_date")
    scope = internal_routing_scope(tenant_id)
    try:
        rows = repository.list_requests_overlapping(
            session, scope=scope, from_date=on_date, to_date=on_date
        )
    except SQLAlchemyError as exc:
        logger.warning("leave_availability_unavailable", tenant_id=tenant_id)
        raise ApiError(
            503,
            "leave_availability_unavailable",
            "Leave availability cannot be determined right now. Please retry.",
        ) from exc
    return {row.employee_id for row in rows}


# ---------------------------------------------------------------------------
# The HTTP-facing service
# ---------------------------------------------------------------------------


def _available(balance: LeaveBalance) -> Decimal:
    """Never clamped at 0 — a negative available balance is legitimate and visible."""

    return balance.entitled_days - balance.consumed_days - balance.pending_days


def _request_payload(row: LeaveRequest) -> dict[str, Any]:
    return schemas.LeaveRequestItem(
        id=row.id,
        leave_type=LeaveType(row.leave_type),
        from_date=row.from_date,
        to_date=row.to_date,
        day_count=float(row.day_count),
        is_half_day=row.is_half_day,
        reason=row.reason,
        status=row.status,
        approval_request_id=row.approval_request_id,
        balance_before=float(row.balance_before),
        balance_after_projected=float(row.balance_after_projected),
        applied_at=row.applied_at,
        decided_at=row.decided_at,
        decision_note=row.decision_note,
    ).model_dump(mode="json")


class LeaveService:
    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._clock = clock or SystemClock()
        self._idempotency = IdempotencyService(session)

    def _scope(self, claims: AccessTokenClaims) -> ScopeContext:
        # Leave rows are activity data: SELF for a Sales Person, OWN_TREE for a Manager, ORG for an
        # Admin. No leave-specific scope logic exists.
        return ScopeResolver.resolve_from_claims(claims, OrgResource.ACTIVITY_DATA)

    # -- reads -------------------------------------------------------------

    def get_my_balances(self, *, claims: AccessTokenClaims) -> dict[str, Any]:
        """Apply-leave balance cards, one per leave type. A type with no ledger row yet for this year
        is reported at the full yearly default — exactly what `_ensure_balance` will open it at on
        first use — so this read never writes."""

        scope = self._scope(claims)
        period_year = current_business_date(self._clock, settings=self._settings).year
        rows = {
            row.leave_type: row
            for row in repository.list_balances(
                self._session,
                scope=scope,
                employee_id=claims.employee_id,
                period_year=period_year,
            )
        }
        defaults = _yearly_default_days(self._settings)
        items = []
        for leave_type in LeaveType:
            row = rows.get(leave_type)
            entitled = row.entitled_days if row is not None else defaults[leave_type]
            consumed = row.consumed_days if row is not None else Decimal(0)
            pending = row.pending_days if row is not None else Decimal(0)
            items.append(
                schemas.LeaveBalanceItem(
                    leave_type=leave_type,
                    period_year=period_year,
                    entitled_days=float(entitled),
                    consumed_days=float(consumed),
                    pending_days=float(pending),
                    available_days=float(entitled - consumed - pending),
                )
            )
        return schemas.LeaveBalancesResponse(period_year=period_year, items=items).model_dump(
            mode="json"
        )

    def preview(
        self,
        *,
        claims: AccessTokenClaims,
        leave_type: LeaveType,
        from_date: date,
        to_date: date,
    ) -> dict[str, Any]:
        """Server-authoritative day count and balance-after for the apply-leave screen.

        Read-only. `exceeds_balance` is an advisory flag, never a gate — the request stays
        submittable and the approver decides.
        """

        scope = self._scope(claims)
        day_count = compute_day_count(from_date=from_date, to_date=to_date)
        # Submission attributes a range to the leave year of its `from_date`, so the
        # preview must read the same ledger the reservation will land on. That is not always the
        # year the balance cards show, so `period_year` is returned and the client says which
        # leave year the projection belongs to.
        period_year = from_date.year
        balance = repository.get_balance(
            self._session,
            scope=scope,
            employee_id=claims.employee_id,
            leave_type=leave_type,
            period_year=period_year,
        )
        available = (
            _available(balance)
            if balance is not None
            else _yearly_default_days(self._settings)[leave_type]
        )
        balance_after = available - day_count
        return schemas.LeavePreviewResponse(
            leave_type=leave_type,
            from_date=from_date,
            to_date=to_date,
            period_year=period_year,
            day_count=float(day_count),
            available_days=float(available),
            balance_after=float(balance_after),
            exceeds_balance=balance_after < 0,
        ).model_dump(mode="json")

    def list_mine(
        self, *, claims: AccessTokenClaims, status_filter: str, limit: int, offset: int
    ) -> dict[str, Any]:
        """Own leave history. One table, `status` read from the mirrored column — no join into `approvals` on
        this path, which is exactly why the mirror exists."""

        rows = repository.list_requests_for_employee(
            self._session,
            scope=self._scope(claims),
            employee_id=claims.employee_id,
            statuses=schemas.MINE_STATUS_FILTERS[status_filter] or None,
            limit=limit,
            offset=offset,
        )
        return schemas.LeaveRequestListResponse(
            items=[schemas.LeaveRequestItem(**_request_payload(row)) for row in rows]
        ).model_dump(mode="json")

    def list_team(
        self, *, claims: AccessTokenClaims, status_filter: str, limit: int, offset: int
    ) -> dict[str, Any]:
        """Team leave. Manager → own tree, Admin → org-wide, entirely via the shared resolver."""

        scope = self._scope(claims)
        if scope.scope is Scope.SELF:
            # A Sales Person has no team-leave capability at all. Refusing here rather than
            # silently serving their own row keeps the screen's contract honest.
            raise ApiError(403, "forbidden", "Team leave is available to managers and admins.")

        rows = repository.list_requests_in_scope(
            self._session,
            scope=scope,
            statuses=schemas.TEAM_STATUS_FILTERS[status_filter] or None,
            limit=limit,
            offset=offset,
        )
        names = self._employee_names({row.employee_id for row in rows}, scope.tenant_id)
        return schemas.TeamLeaveListResponse(
            items=[
                schemas.TeamLeaveItem(
                    id=row.id,
                    employee_id=row.employee_id,
                    employee_name=names[row.employee_id],
                    leave_type=LeaveType(row.leave_type),
                    from_date=row.from_date,
                    to_date=row.to_date,
                    day_count=float(row.day_count),
                    status=row.status,
                    approval_request_id=row.approval_request_id,
                )
                for row in rows
            ]
        ).model_dump(mode="json")

    def _employee_names(self, employee_ids: set[str], tenant_id: str) -> dict[str, str]:
        """Names come from `org`'s public service, never from its tables — one batched
        query for the whole page. An id `org` can no longer resolve keeps its row visible under a
        placeholder rather than rendering a blank name and a blank avatar."""

        resolved = org_service.list_employee_names(
            self._session, tenant_id=tenant_id, employee_ids=sorted(employee_ids)
        )
        return {
            employee_id: resolved.get(employee_id) or UNKNOWN_EMPLOYEE_NAME
            for employee_id in employee_ids
        }

    # -- submission --------------------------------------------------------

    def submit(
        self,
        *,
        claims: AccessTokenClaims,
        body: schemas.SubmitLeaveBody,
        idempotency_key: str,
        raw_body: bytes,
        request_id: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """Leave submit — one transaction covering the leave row, the balance reservation and the
        approval request (a `LeaveRequest` with no `approval_request_id` is not reachable).

        The response status may legitimately be `auto_approved`: when the requester is at the top of
        the hierarchy, `approvals.create` decides re-entrantly inside this same transaction and
        `LeaveAdapter.on_approved` has already converted the reservation before we reply.
        """

        scope = self._scope(claims)
        endpoint = "/api/v1/leave/requests"
        try:
            with transaction(self._session):
                replay = self._check_idempotency(
                    endpoint=endpoint,
                    idempotency_key=idempotency_key,
                    raw_body=raw_body,
                    tenant_id=scope.tenant_id,
                )
                if replay is not None:
                    return replay

                now = self._clock.now_utc()
                applied_business_date = current_business_date(
                    self._clock, settings=self._settings
                )
                day_count = compute_day_count(from_date=body.from_date, to_date=body.to_date)
                # v1 attributes a range to the leave year of its `from_date`.
                balance = self._ensure_balance(
                    scope,
                    employee_id=claims.employee_id,
                    leave_type=body.leave_type,
                    period_year=body.from_date.year,
                )
                balance_before = _available(balance)
                # The leave id is minted here so the row can self-reference as a placeholder for
                # `approval_request_id` (NOT NULL) until the engine mints the real one below.
                leave_request_id = body.id or generate_ulid()

                row = repository.insert_request(
                    self._session,
                    scope=scope,
                    employee_id=claims.employee_id,
                    leave_type=body.leave_type,
                    from_date=body.from_date,
                    to_date=body.to_date,
                    day_count=day_count,
                    is_half_day=False,
                    reason=body.reason,
                    status=ApprovalStatus.PENDING,
                    approval_request_id=leave_request_id,
                    balance_before=balance_before,
                    balance_after_projected=balance_before - day_count,
                    applied_at=now,
                    applied_business_date=applied_business_date,
                    leave_request_id=leave_request_id,
                )
                # Submission reserves; it never debits. Reserved *before* handing over to
                # the engine so the auto-approval path has a reservation to convert.
                repository.apply_balance_delta(
                    self._session, scope=scope, balance=balance, pending_delta=day_count
                )
                approval = approvals_service.create(
                    self._session,
                    tenant_id=scope.tenant_id,
                    subject_type="leave",
                    subject_id=row.id,
                    requester_id=claims.employee_id,
                    clock=self._clock,
                    request_id=request_id,
                )
                repository.link_approval_request(
                    self._session, request=row, approval_request_id=approval.id
                )

                payload = _request_payload(row)
                self._store_idempotency(
                    endpoint=endpoint,
                    idempotency_key=idempotency_key,
                    raw_body=raw_body,
                    status_code=201,
                    payload=payload,
                    scope=scope,
                )
        except IntegrityError as exc:
            # Outside the `with`: the manager has already rolled back, so this only classifies.
            # `leave_no_overlap_excl` is the exclusion constraint that makes the no-overlap rule
            # real — the pre-check narrows the window, the constraint closes it. `pk_leave_requests`
            # means the client replayed its ULID under a fresh `Idempotency-Key`; that is still the
            # same request, so it gets a resolvable 409 rather than a 500.
            detail = str(getattr(exc, "orig", exc))
            if "leave_no_overlap_excl" in detail:
                raise ApiError(
                    409,
                    "overlapping_leave",
                    "You already have leave applied for these dates.",
                ) from exc
            if "pk_leave_requests" in detail:
                raise ApiError(
                    409,
                    "leave_request_exists",
                    "This leave request has already been submitted.",
                ) from exc
            raise

        logger.info(
            "leave_requested",
            leave_request_id=payload["id"],
            approval_request_id=payload["approval_request_id"],
            status=payload["status"],
            leave_type=payload["leave_type"],
        )
        return 201, payload

    def _ensure_balance(
        self,
        scope: ScopeContext,
        *,
        employee_id: str,
        leave_type: LeaveType,
        period_year: int,
    ) -> LeaveBalance:
        """The ledger row a reservation lands on, created on first use.

        The join year is provisioned pro-rated at employee creation; every other year opens here at
        the full yearly default. The insert is conflict-tolerant so two concurrent
        first submissions cannot both try to create the row.
        """

        balance = repository.get_balance(
            self._session,
            scope=scope,
            employee_id=employee_id,
            leave_type=leave_type,
            period_year=period_year,
        )
        if balance is not None:
            return balance
        return repository.insert_balance_if_absent(
            self._session,
            scope=scope,
            employee_id=employee_id,
            leave_type=leave_type,
            period_year=period_year,
            entitled_days=_yearly_default_days(self._settings)[leave_type],
        )

    # -- idempotency -------------------------------------------------------

    def _check_idempotency(
        self, *, endpoint: str, idempotency_key: str, raw_body: bytes, tenant_id: str
    ) -> tuple[int, dict[str, Any]] | None:
        self._idempotency.claim(
            tenant_id=tenant_id, endpoint=endpoint, key=idempotency_key
        )
        existing = self._idempotency.get(
            tenant_id=tenant_id, endpoint=endpoint, key=idempotency_key
        )
        if existing is None:
            return None
        if not self._idempotency.is_exact_replay(existing, _fingerprint(raw_body)):
            raise ApiError(
                409,
                "idempotency_conflict",
                "Idempotency key was already used with a different payload.",
            )
        return existing.status_code, existing.response_payload

    def _store_idempotency(
        self,
        *,
        endpoint: str,
        idempotency_key: str,
        raw_body: bytes,
        status_code: int,
        payload: dict[str, Any],
        scope: ScopeContext,
    ) -> None:
        self._idempotency.save(
            tenant_id=scope.tenant_id,
            endpoint=endpoint,
            key=idempotency_key,
            request_fingerprint=_fingerprint(raw_body),
            response_fingerprint=_fingerprint(
                json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
            ),
            status_code=status_code,
            response_payload=payload,
            actor_employee_id=scope.actor_employee_id,
        )


def _fingerprint(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

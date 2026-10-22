"""The one approval engine — M06 §3a/§3b/§3c.

Transaction ownership lives here, not in the router. Every decision is one transaction covering the
status change, the appended `approvals_decisions` row, the subject adapter's callback, the audit row
and the domain events (R-AP-16); a subject-validation failure rolls the whole thing back, so a
half-approved request is not a reachable state.

`create()` is the exception, and deliberately so: subject modules call it from **inside** their own
submission transaction, so it writes and flushes but never commits. The caller owns the commit and
the `Idempotency-Key` claim for its own endpoint — which is why `create` takes no key. Idempotence
of creation itself is structural: `uq_approvals_one_pending_per_subject` (R-AP-04) means a retried
submit cannot produce a second pending request.

Notifications are written **synchronously in the same transaction** as the transition that caused
them (M06 §5.4, R-AP-16), through `notifications.service.record` — the owning module's public write
primitive, which this module calls and whose table it never touches. Delivery is poll-based with
no transport to fail (§12 Q14). The one thing that must not happen is the reverse — a notification
problem failing a decision (§11.3) — so every notification call site below is guarded and degrades
to a `WARN`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from humbee_sfa.core.business_date import IST_ZONE, to_business_date
from humbee_sfa.core.clock import Clock, SystemClock
from humbee_sfa.core.db import transaction
from humbee_sfa.core.deps import AccessTokenClaims
from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.core.settings import Settings, get_settings
from humbee_sfa.modules.approvals import policies, repository, schemas
from humbee_sfa.modules.approvals.contracts import (
    GRANTED_STATUSES,
    TERMINAL_STATUSES,
    TIMELINE_CURRENT,
    TIMELINE_DONE,
    TIMELINE_EDITED,
    TIMELINE_REJECTED,
    Actor,
    ApprovalStatus,
    ApprovalSubjectAdapter,
    DecisionAction,
    NotificationSpec,
    SubjectEditRejected,
    SubjectEvent,
    registry,
)
from humbee_sfa.modules.approvals.models import Decision, Request
from humbee_sfa.modules.approvals.routing import resolve_approver
from humbee_sfa.modules.notifications import service as notifications_service
from humbee_sfa.modules.org import service as org_service
from humbee_sfa.modules.org.scope import OrgResource, ScopeContext, ScopeResolver
from humbee_sfa.platform.audit import AuditLogService
from humbee_sfa.platform.domain_events import DomainEventPublisher
from humbee_sfa.platform.idempotency import IdempotencyService

logger = structlog.get_logger("humbee_sfa.approvals")

AUDIT_ENTITY = "approvals_request"

# Which timeline `state` each recorded action renders as (M06 §3a.5). `edited` doubles as the
# escalation step, matching the design-system component's four accepted values (§12 Q6).
_TIMELINE_STATE: dict[str, str] = {
    DecisionAction.SUBMITTED: TIMELINE_DONE,
    DecisionAction.ROUTED: TIMELINE_EDITED,
    DecisionAction.ESCALATED: TIMELINE_EDITED,
    DecisionAction.EDITED: TIMELINE_EDITED,
    DecisionAction.APPROVED: TIMELINE_DONE,
    DecisionAction.AUTO_APPROVED: TIMELINE_DONE,
    DecisionAction.WITHDRAWN: TIMELINE_DONE,
    DecisionAction.REJECTED: TIMELINE_REJECTED,
}

_APPROVE = "approve"
_REJECT = "reject"
_EDIT_AND_APPROVE = "edit-and-approve"
_WITHDRAW = "withdraw"

_TERMINAL_STATUS_BY_ACTION: dict[str, ApprovalStatus] = {
    _APPROVE: ApprovalStatus.APPROVED,
    _EDIT_AND_APPROVE: ApprovalStatus.APPROVED_WITH_EDITS,
    _REJECT: ApprovalStatus.REJECTED,
    _WITHDRAW: ApprovalStatus.WITHDRAWN,
}
# `ApprovalStatus` → `NotificationKind` (M06 §3.5). Not an identity map: the status enum and the
# notification-kind enum are different vocabularies, and `approved_with_edits` is the row the
# S-NOTIF list renders with the blue `Edit` icon, i.e. kind `edited` (§4 S-NOTIF).
_NOTIFICATION_KIND_BY_OUTCOME: dict[str, str] = {
    ApprovalStatus.APPROVED: "approved",
    ApprovalStatus.APPROVED_WITH_EDITS: "edited",
    ApprovalStatus.AUTO_APPROVED: "auto_approved",
    ApprovalStatus.REJECTED: "rejected",
    ApprovalStatus.WITHDRAWN: "withdrawn",
}

_DECISION_ACTION_BY_ACTION: dict[str, DecisionAction] = {
    _APPROVE: DecisionAction.APPROVED,
    _EDIT_AND_APPROVE: DecisionAction.APPROVED,
    _REJECT: DecisionAction.REJECTED,
    _WITHDRAW: DecisionAction.WITHDRAWN,
}


# ---------------------------------------------------------------------------
# Payload helpers
# ---------------------------------------------------------------------------


def _request_fingerprint(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()


def _response_fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _item_payload(request: Request, *, actor: Actor) -> dict[str, Any]:
    return schemas.ApprovalListItem(
        id=request.id,
        subject_type=request.subject_type,
        subject_id=request.subject_id,
        subject_version=request.subject_version,
        status=request.status,
        title=request.title,
        subtitle=request.subtitle,
        amount_paise=request.amount_paise,
        requester_id=request.requester_id,
        assigned_approver_id=request.assigned_approver_id,
        routing_reason=request.routing_reason,
        escalated_from_id=request.escalated_from_id,
        escalation_depth=request.escalation_depth,
        submitted_at=request.submitted_at,
        submitted_business_date=request.submitted_business_date,
        decided_at=request.decided_at,
        decided_by_id=request.decided_by_id,
        edit_applied=request.edit_applied,
        is_pending=request.status == ApprovalStatus.PENDING,
        is_granted=request.status in GRANTED_STATUSES,
        is_terminal=request.status in TERMINAL_STATUSES,
        can_decide=policies.can_decide(actor, request),
    ).model_dump(mode="json")


def _timeline_steps(decisions: list[Decision], *, status: str) -> list[schemas.TimelineStep]:
    """`decisions → steps`, with the synthetic trailing `current` step appended **only** while the
    request is pending (M06 §3a.5).

    Step *labels* ("Submitted · by R. Kumar · 10:24 AM") are composed by the client from these
    structured steps rather than server-side: rendering a name here would mean an org lookup per
    step, and the display strings for notifications are Story 2.3's concern.
    """

    steps = [
        schemas.TimelineStep(
            state=_TIMELINE_STATE.get(decision.action, TIMELINE_DONE),
            action=decision.action,
            actor_id=decision.actor_id,
            actor_role=decision.actor_role,
            note=decision.note,
            occurred_at=decision.occurred_at,
        )
        for decision in decisions
    ]
    if status == ApprovalStatus.PENDING:
        steps.append(
            schemas.TimelineStep(
                state=TIMELINE_CURRENT,
                action="awaiting_decision",
                actor_id=None,
                actor_role=None,
                note=None,
                occurred_at=None,
            )
        )
    return steps


def _encode_cursor(request: Request) -> str:
    return f"{request.submitted_at.isoformat()}|{request.id}"


def _decode_cursor(cursor: str | None) -> tuple[datetime, str] | None:
    if not cursor:
        return None
    submitted_at, _, request_id = cursor.partition("|")
    try:
        return datetime.fromisoformat(submitted_at), request_id
    except ValueError as exc:
        raise ApiError(422, "invalid_cursor", "The pagination cursor is not valid.") from exc


def _subject_types_for_filter(filter_key: str | None) -> tuple[str, ...] | None:
    if filter_key is None:
        return None
    try:
        subject_types = schemas.FILTER_TO_SUBJECT_TYPES[filter_key]
    except KeyError as exc:
        raise ApiError(422, "invalid_subject_type_filter", "Unknown subject type filter.") from exc
    return subject_types or None


def _validate_date_range(from_date: date | None, to_date: date | None) -> None:
    if from_date is not None and to_date is not None and from_date > to_date:
        raise ApiError(422, "invalid_date_range", "`from` must be on or before `to`.")


def _seconds_to_hours(value: float | None) -> float | None:
    if value is None:
        return None
    return value / 3600.0


def _decision_window(
    from_date: date | None, to_date: date | None, *, day_boundary_hour: int
) -> tuple[datetime | None, datetime | None]:
    decided_from = (
        datetime.combine(from_date, time(hour=day_boundary_hour), tzinfo=IST_ZONE).astimezone(UTC)
        if from_date is not None
        else None
    )
    decided_before = (
        datetime.combine(
            to_date + timedelta(days=1),
            time(hour=day_boundary_hour),
            tzinfo=IST_ZONE,
        ).astimezone(UTC)
        if to_date is not None
        else None
    )
    return decided_from, decided_before


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ApprovalLatencySummary:
    """Scoped approval-speed snapshot for reporting. Hours; None when that cohort is empty."""

    median_hours: float | None
    p90_hours: float | None
    pending_median_hours: float | None
    decided_count: int
    pending_count: int


class ApprovalService:
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
        self._audit = AuditLogService(session)
        self._events = DomainEventPublisher(session, self._clock)
        self._idempotency = IdempotencyService(session)

    # -- scope / idempotency ----------------------------------------------

    def _scope(self, claims: AccessTokenClaims) -> ScopeContext:
        # Approval requests are activity data: SELF for a Sales Person, OWN_TREE for a Manager,
        # ORG for an Admin (M06 §9). Decision rights are a separate check (§3b.5).
        return ScopeResolver.resolve_from_claims(claims, OrgResource.ACTIVITY_DATA)

    def _check_idempotency(
        self, *, endpoint: str, idempotency_key: str, raw_body: bytes, tenant_id: str
    ) -> tuple[int, dict[str, Any]] | None:
        self._idempotency.claim(tenant_id=tenant_id, endpoint=endpoint, key=idempotency_key)
        existing = self._idempotency.get(
            tenant_id=tenant_id, endpoint=endpoint, key=idempotency_key
        )
        if existing is None:
            return None
        if not self._idempotency.is_exact_replay(existing, _request_fingerprint(raw_body)):
            raise ApiError(
                409,
                "idempotency_conflict",
                "Idempotency key was already used with a different payload.",
            )
        # R-AP-28: a replay returns the original response, never a 409.
        return existing.status_code, existing.response_payload

    def _store_idempotency(
        self,
        *,
        endpoint: str,
        idempotency_key: str,
        raw_body: bytes,
        status_code: int,
        payload: dict[str, Any],
        actor: Actor,
    ) -> None:
        self._idempotency.save(
            tenant_id=actor.tenant_id,
            endpoint=endpoint,
            key=idempotency_key,
            request_fingerprint=_request_fingerprint(raw_body),
            response_fingerprint=_response_fingerprint(payload),
            status_code=status_code,
            response_payload=payload,
            actor_employee_id=actor.employee_id or None,
        )

    # -- reads -------------------------------------------------------------

    def list_requests(
        self,
        *,
        claims: AccessTokenClaims,
        status: str | None,
        subject_type_filter: str | None,
        assigned_to_me: bool,
        from_date: date | None,
        to_date: date | None,
        cursor: str | None,
        limit: int,
    ) -> dict[str, Any]:
        """S-AP1. Rows come from `approvals_requests` alone — `title`, `subtitle` and
        `amount_paise` were denormalised at write time, so the inbox needs no call into a subject
        module or Humbee and still renders when Humbee is down (M06 §5.1.4)."""

        _validate_date_range(from_date, to_date)
        scope = self._scope(claims)
        actor = Actor.from_claims(claims)
        subject_types = _subject_types_for_filter(subject_type_filter)
        statuses = (status,) if status else (ApprovalStatus.PENDING,)
        additional_subject_types = policies.additional_decision_subject_types(actor)
        excluded_subject_types = policies.excluded_subject_types(actor)
        decided_from, decided_before = (
            _decision_window(
                from_date, to_date, day_boundary_hour=self._settings.day_boundary_hour_ist
            )
            if status is not None and status != ApprovalStatus.PENDING
            else (None, None)
        )
        rows = repository.list_visible(
            self._session,
            scope=scope,
            statuses=statuses,
            subject_types=subject_types,
            assigned_approver_id=actor.employee_id if assigned_to_me else None,
            actionable_by_employee_id=actor.employee_id,
            additional_decision_subject_types=additional_subject_types,
            excluded_subject_types=excluded_subject_types,
            decided_from=decided_from,
            decided_before=decided_before,
            cursor=_decode_cursor(cursor),
            limit=limit,
        )
        pending_count = repository.count_visible(
            self._session,
            scope=scope,
            statuses=(ApprovalStatus.PENDING,),
            subject_types=subject_types,
            assigned_approver_id=actor.employee_id if assigned_to_me else None,
            actionable_by_employee_id=actor.employee_id,
            additional_decision_subject_types=additional_subject_types,
            excluded_subject_types=excluded_subject_types,
        )
        return schemas.ApprovalListResponse(
            items=[schemas.ApprovalListItem(**_item_payload(row, actor=actor)) for row in rows],
            pending_count=pending_count,
            next_cursor=_encode_cursor(rows[-1]) if len(rows) == limit else None,
        ).model_dump(mode="json")

    def list_mine(
        self, *, claims: AccessTokenClaims, cursor: str | None, limit: int
    ) -> dict[str, Any]:
        """S-AP3 — every request I raised, all statuses, newest first (M06 §5.3)."""

        scope = self._scope(claims)
        actor = Actor.from_claims(claims)
        rows = repository.list_visible(
            self._session,
            scope=scope,
            requester_id=actor.employee_id,
            cursor=_decode_cursor(cursor),
            limit=limit,
        )
        pending_count = repository.count_visible(
            self._session,
            scope=scope,
            statuses=(ApprovalStatus.PENDING,),
            requester_id=actor.employee_id,
        )
        return schemas.ApprovalListResponse(
            items=[schemas.ApprovalListItem(**_item_payload(row, actor=actor)) for row in rows],
            pending_count=pending_count,
            next_cursor=_encode_cursor(rows[-1]) if len(rows) == limit else None,
        ).model_dump(mode="json")

    def get_summary(self, *, claims: AccessTokenClaims) -> dict[str, Any]:
        """One scoped source for every pending count — dashboard, summary bar, chips (R-AP-30)."""

        scope = self._scope(claims)
        actor = Actor.from_claims(claims)
        by_subject_type = repository.count_pending_by_subject_type(
            self._session,
            scope=scope,
            actionable_by_employee_id=actor.employee_id,
            additional_decision_subject_types=policies.additional_decision_subject_types(actor),
            excluded_subject_types=policies.excluded_subject_types(actor),
        )
        by_filter = {
            filter_key: sum(by_subject_type.get(name, 0) for name in subject_types)
            for filter_key, subject_types in schemas.FILTER_TO_SUBJECT_TYPES.items()
            if subject_types
        }
        return schemas.ApprovalSummaryResponse(
            pending_total=sum(by_subject_type.values()), pending_by_filter=by_filter
        ).model_dump(mode="json")

    def latency_summary(
        self, claims: AccessTokenClaims, *, from_date: date, to_date: date
    ) -> ApprovalLatencySummary:
        """Median/p90 decision time and pending age — one SQL aggregate, not a paged list."""

        _validate_date_range(from_date, to_date)
        scope = self._scope(claims)
        decided_from, decided_before = _decision_window(
            from_date, to_date, day_boundary_hour=self._settings.day_boundary_hour_ist
        )
        assert decided_from is not None and decided_before is not None
        median_s, p90_s, pending_s, decided_count, pending_count = repository.latency_summary(
            self._session,
            scope=scope,
            decided_from=decided_from,
            decided_before=decided_before,
            as_of=self._clock.now_utc(),
        )
        return ApprovalLatencySummary(
            median_hours=_seconds_to_hours(median_s),
            p90_hours=_seconds_to_hours(p90_s),
            pending_median_hours=_seconds_to_hours(pending_s),
            decided_count=decided_count,
            pending_count=pending_count,
        )

    def get_detail(self, *, claims: AccessTokenClaims, approval_id: str) -> dict[str, Any]:
        """S-AP2. The subject's blocks and advisories come from the adapter; the engine renders
        them generically and knows nothing about atta, beats or leave (M06 §3a.4)."""

        scope = self._scope(claims)
        actor = Actor.from_claims(claims)
        request = self._load_visible(scope, actor, approval_id)
        adapter = registry.get(request.subject_type)

        decidable = policies.can_decide(actor, request)
        editable_fields = (
            adapter.editable_fields(self._session, subject_id=request.subject_id)
            if decidable
            else []
        )
        blocks = adapter.detail(self._session, subject_id=request.subject_id, viewer=actor)
        deep_link = adapter.deep_link(request, actor)
        return schemas.ApprovalDetailResponse(
            request=schemas.ApprovalListItem(**_item_payload(request, actor=actor)),
            can_withdraw=policies.can_withdraw(actor, request),
            # R-AP-13: editable only while pending, only for the assigned approver, and only when
            # the adapter declares fields.
            is_editable=decidable and bool(editable_fields),
            blocks=[
                schemas.DetailBlock(kind=block.kind, label=block.label, payload=block.payload)
                for block in blocks.blocks
            ],
            advisories=[
                schemas.Advisory(code=item.code, severity=item.severity, message=item.message)
                for item in adapter.advisories(self._session, subject_id=request.subject_id)
            ],
            editable_fields=[
                schemas.EditableFieldSchema(**vars(item)) for item in editable_fields
            ],
            timeline=_timeline_steps(
                repository.list_decisions(
                    self._session, tenant_id=actor.tenant_id, request_id=request.id
                ),
                status=request.status,
            ),
            deep_link_type=deep_link.target_type,
            deep_link_id=deep_link.target_id,
        ).model_dump(mode="json")

    def get_timeline(self, *, claims: AccessTokenClaims, approval_id: str) -> dict[str, Any]:
        scope = self._scope(claims)
        actor = Actor.from_claims(claims)
        request = self._load_visible(scope, actor, approval_id)
        return schemas.TimelineResponse(
            items=_timeline_steps(
                repository.list_decisions(
                    self._session, tenant_id=actor.tenant_id, request_id=request.id
                ),
                status=request.status,
            )
        ).model_dump(mode="json")

    def get_editable_fields(
        self, *, claims: AccessTokenClaims, approval_id: str
    ) -> dict[str, Any]:
        scope = self._scope(claims)
        actor = Actor.from_claims(claims)
        request = self._load_visible(scope, actor, approval_id)
        fields = (
            registry.get(request.subject_type).editable_fields(
                self._session, subject_id=request.subject_id
            )
            if policies.can_decide(actor, request)
            else []
        )
        return schemas.EditableFieldsResponse(
            items=[schemas.EditableFieldSchema(**vars(item)) for item in fields]
        ).model_dump(mode="json")

    def _load_visible(self, scope: ScopeContext, actor: Actor, approval_id: str) -> Request:
        request = repository.get_visible(
            self._session,
            scope=scope,
            request_id=approval_id,
            excluded_subject_types=policies.excluded_subject_types(actor),
        )
        if request is None:
            # 404, not 403: out of scope must not leak existence (M06 §11.2).
            raise ApiError(404, "approval_not_found", "Approval request was not found.")
        return request

    # -- creation (called by subject modules, inside their transaction) ----

    def create(
        self,
        *,
        tenant_id: str,
        subject_type: str,
        subject_id: str,
        requester_id: str,
        request_id: str | None = None,
    ) -> Request:
        """Route and persist a new request (M06 §3c.2, first three rows of the transition table).

        Does **not** commit: the subject module that calls this owns the transaction, so its own
        state change and this request are one atomic unit (R-AP-16).
        """

        adapter = registry.get(subject_type)
        requester = org_service.get_employee(
            self._session, tenant_id=tenant_id, employee_id=requester_id
        )
        actor = Actor(tenant_id=tenant_id, employee_id=requester_id, role=requester.role_code)
        now = self._clock.now_utc()
        submitted_business_date = to_business_date(now, self._settings.day_boundary_hour_ist)

        existing = repository.pending_for_subject(
            self._session, tenant_id=tenant_id, subject_type=subject_type, subject_id=subject_id
        )
        if existing is not None:
            raise ApiError(
                409,
                "duplicate_pending_request",
                "This subject already has a pending approval request.",
                details={"request_id": existing.id},
            )

        outcome = resolve_approver(
            self._session,
            tenant_id=tenant_id,
            requester_id=requester_id,
        )
        summary = adapter.summary(self._session, subject_id=subject_id, viewer=actor)
        status = ApprovalStatus.AUTO_APPROVED if outcome.auto_decide else ApprovalStatus.PENDING

        try:
            request = repository.insert_request(
                self._session,
                tenant_id=tenant_id,
                subject_type=subject_type,
                subject_id=subject_id,
                requester_id=requester_id,
                requester_manager_id=outcome.direct_parent_id,
                assigned_approver_id=outcome.approver_id,
                routing_reason=outcome.routing_reason,
                escalated_from_id=None,
                escalation_depth=0,
                status=status,
                title=summary.title,
                subtitle=summary.subtitle,
                amount_paise=summary.amount_paise,
                submitted_at=now,
                submitted_business_date=submitted_business_date,
                decided_at=now if outcome.auto_decide else None,
                decided_by_id=None,
                actor_employee_id=requester_id,
            )
        except IntegrityError as exc:
            # The partial unique index is the real guard behind the pre-check above (R-AP-04).
            if "uq_approvals_one_pending_per_subject" in str(getattr(exc, "orig", exc)):
                raise ApiError(
                    409,
                    "duplicate_pending_request",
                    "This subject already has a pending approval request.",
                ) from exc
            raise

        repository.append_decision(
            self._session,
            tenant_id=tenant_id,
            request_id=request.id,
            action=DecisionAction.SUBMITTED,
            occurred_at=now,
            actor_id=requester_id,
            actor_role=requester.role_code,
        )

        self._audit.record_transition(
            tenant_id=tenant_id,
            entity_type=AUDIT_ENTITY,
            entity_id=request.id,
            from_state=None,
            to_state=status,
            actor_employee_id=requester_id,
            request_id=request_id,
            change_payload={
                "transition": "approval_requested",
                "subject_type": subject_type,
                "subject_id": subject_id,
                "routing_reason": request.routing_reason,
                "escalation_depth": request.escalation_depth,
            },
        )

        if outcome.auto_decide:
            # A requester at the top of the hierarchy has no human approver.
            repository.append_decision(
                self._session,
                tenant_id=tenant_id,
                request_id=request.id,
                action=DecisionAction.AUTO_APPROVED,
                occurred_at=now,
                note="No approver above the requester; auto-approved at submission.",
            )
            self._run_callbacks_and_publish(
                adapter,
                request=request,
                outcome_status=ApprovalStatus.AUTO_APPROVED,
                reason=None,
                actor=Actor.system(tenant_id),
                occurred_at=now,
            )
        else:
            self._notify_assigned(adapter, request=request)

        logger.info(
            "approval_requested",
            approval_request_id=request.id,
            subject_type=subject_type,
            subject_id=subject_id,
            status=request.status,
            routing_reason=request.routing_reason,
            escalation_depth=request.escalation_depth,
        )
        return request

    # -- decisions ---------------------------------------------------------

    def approve(
        self,
        *,
        claims: AccessTokenClaims,
        approval_id: str,
        note: str | None,
        idempotency_key: str,
        raw_body: bytes,
        if_match: int | None,
        request_id: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        return self._decide(
            claims=claims,
            approval_id=approval_id,
            action=_APPROVE,
            note=note,
            patch=None,
            idempotency_key=idempotency_key,
            raw_body=raw_body,
            if_match=if_match,
            request_id=request_id,
        )

    def reject(
        self,
        *,
        claims: AccessTokenClaims,
        approval_id: str,
        reason: str,
        idempotency_key: str,
        raw_body: bytes,
        if_match: int | None,
        request_id: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        return self._decide(
            claims=claims,
            approval_id=approval_id,
            action=_REJECT,
            note=reason,
            patch=None,
            idempotency_key=idempotency_key,
            raw_body=raw_body,
            if_match=if_match,
            request_id=request_id,
        )

    def edit_and_approve(
        self,
        *,
        claims: AccessTokenClaims,
        approval_id: str,
        patch: dict[str, Any],
        note: str | None,
        idempotency_key: str,
        raw_body: bytes,
        if_match: int | None,
        request_id: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        return self._decide(
            claims=claims,
            approval_id=approval_id,
            action=_EDIT_AND_APPROVE,
            note=note,
            patch=patch,
            idempotency_key=idempotency_key,
            raw_body=raw_body,
            if_match=if_match,
            request_id=request_id,
        )

    def withdraw(
        self,
        *,
        claims: AccessTokenClaims,
        approval_id: str,
        reason: str | None,
        idempotency_key: str,
        raw_body: bytes,
        if_match: int | None,
        request_id: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        return self._decide(
            claims=claims,
            approval_id=approval_id,
            action=_WITHDRAW,
            note=reason,
            patch=None,
            idempotency_key=idempotency_key,
            raw_body=raw_body,
            if_match=if_match,
            request_id=request_id,
        )

    def _decide(
        self,
        *,
        claims: AccessTokenClaims,
        approval_id: str,
        action: str,
        note: str | None,
        patch: dict[str, Any] | None,
        idempotency_key: str,
        raw_body: bytes,
        if_match: int | None,
        request_id: str | None,
    ) -> tuple[int, dict[str, Any]]:
        """One transaction per state transition: lock, authorise, mutate the subject, append the
        decision, run the adapter callback, audit, publish, claim the key, commit."""

        actor = Actor.from_claims(claims)
        endpoint = f"/api/v1/approvals/{approval_id}/{action}"
        target_status = _TERMINAL_STATUS_BY_ACTION[action]
        # R-AP-16: apply_edit, the status change, the decision row, the callback and the audit row
        # are one unit. A subject-validation failure rolls all of it back.
        with transaction(self._session):
            replay = self._check_idempotency(
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                raw_body=raw_body,
                tenant_id=actor.tenant_id,
            )
            if replay is not None:
                return replay

            request = repository.lock_request(
                self._session, tenant_id=actor.tenant_id, request_id=approval_id
            )
            if request is None:
                raise ApiError(404, "approval_not_found", "Approval request was not found.")
            adapter = registry.get(request.subject_type)
            now = self._clock.now_utc()
            previous_status = request.status

            if action == _WITHDRAW:
                policies.require_withdraw_rights(actor, request)
            else:
                policies.require_decision_rights(actor, request)
            policies.require_subject_version(
                request, if_match, required=action == _EDIT_AND_APPROVE
            )

            decision_note = (
                policies.require_reason(note)
                if action == _REJECT
                else (note.strip() if note and note.strip() else None)
            )

            if action == _EDIT_AND_APPROVE:
                self._apply_subject_edit(
                    adapter, request=request, patch=patch or {}, actor=actor, occurred_at=now
                )

            repository.append_decision(
                self._session,
                tenant_id=actor.tenant_id,
                request_id=request.id,
                action=_DECISION_ACTION_BY_ACTION[action],
                occurred_at=now,
                actor_id=actor.employee_id,
                actor_role=actor.role,
                note=decision_note,
            )
            repository.apply_decision_outcome(
                self._session,
                request=request,
                status=target_status,
                decided_at=now,
                decided_by_id=actor.employee_id,
                decision_note=decision_note,
                edit_applied=action == _EDIT_AND_APPROVE,
            )
            self._run_callbacks_and_publish(
                adapter,
                request=request,
                outcome_status=target_status,
                reason=decision_note,
                actor=actor,
                occurred_at=now,
            )
            self._audit.record_transition(
                tenant_id=actor.tenant_id,
                entity_type=AUDIT_ENTITY,
                entity_id=request.id,
                from_state=previous_status,
                to_state=target_status,
                actor_employee_id=actor.employee_id,
                reason=decision_note,
                request_id=request_id,
                change_payload={
                    "transition": action,
                    "subject_type": request.subject_type,
                    "subject_id": request.subject_id,
                    "subject_version": request.subject_version,
                },
            )

            payload = _item_payload(request, actor=actor)
            self._store_idempotency(
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                raw_body=raw_body,
                status_code=200,
                payload=payload,
                actor=actor,
            )

        logger.info(
            "approval_decided",
            approval_request_id=approval_id,
            subject_type=payload["subject_type"],
            subject_id=payload["subject_id"],
            status=payload["status"],
            actor_employee_id=actor.employee_id,
        )
        return 200, payload

    def _apply_subject_edit(
        self,
        adapter: ApprovalSubjectAdapter,
        *,
        request: Request,
        patch: dict[str, Any],
        actor: Actor,
        occurred_at: datetime,
    ) -> None:
        fields = adapter.editable_fields(self._session, subject_id=request.subject_id)
        policies.require_editable(fields)
        try:
            result = adapter.apply_edit(
                self._session, subject_id=request.subject_id, patch=patch, actor=actor
            )
        except SubjectEditRejected as exc:
            raise ApiError(
                422,
                "subject_edit_rejected",
                exc.message,
                details={"field": exc.field_key} if exc.field_key else None,
            ) from exc

        repository.apply_edit_result(
            self._session,
            request=request,
            subject_version=result.subject_version,
            title=result.summary.title,
            subtitle=result.summary.subtitle,
            amount_paise=result.summary.amount_paise,
        )
        repository.append_decision(
            self._session,
            tenant_id=request.tenant_id,
            request_id=request.id,
            action=DecisionAction.EDITED,
            occurred_at=occurred_at,
            actor_id=actor.employee_id,
            actor_role=actor.role,
            edit_patch=result.patch_applied,
        )
        self._publish_subject_events(result.events, request=request, actor=actor)

    def _run_callbacks_and_publish(
        self,
        adapter: ApprovalSubjectAdapter,
        *,
        request: Request,
        outcome_status: ApprovalStatus,
        reason: str | None,
        actor: Actor,
        occurred_at: datetime,
    ) -> None:
        """The subject callback runs *inside* this transaction: if the beat/order/leave cannot be
        transitioned, the approval rolls back with it (M06 §11.3)."""

        if outcome_status in GRANTED_STATUSES:
            subject_events = adapter.on_approved(self._session, request=request)
        elif outcome_status == ApprovalStatus.REJECTED:
            subject_events = adapter.on_rejected(
                self._session, request=request, reason=reason or ""
            )
        else:
            subject_events = adapter.on_withdrawn(self._session, request=request)

        self._publish_subject_events(subject_events, request=request, actor=actor)
        # One call site for every terminal outcome — decision, withdrawal and the auto-approval
        # `create()` performs — so a new outcome cannot land without its notification.
        self._notify_outcome(
            adapter, request=request, outcome=outcome_status, occurred_at=occurred_at
        )

    # -- notification emission (M06 §5.4) ----------------------------------
    #
    # Who gets told is the **engine's** call, not the adapter's: only the engine knows the routing
    # and the assignment. What they are told is the **adapter's**: it owns the materialised strings
    # (R-AP-22). `dedupe_key` is derived from the request id and the event, so a replayed decision,
    # a retried job or a re-route back to the same approver all collapse onto one row (R-AP-24).

    def _notify_assigned(self, adapter: ApprovalSubjectAdapter, *, request: Request) -> None:
        """Tell the direct manager that a request is awaiting their decision."""

        approver_id = request.assigned_approver_id
        if approver_id is None:
            return
        self._write_notification(
            adapter,
            request=request,
            recipient_id=approver_id,
            kind="submitted",
            title=request.title,
            subtitle=request.subtitle,
            dedupe_key=f"approval:{request.id}:assigned:{approver_id}",
            deep_link_type="approval_request",
            deep_link_id=request.id,
        )

    def _notify_outcome(
        self,
        adapter: ApprovalSubjectAdapter,
        *,
        request: Request,
        outcome: ApprovalStatus,
        occurred_at: datetime,
    ) -> None:
        kind = _NOTIFICATION_KIND_BY_OUTCOME.get(str(outcome))
        if kind is None:
            return
        # A withdrawal is addressed to whoever was waiting on it (Flow 6); every other outcome is
        # addressed to the requester.
        recipient_id = (
            (request.assigned_approver_id or request.requester_id)
            if outcome == ApprovalStatus.WITHDRAWN
            else request.requester_id
        )
        spec = self._subject_notification(
            adapter, request=request, outcome=outcome, occurred_at=occurred_at
        )
        self._write_notification(
            adapter,
            request=request,
            recipient_id=recipient_id,
            # An adapter may name the kind itself; anything the table does not accept falls back to
            # the outcome mapping rather than failing the decision.
            kind=(
                spec.kind
                if spec is not None and spec.kind in notifications_service.KINDS
                else kind
            ),
            title=spec.title if spec is not None else request.title,
            subtitle=spec.subtitle if spec is not None else request.subtitle,
            dedupe_key=(
                spec.dedupe_key
                if spec is not None and spec.dedupe_key
                else f"approval:{request.id}:{kind}"
            ),
            deep_link_type=spec.deep_link_type if spec is not None else None,
            deep_link_id=spec.deep_link_id if spec is not None else None,
        )

    def _subject_notification(
        self,
        adapter: ApprovalSubjectAdapter,
        *,
        request: Request,
        outcome: ApprovalStatus,
        occurred_at: datetime,
    ) -> NotificationSpec | None:
        """`adapter.notification()` for subject types that implement it.

        An adapter that has not got round to this method yet will raise `501`, and an outcome notification is not worth
        rolling a committed-quality decision back for (§11.3). `None` means "fall back to the
        request's own denormalised strings", which are already materialised and correct.
        """

        try:
            return adapter.notification(request, outcome, occurred_at=occurred_at)
        except Exception:
            logger.warning(
                "approval_notification_spec_unavailable",
                approval_request_id=request.id,
                subject_type=request.subject_type,
                outcome=str(outcome),
                exc_info=True,
            )
            return None

    def _write_notification(
        self,
        adapter: ApprovalSubjectAdapter,
        *,
        request: Request,
        recipient_id: str,
        kind: str,
        title: str,
        subtitle: str | None,
        dedupe_key: str,
        deep_link_type: str | None = None,
        deep_link_id: str | None = None,
    ) -> None:
        """The single seam into `notifications`. Runs in this transaction and never commits."""

        try:
            if deep_link_type is None:
                # Resolved per viewer: the requester's row points at the subject, the approver's at
                # the request. Only the adapter knows which, so it decides (M06 §3a.4).
                link = adapter.deep_link(request, self._viewer(request.tenant_id, recipient_id))
                deep_link_type, deep_link_id = link.target_type, link.target_id
            notifications_service.record(
                self._session,
                tenant_id=request.tenant_id,
                recipient_id=recipient_id,
                kind=kind,
                title=title,
                subtitle=subtitle,
                deep_link_type=deep_link_type,
                deep_link_id=deep_link_id,
                source_request_id=request.id,
                dedupe_key=dedupe_key,
            )
        except Exception:
            # §11.3: notification failure never fails a decision. The transition still commits;
            # this is the line an operator reads when a feed row is missing.
            logger.warning(
                "approval_notification_write_skipped",
                approval_request_id=request.id,
                subject_type=request.subject_type,
                kind=kind,
                exc_info=True,
            )

    def _viewer(self, tenant_id: str, employee_id: str) -> Actor:
        try:
            employee = org_service.get_employee(
                self._session, tenant_id=tenant_id, employee_id=employee_id
            )
        except ApiError:
            return Actor(tenant_id=tenant_id, employee_id=employee_id, role="")
        return Actor(
            tenant_id=tenant_id, employee_id=employee_id, role=employee.role_code
        )

    def _publish_subject_events(
        self, subject_events: list[SubjectEvent] | None, *, request: Request, actor: Actor
    ) -> None:
        for event in subject_events or []:
            self._events.publish(
                tenant_id=request.tenant_id,
                stream=event.stream,
                event_type=event.event_type,
                aggregate_type=event.aggregate_type,
                aggregate_id=event.aggregate_id,
                payload=event.payload,
                actor_employee_id=actor.employee_id or None,
            )

# ---------------------------------------------------------------------------
# The interface consuming modules actually use (M06 §10, "Internal (not HTTP)")
# ---------------------------------------------------------------------------


def create(
    session: Session,
    *,
    tenant_id: str,
    subject_type: str,
    subject_id: str,
    requester_id: str,
    clock: Clock | None = None,
    request_id: str | None = None,
) -> Request:
    """Create and route an approval request from inside the caller's transaction (no commit)."""

    return ApprovalService(session, clock=clock).create(
        tenant_id=tenant_id,
        subject_type=subject_type,
        subject_id=subject_id,
        requester_id=requester_id,
        request_id=request_id,
    )


def pending_for_subject(
    session: Session, *, tenant_id: str, subject_type: str, subject_id: str
) -> Request | None:
    """The pending request for a subject, if any — how a subject screen shows its own
    "awaiting approval" banner without duplicating approval state (R-AP-01)."""

    return repository.pending_for_subject(
        session, tenant_id=tenant_id, subject_type=subject_type, subject_id=subject_id
    )


def withdraw_for_subject(
    session: Session,
    *,
    tenant_id: str,
    subject_type: str,
    subject_id: str,
    clock: Clock | None = None,
) -> Request | None:
    """System-initiated withdrawal of a subject's own pending request — e.g. a subject module
    auto-withdrawing its request when the subject itself is deactivated, with no human decision
    (M07 R-BEAT-28). Runs in the caller's transaction and never commits; a no-op if nothing is
    pending, so callers may call it unconditionally.
    """

    request = repository.pending_for_subject(
        session, tenant_id=tenant_id, subject_type=subject_type, subject_id=subject_id
    )
    if request is None:
        return None

    # Re-lock and re-check: a human decision may have landed between the pre-check above and here
    # (repository.lock_request takes the same `FOR UPDATE` every decision path takes, so a
    # concurrent `_decide()` either already committed a terminal status we must not overwrite, or
    # is waiting on this lock and will see WITHDRAWN once we commit).
    request = repository.lock_request(session, tenant_id=tenant_id, request_id=request.id)
    if request is None or request.status != ApprovalStatus.PENDING:
        return None

    service = ApprovalService(session, clock=clock)
    now = service._clock.now_utc()
    actor = Actor.system(tenant_id)
    previous_status = request.status
    repository.append_decision(
        session,
        tenant_id=tenant_id,
        request_id=request.id,
        action=DecisionAction.WITHDRAWN,
        occurred_at=now,
        note="Auto-withdrawn: subject deactivated.",
    )
    repository.apply_decision_outcome(
        session, request=request, status=ApprovalStatus.WITHDRAWN, decided_at=now, decided_by_id=None
    )
    service._run_callbacks_and_publish(
        registry.get(subject_type),
        request=request,
        outcome_status=ApprovalStatus.WITHDRAWN,
        reason=None,
        actor=actor,
        occurred_at=now,
    )
    service._audit.record_transition(
        tenant_id=tenant_id,
        entity_type=AUDIT_ENTITY,
        entity_id=request.id,
        from_state=previous_status,
        to_state=ApprovalStatus.WITHDRAWN,
        actor_employee_id=None,
        reason="Auto-withdrawn: subject deactivated.",
        request_id=request.id,
        change_payload={
            "transition": "system_withdraw",
            "subject_type": subject_type,
            "subject_id": subject_id,
        },
    )
    return request


__all__ = [
    "ApprovalLatencySummary",
    "ApprovalService",
    "create",
    "pending_for_subject",
    "withdraw_for_subject",
]

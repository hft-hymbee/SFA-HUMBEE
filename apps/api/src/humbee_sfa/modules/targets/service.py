"""Targets business logic — M13 §3a, §6, §7.

This module sets targets and nothing else. Achievement is never written, derived or stored here
(R-TGT-01, INV-14): for `sales` it is Humbee's, and for `outlets`/`leads` it is an SFA count owned
by reporting. A target row is therefore a denominator, and reading one never touches Humbee.

Scope: a Manager sets targets for sales people and managers in their reporting tree, an Admin for
any hierarchy member in the org, a Sales Person for nobody (R-TGT-05). Admins cannot hold a target.
The subject is loaded through `org`'s scoped read, so an out-of-tree employee is a 404 before any
rule below runs.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from humbee_sfa.core.business_date import to_business_date
from humbee_sfa.core.clock import Clock, SystemClock
from humbee_sfa.core.conventions import generate_ulid
from humbee_sfa.core.db import transaction
from humbee_sfa.core.deps import AccessTokenClaims
from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.core.security import encrypt_phone, hmac_phone
from humbee_sfa.core.settings import Settings, get_settings
from humbee_sfa.integration.humbee.targets import (
    HumbeeTargetManufacturerProvider,
    TargetManufacturer,
    TargetManufacturerMasterUnavailable,
)
from humbee_sfa.modules.org import service as org_service
from humbee_sfa.modules.org.geography_service import list_employee_zone_labels
from humbee_sfa.modules.org.scope import OrgResource, ScopeContext, ScopeResolver
from humbee_sfa.modules.org.service import OrgService
from humbee_sfa.modules.targets import policies, repository, schemas
from humbee_sfa.modules.targets.models import Lead, Target, TargetManufacturerLine
from humbee_sfa.platform.audit import AuditLogService
from humbee_sfa.platform.domain_events import DomainEventPublisher
from humbee_sfa.platform.idempotency import IdempotencyService

logger = structlog.get_logger("humbee_sfa.targets")

STREAM = "targets"
AGGREGATE = "target"
AUDIT_ENTITY = "target"

TARGET_SET = "target_set"
TARGET_UPDATED = "target_updated"
TARGET_REMOVED = "target_removed"
LEAD_CAPTURED = "lead_captured"


def _fingerprint(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()


def _derived_value(body: schemas.TargetShape) -> int | None:
    """A sales target stores no single `target_value` — it has no single basis, so `_payload`
    derives the amount/volume rollups from the lines instead (R-TGT-09). Every other type carries
    the value the manager typed."""

    if body.lines:
        return None
    return body.target_value


def _line_total(lines: list[TargetManufacturerLine], basis: str) -> int | None:
    values = [line.line_value for line in lines if line.line_basis == basis]
    return sum(values) if values else None


class TargetService:
    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        clock: Clock | None = None,
        manufacturer_port: HumbeeTargetManufacturerProvider | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._clock = clock or SystemClock()
        self._manufacturer_port = manufacturer_port
        self._audit = AuditLogService(session)
        self._events = DomainEventPublisher(session, self._clock)
        self._idempotency = IdempotencyService(session)

    # -- shared helpers -------------------------------------------------------

    def _scope(self, claims: AccessTokenClaims) -> ScopeContext:
        return ScopeResolver.resolve_from_claims(claims, OrgResource.EMPLOYEE)

    def _today(self) -> date:
        return to_business_date(self._clock.now_utc(), self._settings.day_boundary_hour_ist)

    def _check_idempotency(
        self, *, tenant_id: str, endpoint: str, idempotency_key: str, raw_body: bytes
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
        return existing.status_code, dict(existing.response_payload)

    def _store_idempotency(
        self,
        *,
        tenant_id: str,
        actor_employee_id: str,
        endpoint: str,
        idempotency_key: str,
        raw_body: bytes,
        status_code: int,
        payload: dict[str, Any],
    ) -> None:
        self._idempotency.save(
            tenant_id=tenant_id,
            endpoint=endpoint,
            key=idempotency_key,
            request_fingerprint=_fingerprint(raw_body),
            response_fingerprint=_fingerprint(
                json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
            ),
            status_code=status_code,
            response_payload=payload,
            actor_employee_id=actor_employee_id,
        )

    def _payload(self, targets: list[Target]) -> list[dict[str, Any]]:
        target_ids = [target.id for target in targets]
        lines = repository.lines_for(self._session, target_ids=target_ids)
        return [
            schemas.TargetOut(
                id=target.id,
                employee_id=target.employee_id,
                target_type=schemas.TargetType(target.target_type),
                period_month=target.period_month,
                target_value=target.target_value,
                target_value_amount_paise=_line_total(lines.get(target.id, []), "amount"),
                target_value_volume_units=_line_total(lines.get(target.id, []), "volume"),
                outlet_category_scope=(
                    schemas.OutletCategoryScope(target.outlet_category_scope)
                    if target.outlet_category_scope
                    else None
                ),
                status=schemas.TargetStatus(target.status),
                version=target.version,
                created_at=target.created_at,
                lines=[
                    schemas.TargetLineOut(
                        manufacturer_id=line.humbee_manufacturer_id,
                        manufacturer_label=line.manufacturer_label_snapshot,
                        line_basis=schemas.TargetBasis(line.line_basis),
                        uom_label=line.uom_label_snapshot,
                        line_value=line.line_value,
                    )
                    for line in lines.get(target.id, [])
                ],
            ).model_dump(mode="json")
            for target in targets
        ]

    def _manufacturer_roster(self) -> dict[str, TargetManufacturer]:
        port = self._manufacturer_port or HumbeeTargetManufacturerProvider(self._settings)
        try:
            manufacturers = port.list_manufacturers()
        except TargetManufacturerMasterUnavailable as exc:
            # R-TGT-04: the sales target type is disabled upstream of an empty list, never shown
            # with one, so this must be an error rather than an empty roster.
            raise ApiError(
                503,
                "manufacturer_roster_unavailable",
                "The manufacturer list is unavailable right now.",
                details={"corr_id": exc.corr_id},
            ) from exc
        if not manufacturers:
            raise ApiError(
                503,
                "manufacturer_roster_unavailable",
                "The manufacturer list is unavailable right now.",
            )
        roster: dict[str, TargetManufacturer] = {}
        for manufacturer in manufacturers:
            if manufacturer.manufacturer_id in roster:
                raise ApiError(
                    503,
                    "manufacturer_roster_unavailable",
                    "The manufacturer list is unavailable right now.",
                )
            roster[manufacturer.manufacturer_id] = manufacturer
        return roster

    def _resolve_lines(
        self, lines: list[schemas.TargetLineBody]
    ) -> list[tuple[str, str, str, str, int]]:
        """Each line's basis and unit label come from the manufacturer roster, never the client
        (R-TGT-04) — resolved once per write so every line in the same request reads one snapshot."""

        roster = self._manufacturer_roster()
        resolved = []
        for line in lines:
            manufacturer = roster.get(line.manufacturer_id)
            if manufacturer is None:
                raise ApiError(
                    422,
                    "manufacturer_not_found",
                    f"Manufacturer {line.manufacturer_id} is not on the current manufacturer roster.",
                )
            resolved.append(
                (
                    line.manufacturer_id,
                    manufacturer.name,
                    manufacturer.basis,
                    manufacturer.uom_label,
                    line.line_value,
                )
            )
        return resolved

    def _write_children(
        self, *, scope: ScopeContext, target: Target, body: schemas.TargetShape, now: datetime
    ) -> None:
        if target.target_type == schemas.TargetType.SALES:
            repository.replace_lines(
                self._session,
                scope=scope,
                target_id=target.id,
                lines=self._resolve_lines(body.lines),
                now=now,
            )

    # -- reads ----------------------------------------------------------------

    def list_targets(
        self,
        *,
        claims: AccessTokenClaims,
        employee_id: str,
        period_month: date,
        target_type: str | None,
    ) -> dict[str, Any]:
        """S-TGT1 edit-mode load: every active target this employee holds for the month."""

        scope = self._scope(claims)
        org_service.get_employee_in_scope(self._session, scope=scope, employee_id=employee_id)
        targets = repository.list_active(
            self._session,
            scope=scope,
            employee_id=employee_id,
            period_month=period_month,
            target_type=target_type,
        )
        return schemas.TargetListResponse(
            targets=self._payload(targets)  # type: ignore[arg-type]
        ).model_dump(mode="json")

    def list_targets_in_scope(
        self,
        claims: AccessTokenClaims,
        *,
        period_month: date,
        target_type: str = "sales",
    ) -> dict[str, Any]:
        """Active targets for every employee in the caller's tree/org, lines included.

        Scope is `apply_scope` on `Target.employee_id` — one query, no per-employee loop, no Humbee.
        """

        scope = self._scope(claims)
        targets = repository.list_active_in_scope(
            self._session,
            scope=scope,
            period_month=period_month,
            target_type=target_type,
        )
        return schemas.TargetListResponse(
            targets=self._payload(targets)  # type: ignore[arg-type]
        ).model_dump(mode="json")

    def get_target(self, *, claims: AccessTokenClaims, target_id: str) -> dict[str, Any]:
        target = repository.get_target(
            self._session, scope=self._scope(claims), target_id=target_id
        )
        if target is None:
            raise ApiError(404, "target_not_found", "Target was not found.")
        return self._payload([target])[0]

    def list_manufacturers(self) -> dict[str, Any]:
        """The roster behind a sales target's lines, served from
        `GET /sfa/v1/targets/manufacturers` — the target-setting-specific roster that carries each
        manufacturer's fixed unit, unlike `/sfa/v1/manufacturer-roles` (onboarding role assignment)."""

        roster = self._manufacturer_roster()
        return schemas.ManufacturerRosterResponse(
            manufacturers=[
                schemas.ManufacturerOut(
                    manufacturer_id=manufacturer.manufacturer_id,
                    display_label=manufacturer.name,
                    basis=schemas.TargetBasis(manufacturer.basis),
                    uom_label=manufacturer.uom_label,
                )
                for manufacturer in roster.values()
            ]
        ).model_dump(mode="json")

    def list_roster(
        self, *, claims: AccessTokenClaims, period_month: date | None
    ) -> dict[str, Any]:
        scope = self._scope(claims)
        policies.authorize_target_write(scope)
        resolved_month = period_month or self._today().replace(day=1)
        members = OrgService(
            self._session, settings=self._settings, clock=self._clock
        ).list_active_hierarchy_members(claims=claims)
        counts = repository.count_active_by_employee(
            self._session,
            scope=scope,
            period_month=resolved_month,
            employee_ids=[member.id for member in members],
        )
        zone_labels = list_employee_zone_labels(self._session, tenant_id=claims.tenant_id)
        rows = [
            schemas.TargetRosterMember(
                employee_id=member.id,
                full_name=member.full_name,
                display_initials=member.display_initials,
                role_code=member.role_code,
                zone_label=zone_labels.get(member.id),
                active_target_count=counts.get(member.id, 0),
            )
            for member in members
        ]
        with_target = sum(1 for row in rows if row.active_target_count > 0)
        return schemas.TargetRosterResponse(
            period_month=resolved_month,
            with_target=with_target,
            total=len(rows),
            members=rows,
        ).model_dump(mode="json")

    # -- writes ---------------------------------------------------------------

    def create_target(
        self,
        *,
        claims: AccessTokenClaims,
        body: schemas.CreateTargetBody,
        idempotency_key: str,
        raw_body: bytes,
    ) -> tuple[int, dict[str, Any]]:
        endpoint = "/api/v1/targets"
        scope = self._scope(claims)
        policies.authorize_target_write(scope)

        try:
            with transaction(self._session):
                replay = self._check_idempotency(
                    tenant_id=scope.tenant_id,
                    endpoint=endpoint,
                    idempotency_key=idempotency_key,
                    raw_body=raw_body,
                )
                if replay is not None:
                    return replay

                employee = org_service.get_employee_in_scope(
                    self._session, scope=scope, employee_id=body.employee_id
                )
                policies.authorize_subject(employee)
                policies.authorize_period(body.period_month, today=self._today())

                if repository.find_active(
                    self._session,
                    scope=scope,
                    employee_id=body.employee_id,
                    target_type=body.target_type,
                    period_month=body.period_month,
                ):
                    # R-TGT-08. The client reloads and PUTs rather than getting a second row.
                    raise ApiError(
                        409,
                        "target_already_set",
                        "This employee already has a target of that type for the month.",
                    )

                target = repository.insert_target(
                    self._session,
                    scope=scope,
                    target_id=body.id or generate_ulid(),
                    employee_id=body.employee_id,
                    target_type=body.target_type,
                    period_month=body.period_month,
                    target_value=_derived_value(body),
                    outlet_category_scope=body.outlet_category_scope,
                )
                self._write_children(
                    scope=scope, target=target, body=body, now=self._clock.now_utc()
                )
                payload = self._payload([target])[0]
                self._record(
                    scope=scope,
                    target=target,
                    event_type=TARGET_SET,
                    from_state=None,
                    to_state="active",
                    before=None,
                )
                self._store_idempotency(
                    tenant_id=scope.tenant_id,
                    actor_employee_id=scope.actor_employee_id,
                    endpoint=endpoint,
                    idempotency_key=idempotency_key,
                    raw_body=raw_body,
                    status_code=201,
                    payload=payload,
                )
        except IntegrityError as exc:
            raise _write_conflict(exc) from exc

        logger.info(
            "target_set",
            target_id=target.id,
            target_type=target.target_type,
            period_month=target.period_month.isoformat(),
        )
        return 201, payload

    def update_target(
        self,
        *,
        claims: AccessTokenClaims,
        target_id: str,
        body: schemas.UpdateTargetBody,
        idempotency_key: str,
        raw_body: bytes,
    ) -> dict[str, Any]:
        endpoint = f"/api/v1/targets/{target_id}"
        scope = self._scope(claims)
        policies.authorize_target_write(scope)

        with transaction(self._session):
            replay = self._check_idempotency(
                tenant_id=scope.tenant_id,
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                raw_body=raw_body,
            )
            if replay is not None:
                return replay[1]

            target = repository.get_target_for_update(
                self._session, scope=scope, target_id=target_id
            )
            if target is None:
                raise ApiError(404, "target_not_found", "Target was not found.")
            if target.status != "active":
                raise ApiError(409, "target_removed", "That target has been removed.")
            if target.target_type != body.target_type:
                raise ApiError(
                    422,
                    "target_type_immutable",
                    "A target's type is part of its identity. Remove it and set a new one.",
                )
            if target.version != body.version:
                raise ApiError(
                    409,
                    "target_version_conflict",
                    "This target was changed by someone else. Reload to see the latest.",
                )
            policies.authorize_period(target.period_month, today=self._today())

            before = self._snapshot(target)
            now = self._clock.now_utc()
            target.target_value = _derived_value(body)
            target.outlet_category_scope = body.outlet_category_scope
            target.version += 1
            self._write_children(scope=scope, target=target, body=body, now=now)
            self._session.flush()

            payload = self._payload([target])[0]
            self._record(
                scope=scope,
                target=target,
                event_type=TARGET_UPDATED,
                from_state="active",
                to_state="active",
                before=before,
            )
            self._store_idempotency(
                tenant_id=scope.tenant_id,
                actor_employee_id=scope.actor_employee_id,
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                raw_body=raw_body,
                status_code=200,
                payload=payload,
            )

        logger.info("target_updated", target_id=target.id, version=target.version)
        return payload

    def remove_target(
        self, *, claims: AccessTokenClaims, target_id: str, idempotency_key: str, raw_body: bytes
    ) -> dict[str, Any]:
        """R-TGT-13 — a soft delete. The employee then reads "No target", which is a product state
        rather than an absence of history: the row and its lines stay auditable."""

        endpoint = f"/api/v1/targets/{target_id}/remove"
        scope = self._scope(claims)
        policies.authorize_target_write(scope)

        with transaction(self._session):
            replay = self._check_idempotency(
                tenant_id=scope.tenant_id,
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                raw_body=raw_body,
            )
            if replay is not None:
                return replay[1]

            target = repository.get_target_for_update(
                self._session, scope=scope, target_id=target_id
            )
            if target is None:
                raise ApiError(404, "target_not_found", "Target was not found.")
            if target.status != "active":
                raise ApiError(409, "target_removed", "That target has already been removed.")
            # R-TGT-15 applies to removal too: withdrawing a closed month's target would delete the
            # denominator whatever achievement was already measured against.
            policies.authorize_period(target.period_month, today=self._today())

            before = self._snapshot(target)
            now = self._clock.now_utc()
            target.status = "removed"
            target.removed_at = now
            target.removed_by = claims.employee_id
            target.version += 1
            self._session.flush()

            payload = schemas.RemoveTargetResponse(
                target_id=target.id,
                status=schemas.TargetStatus.REMOVED,
                removed_at=now,
                removed_by=claims.employee_id,
            ).model_dump(mode="json")
            self._record(
                scope=scope,
                target=target,
                event_type=TARGET_REMOVED,
                from_state="active",
                to_state="removed",
                before=before,
            )
            self._store_idempotency(
                tenant_id=scope.tenant_id,
                actor_employee_id=scope.actor_employee_id,
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                raw_body=raw_body,
                status_code=200,
                payload=payload,
            )

        logger.info("target_removed", target_id=target.id)
        return payload

    def capture_lead(
        self,
        *,
        claims: AccessTokenClaims,
        body: schemas.CaptureLeadBody,
        idempotency_key: str,
        raw_body: bytes,
    ) -> tuple[int, dict[str, Any]]:
        """S-LEAD1 — any hierarchy member captures a lead for themselves; there is no manager
        approval step, unlike `create_target`, which is why this skips `policies.authorize_*` and
        `ScopeResolver` entirely and writes straight off `claims` (the same pattern
        `outlets.submit_candidate` uses for a self-scoped create)."""

        endpoint = "/api/v1/leads"

        try:
            with transaction(self._session):
                replay = self._check_idempotency(
                    tenant_id=claims.tenant_id,
                    endpoint=endpoint,
                    idempotency_key=idempotency_key,
                    raw_body=raw_body,
                )
                if replay is not None:
                    return replay

                now = self._clock.now_utc()
                lead = repository.insert_lead(
                    self._session,
                    lead_id=body.id or generate_ulid(),
                    tenant_id=claims.tenant_id,
                    captured_by_employee_id=claims.employee_id,
                    prospect_name=body.name,
                    contact_designation=body.designation,
                    contact_mobile_hmac=hmac_phone(body.mobile),
                    contact_mobile_enc=encrypt_phone(body.mobile),
                    contact_mobile_last4=body.mobile[-4:],
                    contact_email=body.email,
                    company_name=body.company_name,
                    associated_manufacturer_names=body.associated_manufacturers,
                    annual_turnover_cr=body.annual_turnover_cr,
                    head_office_location=body.head_office_location,
                    notes=body.message,
                    occurred_at=now,
                    received_at=now,
                    business_date=to_business_date(now, self._settings.day_boundary_hour_ist),
                )
                payload = self._lead_payload(lead)
                self._record_lead(claims=claims, lead=lead)
                self._store_idempotency(
                    tenant_id=claims.tenant_id,
                    actor_employee_id=claims.employee_id,
                    endpoint=endpoint,
                    idempotency_key=idempotency_key,
                    raw_body=raw_body,
                    status_code=201,
                    payload=payload,
                )
        except IntegrityError as exc:
            raise _lead_write_conflict(exc) from exc

        logger.info("lead_captured", lead_id=lead.id)
        return 201, payload

    def count_leads_in_scope(
        self, *, claims: AccessTokenClaims, from_date: date, to_date: date
    ) -> int:
        """Leads captured within the caller's tree and window, for another module's
        (reporting) manager-dashboard rollup."""

        return repository.count_leads_in_scope(
            self._session, scope=self._scope(claims), from_date=from_date, to_date=to_date
        )

    @staticmethod
    def _lead_payload(lead: Lead) -> dict[str, Any]:
        return schemas.LeadOut(
            id=lead.id,
            name=lead.prospect_name,
            designation=lead.contact_designation,
            mobile_last4=lead.contact_mobile_last4,
            email=lead.contact_email,
            company_name=lead.company_name,
            associated_manufacturers=lead.associated_manufacturer_names,
            annual_turnover_cr=(
                float(lead.annual_turnover_cr) if lead.annual_turnover_cr is not None else None
            ),
            head_office_location=lead.head_office_location,
            message=lead.notes,
            interest_level=schemas.LeadInterestLevel(lead.interest_level),
            status=schemas.LeadStatus(lead.status),
            captured_at=lead.occurred_at,
        ).model_dump(mode="json")

    def _record_lead(self, *, claims: AccessTokenClaims, lead: Lead) -> None:
        """One audit row and one domain event per capture. Never carries the contact's mobile or
        email — only ids, per the PII logging rule."""

        self._audit.record_transition(
            tenant_id=claims.tenant_id,
            entity_type="lead",
            entity_id=lead.id,
            from_state=None,
            to_state=lead.status,
            actor_employee_id=claims.employee_id,
            reason=None,
            request_id=None,
            change_payload={"transition": LEAD_CAPTURED},
        )
        self._events.publish(
            tenant_id=claims.tenant_id,
            stream=STREAM,
            event_type=LEAD_CAPTURED,
            aggregate_type="lead",
            aggregate_id=lead.id,
            payload={
                "lead_id": lead.id,
                "captured_by_employee_id": lead.captured_by_employee_id,
                "status": lead.status,
            },
            actor_employee_id=claims.employee_id,
            occurred_at=lead.occurred_at,
        )

    @staticmethod
    def _snapshot(target: Target) -> dict[str, Any]:
        """The fields an edit can change, for the audit trail's before-image."""

        return {
            "target_value": target.target_value,
            "outlet_category_scope": target.outlet_category_scope,
            "status": target.status,
            "version": target.version,
        }

    def _record(
        self,
        *,
        scope: ScopeContext,
        target: Target,
        event_type: str,
        from_state: str | None,
        to_state: str,
        before: dict[str, Any] | None,
    ) -> None:
        """R-TGT-28 — every transition leaves an audit row carrying actor, subject, before and
        after, plus one domain event."""

        self._audit.record_transition(
            tenant_id=scope.tenant_id,
            entity_type=AUDIT_ENTITY,
            entity_id=target.id,
            from_state=from_state,
            to_state=to_state,
            actor_employee_id=scope.actor_employee_id,
            reason=None,
            request_id=None,
            change_payload={
                "transition": event_type,
                "target_type": target.target_type,
                "before": before,
                "after": self._snapshot(target),
            },
        )
        self._events.publish(
            tenant_id=scope.tenant_id,
            stream=STREAM,
            event_type=event_type,
            aggregate_type=AGGREGATE,
            aggregate_id=target.id,
            payload={
                "target_id": target.id,
                "employee_id": target.employee_id,
                "target_type": target.target_type,
                "period_month": target.period_month.isoformat(),
                "target_value": target.target_value,
                "status": target.status,
            },
            actor_employee_id=scope.actor_employee_id,
        )


def _write_conflict(exc: IntegrityError) -> ApiError:
    """Classify a constraint violation that escaped the transaction.

    `uq_targets_active` is the real guard behind R-TGT-08 — the pre-check narrows the window, the
    index closes it when two managers save the same target at once. Anything else is a server-side
    bug, so it is re-raised as itself rather than reported to the client as a validation error.
    """

    detail = str(getattr(exc, "orig", exc))
    if "uq_targets_active" in detail:
        return ApiError(
            409,
            "target_already_set",
            "This employee already has a target of that type for the month.",
        )
    if "pk_targets" in detail:
        return ApiError(409, "target_id_taken", "That target id is already in use.")
    raise exc


def count_leads_for_employee_day(
    session: Session, *, tenant_id: str, employee_id: str, business_date: date
) -> int:
    return repository.count_leads_for_day(
        session, tenant_id=tenant_id, employee_id=employee_id, business_date=business_date
    )


def _lead_write_conflict(exc: IntegrityError) -> ApiError:
    """A client-generated lead id colliding with an existing row is the only realistic conflict
    here — everything else a `CaptureLeadBody` could violate is already refused by its own field
    validation before a write is attempted."""

    detail = str(getattr(exc, "orig", exc))
    if "pk_targets_leads" in detail:
        return ApiError(409, "lead_id_taken", "That lead id is already in use.")
    raise exc

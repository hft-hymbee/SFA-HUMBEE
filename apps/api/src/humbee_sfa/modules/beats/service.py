"""Beats business logic.

Transaction ownership lives here, not in the router (a service owns one transaction
per state transition together with its audit and domain-event writes). Submission and edit-submission
route through the generic approval engine (`approvals.service.create`) exactly like
`leave.service.submit` — beats never implements its own approve/reject path.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any, Literal, NoReturn

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from humbee_sfa.core.business_date import to_business_date
from humbee_sfa.core.clock import Clock, SystemClock
from humbee_sfa.core.conventions import generate_ulid
from humbee_sfa.core.db import end_read_transaction, transaction
from humbee_sfa.core.deps import AccessTokenClaims
from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.core.settings import Settings, get_settings
from humbee_sfa.integration.humbee.outlet import HumbeeOutletMasterProvider
from humbee_sfa.modules.approvals import repository as approvals_repository
from humbee_sfa.modules.approvals import service as approvals_service
from humbee_sfa.modules.approvals.contracts import ApprovalStatus, DecisionAction, SubjectEvent
from humbee_sfa.modules.beats import repository, schemas
from humbee_sfa.modules.beats.adapter import (
    _frequency_label,
    apply_create_approved,
    apply_edit_approved,
)
from humbee_sfa.modules.beats.models.beat import Beat
from humbee_sfa.modules.beats.models.beat_version import BeatVersion
from humbee_sfa.modules.org.geography_service import GeographyService
from humbee_sfa.modules.org.scope import OrgResource, Role, ScopeContext, ScopeResolver
from humbee_sfa.modules.outlets.service import OutletReadService, ProjectedOutlet
from humbee_sfa.platform.audit import AuditLogService
from humbee_sfa.platform.domain_events import DomainEventPublisher
from humbee_sfa.platform.idempotency import IdempotencyService

AUDIT_ENTITY = "beats_beat"


# A beat row exists from the wizard's first step, two screens before the sales person names it,
# so creation fills the not-null `display_name` and the tenant-unique `code` with placeholders.
# The naming step replaces both; submit refuses a version still carrying them.
PLACEHOLDER_DISPLAY_NAME = "Untitled beat"


def _fingerprint(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _require_frequency_complete(
    frequency: str | None, visit_days: list[int], week_cycle: list[int]
) -> None:
    if frequency != "daily" and not visit_days:
        raise ApiError(422, "frequency_incomplete", "Select at least one visit day.")
    if frequency in ("fortnightly", "monthly") and not week_cycle:
        raise ApiError(422, "frequency_incomplete", "Select at least one week in the cycle.")


def _code_conflict(exc: IntegrityError) -> NoReturn:
    if "uq_beats_tenant_code" not in str(getattr(exc, "orig", exc)):
        raise exc
    raise ApiError(409, "beat_code_taken", "That beat code is already in use.") from exc


def _validate_frequency(freq: schemas.Frequency) -> dict[str, Any]:
    _require_frequency_complete(freq.frequency, freq.visit_days, freq.week_cycle)
    if any(day < 0 or day > 6 for day in freq.visit_days):
        raise ApiError(422, "frequency_incomplete", "visit_days must be 0-6 (0 = Sunday).")
    if any(week < 1 or week > 4 for week in freq.week_cycle):
        raise ApiError(422, "frequency_incomplete", "week_cycle must be 1-4.")
    return {
        "frequency": freq.frequency,
        "visit_days": [] if freq.frequency == "daily" else freq.visit_days,
        "week_cycle": freq.week_cycle if freq.frequency in ("fortnightly", "monthly") else [],
    }


def _validate_version_for_submit(version: BeatVersion) -> None:
    if version.display_name == PLACEHOLDER_DISPLAY_NAME or version.code == version.beat_id:
        raise ApiError(422, "beat_not_named", "Give this beat a name and code before submitting.")
    if not repository.read_districts(version.geo_scope):
        raise ApiError(422, "district_required", "Select at least one district cluster.")
    if version.outlet_count < 1:
        raise ApiError(422, "no_outlets_selected", "Add at least one outlet to this beat.")
    freq = version.frequency
    _require_frequency_complete(
        freq.get("frequency"), freq.get("visit_days") or [], freq.get("week_cycle") or []
    )


def _is_abandoned_draft(beat: Beat, version: BeatVersion | None) -> bool:
    """A wizard draft opened and never named. The `Beat` row exists from the wizard's first step,
    so an abandoned session leaves a placeholder-named, outlet-less row that carries no
    information — it is the owner's to resume, never an org-wide report line."""

    return (
        beat.lifecycle_state == "draft"
        and beat.display_name == PLACEHOLDER_DISPLAY_NAME
        and (version.outlet_count if version else 0) == 0
    )


def display_status(beat: Beat, *, edit_pending: bool) -> str:
    """Derived, never stored. `edit_pending` means a submitted edit request awaits
    approval; an unsubmitted edit branch leaves the beat plainly active."""

    if beat.lifecycle_state == "approved":
        if beat.activation_state == "inactive":
            return "inactive"
        return "edit_pending" if edit_pending else "active"
    return beat.lifecycle_state


def _assigned_on_business_date(frequency: dict[str, Any], business_date: date) -> bool:
    if frequency.get("frequency") == "daily":
        return True
    visit_days = frequency.get("visit_days") or []
    sunday_based_weekday = (business_date.weekday() + 1) % 7
    return sunday_based_weekday in visit_days


def _run_origin_for_business_date(
    beat: Beat, *, frequency: dict[str, Any], business_date: date
) -> Literal["assigned_beat", "unplanned_beat"] | None:
    if beat.lifecycle_state != "approved" or beat.activation_state != "active":
        return None
    return "assigned_beat" if _assigned_on_business_date(frequency, business_date) else "unplanned_beat"


class BeatService:
    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        clock: Clock | None = None,
        outlet_port: HumbeeOutletMasterProvider | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._clock = clock or SystemClock()
        self._outlet_port = outlet_port
        self._audit = AuditLogService(session)
        self._events = DomainEventPublisher(session, self._clock)
        self._idempotency = IdempotencyService(session)

    # -- scope / idempotency ------------------------------------------------

    def _scope(self, claims: AccessTokenClaims) -> ScopeContext:
        # Beats are activity data: SELF for a Sales Person, OWN_TREE (read-only) for their
        # manager, ORG for Admin.
        return ScopeResolver.resolve_from_claims(claims, OrgResource.ACTIVITY_DATA)

    def _load(self, scope: ScopeContext, beat_id: str) -> Beat:
        beat = repository.get_beat(self._session, scope=scope, beat_id=beat_id)
        if beat is None:
            raise ApiError(404, "beat_not_found", "Beat was not found.")
        return beat

    def _load_for_update(self, scope: ScopeContext, beat_id: str) -> Beat:
        beat = repository.get_beat_for_update(
            self._session, scope=scope, beat_id=beat_id
        )
        if beat is None:
            raise ApiError(404, "beat_not_found", "Beat was not found.")
        return beat

    def _require_active(self, beat: Beat) -> None:
        if beat.activation_state == "inactive":
            raise ApiError(409, "beat_inactive", "This beat is inactive. Contact Admin.")

    def _reject_taken_code(self, beat: Beat, code: str) -> None:
        if repository.code_taken(
            self._session, tenant_id=beat.tenant_id, code=code, exclude_beat_id=beat.id
        ):
            raise ApiError(409, "beat_code_taken", "That beat code is already in use.")

    def _require_owner(self, scope: ScopeContext, beat: Beat) -> None:
        if scope.actor_employee_id != beat.owner_employee_id:
            raise ApiError(403, "forbidden", "Only the beat's owner may do this.")

    def _is_privileged(self, scope: ScopeContext) -> bool:
        """Admin or Manager — they write without approval. Which beats they can reach
        is already settled by `_load`'s ORG/OWN_TREE scoping, so role alone decides here."""

        return scope.actor_role in {Role.ADMIN, Role.MANAGER}

    def _require_admin(self, scope: ScopeContext) -> None:
        if scope.actor_role != Role.ADMIN:
            raise ApiError(403, "forbidden", "This action is Admin-only.")

    def _require_privileged(self, scope: ScopeContext) -> None:
        if not self._is_privileged(scope):
            raise ApiError(403, "forbidden", "This action is limited to Admins and Managers.")

    def _require_owner_or_privileged(self, scope: ScopeContext, beat: Beat) -> None:
        if scope.actor_employee_id != beat.owner_employee_id and not self._is_privileged(scope):
            raise ApiError(
                403, "forbidden", "Only the beat's owner, a manager, or an admin may do this."
            )

    def _publish_applied(self, claims: AccessTokenClaims, event: SubjectEvent) -> None:
        self._events.publish(
            tenant_id=claims.tenant_id,
            stream=event.stream,
            event_type=event.event_type,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            payload=event.payload,
            actor_employee_id=claims.employee_id,
        )

    def _outlets(self) -> OutletReadService:
        return OutletReadService(
            self._session,
            settings=self._settings,
            clock=self._clock,
            outlet_port=self._outlet_port,
        )

    def _refresh_and_validate_outlets(
        self,
        *,
        tenant_id: str,
        geo_scope: dict[str, Any],
        outlet_refs: list[str],
        actor_employee_id: str | None,
    ) -> None:
        """Humbee's outlet search is the authority on which outlets a beat's geography contains, so membership is
        checked against a live search rather than against what the client claims.

        The refreshed projection is staged, not committed — it lands with the beat write that
        follows, in the caller's transaction.
        """

        records = self._outlets().search_outlets(
            tenant_id=tenant_id,
            district_ids=repository.read_districts(geo_scope),
            category_ids=list(geo_scope.get("cats") or []),
            query=None,
            actor_employee_id=actor_employee_id,
            upsert_refs=set(outlet_refs),
        )
        in_scope = {record.external_id for record in records}
        missing = [outlet_ref for outlet_ref in outlet_refs if outlet_ref not in in_scope]
        if missing:
            projected = self._projected_by_outlet_ref(tenant_id=tenant_id, outlet_refs=missing)
            names = ", ".join(
                projected[ref].record.name if ref in projected else ref for ref in missing
            )
            raise ApiError(
                422,
                "outlet_out_of_scope",
                f"Outside this beat's geography or shop categories: {names}. "
                "Remove these outlets or widen the scope.",
                details={"outlets": missing},
            )

    def _version_outlets(
        self, *, tenant_id: str, version_id: str
    ) -> list[tuple[int | None, ProjectedOutlet]]:
        """A version's outlet membership paired with the current projected outlet, in sequence."""

        return self._outlets_for_versions(
            tenant_id=tenant_id, version_ids=[version_id]
        )[version_id]

    def _outlets_for_versions(
        self, *, tenant_id: str, version_ids: list[str]
    ) -> dict[str, list[tuple[int | None, ProjectedOutlet]]]:
        memberships = repository.list_memberships_for_versions(
            self._session, version_ids=version_ids
        )
        projected = self._outlets().get_projected_outlets(
            tenant_id=tenant_id,
            outlet_ids=[membership.outlet_id for membership in memberships],
            ids_are_local=True,
        )
        projected_by_id = {outlet.local_id: outlet for outlet in projected}
        result: dict[str, list[tuple[int | None, ProjectedOutlet]]] = {
            version_id: [] for version_id in version_ids
        }
        for membership in memberships:
            result[membership.beat_version_id].append(
                (membership.sequence_hint, projected_by_id[membership.outlet_id])
            )
        return result

    def _projected_by_outlet_ref(
        self, *, tenant_id: str, outlet_refs: list[str]
    ) -> dict[str, ProjectedOutlet]:
        return {
            outlet.record.external_id: outlet
            for outlet in self._outlets().get_projected_outlets(
                tenant_id=tenant_id, outlet_ids=outlet_refs
            )
        }

    def _outlet_claims(
        self,
        *,
        tenant_id: str,
        exclude_beat_id: str,
        projected_by_ref: dict[str, ProjectedOutlet],
    ) -> dict[str, str]:
        """Humbee ref -> holding beat's name, for outlets another active beat has approved or
        has awaiting approval. A rejected submission claims nothing."""

        ref_by_local_id = {
            outlet.local_id: ref for ref, outlet in projected_by_ref.items()
        }
        claims = repository.outlet_claims(
            self._session,
            tenant_id=tenant_id,
            exclude_beat_id=exclude_beat_id,
            outlet_ids=list(ref_by_local_id),
        )
        return {ref_by_local_id[local_id]: beat_name for local_id, beat_name in claims.items()}

    def _reject_taken_outlets(
        self, beat: Beat, outlet_refs: list[str]
    ) -> dict[str, ProjectedOutlet]:
        repository.lock_outlet_claims(
            self._session, tenant_id=beat.tenant_id, outlet_refs=outlet_refs
        )
        projected_by_ref = self._projected_by_outlet_ref(
            tenant_id=beat.tenant_id, outlet_refs=outlet_refs
        )
        claims = self._outlet_claims(
            tenant_id=beat.tenant_id, exclude_beat_id=beat.id, projected_by_ref=projected_by_ref
        )
        if claims:
            clash = sorted(claims)
            names = ", ".join(
                f"{projected_by_ref[ref].record.name} (beat {claims[ref]})" for ref in clash
            )
            raise ApiError(
                409,
                "outlet_already_on_beat",
                f"Already on another beat: {names}. Remove these outlets to continue.",
                details={"outlets": clash},
            )
        return projected_by_ref

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
                409, "idempotency_conflict", "Idempotency key was already used with a different payload."
            )
        return existing.status_code, existing.response_payload

    def _store_idempotency(
        self, *, endpoint: str, idempotency_key: str, raw_body: bytes, status_code: int,
        payload: dict[str, Any], scope: ScopeContext,
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

    # -- reads ---------------------------------------------------------------

    def list_beats(
        self, *, claims: AccessTokenClaims, status_filter: str | None, business_date: date | None,
        limit: int, offset: int
    ) -> dict[str, Any]:
        scope = self._scope(claims)
        effective_business_date = business_date or to_business_date(
            self._clock.now_utc(), self._settings.day_boundary_hour_ist
        )
        rows = repository.list_beats(
            self._session, scope=scope, status_filter=status_filter, limit=limit, offset=offset
        )
        facets = repository.count_facets(self._session, scope=scope)
        pending_edit_beat_ids = repository.list_pending_edit_beat_ids(
            self._session, tenant_id=scope.tenant_id, beat_ids=[beat.id for beat in rows]
        )
        row_version_ids = [
            version_id
            for beat in rows
            if (version_id := beat.current_version_id or beat.draft_version_id)
        ]
        versions_by_id = {
            version.id: version
            for version in repository.list_versions(
                self._session, tenant_id=scope.tenant_id, version_ids=row_version_ids
            )
        }
        items = []
        for beat in rows:
            version_id = beat.current_version_id or beat.draft_version_id
            version = versions_by_id.get(version_id) if version_id else None
            frequency = version.frequency if version else {}
            run_origin = _run_origin_for_business_date(
                beat, frequency=frequency, business_date=effective_business_date
            )
            items.append(
                schemas.BeatListItem(
                    id=beat.id,
                    code=beat.code,
                    display_name=beat.display_name,
                    owner_employee_id=beat.owner_employee_id,
                    lifecycle_state=beat.lifecycle_state,
                    activation_state=beat.activation_state,
                    display_status=display_status(
                        beat, edit_pending=beat.id in pending_edit_beat_ids
                    ),
                    outlet_count=version.outlet_count if version else 0,
                    frequency=frequency,
                    run_origin=run_origin,
                    planned_for_business_date=(run_origin == "assigned_beat") if run_origin else None,
                    created_at=beat.created_at,
                )
            )
        return schemas.BeatListResponse(
            business_date=effective_business_date,
            items=items,
            facets=facets,
            total=facets.get(status_filter or "all", facets["all"]),
        ).model_dump(mode="json")

    def list_assigned_outlets(self, *, claims: AccessTokenClaims) -> list[dict[str, str]]:
        scope = self._scope(claims)
        beats = repository.list_active_approved_beats(self._session, scope=scope)
        version_ids = [
            beat.current_version_id for beat in beats if beat.current_version_id is not None
        ]
        memberships = repository.list_memberships_for_versions(
            self._session, version_ids=version_ids
        )
        projected = self._outlets().get_projected_outlets(
            tenant_id=scope.tenant_id,
            outlet_ids=[membership.outlet_id for membership in memberships],
            ids_are_local=True,
        )
        projected_by_id = {outlet.local_id: outlet for outlet in projected}
        assigned: dict[str, dict[str, str]] = {}
        for membership in memberships:
            outlet = projected_by_id.get(membership.outlet_id)
            if outlet is None:
                continue
            assigned[outlet.record.external_id] = {
                "humbee_outlet_id": outlet.record.external_id,
                "name": outlet.record.name,
            }
        return list(assigned.values())

    def list_beats_for_report(self, *, claims: AccessTokenClaims) -> list[dict[str, Any]]:
        """Admin-only bulk export: every active, approved beat with its owner, district
        geography and current outlet membership — for the beat / beat-outlet / unassigned-outlet
        admin reports."""

        scope = self._scope(claims)
        beats = repository.list_active_approved_beats(self._session, scope=scope)
        version_ids = [beat.current_version_id for beat in beats if beat.current_version_id]
        versions_by_id = {
            version.id: version
            for version in repository.list_versions(
                self._session, tenant_id=scope.tenant_id, version_ids=version_ids
            )
        }
        memberships = repository.list_memberships_for_versions(self._session, version_ids=version_ids)
        outlets_by_version: dict[str, list[tuple[str, int | None]]] = {}
        for membership in memberships:
            outlets_by_version.setdefault(membership.beat_version_id, []).append(
                (membership.outlet_id, membership.sequence_hint)
            )
        return [
            {
                "beat_id": beat.id,
                "code": beat.code,
                "display_name": beat.display_name,
                "owner_employee_id": beat.owner_employee_id,
                "district_ids": repository.read_districts(versions_by_id[beat.current_version_id].geo_scope)
                if beat.current_version_id in versions_by_id
                else [],
                # `list_memberships_for_versions` orders by `sequence_hint asc nulls last`, so
                # position in this list is already the outlet's run order.
                "outlets": outlets_by_version.get(beat.current_version_id, [])
                if beat.current_version_id
                else [],
            }
            for beat in beats
        ]

    def list_beats_for_directory_report(self, *, claims: AccessTokenClaims) -> list[dict[str, Any]]:
        """Admin-only bulk export: every beat regardless of lifecycle state (draft, pending,
        approved/active, approved/inactive) with its best-available version data — for the admin
        beats directory report. Unlike `list_beats_for_report`, this is not limited to
        active+approved beats, so a draft or deactivated beat still shows up with a `display_status`.
        """

        scope = self._scope(claims)
        beats = repository.list_beats(
            self._session, scope=scope, status_filter=None, limit=None, offset=0
        )
        version_ids = list(
            {
                version_id
                for beat in beats
                if (version_id := beat.current_version_id or beat.draft_version_id)
            }
        )
        versions_by_id = {
            version.id: version
            for version in repository.list_versions(
                self._session, tenant_id=scope.tenant_id, version_ids=version_ids
            )
        }
        approved_version_ids = [beat.current_version_id for beat in beats if beat.current_version_id]
        memberships = repository.list_memberships_for_versions(
            self._session, version_ids=approved_version_ids
        )
        outlet_ids_by_version: dict[str, list[str]] = {}
        for membership in memberships:
            outlet_ids_by_version.setdefault(membership.beat_version_id, []).append(membership.outlet_id)
        pending_edit_beat_ids = repository.list_pending_edit_beat_ids(
            self._session, tenant_id=scope.tenant_id, beat_ids=[beat.id for beat in beats]
        )

        rows: list[dict[str, Any]] = []
        for beat in beats:
            version_id = beat.current_version_id or beat.draft_version_id
            version = versions_by_id.get(version_id) if version_id else None
            if _is_abandoned_draft(beat, version):
                continue
            rows.append(
                {
                    "beat_id": beat.id,
                    "code": beat.code,
                    "display_name": beat.display_name,
                    "owner_employee_id": beat.owner_employee_id,
                    "display_status": display_status(
                        beat, edit_pending=beat.id in pending_edit_beat_ids
                    ),
                    "frequency_label": _frequency_label(version.frequency) if version else "",
                    "district_ids": repository.read_districts(version.geo_scope) if version else [],
                    "outlet_count": version.outlet_count if version else 0,
                    "approved_at": version.approved_at if version else None,
                    "approved_by_employee_id": version.approved_by_employee_id if version else None,
                    "pending_edit_request": beat.id in pending_edit_beat_ids,
                    "outlet_ids": outlet_ids_by_version.get(beat.current_version_id, [])
                    if beat.current_version_id
                    else [],
                }
            )
        return rows

    def get_beat_detail(self, *, claims: AccessTokenClaims, beat_id: str) -> dict[str, Any]:
        scope = self._scope(claims)
        beat = self._load(scope, beat_id)
        if beat.current_version_id is None:
            raise ApiError(404, "no_current_version", "This beat has not been approved yet.")
        return self._detail_payload(scope.tenant_id, beat, version_id=beat.current_version_id)

    def get_beat_detail_for_planning(
        self, *, claims: AccessTokenClaims, beat_id: str
    ) -> tuple[dict[str, Any], str]:
        """Beat detail plus the live approved version id for route snapshotting."""

        scope = self._scope(claims)
        beat = self._load(scope, beat_id)
        if beat.current_version_id is None:
            raise ApiError(404, "no_current_version", "This beat has not been approved yet.")
        detail = self._detail_payload(scope.tenant_id, beat, version_id=beat.current_version_id)
        return detail, beat.current_version_id

    def route_group_names_for_versions(
        self, *, tenant_id: str, version_ids: list[str]
    ) -> dict[str, str]:
        """Display labels for route groups keyed by snapshotted beat version id."""

        return {
            version.id: version.display_name
            for version in repository.list_versions(
                self._session, tenant_id=tenant_id, version_ids=list(dict.fromkeys(version_ids))
            )
        }

    def get_beat_draft(self, *, claims: AccessTokenClaims, beat_id: str) -> dict[str, Any]:
        """The version pending approval — a first-time draft or a proposed edit — never the live
        one. At most one exists per beat (`uq_beats_versions_one_pending`,
        `uq_beats_edit_one_pending`), so there is no ambiguity about which."""

        scope = self._scope(claims)
        beat = self._load(scope, beat_id)
        if beat.draft_version_id is None:
            raise ApiError(404, "no_pending_version", "This beat has nothing pending approval.")
        version = repository.get_version(
            self._session, tenant_id=scope.tenant_id, version_id=beat.draft_version_id
        )
        if version is None or version.state not in {"draft", "pending_approval"}:
            raise ApiError(404, "no_pending_version", "This beat has nothing pending approval.")
        return self._detail_payload(scope.tenant_id, beat, version_id=version.id)

    def _detail_payload(self, tenant_id: str, beat: Beat, *, version_id: str | None) -> dict[str, Any]:
        version = repository.get_version(self._session, tenant_id=tenant_id, version_id=version_id)
        if version is None:
            raise ApiError(404, "beat_not_found", "Beat was not found.")
        outlets = self._version_outlets(tenant_id=tenant_id, version_id=version.id)
        pending_edit = None
        if beat.current_version_id:
            edit_request = repository.get_pending_edit_request(
                self._session, tenant_id=tenant_id, beat_id=beat.id
            )
            if edit_request is not None:
                pending_edit = schemas.PendingEditSummary(
                    state=edit_request.state,
                    diff=edit_request.diff,
                    approval_request_id=edit_request.approval_request_id,
                    submitted_at=edit_request.submitted_at,
                )
        return schemas.BeatDetailResponse(
            id=beat.id,
            version_id=version.id,
            version_state=version.state,
            code=version.code,
            display_name=version.display_name,
            owner_employee_id=beat.owner_employee_id,
            lifecycle_state=beat.lifecycle_state,
            activation_state=beat.activation_state,
            display_status=display_status(beat, edit_pending=pending_edit is not None),
            geo_scope=version.geo_scope,
            frequency=version.frequency,
            outlet_count=version.outlet_count,
            outlets=[
                schemas.BeatOutletItem(
                    outlet_ref=outlet.record.external_id,
                    name=outlet.record.name,
                    locality=outlet.record.locality,
                    category=schemas.to_shop_category(outlet.record.category),
                    sequence_hint=sequence_hint,
                )
                for sequence_hint, outlet in outlets
            ],
            approval_request_id=version.approval_request_id,
            created_at=beat.created_at,
            deactivation_reason=beat.deactivation_reason,
            deactivated_at=beat.deactivated_at,
            pending_edit=pending_edit,
        ).model_dump(mode="json")

    # -- create / draft --------------------------------------------------------

    def create_beat(self, *, claims: AccessTokenClaims, body: schemas.CreateBeatBody) -> tuple[int, dict[str, Any]]:
        """Idempotent on the client ULID — a retried create with the same `id`
        converges on the existing draft rather than erroring."""

        scope = self._scope(claims)
        owner_employee_id = body.owner_employee_id or claims.employee_id
        if owner_employee_id != claims.employee_id:
            self._require_privileged(scope)
            self._owner_geo_assignment(claims, owner_employee_id)
        beat_id = body.id or generate_ulid()
        try:
            with transaction(self._session):
                existing = repository.get_beat(self._session, scope=scope, beat_id=beat_id)
                if existing is not None:
                    if existing.current_version_id is None and existing.draft_version_id is None:
                        raise ApiError(
                            409, "beat_id_taken", "That beat id is already in use. Retry with a new one."
                        )
                    status_code = 200
                    beat = existing
                else:
                    beat, _version = repository.insert_beat_with_draft(
                        self._session,
                        beat_id=beat_id,
                        tenant_id=scope.tenant_id,
                        code=beat_id,
                        display_name=PLACEHOLDER_DISPLAY_NAME,
                        owner_employee_id=owner_employee_id,
                        created_by_employee_id=claims.employee_id,
                        now=self._clock.now_utc(),
                    )
                    self._audit.record_transition(
                        tenant_id=scope.tenant_id, entity_type=AUDIT_ENTITY, entity_id=beat.id,
                        from_state=None, to_state="draft", actor_employee_id=claims.employee_id,
                        change_payload={"transition": "beat_created"},
                    )
                    status_code = 201
                payload = self._detail_payload(
                    scope.tenant_id, beat, version_id=beat.current_version_id or beat.draft_version_id
                )
        except IntegrityError as exc:
            # The lookup above is scope-filtered and excludes deactivated rows, so an id belonging
            # to another tenant, another owner, or a deactivated beat reaches the insert and
            # collides on the primary key. That is the client's id to fix, not a server fault.
            if "pk_beats" not in str(getattr(exc, "orig", exc)):
                raise
            raise ApiError(
                409, "beat_id_taken", "That beat id is already in use. Retry with a new one."
            ) from exc
        return status_code, payload

    def _working_version(
        self, scope: ScopeContext, beat: Beat, *, allow_pending_approval: bool = False
    ) -> BeatVersion:
        version_id = beat.draft_version_id
        version = (
            repository.get_version(self._session, tenant_id=scope.tenant_id, version_id=version_id)
            if version_id
            else None
        )
        if version is None:
            raise ApiError(409, "no_draft_in_progress", "This beat has no draft to edit right now.")
        if version.state == "draft":
            return version
        if allow_pending_approval and version.state == "pending_approval":
            return version
        raise ApiError(
            409, "draft_locked", "This edit has already been submitted and can't be changed."
        )

    def _owner_geo_assignment(
        self, claims: AccessTokenClaims, owner_employee_id: str
    ) -> dict[str, Any]:
        try:
            return GeographyService(self._session).get_geography_scope(
                claims=claims, employee_id=owner_employee_id
            )
        except ApiError as exc:
            # An out-of-tree or unknown employee already answers `404 employee_not_found` and must
            # keep doing so — only a real missing assignment is this module's 422.
            if exc.code != "geography_scope_not_assigned":
                raise
            raise ApiError(
                422, "geo_scope_not_assigned", "This beat's owner has no assigned geography."
            ) from exc

    def _resolve_geo_scope(
        self,
        claims: AccessTokenClaims,
        owner_employee_id: str,
        geo: schemas.GeoScope,
        *,
        previous_labels: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """The owner's assigned territory guides the picker but never blocks a
        save, so a beat outlives a territory change. Labels come from the owner's assignment
        snapshot, falling back to the beat's own prior snapshot (`previous_labels`) — never a
        fresh Humbee read, so a draft autosave makes zero upstream calls."""

        assigned = self._owner_geo_assignment(claims, owner_employee_id)["geo_labels"]
        previous = previous_labels or {}
        selected = {"zones": geo.zones, "states": geo.states, "districts": geo.districts}
        geo_json = repository.build_geo_scope_json(
            zones=geo.zones, states=geo.states, districts=geo.districts,
            cats=[c.value for c in geo.cats], as_of=self._clock.now_utc(),
        )
        geo_json["labels"] = {}
        for level, ids in selected.items():
            by_id = {
                label["id"]: label
                for label in [*previous.get(level, []), *assigned[level]]
            }
            geo_json["labels"][level] = [by_id[value] for value in ids if value in by_id]
        return geo_json

    def update_draft(
        self, *, claims: AccessTokenClaims, beat_id: str, body: schemas.PatchDraftBody
    ) -> dict[str, Any]:
        """Autosave for the wizard's geography step (`geo_scope`) and naming step (`display_name`, `frequency`)."""

        scope = self._scope(claims)
        beat = self._load(scope, beat_id)
        self._require_owner_or_privileged(scope, beat)
        allow_pending_approval = self._is_privileged(scope)
        self._require_active(beat)
        version = self._working_version(
            scope, beat, allow_pending_approval=allow_pending_approval
        )
        expected_version_id = version.id
        expected_version_updated_at = version.updated_at

        # Resolved before the write transaction opens: geography validation reads the owner's
        # assignment rows, and that read must not hold a transaction open across the write below.
        geo_json = (
            self._resolve_geo_scope(
                claims, beat.owner_employee_id, body.geo_scope,
                previous_labels=(version.geo_scope or {}).get("labels"),
            )
            if body.geo_scope
            else None
        )
        freq_json = _validate_frequency(body.frequency) if body.frequency else None
        end_read_transaction(self._session)

        try:
            with transaction(self._session):
                beat = self._load_for_update(scope, beat_id)
                self._require_owner_or_privileged(scope, beat)
                self._require_active(beat)
                version = self._working_version(
                    scope, beat, allow_pending_approval=self._is_privileged(scope)
                )
                if (
                    version.id != expected_version_id
                    or version.updated_at != expected_version_updated_at
                ):
                    raise ApiError(
                        409, "stale_draft", "This beat's draft changed while it was being updated."
                    )
                if body.code is not None:
                    self._reject_taken_code(beat, body.code)
                repository.update_draft_version(
                    self._session,
                    version=version,
                    display_name=body.display_name,
                    code=body.code,
                    geo_scope=geo_json,
                    frequency=freq_json,
                )
                self._refresh_pending_edit_diff(scope, beat)
                if beat.current_version_id is None and (
                    body.display_name is not None or body.code is not None
                ):
                    beat.display_name = version.display_name
                    beat.code = version.code
                    self._session.flush()
                payload = self._detail_payload(
                    scope.tenant_id, beat, version_id=version.id
                )
        except IntegrityError as exc:
            _code_conflict(exc)
        return payload

    def search_scope_outlets(
        self, *, claims: AccessTokenClaims, beat_id: str, query: str | None,
        cursor: str | None = None, limit: int = 100,
        district_ids: list[str] | None = None,
        shop_categories: list[schemas.ShopCategory] | None = None,
    ) -> dict[str, Any]:
        """Outlet-picker pool: exactly one Humbee outlet-search page per call. Outlets another beat holds are
        returned with `taken_by_beat` set so the picker can show who holds them.

        `district_ids` / `shop_categories` browse the scope being edited on screen before it is
        saved; the save itself re-validates the outlets.
        """

        scope = self._scope(claims)
        beat = self._load(scope, beat_id)
        self._require_owner_or_privileged(scope, beat)
        version_id = beat.draft_version_id or beat.current_version_id
        version = (
            repository.get_version(self._session, tenant_id=scope.tenant_id, version_id=version_id)
            if version_id
            else None
        )
        if version is None or version_id is None:
            raise ApiError(409, "no_version_in_progress", "This beat has no version to search from.")
        if district_ids is None:
            if shop_categories is not None:
                raise ApiError(
                    422, "district_required", "Pass district_ids with shop_categories."
                )
            search_districts = repository.read_districts(version.geo_scope)
            search_categories = list(version.geo_scope.get("cats") or [])
        else:
            search_districts = list(dict.fromkeys(district_ids))
            search_categories = [category.value for category in shop_categories or []]
        end_read_transaction(self._session)

        with transaction(self._session):
            page = self._outlets().search_outlet_page(
                tenant_id=scope.tenant_id,
                district_ids=search_districts,
                category_ids=search_categories,
                query=query,
                cursor=cursor,
                limit=limit,
                actor_employee_id=scope.actor_employee_id,
            )
            projected_by_ref = self._projected_by_outlet_ref(
                tenant_id=scope.tenant_id,
                outlet_refs=[record.external_id for record in page.records],
            )
            taken_by = self._outlet_claims(
                tenant_id=scope.tenant_id,
                exclude_beat_id=beat_id,
                projected_by_ref=projected_by_ref,
            )
            member_ids = repository.member_outlet_ids(
                self._session,
                version_id=version_id,
                outlet_ids=[outlet.local_id for outlet in projected_by_ref.values()],
            )
            selected = {
                ref for ref, outlet in projected_by_ref.items() if outlet.local_id in member_ids
            }
        return schemas.ScopeOutletsResponse(
            next_cursor=page.next_cursor,
            items=[
                schemas.ScopeOutletItem(
                    outlet_ref=record.external_id,
                    name=record.name,
                    locality=record.locality,
                    category=schemas.to_shop_category(record.category),
                    selected=record.external_id in selected,
                    taken_by_beat=taken_by.get(record.external_id),
                )
                for record in page.records
            ],
        ).model_dump(mode="json")

    def replace_draft_outlets(
        self, *, claims: AccessTokenClaims, beat_id: str, body: schemas.DraftOutletsBody
    ) -> dict[str, Any]:
        scope = self._scope(claims)
        beat = self._load(scope, beat_id)
        self._require_owner_or_privileged(scope, beat)
        allow_pending_approval = self._is_privileged(scope)
        self._require_active(beat)
        version = self._working_version(
            scope, beat, allow_pending_approval=allow_pending_approval
        )
        expected_version_id = version.id
        expected_version_updated_at = version.updated_at
        geo_scope = dict(version.geo_scope)
        refs = list(dict.fromkeys(body.outlet_refs))
        end_read_transaction(self._session)

        self._refresh_and_validate_outlets(
            tenant_id=scope.tenant_id,
            geo_scope=geo_scope,
            outlet_refs=refs,
            actor_employee_id=scope.actor_employee_id,
        )

        with transaction(self._session):
            beat = self._load_for_update(scope, beat_id)
            self._require_owner_or_privileged(scope, beat)
            self._require_active(beat)
            version = self._working_version(
                scope, beat, allow_pending_approval=self._is_privileged(scope)
            )
            if (
                version.id != expected_version_id
                or version.updated_at != expected_version_updated_at
            ):
                raise ApiError(
                    409,
                    "stale_draft",
                    "This beat's draft changed while outlets were being validated.",
                )
            # Every ref was just returned by the outlet search and upserted in this transaction, so the
            # projection row exists; this also resolves the local ids the membership FK needs.
            projected_by_ref = self._reject_taken_outlets(beat, refs)
            count = repository.replace_outlets(
                self._session,
                tenant_id=scope.tenant_id,
                version_id=version.id,
                outlet_ids=[projected_by_ref[ref].local_id for ref in refs],
                created_by_employee_id=scope.actor_employee_id,
                now=self._clock.now_utc(),
            )
            repository.update_draft_version(self._session, version=version, outlet_count=count)
            self._refresh_pending_edit_diff(scope, beat)
            payload = self._detail_payload(
                scope.tenant_id, beat, version_id=version.id
            )
        return payload

    def _outlet_refs(self, *, tenant_id: str, version_id: str) -> list[str]:
        return [
            outlet.record.external_id
            for _, outlet in self._version_outlets(
                tenant_id=tenant_id, version_id=version_id
            )
        ]

    # -- submit ---------------------------------------------------------------

    def submit_beat(
        self, *, claims: AccessTokenClaims, beat_id: str, idempotency_key: str, raw_body: bytes,
        request_id: str | None,
    ) -> tuple[int, dict[str, Any]]:
        scope = self._scope(claims)
        endpoint = f"/api/v1/beats/{beat_id}/submit"
        replay = self._check_idempotency(
            endpoint=endpoint,
            idempotency_key=idempotency_key,
            raw_body=raw_body,
            tenant_id=scope.tenant_id,
        )
        if replay is not None:
            end_read_transaction(self._session)
            return replay

        beat = self._load(scope, beat_id)
        self._require_owner_or_privileged(scope, beat)
        if beat.lifecycle_state != "draft":
            raise ApiError(
                409, "not_a_draft", f"This beat is already {beat.lifecycle_state}.",
            )
        version = self._working_version(scope, beat)
        expected_version_id = version.id
        expected_version_updated_at = version.updated_at
        expected_outlet_refs = self._outlet_refs(
            tenant_id=scope.tenant_id, version_id=version.id
        )
        geo_scope = dict(version.geo_scope)
        end_read_transaction(self._session)

        self._refresh_and_validate_outlets(
            tenant_id=scope.tenant_id,
            geo_scope=geo_scope,
            outlet_refs=expected_outlet_refs,
            actor_employee_id=scope.actor_employee_id,
        )

        with transaction(self._session):
            replay = self._check_idempotency(
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                raw_body=raw_body,
                tenant_id=scope.tenant_id,
            )
            if replay is not None:
                status_code, payload = replay
            else:
                beat = self._load_for_update(scope, beat_id)
                self._require_owner_or_privileged(scope, beat)
                if beat.lifecycle_state != "draft":
                    raise ApiError(
                        409, "not_a_draft", f"This beat is already {beat.lifecycle_state}.",
                    )
                previous_state = beat.lifecycle_state
                version = self._working_version(scope, beat)
                if (
                    version.id != expected_version_id
                    or version.updated_at != expected_version_updated_at
                    or self._outlet_refs(
                        tenant_id=scope.tenant_id, version_id=version.id
                    )
                    != expected_outlet_refs
                ):
                    raise ApiError(
                        409,
                        "stale_draft",
                        "This beat's draft changed while outlets were being validated.",
                    )
                self._reject_taken_outlets(beat, expected_outlet_refs)
                _validate_version_for_submit(version)
                self._reject_taken_code(beat, version.code)

                if self._is_privileged(scope):
                    self._publish_applied(
                        claims,
                        apply_create_approved(
                            self._session,
                            tenant_id=scope.tenant_id,
                            beat_id=beat.id,
                            approved_at=self._clock.now_utc(),
                            approved_by_id=claims.employee_id,
                        ),
                    )
                    status_code = 200
                else:
                    version.state = "pending_approval"
                    beat.lifecycle_state = "pending_approval"
                    self._session.flush()
                    version.approval_request_id = approvals_service.create(
                        self._session,
                        tenant_id=scope.tenant_id,
                        subject_type="beat_create",
                        subject_id=beat.id,
                        requester_id=beat.owner_employee_id,
                        clock=self._clock,
                        request_id=request_id,
                    ).id
                    self._session.flush()
                    status_code = 202

                self._audit.record_transition(
                    tenant_id=scope.tenant_id, entity_type=AUDIT_ENTITY, entity_id=beat.id,
                    from_state=previous_state, to_state=beat.lifecycle_state,
                    actor_employee_id=claims.employee_id, request_id=request_id,
                    change_payload={"transition": "beat_submitted", "version_id": version.id},
                )
                payload = self._detail_payload(
                    scope.tenant_id, beat, version_id=version.id
                )
                self._store_idempotency(
                    endpoint=endpoint,
                    idempotency_key=idempotency_key,
                    raw_body=raw_body,
                    status_code=status_code,
                    payload=payload,
                    scope=scope,
                )
        return status_code, payload

    # -- edit -------------------------------------------------------------

    def create_edit_branch(self, *, claims: AccessTokenClaims, beat_id: str) -> dict[str, Any]:
        """Edit-screen entry — branches a proposed version from the approved current one."""

        scope = self._scope(claims)
        with transaction(self._session):
            beat = self._load_for_update(scope, beat_id)
            self._require_owner(scope, beat)
            if (
                beat.lifecycle_state != "approved"
                or beat.activation_state != "active"
                or beat.current_version_id is None
            ):
                raise ApiError(409, "beat_inactive", "This beat cannot be edited right now.")
            if beat.draft_version_id is not None:
                existing = repository.get_version(
                    self._session, tenant_id=scope.tenant_id, version_id=beat.draft_version_id
                )
                if existing is not None and existing.state == "draft":
                    return schemas.BranchEditResponse(
                        beat_id=beat.id,
                        base_version_id=beat.current_version_id,
                        proposed_version_id=existing.id,
                    ).model_dump(mode="json")
                raise ApiError(
                    409, "edit_already_pending", "An edit for this beat is already in progress."
                )
            current = repository.get_version(
                self._session, tenant_id=scope.tenant_id, version_id=beat.current_version_id
            )
            if current is None:
                raise ApiError(409, "beat_inactive", "This beat has no approved version to edit.")

            version_no = repository.next_version_no(
                self._session, tenant_id=scope.tenant_id, beat_id=beat.id
            )
            proposed = repository.insert_version(
                self._session, tenant_id=scope.tenant_id, beat_id=beat.id, version_no=version_no,
                state="draft", display_name=current.display_name, code=current.code,
                geo_scope=current.geo_scope, frequency=current.frequency,
                outlet_count=current.outlet_count, created_by_employee_id=claims.employee_id,
            )
            repository.copy_outlets(
                self._session, tenant_id=scope.tenant_id, from_version_id=current.id,
                to_version_id=proposed.id, created_by_employee_id=claims.employee_id,
            )
            beat.draft_version_id = proposed.id
            self._session.flush()
            payload = schemas.BranchEditResponse(
                beat_id=beat.id, base_version_id=current.id, proposed_version_id=proposed.id
            ).model_dump(mode="json")
        return payload

    def discard_draft(self, *, claims: AccessTokenClaims, beat_id: str) -> dict[str, Any]:
        """Edit-screen "Discard" — abandons an in-progress edit of an already-approved beat, falling
        back to the current version. A first-time draft has nothing to fall back to, so discarding
        it retires the beat and releases its outlets."""

        scope = self._scope(claims)
        with transaction(self._session):
            beat = self._load_for_update(scope, beat_id)
            self._require_owner(scope, beat)
            if beat.draft_version_id is None:
                if beat.current_version_id is None:
                    raise ApiError(409, "no_draft_in_progress", "This beat has no draft to discard.")
                return self._detail_payload(
                    scope.tenant_id, beat, version_id=beat.current_version_id
                )
            draft = repository.get_version(
                self._session, tenant_id=scope.tenant_id, version_id=beat.draft_version_id
            )
            if draft is None:
                raise ApiError(409, "no_draft_in_progress", "This beat has no draft to discard.")
            if draft.state == "pending_approval":
                raise ApiError(
                    409,
                    "already_submitted",
                    "This edit has already been submitted; withdraw it through the approval instead.",
                )
            draft.state = "withdrawn"
            beat.draft_version_id = None
            if beat.current_version_id is None:
                beat.is_active = False
                beat.code = beat.id
            self._session.flush()
            payload = self._detail_payload(
                scope.tenant_id, beat, version_id=beat.current_version_id or draft.id
            )
        return payload

    def _compute_diff(
        self, tenant_id: str, base: BeatVersion, proposed: BeatVersion
    ) -> list[dict[str, Any]]:
        diff: list[dict[str, Any]] = []
        if base.display_name != proposed.display_name:
            diff.append(
                {"field": "display_name", "label": "Beat name",
                 "from_display": base.display_name, "to_display": proposed.display_name}
            )
        if base.code != proposed.code:
            diff.append(
                {"field": "code", "label": "Beat code",
                 "from_display": base.code, "to_display": proposed.code}
            )
        for key, label in (
            ("zones", "Zone cluster"), ("states", "State cluster"),
            ("districts", "District cluster"), ("cats", "Shop category"),
        ):
            before = set(base.geo_scope.get(key) or [])
            after = set(proposed.geo_scope.get(key) or [])
            if before != after:
                diff.append(
                    {"field": f"geo.{key}", "label": label,
                     "from_display": ", ".join(sorted(before)) or "—",
                     "to_display": ", ".join(sorted(after)) or "—",
                     "added": sorted(after - before), "removed": sorted(before - after)}
                )
        if base.frequency.get("frequency") != proposed.frequency.get("frequency"):
            diff.append(
                {"field": "frequency.frequency", "label": "Visit frequency",
                 "from_display": base.frequency.get("frequency"),
                 "to_display": proposed.frequency.get("frequency")}
            )
        # Compared separately from the frequency category above: a schedule can change which days
        # it runs on without changing daily/weekly/etc, and that must still show up as a diff line
        # instead of two identical-looking "Visit frequency" values.
        if (base.frequency.get("visit_days") or []) != (proposed.frequency.get("visit_days") or []):
            diff.append(
                {"field": "frequency.visit_days", "label": "Visit days",
                 "from_display": sorted(base.frequency.get("visit_days") or []),
                 "to_display": sorted(proposed.frequency.get("visit_days") or [])}
            )
        if (base.frequency.get("week_cycle") or []) != (proposed.frequency.get("week_cycle") or []):
            diff.append(
                {"field": "frequency.week_cycle", "label": "Week cycle",
                 "from_display": sorted(base.frequency.get("week_cycle") or []),
                 "to_display": sorted(proposed.frequency.get("week_cycle") or [])}
            )
        memberships = self._outlets_for_versions(
            tenant_id=tenant_id, version_ids=[base.id, proposed.id]
        )
        base_by_ref = {outlet.record.external_id: outlet for _, outlet in memberships[base.id]}
        proposed_by_ref = {
            outlet.record.external_id: outlet for _, outlet in memberships[proposed.id]
        }
        base_order = [outlet.record.external_id for _, outlet in memberships[base.id]]
        proposed_order = [outlet.record.external_id for _, outlet in memberships[proposed.id]]
        base_refs = set(base_order)
        proposed_refs = set(proposed_order)
        if base_order != proposed_order:
            diff.append(
                {"field": "outlets", "label": "Outlets",
                 "from_display": str(len(base_refs)), "to_display": str(len(proposed_refs)),
                 # Named, not just counted: these are the same `ProjectedOutlet` rows already
                 # fetched above for the id comparison, so naming them costs nothing extra.
                 "added": [
                     {"outlet_ref": ref, "name": proposed_by_ref[ref].record.name,
                      "locality": proposed_by_ref[ref].record.locality}
                     for ref in sorted(proposed_refs - base_refs)
                 ],
                 "removed": [
                     {"outlet_ref": ref, "name": base_by_ref[ref].record.name,
                      "locality": base_by_ref[ref].record.locality}
                     for ref in sorted(base_refs - proposed_refs)
                 ]}
            )
        return diff

    def _refresh_pending_edit_diff(self, scope: ScopeContext, beat: Beat) -> None:
        if beat.current_version_id is None or beat.draft_version_id is None:
            return
        edit_request = repository.get_pending_edit_request(
            self._session, tenant_id=scope.tenant_id, beat_id=beat.id
        )
        if edit_request is None:
            return
        current = repository.get_version(
            self._session, tenant_id=scope.tenant_id, version_id=beat.current_version_id
        )
        draft = repository.get_version(
            self._session, tenant_id=scope.tenant_id, version_id=beat.draft_version_id
        )
        if current is None or draft is None:
            return
        repository.update_edit_request_diff(
            self._session,
            edit_request=edit_request,
            diff=self._compute_diff(scope.tenant_id, current, draft),
        )

    def submit_edit(
        self, *, claims: AccessTokenClaims, beat_id: str, idempotency_key: str, raw_body: bytes,
        request_id: str | None,
    ) -> tuple[int, dict[str, Any]]:
        scope = self._scope(claims)
        endpoint = f"/api/v1/beats/{beat_id}/edit-requests/submit"
        replay = self._check_idempotency(
            endpoint=endpoint,
            idempotency_key=idempotency_key,
            raw_body=raw_body,
            tenant_id=scope.tenant_id,
        )
        if replay is not None:
            end_read_transaction(self._session)
            return replay

        beat = self._load(scope, beat_id)
        self._require_owner(scope, beat)
        self._require_active(beat)
        if beat.draft_version_id is None:
            raise ApiError(409, "no_edit_in_progress", "There is no edit in progress for this beat.")
        draft = self._working_version(scope, beat)
        current = repository.get_version(
            self._session, tenant_id=scope.tenant_id, version_id=beat.current_version_id
        )
        if current is None or current.version_no != draft.version_no - 1:
            raise ApiError(
                409, "stale_edit_base", "This beat changed since you started editing."
            )
        expected_draft_id = draft.id
        expected_draft_updated_at = draft.updated_at
        expected_current_id = current.id
        expected_outlet_refs = self._outlet_refs(
            tenant_id=scope.tenant_id, version_id=draft.id
        )
        geo_scope = dict(draft.geo_scope)
        end_read_transaction(self._session)

        self._refresh_and_validate_outlets(
            tenant_id=scope.tenant_id,
            geo_scope=geo_scope,
            outlet_refs=expected_outlet_refs,
            actor_employee_id=scope.actor_employee_id,
        )

        with transaction(self._session):
            replay = self._check_idempotency(
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                raw_body=raw_body,
                tenant_id=scope.tenant_id,
            )
            if replay is not None:
                status_code, payload = replay
            else:
                beat = self._load_for_update(scope, beat_id)
                self._require_owner(scope, beat)
                self._require_active(beat)
                if (
                    beat.draft_version_id != expected_draft_id
                    or beat.current_version_id != expected_current_id
                ):
                    raise ApiError(
                        409, "stale_edit_base", "This beat changed since you started editing."
                    )
                draft = self._working_version(scope, beat)
                current = repository.get_version(
                    self._session,
                    tenant_id=scope.tenant_id,
                    version_id=expected_current_id,
                )
                if (
                    current is None
                    or current.version_no != draft.version_no - 1
                    or draft.updated_at != expected_draft_updated_at
                    or self._outlet_refs(
                        tenant_id=scope.tenant_id, version_id=draft.id
                    )
                    != expected_outlet_refs
                ):
                    raise ApiError(
                        409, "stale_edit_base", "This beat changed since you started editing."
                    )
                self._reject_taken_outlets(beat, expected_outlet_refs)
                _validate_version_for_submit(draft)
                self._reject_taken_code(beat, draft.code)
                diff = self._compute_diff(scope.tenant_id, current, draft)
                if not diff:
                    raise ApiError(422, "empty_edit", "Nothing has changed yet.")

                edit_request = repository.insert_edit_request(
                    self._session,
                    tenant_id=scope.tenant_id,
                    beat_id=beat.id,
                    base_version_id=current.id,
                    proposed_version_id=draft.id,
                    diff=diff,
                    submitted_at=self._clock.now_utc(),
                    submitted_by_employee_id=claims.employee_id,
                )
                if self._is_privileged(scope):
                    self._publish_applied(
                        claims,
                        apply_edit_approved(
                            self._session,
                            tenant_id=scope.tenant_id,
                            beat_id=beat.id,
                            approved_at=self._clock.now_utc(),
                            approved_by_id=claims.employee_id,
                        ),
                    )
                    status_code = 200
                else:
                    draft.state = "pending_approval"
                    self._session.flush()
                    approval = approvals_service.create(
                        self._session,
                        tenant_id=scope.tenant_id,
                        subject_type="beat_edit",
                        subject_id=beat.id,
                        requester_id=beat.owner_employee_id,
                        clock=self._clock,
                        request_id=request_id,
                    )
                    repository.link_edit_request_approval(
                        self._session,
                        edit_request=edit_request,
                        approval_request_id=approval.id,
                    )
                    status_code = 202
                self._audit.record_transition(
                    tenant_id=scope.tenant_id, entity_type=AUDIT_ENTITY, entity_id=beat.id,
                    from_state="approved", to_state="approved",
                    actor_employee_id=claims.employee_id, request_id=request_id,
                    change_payload={"transition": "beat_edit_submitted", "version_id": draft.id},
                )

                payload = self._detail_payload(
                    scope.tenant_id, beat, version_id=draft.id
                )
                self._store_idempotency(
                    endpoint=endpoint,
                    idempotency_key=idempotency_key,
                    raw_body=raw_body,
                    status_code=status_code,
                    payload=payload,
                    scope=scope,
                )
        return status_code, payload

    # -- admin ------------------------------------------------------------

    def admin_update_beat(
        self, *, claims: AccessTokenClaims, beat_id: str, body: schemas.AdminUpdateBeatBody,
        idempotency_key: str, raw_body: bytes,
    ) -> dict[str, Any]:
        """Applies immediately, no approval. Admin may edit any beat; a Manager may
        do the same for beats owned by Sales Persons in their own reporting tree (`_load`'s
        OWN_TREE scoping already restricts which beat this resolves to). Reassigning the beat's
        owner stays Admin-only regardless of who calls this."""

        scope = self._scope(claims)
        self._require_privileged(scope)
        endpoint = f"/api/v1/beats/{beat_id}"
        replay = self._check_idempotency(
            endpoint=endpoint,
            idempotency_key=idempotency_key,
            raw_body=raw_body,
            tenant_id=scope.tenant_id,
        )
        if replay is not None:
            end_read_transaction(self._session)
            return replay[1]

        beat = self._load(scope, beat_id)
        if beat.lifecycle_state not in {"approved", "pending_approval"}:
            raise ApiError(
                409,
                "not_editable",
                "Only approved or pending approval beats can be edited directly.",
            )
        expected_lifecycle_state = beat.lifecycle_state
        expected_owner_id = beat.owner_employee_id
        # The active draft/proposal (if any) is the version Admin finalizes, never the stale
        # approved one it would supersede — see the branch below.
        source_version_id = beat.draft_version_id or beat.current_version_id
        current = repository.get_version(
            self._session, tenant_id=scope.tenant_id, version_id=source_version_id
        )
        if current is None or source_version_id is None:
            raise ApiError(409, "not_editable", "This beat has no editable version.")
        expected_source_updated_at = current.updated_at

        new_owner = body.owner_employee_id or beat.owner_employee_id
        geo_json = (
            self._resolve_geo_scope(
                claims, new_owner, body.geo_scope,
                previous_labels=(current.geo_scope or {}).get("labels"),
            )
            if body.geo_scope
            else dict(current.geo_scope)
        )
        freq_json = (
            _validate_frequency(body.frequency)
            if body.frequency
            else dict(current.frequency)
        )
        display_name = body.display_name or current.display_name
        outlet_refs = (
            list(dict.fromkeys(body.outlet_refs))
            if body.outlet_refs is not None
            else None
        )
        if body.owner_employee_id and body.owner_employee_id != beat.owner_employee_id:
            self._require_admin(scope)
        refs_to_validate = outlet_refs
        if refs_to_validate is None and body.geo_scope:
            refs_to_validate = (
                self._outlet_refs(tenant_id=scope.tenant_id, version_id=source_version_id) or None
            )
        end_read_transaction(self._session)

        if refs_to_validate is not None:
            self._refresh_and_validate_outlets(
                tenant_id=scope.tenant_id,
                geo_scope=geo_json,
                outlet_refs=refs_to_validate,
                actor_employee_id=scope.actor_employee_id,
            )

        with transaction(self._session):
            replay = self._check_idempotency(
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                raw_body=raw_body,
                tenant_id=scope.tenant_id,
            )
            if replay is not None:
                payload = replay[1]
            else:
                beat = self._load_for_update(scope, beat_id)
                current_source_id = beat.draft_version_id or beat.current_version_id
                if (
                    beat.lifecycle_state != expected_lifecycle_state
                    or beat.owner_employee_id != expected_owner_id
                    or current_source_id != source_version_id
                ):
                    raise ApiError(
                        409,
                        "stale_beat",
                        "This beat changed while outlets were being validated.",
                    )
                current = repository.get_version(
                    self._session,
                    tenant_id=scope.tenant_id,
                    version_id=source_version_id,
                )
                if current is None:
                    raise ApiError(409, "not_editable", "This beat has no editable version.")
                if current.updated_at != expected_source_updated_at:
                    raise ApiError(
                        409,
                        "stale_beat",
                        "This beat changed while outlets were being validated.",
                    )

                outlet_ids: list[str] | None = None
                if outlet_refs is not None:
                    projected_by_ref = self._reject_taken_outlets(beat, outlet_refs)
                    outlet_ids = [
                        projected_by_ref[ref].local_id for ref in outlet_refs
                    ]

                now = self._clock.now_utc()
                # The active draft/proposal (if any) is what gets finalized — a first-time
                # submission (no prior approved version) or an SP's edit-in-progress against an
                # already-approved beat. `current` already resolved to it above (`source_version_id`
                # prioritizes `draft_version_id`).
                old_current_id = beat.current_version_id
                if beat.draft_version_id is not None:
                    if old_current_id is not None:
                        old_current = repository.get_version(
                            self._session, tenant_id=scope.tenant_id, version_id=old_current_id
                        )
                        if old_current is not None:
                            # Must stop being `approved` before `current` becomes `approved`,
                            # because the partial unique index is non-deferrable.
                            old_current.state = "superseded"
                            self._session.flush()
                    current.state = "approved"
                    current.display_name = display_name
                    current.geo_scope = geo_json
                    current.frequency = freq_json
                    if outlet_ids is not None:
                        current.outlet_count = len(outlet_ids)
                    current.approved_at = now
                    current.approved_by_employee_id = claims.employee_id
                    beat.lifecycle_state = "approved"
                    beat.current_version_id = current.id
                    beat.draft_version_id = None
                    new_version = current
                    if outlet_ids is not None:
                        repository.replace_outlets(
                            self._session,
                            tenant_id=scope.tenant_id,
                            version_id=new_version.id,
                            outlet_ids=outlet_ids,
                            created_by_employee_id=claims.employee_id,
                            now=now,
                        )
                    # First-time submission routes through `beat_create`; an edit-in-progress
                    # against an already-approved beat routes through `beat_edit`.
                    subject_type = "beat_create" if old_current_id is None else "beat_edit"
                    request = approvals_repository.pending_for_subject(
                        self._session,
                        tenant_id=scope.tenant_id,
                        subject_type=subject_type,
                        subject_id=beat.id,
                    )
                    if request is not None:
                        note = "Admin immediate beat update applied without separate approval."
                        approvals_repository.append_decision(
                            self._session,
                            tenant_id=scope.tenant_id,
                            request_id=request.id,
                            action=DecisionAction.APPROVED,
                            occurred_at=now,
                            actor_id=claims.employee_id,
                            actor_role=claims.role,
                            note=note,
                        )
                        approvals_repository.apply_decision_outcome(
                            self._session,
                            request=request,
                            status=ApprovalStatus.APPROVED,
                            decided_at=now,
                            decided_by_id=claims.employee_id,
                            decision_note=note,
                        )
                    if old_current_id is not None:
                        edit_request = repository.get_pending_edit_request(
                            self._session, tenant_id=scope.tenant_id, beat_id=beat.id
                        )
                        if edit_request is not None:
                            repository.resolve_edit_request(
                                self._session,
                                edit_request=edit_request,
                                state="applied",
                                resolved_at=now,
                            )
                else:
                    # No draft/proposal exists — a pure direct edit of an approved beat with
                    # nothing pending. Branch a fresh version from the current one.
                    version_no = repository.next_version_no(
                        self._session, tenant_id=scope.tenant_id, beat_id=beat.id
                    )
                    # The old version must stop being `approved` before the new approved
                    # version is inserted because the partial unique index is non-deferrable.
                    current.state = "superseded"
                    self._session.flush()
                    new_version = repository.insert_version(
                        self._session,
                        tenant_id=scope.tenant_id,
                        beat_id=beat.id,
                        version_no=version_no,
                        state="approved",
                        display_name=display_name,
                        code=current.code,
                        geo_scope=geo_json,
                        frequency=freq_json,
                        outlet_count=(
                            len(outlet_ids)
                            if outlet_ids is not None
                            else current.outlet_count
                        ),
                        created_by_employee_id=claims.employee_id,
                        approved_at=now,
                        approved_by_employee_id=claims.employee_id,
                    )
                    if outlet_ids is not None:
                        repository.replace_outlets(
                            self._session,
                            tenant_id=scope.tenant_id,
                            version_id=new_version.id,
                            outlet_ids=outlet_ids,
                            created_by_employee_id=claims.employee_id,
                            now=now,
                        )
                    else:
                        repository.copy_outlets(
                            self._session,
                            tenant_id=scope.tenant_id,
                            from_version_id=current.id,
                            to_version_id=new_version.id,
                            created_by_employee_id=claims.employee_id,
                        )
                    beat.current_version_id = new_version.id
                    approvals_service.withdraw_for_subject(
                        self._session,
                        tenant_id=scope.tenant_id,
                        subject_type="beat_edit",
                        subject_id=beat.id,
                        clock=self._clock,
                    )
                owner_reassigned = new_owner != beat.owner_employee_id
                beat.owner_employee_id = new_owner
                beat.display_name = display_name
                self._session.flush()

                self._audit.record_transition(
                    tenant_id=scope.tenant_id,
                    entity_type=AUDIT_ENTITY,
                    entity_id=beat.id,
                    from_state=expected_lifecycle_state,
                    to_state="approved",
                    actor_employee_id=claims.employee_id,
                    change_payload={
                        "transition": "beat_admin_edited",
                        "new_version_id": new_version.id,
                    },
                )
                if owner_reassigned:
                    self._events.publish(
                        tenant_id=scope.tenant_id,
                        stream="beats",
                        event_type="beat_owner_reassigned",
                        aggregate_type="beat",
                        aggregate_id=beat.id,
                        payload={"beat_id": beat.id, "owner_employee_id": new_owner},
                        actor_employee_id=claims.employee_id,
                    )
                # `draft_version_id` is always cleared by this point — either it was already
                # None, or the branch above just finalized and cleared it.
                payload = self._detail_payload(
                    scope.tenant_id, beat, version_id=beat.current_version_id
                )
                self._store_idempotency(
                    endpoint=endpoint,
                    idempotency_key=idempotency_key,
                    raw_body=raw_body,
                    status_code=200,
                    payload=payload,
                    scope=scope,
                )
        return payload

    def deactivate(
        self, *, claims: AccessTokenClaims, beat_id: str, body: schemas.DeactivateBody,
        idempotency_key: str, raw_body: bytes,
    ) -> dict[str, Any]:
        """Admin-only; auto-withdraws a pending edit."""

        scope = self._scope(claims)
        self._require_admin(scope)
        endpoint = f"/api/v1/beats/{beat_id}/deactivate"
        with transaction(self._session):
            replay = self._check_idempotency(
                endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body,
                tenant_id=scope.tenant_id,
            )
            if replay is not None:
                payload = replay[1]
            else:
                beat = self._load_for_update(scope, beat_id)
                if beat.lifecycle_state != "approved" or beat.activation_state != "active":
                    raise ApiError(409, "already_inactive", "This beat is already inactive.")

                now = self._clock.now_utc()
                beat.activation_state = "inactive"
                beat.deactivated_at = now
                beat.deactivated_by = claims.employee_id
                beat.deactivation_reason = body.reason
                self._session.flush()

                repository.insert_activation_event(
                    self._session, tenant_id=scope.tenant_id, beat_id=beat.id, action="deactivated",
                    actor_employee_id=claims.employee_id, reason=body.reason, occurred_at=now,
                )
                approvals_service.withdraw_for_subject(
                    self._session, tenant_id=scope.tenant_id, subject_type="beat_edit",
                    subject_id=beat.id, clock=self._clock,
                )
                self._audit.record_transition(
                    tenant_id=scope.tenant_id, entity_type=AUDIT_ENTITY, entity_id=beat.id,
                    from_state="approved", to_state="approved",
                    actor_employee_id=claims.employee_id, reason=body.reason,
                    change_payload={"transition": "beat_deactivated"},
                )
                self._events.publish(
                    tenant_id=scope.tenant_id, stream="beats", event_type="beat_deactivated",
                    aggregate_type="beat", aggregate_id=beat.id, payload={"beat_id": beat.id},
                    actor_employee_id=claims.employee_id,
                )
                payload = self._detail_payload(
                    scope.tenant_id, beat, version_id=beat.current_version_id or beat.draft_version_id
                )
                self._store_idempotency(
                    endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body,
                    status_code=200, payload=payload, scope=scope,
                )
        return payload

    def reactivate(
        self, *, claims: AccessTokenClaims, beat_id: str, idempotency_key: str, raw_body: bytes,
    ) -> dict[str, Any]:
        """Admin-only."""

        scope = self._scope(claims)
        self._require_admin(scope)
        endpoint = f"/api/v1/beats/{beat_id}/reactivate"
        with transaction(self._session):
            replay = self._check_idempotency(
                endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body,
                tenant_id=scope.tenant_id,
            )
            if replay is not None:
                payload = replay[1]
            else:
                beat = self._load_for_update(scope, beat_id)
                if (
                    beat.lifecycle_state != "approved"
                    or beat.activation_state != "inactive"
                    or beat.current_version_id is None
                ):
                    raise ApiError(409, "already_active", "This beat is already active.")
                self._reject_taken_outlets(
                    beat,
                    self._outlet_refs(tenant_id=scope.tenant_id, version_id=beat.current_version_id),
                )

                now = self._clock.now_utc()
                beat.activation_state = "active"
                beat.deactivated_at = None
                beat.deactivated_by = None
                beat.deactivation_reason = None
                self._session.flush()

                repository.insert_activation_event(
                    self._session, tenant_id=scope.tenant_id, beat_id=beat.id, action="reactivated",
                    actor_employee_id=claims.employee_id, reason=None, occurred_at=now,
                )
                self._audit.record_transition(
                    tenant_id=scope.tenant_id, entity_type=AUDIT_ENTITY, entity_id=beat.id,
                    from_state="approved", to_state="approved", actor_employee_id=claims.employee_id,
                    change_payload={"transition": "beat_reactivated"},
                )
                self._events.publish(
                    tenant_id=scope.tenant_id, stream="beats", event_type="beat_reactivated",
                    aggregate_type="beat", aggregate_id=beat.id, payload={"beat_id": beat.id},
                    actor_employee_id=claims.employee_id,
                )
                payload = self._detail_payload(
                    scope.tenant_id, beat, version_id=beat.current_version_id or beat.draft_version_id
                )
                self._store_idempotency(
                    endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body,
                    status_code=200, payload=payload, scope=scope,
                )
        return payload


__all__ = ["BeatService", "display_status"]

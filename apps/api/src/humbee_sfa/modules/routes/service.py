"""Routes/Visits business logic: visit lifecycle, data assembly and invariants.

Transaction ownership lives here, not in the router, mirroring `beats.service` / `leave.service`.
The punch-in gate is re-checked here on every write, in-process, via
`attendance.service.get_duty_state` — never by re-deriving punch state from another module's
tables. Beat data (approved+active listing, outlet snapshots) comes from `beats.service`'s public
`BeatService` the same way.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import literal, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from humbee_sfa.core.business_date import to_business_date
from humbee_sfa.core.clock import Clock, SystemClock
from humbee_sfa.core.conventions import generate_ulid
from humbee_sfa.core.db import end_read_transaction, transaction
from humbee_sfa.core.deps import AccessTokenClaims
from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.core.settings import Settings, get_settings
from humbee_sfa.integration.humbee.outlet import (
    HumbeeOutletMasterProvider,
    OutletRecord,
)
from humbee_sfa.modules.attendance import service as attendance_service
from humbee_sfa.modules.beats.service import BeatService
from humbee_sfa.modules.org.scope import (
    OrgResource,
    Scope,
    ScopeContext,
    ScopeResolver,
    employee_scope_condition,
)
from humbee_sfa.modules.org.service import OrgService, list_employee_names
from humbee_sfa.modules.outlets.service import OutletReadService
from humbee_sfa.modules.routes import repository, schemas
from humbee_sfa.modules.routes.models.route_combined_visit import RouteCombinedVisit
from humbee_sfa.modules.routes.models.route_combined_visit_feedback import (
    RouteCombinedVisitFeedback,
)
from humbee_sfa.modules.routes.models.route_missed_visit_audit import RouteMissedVisitAudit
from humbee_sfa.modules.routes.models.route_outlet_coordinate_correction import (
    RouteOutletCoordinateCorrection,
)
from humbee_sfa.modules.routes.models.route_plan import RoutePlan
from humbee_sfa.modules.routes.models.route_stop import RouteStop
from humbee_sfa.modules.routes.models.route_visit import RouteVisit
from humbee_sfa.modules.routes.models.route_visit_outcome import RouteVisitOutcome
from humbee_sfa.platform.audit import AuditLogService
from humbee_sfa.platform.domain_events import DomainEventPublisher
from humbee_sfa.platform.idempotency import IdempotencyService

AUDIT_ENTITY_PLAN = "routes_plan"
AUDIT_ENTITY_VISIT = "routes_visit"
AUDIT_ENTITY_COMBINED_VISIT = "routes_combined_visit"

COMBINED_VISIT_FEEDBACK_FORM_KEY = "combined_visit_feedback"
# The field set is still pending from the business; this is the fixed v1 shape.
_COMBINED_VISIT_FEEDBACK_FORM_SCHEMA: dict[str, Any] = {
    "fields": ["went_well", "needs_coaching", "next_visit_action"]
}


def current_business_date(clock: Clock, *, settings: Settings | None = None) -> date:
    resolved = settings or get_settings()
    return to_business_date(clock.now_utc(), resolved.day_boundary_hour_ist)


def _fingerprint(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _next_visit_id(
    stops: list[RouteStop], visits_by_stop: dict[str, RouteVisit], visits: list[RouteVisit]
) -> str | None:
    """`next_stop`: the lowest-sequence stop whose visit is still `scheduled`, else the
    oldest visit in progress."""

    pending = [
        visit
        for stop in stops
        if (visit := visits_by_stop.get(stop.id)) is not None and visit.state == "scheduled"
    ]
    in_progress = sorted(
        (visit for visit in visits if visit.state == "in_progress"),
        key=lambda visit: visit.checked_in_at or visit.created_at,
    )
    return next((visit.id for visit in [*pending, *in_progress]), None)


def _derived_id(*parts: str) -> str:
    return hashlib.blake2b("\x00".join(parts).encode(), digest_size=13).hexdigest()


def _outlet_seconds(visit: RouteVisit) -> int | None:
    if visit.checked_in_at is None or visit.checked_out_at is None:
        return None
    return max(0, int((visit.checked_out_at - visit.checked_in_at).total_seconds()))


def _outlets_by_ref(outlets: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {o["outlet_ref"]: o for o in outlets}


def _weekday_assigned(frequency: dict[str, Any], business_date: date) -> bool:
    """Does the beat's frequency (jsonb) schedule it for this weekday?

    Beats store `visit_days` as 0=Sunday..6=Saturday.
    """

    if frequency.get("frequency") == "daily":
        return True
    visit_days = frequency.get("visit_days") or []
    sunday_based_weekday = (business_date.weekday() + 1) % 7
    return sunday_based_weekday in visit_days


class RouteService:
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
        self._injected_outlet_port = outlet_port
        self._audit = AuditLogService(session)
        self._events = DomainEventPublisher(session, self._clock)
        self._idempotency = IdempotencyService(session)

    # -- scope / idempotency ------------------------------------------------

    def _scope(self, claims: AccessTokenClaims) -> ScopeContext:
        # Routes/visits are activity data: SELF for the owning Sales Person, OWN_TREE (read-only)
        # for their manager, ORG (read-only) for Admin.
        return ScopeResolver.resolve_from_claims(claims, OrgResource.ACTIVITY_DATA)

    def _require_self(self, scope: ScopeContext) -> None:
        if scope.scope is not Scope.SELF:
            raise ApiError(403, "forbidden", "Only the Sales Person may do this.")

    def _authorize_report(self, scope: ScopeContext, employee_id: str) -> None:
        if scope.scope is Scope.SELF:
            raise ApiError(403, "forbidden", "Only the Sales Person may do this.")
        if scope.scope is Scope.ORG:
            return
        allowed = self._session.execute(
            select(employee_scope_condition(scope, literal(employee_id)))
        ).scalar()
        if not allowed:
            raise ApiError(403, "forbidden", "That employee is not in your reporting tree.")

    def _outlet_port(self) -> HumbeeOutletMasterProvider:
        if self._injected_outlet_port is not None:
            return self._injected_outlet_port
        try:
            return HumbeeOutletMasterProvider(self._settings)
        except RuntimeError as exc:
            raise ApiError(
                503, "upstream_unavailable", "The outlet directory is unavailable right now."
            ) from exc

    def _refresh_check_in_outlet(
        self, *, tenant_id: str, outlet_id: str, actor_employee_id: str
    ) -> OutletRecord | None:
        """Refresh the outlet projection without enclosing the network wait in a route transaction.

        Everything before this gate is read-only, so the transaction is closed for the duration of
        the outlet detail call. The refreshed projection is only staged; it commits with the visit transition
        the caller goes on to apply, which reloads the visit first.
        """

        end_read_transaction(self._session)
        try:
            return OutletReadService(
                self._session,
                settings=self._settings,
                clock=self._clock,
                outlet_port=self._outlet_port(),
            ).refresh_outlet(
                tenant_id=tenant_id,
                outlet_id=outlet_id,
                actor_employee_id=actor_employee_id,
            )
        except ApiError as exc:
            if exc.code != "upstream_unavailable":
                raise
            return None

    def _assert_punched_in(self, *, tenant_id: str, employee_id: str) -> None:
        """Punch-in gate, defence in depth. Attendance unavailable fails closed: any exception
        surfacing from `get_duty_state` is a 5xx already handled by the global error handler, not
        silently treated as punched-in."""

        duty = attendance_service.get_duty_state(
            self._session, tenant_id=tenant_id, employee_id=employee_id, clock=self._clock,
            settings=self._settings,
        )
        if not duty.get("on_duty"):
            raise ApiError(403, "not_punched_in", "Punch in to run your route.")

    def _assert_no_conflicting_activity(
        self, *, claims: AccessTokenClaims, scope: ScopeContext, visit_id: str
    ) -> None:
        """Only one of {outlet visit, official work} may run at a time per employee. Re-checked at
        both `check_in` call sites for the same reason as `_assert_punched_in` (defence in depth
        around the outlet detail network wait)."""

        active_visit = repository.get_active_visit(
            self._session, tenant_id=scope.tenant_id, employee_id=claims.employee_id
        )
        if active_visit is not None and active_visit.id != visit_id:
            raise ApiError(
                409, "visit_already_in_progress", "End your current visit before starting another."
            )
        if attendance_service.OfficialWorkService(
            self._session, settings=self._settings, clock=self._clock
        ).current(claims=claims) is not None:
            raise ApiError(409, "official_work_running", "End official work before starting a visit.")

    def _check_idempotency(
        self, *, endpoint: str, idempotency_key: str, raw_body: bytes, tenant_id: str
    ) -> tuple[int, dict[str, Any]] | None:
        self._idempotency.claim(tenant_id=tenant_id, endpoint=endpoint, key=idempotency_key)
        existing = self._idempotency.get(tenant_id=tenant_id, endpoint=endpoint, key=idempotency_key)
        if existing is None:
            return None
        if not self._idempotency.is_exact_replay(existing, _fingerprint(raw_body)):
            raise ApiError(
                409, "idempotency_conflict", "Idempotency key was already used with a different payload."
            )
        return existing.status_code, existing.response_payload

    def _store_idempotency(
        self, *, endpoint: str, idempotency_key: str, raw_body: bytes, status_code: int,
        payload: dict[str, Any], tenant_id: str, actor_employee_id: str,
    ) -> None:
        self._idempotency.save(
            tenant_id=tenant_id, endpoint=endpoint, key=idempotency_key,
            request_fingerprint=_fingerprint(raw_body),
            response_fingerprint=_fingerprint(json.dumps(payload, sort_keys=True, default=str).encode()),
            status_code=status_code, response_payload=payload, actor_employee_id=actor_employee_id,
        )

    # -- route plans ----------------------------------------------------------

    def _load_plannable_beat(
        self, claims: AccessTokenClaims, beat_id: str
    ) -> tuple[dict[str, Any], str]:
        beat, live_version_id = BeatService(self._session).get_beat_detail_for_planning(
            claims=claims, beat_id=beat_id
        )
        if beat["lifecycle_state"] != "approved" or beat["activation_state"] != "active":
            raise ApiError(422, "beat_not_plannable", "The beat must be approved and active.")
        if not beat["outlets"]:
            raise ApiError(422, "beat_has_no_outlets", "The beat has no outlets to plan a route from.")
        return beat, live_version_id

    def _append_beat_stops(
        self, *, scope: ScopeContext, claims: AccessTokenClaims, business_date: date,
        beat: dict[str, Any], beat_version_id: str, run_origin: str,
    ) -> RoutePlan:
        plan = repository.lock_or_create_plan(
            self._session,
            tenant_id=scope.tenant_id,
            employee_id=claims.employee_id,
            business_date=business_date,
            beat_id=beat["id"],
            beat_version_id=beat_version_id,
            created_by_employee_id=claims.employee_id,
        )
        repository.attach_day_visits_to_plan(
            self._session,
            tenant_id=scope.tenant_id,
            employee_id=claims.employee_id,
            business_date=business_date,
            route_plan_id=plan.id,
        )
        outlets = beat["outlets"]
        by_ref = _outlets_by_ref(outlets)
        existing_stops = repository.list_stops(self._session, route_plan_id=plan.id)
        existing_refs = {s.humbee_outlet_id for s in existing_stops}
        new_refs = [o["outlet_ref"] for o in outlets if o["outlet_ref"] not in existing_refs]

        day_visits = repository.list_day_visits(
            self._session,
            tenant_id=scope.tenant_id,
            employee_id=claims.employee_id,
            business_date=business_date,
        )
        stopless_visits_by_outlet = {
            visit.humbee_outlet_id: visit
            for visit in day_visits
            if visit.route_stop_id is None and visit.state != "cancelled"
        }
        now = self._clock.now_utc()
        points = repository.outlet_points(
            self._session, tenant_id=scope.tenant_id, outlet_refs=new_refs
        )

        sequence_no = max((s.sequence_no for s in existing_stops), default=0)
        new_rows: list[RouteStop | RouteVisit] = []
        relinked_visits: list[RouteVisit] = []
        for ref in new_refs:
            sequence_no += 1
            outlet = by_ref[ref]
            stop = RouteStop(
                id=generate_ulid(), tenant_id=scope.tenant_id, route_plan_id=plan.id, humbee_outlet_id=ref,
                sequence_no=sequence_no, beat_id=beat["id"], beat_version_id=beat_version_id,
                run_origin=run_origin, snapshot_name=outlet["name"], snapshot_locality=outlet["locality"],
                snapshot_category=outlet.get("category"), snapshot_as_of=now,
                snapshot_point=points.get(ref), created_by_employee_id=claims.employee_id,
            )
            new_rows.append(stop)
            existing_visit = stopless_visits_by_outlet.get(ref)
            if existing_visit is not None:
                existing_visit.route_plan_id = plan.id
                existing_visit.route_stop_id = stop.id
                existing_visit.origin = "planned"
                stop.visit_id = existing_visit.id
                relinked_visits.append(existing_visit)
            else:
                visit = RouteVisit(
                    id=generate_ulid(),
                    tenant_id=scope.tenant_id,
                    employee_id=scope.actor_employee_id,
                    route_plan_id=plan.id,
                    route_stop_id=stop.id,
                    humbee_outlet_id=ref,
                    state="scheduled",
                    origin="planned",
                    visit_type="physical",
                    planned_for_date=business_date,
                    occurred_at=now,
                    received_at=now,
                    business_date=business_date,
                    created_by_employee_id=claims.employee_id,
                )
                new_rows.append(visit)
                stop.visit_id = visit.id

        self._session.add_all(new_rows)
        self._session.flush()
        repository.fill_stop_distances(self._session, route_plan_id=plan.id)

        closed_visits = [
            visit for visit in relinked_visits if visit.state in repository.VISITED_STATES
        ]
        outcomes = repository.outcomes_for_visits(
            self._session, visit_ids=[visit.id for visit in closed_visits]
        )
        for visit in closed_visits:
            self._publish_visit_completed(
                visit=visit, outcome=outcomes[visit.id], actor_employee_id=claims.employee_id
            )

        if run_origin == "unplanned_beat" and new_refs:
            self._events.publish(
                tenant_id=scope.tenant_id, stream="routes", event_type="unplanned_beat_run_started",
                aggregate_type="route_plan", aggregate_id=plan.id,
                payload={"employee_id": scope.actor_employee_id, "beat_id": beat["id"]},
                actor_employee_id=claims.employee_id,
            )
        return plan

    def _day_payload(
        self, *, tenant_id: str, employee_id: str, business_date: date, plan: RoutePlan | None
    ) -> dict[str, Any]:
        stops = repository.list_stops(self._session, route_plan_id=plan.id) if plan is not None else []
        all_visits = repository.list_day_visits(
            self._session,
            tenant_id=tenant_id,
            employee_id=employee_id,
            business_date=business_date,
        )
        visits_by_stop = {
            visit.route_stop_id: visit for visit in all_visits if visit.route_stop_id is not None
        }
        next_visit_id = _next_visit_id(stops, visits_by_stop, all_visits)
        checkin_points = repository.checkin_points_for_visits(
            self._session, visit_ids=[v.id for v in all_visits]
        )
        outcomes = repository.outcomes_for_visits(
            self._session, visit_ids=[v.id for v in all_visits]
        )

        def _checkin_gps_for(visit: RouteVisit | None) -> schemas.GpsFix | None:
            if visit is None or visit.id not in checkin_points:
                return None
            lat, lng = checkin_points[visit.id]
            return schemas.GpsFix(
                lat=lat, lng=lng,
                accuracy_m=float(visit.checkin_gps_accuracy_m) if visit.checkin_gps_accuracy_m is not None else None,
                provider=visit.checkin_gps_provider, is_mock=visit.checkin_gps_is_mock,
            )

        def _outcome_fields(visit: RouteVisit | None) -> dict[str, Any]:
            outcome = outcomes.get(visit.id) if visit else None
            if outcome is None:
                return {"outcome": None, "no_order_reason": None, "order_count": None}
            return {
                "outcome": outcome.outcome,
                "no_order_reason": outcome.no_order_reason,
                "order_count": len(outcome.order_ids) if outcome.outcome == "order_placed" else None,
            }

        beat_names_by_version = BeatService(self._session).route_group_names_for_versions(
            tenant_id=tenant_id, version_ids=[stop.beat_version_id for stop in stops]
        )
        combined_visit_outlet_refs = {
            row.humbee_outlet_id
            for row in repository.list_scheduled_combined_visits_for_sales_person(
                self._session,
                tenant_id=tenant_id,
                sales_person_employee_id=employee_id,
                business_date=business_date,
            )
        }
        outlet_groups: list[schemas.RouteOutletGroup] = []
        group_indexes: dict[str | None, int] = {}

        def _append_group_outlet(
            *, beat_id: str | None, beat_name: str, run_origin: str | None,
            outlet: schemas.RouteStopItem,
        ) -> None:
            if beat_id not in group_indexes:
                group_indexes[beat_id] = len(outlet_groups)
                outlet_groups.append(
                    schemas.RouteOutletGroup(
                        beat_id=beat_id, beat_name=beat_name, run_origin=run_origin, outlets=[]
                    )
                )
            outlet_groups[group_indexes[beat_id]].outlets.append(outlet)

        for stop in stops:
            visit = visits_by_stop.get(stop.id)
            _append_group_outlet(
                beat_id=stop.beat_id,
                beat_name=beat_names_by_version.get(stop.beat_version_id, "Beat unavailable"),
                run_origin=stop.run_origin,
                outlet=schemas.RouteStopItem(
                    outlet_ref=stop.humbee_outlet_id, sequence_no=stop.sequence_no,
                    name=stop.snapshot_name, locality=stop.snapshot_locality,
                    category=stop.snapshot_category,
                    distance_from_prev_km=float(stop.distance_from_prev_km) if stop.distance_from_prev_km is not None else None,
                    beat_id=stop.beat_id, run_origin=stop.run_origin,
                    checkin_gps=_checkin_gps_for(visit),
                    visit_id=visit.id if visit else None,
                    visit_state=visit.state if visit else None,
                    visit_origin=visit.origin if visit else None,
                    visit_type=visit.visit_type if visit else None,
                    checked_in_at=visit.checked_in_at if visit else None,
                    checked_out_at=visit.checked_out_at if visit else None,
                    combined_visit_scheduled=stop.humbee_outlet_id in combined_visit_outlet_refs,
                    is_next=visit is not None and visit.id == next_visit_id,
                    **_outcome_fields(visit),
                ),
            )
        # Unplanned visits are appended after planned stops.
        unplanned = sorted(
            (v for v in all_visits if v.route_stop_id is None and v.state != "cancelled"),
            key=lambda v: v.checked_in_at or v.created_at,
        )
        unplanned_outlets = {
            outlet.record.external_id: outlet.record
            for outlet in OutletReadService(
                self._session, settings=self._settings, clock=self._clock
            ).get_projected_outlets(
                tenant_id=tenant_id,
                outlet_ids=[v.humbee_outlet_id for v in unplanned],
            )
        }
        next_sequence_no = len(stops)
        for visit in unplanned:
            next_sequence_no += 1
            outlet_record = unplanned_outlets.get(visit.humbee_outlet_id)
            _append_group_outlet(
                beat_id=None,
                beat_name="Unplanned visits",
                run_origin=None,
                outlet=schemas.RouteStopItem(
                    outlet_ref=visit.humbee_outlet_id, sequence_no=next_sequence_no,
                    name=outlet_record.name if outlet_record else "Outlet unavailable",
                    locality=outlet_record.locality if outlet_record else None, category=None,
                    distance_from_prev_km=None, beat_id=None, run_origin=None,
                    checkin_gps=_checkin_gps_for(visit),
                    visit_id=visit.id, visit_state=visit.state,
                    visit_origin=visit.origin, visit_type=visit.visit_type,
                    checked_in_at=visit.checked_in_at, checked_out_at=visit.checked_out_at,
                    combined_visit_scheduled=visit.humbee_outlet_id in combined_visit_outlet_refs,
                    is_next=visit.id == next_visit_id,
                    **_outcome_fields(visit),
                ),
            )
        totals = repository.day_totals(
            self._session, tenant_id=tenant_id, employee_ids=[employee_id], business_date=business_date
        )[employee_id]
        day = attendance_service.day_summary(
            self._session, tenant_id=tenant_id, employee_id=employee_id, business_date=business_date
        )
        return schemas.RoutePlanResponse(
            id=plan.id if plan is not None else None,
            business_date=business_date,
            beat_id=plan.beat_id if plan is not None else None,
            state=plan.state if plan is not None else None,
            planned_stop_count=totals.planned,
            visited_count=totals.visited,
            planned_visited_count=totals.planned_visited,
            unplanned_visit_count=totals.unplanned_visited,
            coverage_pct=totals.coverage_pct,
            started_at=plan.started_at if plan is not None else None,
            closed_at=plan.closed_at if plan is not None else None,
            outlet_groups=outlet_groups,
            punched_in_at=day["punched_in_at"], punched_out_at=day["punched_out_at"],
            on_duty=day["on_duty"], official_work=day["official_work"],
        ).model_dump(mode="json")

    def get_day(
        self, *, claims: AccessTokenClaims, business_date: date | None = None, employee_id: str | None = None,
    ) -> dict[str, Any]:
        scope = self._scope(claims)
        resolved_business_date = business_date or current_business_date(
            self._clock, settings=self._settings
        )
        target_employee_id = employee_id or claims.employee_id
        if employee_id is None or employee_id == scope.actor_employee_id:
            self._require_self(scope)
        else:
            self._authorize_report(scope, employee_id)
        plan = repository.get_active_plan(
            self._session, tenant_id=scope.tenant_id, employee_id=target_employee_id,
            business_date=resolved_business_date,
        )
        return self._day_payload(
            tenant_id=scope.tenant_id,
            employee_id=target_employee_id,
            business_date=resolved_business_date,
            plan=plan,
        )

    def list_unplanned_outlets(self, *, claims: AccessTokenClaims) -> list[dict[str, Any]]:
        """Outlet search never returns locality — only the per-outlet detail call
        does, and this list is too large to fetch one at a time. `UnplannedOutletItem` carries
        no locality field for that reason; the picker shows name only."""

        assigned = BeatService(self._session).list_assigned_outlets(claims=claims)
        return [
            {"outlet_ref": row["humbee_outlet_id"], "name": row["name"]}
            for row in assigned
        ]

    def get_active_visit_outlet(self, *, claims: AccessTokenClaims, visit_id: str) -> str:
        """The outlet behind one of the caller's own visits, in progress right now.

        Unlike `get_day`, this does not require a `RoutePlan` to exist — an unplanned visit
        has no plan at all, only a `RouteVisit` row. This resolves cart context for both planned
        and unplanned visits.
        """

        scope = self._scope(claims)
        self._require_self(scope)
        visit = self._load_own_visit(scope, visit_id)
        if visit.state != "in_progress":
            raise ApiError(409, "visit_not_active", "This visit is not in progress.")
        return str(visit.humbee_outlet_id)

    def get_active_visit_id(self, *, claims: AccessTokenClaims) -> str | None:
        """The caller's own visit currently `in_progress`, if any (at most one, per the unique
        `ix_routes_visits_open` index). Attendance's official-work/punch-out mutex uses this
        to block starting official work or punching out while a visit is running."""

        scope = self._scope(claims)
        self._require_self(scope)
        visit = repository.get_active_visit(
            self._session, tenant_id=scope.tenant_id, employee_id=claims.employee_id
        )
        return visit.id if visit is not None else None

    def get_visit_outcome(self, *, claims: AccessTokenClaims, visit_id: str) -> dict[str, Any]:
        """Read-back for a completed visit — reopening the outlet after check-out shows the
        recorded outcome (reason/comment) and the orders placed, not just the outcome chip."""

        scope = self._scope(claims)
        self._require_self(scope)
        visit = self._load_own_visit(scope, visit_id)
        outcome = repository.outcomes_for_visits(self._session, visit_ids=[visit.id]).get(visit.id)
        return schemas.VisitOutcomeDetail(
            visit_id=visit.id,
            outcome=outcome.outcome if outcome else None,
            no_order_reason=outcome.no_order_reason if outcome else None,
            note=outcome.no_order_note if outcome else None,
            order_ids=list(outcome.order_ids) if outcome else [],
            recorded_at=outcome.recorded_at if outcome else None,
        ).model_dump(mode="json")

    def get_last_outlet_visit(self, *, claims: AccessTokenClaims, outlet_ref: str) -> dict[str, Any]:
        scope = self._scope(claims)
        found = repository.last_closed_outlet_visit(
            self._session, tenant_id=scope.tenant_id, humbee_outlet_id=outlet_ref
        )
        if found is None:
            return schemas.LastOutletVisitResponse(outlet_ref=outlet_ref, last_visit=None).model_dump(mode="json")
        visit, outcome = found
        names = list_employee_names(
            self._session, tenant_id=scope.tenant_id, employee_ids=[visit.employee_id]
        )
        return schemas.LastOutletVisitResponse(
            outlet_ref=outlet_ref,
            last_visit=schemas.LastOutletVisit(
                visit_id=visit.id,
                business_date=visit.business_date,
                employee_name=names.get(visit.employee_id),
                visit_type=visit.visit_type,
                checked_in_at=visit.checked_in_at,
                checked_out_at=visit.checked_out_at,
                outcome=outcome.outcome,
                no_order_reason=outcome.no_order_reason,
                note=outcome.no_order_note,
                order_count=len(outcome.order_ids),
            ),
        ).model_dump(mode="json")

    def start_beat(
        self, *, claims: AccessTokenClaims, body: schemas.SwitchBeatBody,
        idempotency_key: str, raw_body: bytes,
    ) -> tuple[int, dict[str, Any]]:
        scope = self._scope(claims)
        self._require_self(scope)
        endpoint = "POST /route-plans/switch-beat"
        replay = self._check_idempotency(
            endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body,
            tenant_id=scope.tenant_id,
        )
        if replay is not None:
            return replay

        self._assert_punched_in(tenant_id=scope.tenant_id, employee_id=claims.employee_id)
        if repository.get_active_visit(
            self._session, tenant_id=scope.tenant_id, employee_id=claims.employee_id
        ) is not None:
            raise ApiError(409, "visit_already_in_progress", "End your current visit before switching.")

        beat, live_version_id = self._load_plannable_beat(claims, body.beat_id)
        business_date = current_business_date(self._clock, settings=self._settings)
        run_origin = (
            "assigned_beat"
            if _weekday_assigned(beat["frequency"], business_date)
            else "unplanned_beat"
        )

        with transaction(self._session):
            plan = self._append_beat_stops(
                scope=scope,
                claims=claims,
                business_date=business_date,
                beat=beat,
                beat_version_id=live_version_id,
                run_origin=run_origin,
            )
            stop_count = len(repository.list_stops(self._session, route_plan_id=plan.id))
            self._events.publish(
                tenant_id=scope.tenant_id,
                stream="routes",
                event_type="route_plan_saved",
                aggregate_type="route_plan",
                aggregate_id=plan.id,
                payload={
                    "employee_id": scope.actor_employee_id,
                    "business_date": business_date.isoformat(),
                    "beat_id": body.beat_id,
                    "run_origin": run_origin,
                    "stop_count": stop_count,
                },
                actor_employee_id=claims.employee_id,
            )
            payload = self._day_payload(
                tenant_id=scope.tenant_id,
                employee_id=claims.employee_id,
                business_date=business_date,
                plan=plan,
            )
            self._store_idempotency(
                endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body, status_code=200,
                payload=payload, tenant_id=scope.tenant_id, actor_employee_id=claims.employee_id,
            )
        return 200, payload

    # -- visits -----------------------------------------------------------

    def _visit_payload(self, visit: RouteVisit) -> dict[str, Any]:
        return schemas.VisitResponse(
            id=visit.id, route_plan_id=visit.route_plan_id, route_stop_id=visit.route_stop_id,
            outlet_ref=visit.humbee_outlet_id, state=visit.state, origin=visit.origin,
            visit_type=visit.visit_type, checked_in_at=visit.checked_in_at,
            checked_out_at=visit.checked_out_at, note=visit.note,
        ).model_dump(mode="json")

    def _resolve_check_in_visit(
        self,
        *,
        claims: AccessTokenClaims,
        scope: ScopeContext,
        visit_id: str,
        outlet_ref: str | None,
    ) -> tuple[RouteVisit | None, str, bool]:
        business_date = current_business_date(self._clock, settings=self._settings)
        existing_visit = repository.get_visit(
            self._session, tenant_id=scope.tenant_id, visit_id=visit_id
        )
        if existing_visit is not None:
            if existing_visit.employee_id != claims.employee_id:
                raise ApiError(404, "visit_not_found", "Visit was not found.")
            if existing_visit.business_date != business_date:
                raise ApiError(
                    409,
                    "visit_not_today",
                    "Visit does not belong to today's business date.",
                )
            return existing_visit, existing_visit.humbee_outlet_id, False
        if outlet_ref is None:
            raise ApiError(422, "outlet_ref_required", "outlet_ref is required for a new visit.")
        planned_visit = repository.find_scheduled_day_visit(
            self._session,
            tenant_id=scope.tenant_id,
            employee_id=claims.employee_id,
            business_date=business_date,
            outlet_ref=outlet_ref,
        )
        if planned_visit is not None:
            return planned_visit, planned_visit.humbee_outlet_id, False
        return None, outlet_ref, True

    def check_in(
        self, *, claims: AccessTokenClaims, visit_id: str, body: schemas.CheckInBody,
        idempotency_key: str, raw_body: bytes,
    ) -> tuple[int, dict[str, Any]]:
        """Unplanned or planned visit entry."""

        scope = self._scope(claims)
        self._require_self(scope)
        endpoint = f"POST /visits/{visit_id}/check-in"
        replay = self._check_idempotency(
            endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body,
            tenant_id=scope.tenant_id,
        )
        if replay is not None:
            return replay

        self._assert_punched_in(tenant_id=scope.tenant_id, employee_id=claims.employee_id)
        occurred_at = body.occurred_at
        if occurred_at.tzinfo is None:
            raise ApiError(422, "invalid_timestamp", "occurred_at must be timezone-aware.")
        if to_business_date(
            occurred_at, self._settings.day_boundary_hour_ist
        ) != current_business_date(self._clock, settings=self._settings):
            raise ApiError(
                422, "invalid_business_date", "occurred_at is not for today's business date."
            )
        visit, resolved_outlet_ref, create_new_visit = self._resolve_check_in_visit(
            claims=claims, scope=scope, visit_id=visit_id, outlet_ref=body.outlet_ref
        )
        resolved_visit_id = visit.id if visit is not None else visit_id
        self._assert_no_conflicting_activity(
            claims=claims, scope=scope, visit_id=resolved_visit_id
        )

        outlet_record: OutletRecord | None = None
        if visit is None or visit.state != "in_progress":
            # Gate before any state transition, so an inactive outlet never reaches in_progress.
            outlet_record = self._refresh_check_in_outlet(
                tenant_id=scope.tenant_id,
                outlet_id=resolved_outlet_ref,
                actor_employee_id=claims.employee_id,
            )
            # `end_read_transaction` above closed the preflight transaction for the outlet detail wait.
            # Re-check mutable command preconditions before applying route state.
            replay = self._check_idempotency(
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                raw_body=raw_body,
                tenant_id=scope.tenant_id,
            )
            if replay is not None:
                return replay
            self._assert_punched_in(
                tenant_id=scope.tenant_id, employee_id=claims.employee_id
            )
            visit, resolved_outlet_ref, create_new_visit = self._resolve_check_in_visit(
                claims=claims, scope=scope, visit_id=visit_id, outlet_ref=body.outlet_ref
            )
            resolved_visit_id = visit.id if visit is not None else visit_id
            self._assert_no_conflicting_activity(
                claims=claims, scope=scope, visit_id=resolved_visit_id
            )
            if (
                (visit is None or visit.state != "in_progress")
                and outlet_record is not None
                and outlet_record.is_active is False
            ):
                raise ApiError(409, "outlet_inactive", "This outlet is inactive. Contact Admin.")

        try:
            with transaction(self._session):
                if create_new_visit:
                    business_date = to_business_date(occurred_at, self._settings.day_boundary_hour_ist)
                    active_plan = repository.get_active_plan(
                        self._session, tenant_id=scope.tenant_id, employee_id=claims.employee_id,
                        business_date=business_date,
                    )
                    visit = RouteVisit(
                        id=visit_id, tenant_id=scope.tenant_id, employee_id=scope.actor_employee_id,
                        route_plan_id=active_plan.id if active_plan is not None else None,
                        route_stop_id=None, humbee_outlet_id=resolved_outlet_ref,
                        state="in_progress", origin="unplanned", visit_type=body.visit_type,
                        occurred_at=occurred_at, received_at=self._clock.now_utc(), business_date=business_date,
                        created_by_employee_id=claims.employee_id,
                    )
                    self._session.add(visit)
                    self._session.flush()
                elif visit is not None and visit.state == "scheduled":
                    visit.visit_type = body.visit_type
                    visit.state = "in_progress"
                    visit.occurred_at = occurred_at
                    visit.received_at = self._clock.now_utc()
                elif visit is not None and visit.state == "in_progress":
                    payload = self._visit_payload(visit)
                    self._store_idempotency(
                        endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body, status_code=200,
                        payload=payload, tenant_id=scope.tenant_id, actor_employee_id=claims.employee_id,
                    )
                    return 200, payload
                else:
                    raise ApiError(409, "visit_already_closed", "This visit is already closed.")

                assert visit is not None
                if body.visit_type == "physical":
                    if body.gps is None:
                        raise ApiError(424, "gps_required", "A GPS fix is required for a physical visit.")
                    from geoalchemy2.elements import WKTElement

                    visit.checkin_gps = WKTElement(f"POINT({body.gps.lng} {body.gps.lat})", srid=4326)
                    visit.checkin_gps_accuracy_m = body.gps.accuracy_m
                    visit.checkin_gps_provider = body.gps.provider
                    visit.checkin_gps_is_mock = body.gps.is_mock
                visit.checked_in_at = occurred_at
                if body.note is not None:
                    visit.note = body.note

                if visit.route_plan_id:
                    plan = repository.get_plan(self._session, scope=scope, plan_id=visit.route_plan_id)
                    if plan is not None and plan.started_at is None:
                        plan.started_at = occurred_at
                        plan.state = "in_progress"

                self._session.flush()
                self._audit.record_transition(
                    tenant_id=scope.tenant_id, entity_type=AUDIT_ENTITY_VISIT, entity_id=visit.id,
                    from_state="scheduled" if visit.origin == "planned" else None, to_state="in_progress",
                    actor_employee_id=claims.employee_id,
                )
                self._events.publish(
                    tenant_id=scope.tenant_id, stream="routes", event_type="visit_started",
                    aggregate_type="route_visit", aggregate_id=visit.id,
                    payload={"employee_id": scope.actor_employee_id, "outlet_ref": visit.humbee_outlet_id,
                             "origin": visit.origin, "visit_type": visit.visit_type},
                    actor_employee_id=claims.employee_id, occurred_at=occurred_at,
                )
                payload = self._visit_payload(visit)
                self._store_idempotency(
                    endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body, status_code=200,
                    payload=payload, tenant_id=scope.tenant_id, actor_employee_id=claims.employee_id,
                )
        except IntegrityError as exc:
            raise _visit_write_conflict(exc) from exc
        return 200, payload

    def _load_own_visit(self, scope: ScopeContext, visit_id: str) -> RouteVisit:
        visit = repository.get_visit(self._session, tenant_id=scope.tenant_id, visit_id=visit_id)
        if visit is None or visit.employee_id != scope.actor_employee_id:
            raise ApiError(404, "visit_not_found", "Visit was not found.")
        return visit

    def submit_coordinate_correction(
        self, *, claims: AccessTokenClaims, visit_id: str, body: schemas.CoordinateCorrectionBody,
        idempotency_key: str, raw_body: bytes,
    ) -> tuple[int, dict[str, Any]]:
        """Queued in `captured_at` order and committed durably before the
        Humbee call — the same "commit before the network call" rule the order write path uses,
        generalised to this write."""

        scope = self._scope(claims)
        self._require_self(scope)
        endpoint = f"POST /visits/{visit_id}/outlet-coordinates"
        port = self._outlet_port()
        with transaction(self._session):
            replay = self._check_idempotency(
                endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body,
                tenant_id=scope.tenant_id,
            )
            if replay is not None:
                return replay
            visit = self._load_own_visit(scope, visit_id)
            if visit.state != "in_progress":
                raise ApiError(409, "visit_not_active", "This visit is not in progress.")
            correction = self._begin_correction(
                correction_id=_derived_id(scope.tenant_id, endpoint, idempotency_key),
                visit=visit, body=body, claims=claims,
            )

        try:
            result = port.submit_coordinate_correction(
                tenant_id=scope.tenant_id, outlet_id=visit.humbee_outlet_id,
                latitude=Decimal(str(body.lat)), longitude=Decimal(str(body.lng)),
                accuracy_m=Decimal(str(body.accuracy_m)), provider=body.provider,
                captured_at=body.captured_at, captured_by=claims.employee_id,
                idempotency_key=correction.id,
            )
        except Exception as exc:
            with transaction(self._session):
                correction.attempts += 1
                correction.status = "failed"
                correction.last_error = str(exc)
            raise

        with transaction(self._session):
            correction.attempts += 1
            correction.status = "accepted" if result.accepted else "rejected"
            correction.rejection_code = result.rejection_code
            correction.submitted_at = self._clock.now_utc()
            payload = schemas.CoordinateCorrectionResponse(
                id=correction.id, outlet_ref=visit.humbee_outlet_id, status=correction.status,
                latitude=float(result.latitude) if result.latitude is not None else None,
                longitude=float(result.longitude) if result.longitude is not None else None,
                rejection_code=result.rejection_code,
            ).model_dump(mode="json")
            self._store_idempotency(
                endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body, status_code=200,
                payload=payload, tenant_id=scope.tenant_id, actor_employee_id=claims.employee_id,
            )
        return 200, payload

    def _begin_correction(
        self, *, correction_id: str, visit: RouteVisit, body: schemas.CoordinateCorrectionBody,
        claims: AccessTokenClaims,
    ) -> RouteOutletCoordinateCorrection:
        correction = self._session.get(RouteOutletCoordinateCorrection, correction_id)
        if correction is None:
            correction = RouteOutletCoordinateCorrection(
                id=correction_id, tenant_id=visit.tenant_id, visit_id=visit.id,
                humbee_outlet_id=visit.humbee_outlet_id, employee_id=visit.employee_id,
                latitude=body.lat, longitude=body.lng, accuracy_m=body.accuracy_m,
                provider=body.provider, captured_at=body.captured_at,
                created_by_employee_id=claims.employee_id,
            )
            self._session.add(correction)
        elif correction.status == "failed":
            correction.status = "pending"
        else:
            raise ApiError(
                409, "correction_in_progress", "This coordinate correction is already being submitted."
            )
        return correction

    def _close_visit(
        self,
        *,
        tenant_id: str,
        visit: RouteVisit,
        actor_employee_id: str,
        closed_at: datetime,
        to_state: str,
        outcome: str,
        no_order_reason: str | None = None,
        no_order_note: str | None = None,
        order_ids: list[str] | None = None,
        timed: bool = True,
    ) -> None:
        outcome_row = RouteVisitOutcome(
            tenant_id=tenant_id,
            visit_id=visit.id,
            outcome=outcome,
            no_order_reason=no_order_reason,
            no_order_note=no_order_note,
            order_ids=order_ids or [],
            recorded_at=closed_at,
            created_by_employee_id=actor_employee_id,
        )
        self._session.add(outcome_row)
        from_state = visit.state
        visit.state = to_state
        visit.checked_out_at = closed_at
        self._session.flush()

        self._audit.record_transition(
            tenant_id=tenant_id,
            entity_type=AUDIT_ENTITY_VISIT,
            entity_id=visit.id,
            from_state=from_state,
            to_state=to_state,
            actor_employee_id=actor_employee_id,
            reason=no_order_reason,
        )
        self._publish_visit_completed(
            visit=visit, outcome=outcome_row, actor_employee_id=actor_employee_id, timed=timed
        )

    def _publish_visit_completed(
        self, *, visit: RouteVisit, outcome: RouteVisitOutcome, actor_employee_id: str,
        timed: bool = True,
    ) -> None:
        productive = visit.state == "visited_with_order"
        payload: dict[str, Any] = {
            "employee_id": visit.employee_id,
            "business_date": visit.business_date.isoformat(),
            "outlet_ref": visit.humbee_outlet_id,
            "productive": productive,
            "planned": visit.route_stop_id is not None,
            "visit_type": visit.visit_type,
            "outlet_seconds": _outlet_seconds(visit) if timed else None,
        }
        if productive:
            payload["order_id"] = list(outcome.order_ids)
            payload["order_ids"] = list(outcome.order_ids)
        else:
            payload["no_order_reason"] = outcome.no_order_reason
        self._events.publish(
            tenant_id=visit.tenant_id,
            stream="routes",
            event_type="visit_completed",
            aggregate_type="route_visit",
            aggregate_id=visit.id,
            payload=payload,
            actor_employee_id=actor_employee_id,
        )

    def log_outcome(
        self, *, claims: AccessTokenClaims, visit_id: str, body: schemas.OutcomeBody,
        idempotency_key: str, raw_body: bytes,
    ) -> tuple[int, dict[str, Any]]:
        """"Mark visited — no order"."""

        scope = self._scope(claims)
        self._require_self(scope)
        endpoint = f"POST /visits/{visit_id}/outcome"
        replay = self._check_idempotency(
            endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body,
            tenant_id=scope.tenant_id,
        )
        if replay is not None:
            return replay

        visit = self._load_own_visit(scope, visit_id)
        if visit.state != "in_progress":
            raise ApiError(409, "visit_already_closed", "This visit is already closed.")

        now = self._clock.now_utc()
        with transaction(self._session):
            self._close_visit(
                tenant_id=scope.tenant_id,
                visit=visit,
                actor_employee_id=claims.employee_id,
                closed_at=now,
                to_state="visited_no_order",
                outcome="no_order",
                no_order_reason=body.reason,
                no_order_note=body.note,
            )
            payload = self._visit_payload(visit)
            self._store_idempotency(
                endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body, status_code=200,
                payload=payload, tenant_id=scope.tenant_id, actor_employee_id=claims.employee_id,
            )
        return 200, payload

    def check_out(self, *, claims: AccessTokenClaims, visit_id: str) -> tuple[int, dict[str, Any]]:
        """"End visit & check out". A visit stays `in_progress` across multiple orders
        (`submit_order` no longer closes it) — check-out is where it actually closes: if
        orders exist for it, this closes the visit with all of them now; with none,
        it's blocked without an outcome. A no-op success if the visit is
        already closed. Not an `Idempotency-Key` command: the multi-order path is naturally
        idempotent (re-derives the order list, and `check_out` is a no-op on an already-closed
        visit), and the rest only reads persisted state."""

        scope = self._scope(claims)
        self._require_self(scope)
        visit = self._load_own_visit(scope, visit_id)
        if visit.state in ("visited_with_order", "visited_no_order"):
            return 200, self._visit_payload(visit)
        if visit.state != "in_progress":
            raise ApiError(409, "visit_already_closed", "This visit is already closed.")

        # Cross-module read via orders' own public service — mirrors how `orders.service` reads
        # `RouteService.get_day` rather than querying `routes` tables directly.
        from humbee_sfa.modules.orders.service import OrderService

        order_ids = OrderService(
            self._session, settings=self._settings, clock=self._clock
        ).order_ids_by_visit(tenant_id=scope.tenant_id, visit_ids=[visit.id]).get(visit.id, [])
        if not order_ids:
            raise ApiError(422, "outcome_required", "Log a visit outcome before ending the visit.")

        now = self._clock.now_utc()
        with transaction(self._session):
            self._close_visit(
                tenant_id=scope.tenant_id,
                visit=visit,
                actor_employee_id=claims.employee_id,
                closed_at=now,
                to_state="visited_with_order",
                outcome="order_placed",
                order_ids=order_ids,
            )
            payload = self._visit_payload(visit)
        return 200, payload

    def close_day(self, *, tenant_id: str, business_date: date, now: datetime) -> int:
        from humbee_sfa.modules.orders.service import OrderService

        open_visits = repository.list_open_day_visits(
            self._session, tenant_id=tenant_id, business_date=business_date
        )
        order_ids_by_visit = OrderService(
            self._session, settings=self._settings, clock=self._clock
        ).order_ids_by_visit(
            tenant_id=tenant_id, visit_ids=[visit.id for visit in open_visits]
        )
        missed_visits = 0
        for visit in open_visits:
            order_ids = order_ids_by_visit.get(visit.id, [])
            if order_ids:
                self._close_visit(
                    tenant_id=tenant_id,
                    visit=visit,
                    actor_employee_id=visit.employee_id,
                    closed_at=now,
                    to_state="visited_with_order",
                    outcome="order_placed",
                    order_ids=order_ids,
                    timed=False,
                )
                continue
            from_state = visit.state
            visit.state = "missed"
            visit.missed_at = now
            self._session.add(
                RouteMissedVisitAudit(
                    tenant_id=tenant_id,
                    visit_id=visit.id,
                    employee_id=visit.employee_id,
                    business_date=business_date,
                    humbee_outlet_id=visit.humbee_outlet_id,
                    planned_visit_type=visit.visit_type,
                    swept_at=now,
                    sweep_run_id=generate_ulid(),
                    created_by_employee_id=visit.created_by_employee_id,
                )
            )
            self._audit.record_transition(
                tenant_id=tenant_id,
                entity_type=AUDIT_ENTITY_VISIT,
                entity_id=visit.id,
                from_state=from_state,
                to_state="missed",
                actor_employee_id=visit.employee_id,
            )
            missed_visits += 1
        plans = (
            self._session.execute(
                select(RoutePlan).where(
                    RoutePlan.tenant_id == tenant_id,
                    RoutePlan.business_date == business_date,
                    RoutePlan.state.in_(("scheduled", "in_progress")),
                    RoutePlan.is_active.is_(True),
                )
            )
            .scalars()
            .all()
        )
        for plan in plans:
            plan.state = "closed"
            plan.closed_at = now
            plan.swept_at = now
        confirmed_visits = {
            (visit.employee_id, visit.humbee_outlet_id): visit
            for visit in self._session.execute(
                select(RouteVisit).where(
                    RouteVisit.tenant_id == tenant_id,
                    RouteVisit.business_date == business_date,
                    RouteVisit.state.in_(("visited_with_order", "visited_no_order")),
                    RouteVisit.is_active.is_(True),
                )
            )
            .scalars()
            .all()
        }
        combined_visits = repository.list_scheduled_combined_visits_for_day(
            self._session, tenant_id=tenant_id, business_date=business_date
        )
        for combined_visit in combined_visits:
            confirmed_visit = confirmed_visits.get(
                (
                    combined_visit.sales_person_employee_id,
                    combined_visit.humbee_outlet_id,
                )
            )
            if confirmed_visit is None:
                continue
            combined_visit.state = "feedback_pending"
            combined_visit.visit_id = confirmed_visit.id
            self._audit.record_transition(
                tenant_id=tenant_id,
                entity_type=AUDIT_ENTITY_COMBINED_VISIT,
                entity_id=combined_visit.id,
                from_state="scheduled",
                to_state="feedback_pending",
                actor_employee_id=combined_visit.manager_employee_id,
            )
        self._session.flush()
        return missed_visits

    # -- missed visits -------------------------------------------

    def list_missed_visits(
        self, *, claims: AccessTokenClaims, employee_id: str | None,
        from_date: date | None, to_date: date | None,
    ) -> dict[str, Any]:
        """Defaults to the trailing 7 days ("this week") from the injected clock."""

        scope = self._scope(claims)
        target_employee = employee_id or scope.actor_employee_id
        if scope.scope is Scope.SELF and target_employee != scope.actor_employee_id:
            raise ApiError(403, "forbidden", "You may only view your own missed visits.")

        to_date = to_date or current_business_date(self._clock, settings=self._settings)
        from_date = from_date or date.fromordinal(to_date.toordinal() - 6)

        rows = repository.list_missed_visits(
            self._session, scope=scope, employee_id=target_employee, from_date=from_date, to_date=to_date
        )
        missed = len(rows)
        visited = repository.count_visited_in_window(
            self._session, scope=scope, employee_id=target_employee, from_date=from_date, to_date=to_date
        )
        planned_missed = sum(1 for _audit, stop in rows if stop is not None)
        planned_visited = repository.count_visited_in_window(
            self._session,
            scope=scope,
            employee_id=target_employee,
            from_date=from_date,
            to_date=to_date,
            planned_only=True,
        )
        denominator = planned_visited + planned_missed
        adherence_pct = round(planned_visited / denominator * 100) if denominator else None
        return schemas.MissedVisitsResponse(
            items=[
                schemas.MissedVisitItem(
                    id=row.id, visit_id=row.visit_id, employee_id=row.employee_id,
                    outlet_ref=row.humbee_outlet_id,
                    outlet_name=stop.snapshot_name if stop else None,
                    outlet_locality=stop.snapshot_locality if stop else None,
                    business_date=row.business_date, planned_visit_type=row.planned_visit_type,
                    swept_at=row.swept_at,
                )
                for row, stop in rows
            ],
            summary=schemas.MissedVisitsSummary(missed=missed, visited=visited, adherence_pct=adherence_pct),
        ).model_dump(mode="json")

    # -- coverage -------------------------------------------------

    def day_totals(
        self, *, tenant_id: str, employee_ids: list[str], business_date: date
    ) -> dict[str, repository.DayTotals]:
        return repository.day_totals(
            self._session,
            tenant_id=tenant_id,
            employee_ids=employee_ids,
            business_date=business_date,
        )

    def coverage_team(
        self, *, claims: AccessTokenClaims, business_date: date, only_sales_person: bool = False,
    ) -> dict[str, Any]:
        scope = self._scope(claims)
        if scope.scope is Scope.SELF:
            raise ApiError(403, "forbidden", "Team coverage is available to managers and admins.")

        roster = OrgService(self._session, settings=self._settings, clock=self._clock).list_all_employees(
            claims=claims,
            role_code="sales_person" if only_sales_person else None,
            status="active",
        )
        employee_ids = [item["id"] for item in roster]
        totals = self.day_totals(
            tenant_id=scope.tenant_id, employee_ids=employee_ids, business_date=business_date
        )
        duty = attendance_service.AttendanceService(
            self._session, settings=self._settings, clock=self._clock
        ).team(claims=claims, business_date=business_date, page=1, page_size=None)
        duty_by_employee = {row["employee_id"]: row for row in duty["items"]}
        positions = attendance_service.latest_positions(
            self._session, tenant_id=scope.tenant_id, employee_ids=employee_ids,
            business_date=business_date, settings=self._settings,
        )

        rows = []
        on_route = 0
        for item in roster:
            day_total = totals[item["id"]]
            duty_row = duty_by_employee.get(item["id"], {})
            on_duty = bool(duty_row.get("on_duty"))
            on_leave = bool(duty_row.get("on_leave"))
            if on_duty and day_total.planned > 0:
                on_route += 1
            fix = positions.get(item["id"])
            rows.append(
                schemas.CoverageRow(
                    employee_id=item["id"], employee_name=item["full_name"], on_duty=on_duty,
                    on_leave=on_leave,
                    punched_in_at=duty_row.get("punched_in_at"),
                    latest_fix=schemas.LatestFix(**fix) if fix else None,
                    visited=day_total.visited, planned=day_total.planned,
                    unplanned_visited=day_total.unplanned_visited,
                )
            )
        team_total = sum(totals.values(), repository.NO_ACTIVITY)
        return schemas.CoverageResponse(
            business_date=business_date, on_route=on_route, on_route_total=len(roster),
            visited=team_total.visited, planned=team_total.planned,
            productive=team_total.productive,
            coverage_pct=team_total.coverage_pct, items=rows,
        ).model_dump(mode="json")

    # -- combined visits -----------------------------------------

    def route_days(
        self, *, claims: AccessTokenClaims, employee_id: str, from_date: date, to_date: date,
    ) -> dict[str, Any]:
        scope = self._scope(claims)
        if scope.scope is Scope.SELF and employee_id != scope.actor_employee_id:
            raise ApiError(403, "forbidden", "You may only view your own route days.")
        dates = repository.route_business_dates(
            self._session, tenant_id=scope.tenant_id, employee_id=employee_id,
            from_date=from_date, to_date=to_date,
        )
        return schemas.RouteDaysResponse(business_dates=dates).model_dump(mode="json")

    def _combined_visit_feedback_payload(
        self, feedback: RouteCombinedVisitFeedback | None,
    ) -> schemas.CombinedVisitFeedbackResponse | None:
        if feedback is None:
            return None
        return schemas.CombinedVisitFeedbackResponse.model_validate(feedback, from_attributes=True)

    def _combined_visit_payload(self, row: RouteCombinedVisit) -> dict[str, Any]:
        feedback = repository.get_combined_visit_feedback(
            self._session, tenant_id=row.tenant_id, combined_visit_id=row.id
        )
        return schemas.CombinedVisitResponse(
            id=row.id, manager_employee_id=row.manager_employee_id,
            sales_person_employee_id=row.sales_person_employee_id, beat_id=row.beat_id,
            outlet_ref=row.humbee_outlet_id, scheduled_business_date=row.scheduled_business_date,
            state=row.state, visit_id=row.visit_id,
            feedback=self._combined_visit_feedback_payload(feedback),
        ).model_dump(mode="json")

    def create_combined_visit(
        self, *, claims: AccessTokenClaims, body: schemas.CreateCombinedVisitBody,
        idempotency_key: str, raw_body: bytes,
    ) -> tuple[int, dict[str, Any]]:
        scope = ScopeResolver.resolve_from_claims(claims, OrgResource.ACTIVITY_DATA)
        if scope.scope is Scope.SELF:
            raise ApiError(403, "forbidden", "Only a manager may schedule a combined visit.")
        endpoint = "POST /combined-visits"
        replay = self._check_idempotency(
            endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body,
            tenant_id=scope.tenant_id,
        )
        if replay is not None:
            return replay

        # The beat's owner must be the named SP, and that SP must be in the manager's
        # tree — `BeatService.get_beat_detail` already enforces OWN_TREE scoping on the load.
        beats = BeatService(self._session)
        beat = beats.get_beat_detail(claims=claims, beat_id=body.beat_id)
        if beat["owner_employee_id"] != body.sales_person_employee_id:
            raise ApiError(403, "forbidden", "The beat does not belong to that Sales Person.")

        if body.outlet_ref not in {o["outlet_ref"] for o in beat["outlets"]}:
            raise ApiError(422, "outlet_not_in_beat", "The outlet must belong to the chosen beat.")

        plannable_days = repository.route_business_dates(
            self._session, tenant_id=scope.tenant_id, employee_id=body.sales_person_employee_id,
            from_date=body.scheduled_business_date, to_date=body.scheduled_business_date,
        )
        if body.scheduled_business_date not in plannable_days:
            raise ApiError(
                422, "no_route_plan_for_day",
                "The Sales Person has no route plan for that day.",
            )

        with transaction(self._session):
            row = RouteCombinedVisit(
                tenant_id=scope.tenant_id, manager_employee_id=scope.actor_employee_id,
                sales_person_employee_id=body.sales_person_employee_id, beat_id=body.beat_id,
                humbee_outlet_id=body.outlet_ref, scheduled_business_date=body.scheduled_business_date,
                state="scheduled", created_by_employee_id=claims.employee_id,
            )
            if body.id:
                row.id = body.id
            self._session.add(row)
            self._session.flush()

            self._audit.record_transition(
                tenant_id=scope.tenant_id, entity_type=AUDIT_ENTITY_COMBINED_VISIT, entity_id=row.id,
                from_state=None, to_state="scheduled", actor_employee_id=claims.employee_id,
            )
            self._events.publish(
                tenant_id=scope.tenant_id, stream="routes", event_type="combined_visit_scheduled",
                aggregate_type="route_combined_visit", aggregate_id=row.id,
                payload={"sales_person_employee_id": body.sales_person_employee_id, "outlet_ref": body.outlet_ref,
                         "scheduled_business_date": body.scheduled_business_date.isoformat()},
                actor_employee_id=claims.employee_id,
            )
            payload = self._combined_visit_payload(row)
            self._store_idempotency(
                endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body, status_code=201,
                payload=payload, tenant_id=scope.tenant_id, actor_employee_id=claims.employee_id,
            )
        return 201, payload

    def list_combined_visits(self, *, claims: AccessTokenClaims) -> dict[str, Any]:
        scope = ScopeResolver.resolve_from_claims(claims, OrgResource.ACTIVITY_DATA)
        if scope.scope is Scope.SELF:
            raise ApiError(403, "forbidden", "Only a manager may view combined visits.")
        rows = repository.list_combined_visits(self._session, scope=scope)
        return {"items": [self._combined_visit_payload(row) for row in rows]}

    def _load_combined_visit(self, claims: AccessTokenClaims, combined_visit_id: str) -> RouteCombinedVisit:
        scope = ScopeResolver.resolve_from_claims(claims, OrgResource.ACTIVITY_DATA)
        if scope.scope is Scope.SELF:
            raise ApiError(403, "forbidden", "Only a manager may view combined visits.")
        row = repository.get_combined_visit(self._session, scope=scope, combined_visit_id=combined_visit_id)
        if row is None:
            raise ApiError(404, "combined_visit_not_found", "Combined visit was not found.")
        return row

    def get_combined_visit(self, *, claims: AccessTokenClaims, combined_visit_id: str) -> dict[str, Any]:
        return self._combined_visit_payload(self._load_combined_visit(claims, combined_visit_id))

    def submit_combined_visit_feedback(
        self, *, claims: AccessTokenClaims, combined_visit_id: str,
        body: schemas.CombinedVisitFeedbackBody, idempotency_key: str, raw_body: bytes,
    ) -> tuple[int, dict[str, Any]]:
        scope = ScopeResolver.resolve_from_claims(claims, OrgResource.ACTIVITY_DATA)
        endpoint = f"POST /combined-visits/{combined_visit_id}/feedback"
        replay = self._check_idempotency(
            endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body,
            tenant_id=scope.tenant_id,
        )
        if replay is not None:
            return replay

        row = self._load_combined_visit(claims, combined_visit_id)
        if row.manager_employee_id != scope.actor_employee_id:
            raise ApiError(403, "forbidden", "Only the scheduling manager may submit feedback.")
        confirmed_visit = repository.get_confirmed_visit(
            self._session, tenant_id=scope.tenant_id, employee_id=row.sales_person_employee_id,
            humbee_outlet_id=row.humbee_outlet_id, business_date=row.scheduled_business_date,
        )
        if confirmed_visit is None:
            raise ApiError(
                409, "visit_not_confirmed",
                "The joint visit has not been confirmed yet — the Sales Person has not checked in "
                "at this outlet for the scheduled date.",
            )

        with transaction(self._session):
            form = repository.get_or_create_form_definition(
                self._session, tenant_id=scope.tenant_id, form_key=COMBINED_VISIT_FEEDBACK_FORM_KEY,
                schema_payload=_COMBINED_VISIT_FEEDBACK_FORM_SCHEMA,
            )
            now = self._clock.now_utc()
            feedback = repository.get_combined_visit_feedback(
                self._session, tenant_id=scope.tenant_id, combined_visit_id=row.id
            )
            if feedback is None:
                feedback = RouteCombinedVisitFeedback(
                    tenant_id=scope.tenant_id, combined_visit_id=row.id, form_definition_id=form.id,
                    overall_rating=body.overall_rating, responses=body.responses, submitted_at=now,
                    submitted_by_employee_id=claims.employee_id, created_by_employee_id=claims.employee_id,
                )
                self._session.add(feedback)
            else:
                feedback.form_definition_id = form.id
                feedback.overall_rating = body.overall_rating
                feedback.responses = body.responses
                feedback.submitted_at = now
                feedback.submitted_by_employee_id = claims.employee_id
            # Same-day feedback can land before the nightly sweep resolves `scheduled ->
            # feedback_pending` (routes/sweep.py) — link it here too so `visit_id` is never left
            # null just because the sweep hasn't run yet.
            row.visit_id = confirmed_visit.id
            row.state = "feedback_submitted"
            self._session.flush()

            self._events.publish(
                tenant_id=scope.tenant_id, stream="routes", event_type="combined_visit_feedback_submitted",
                aggregate_type="route_combined_visit", aggregate_id=row.id,
                payload={"overall_rating": body.overall_rating}, actor_employee_id=claims.employee_id,
            )
            payload = self._combined_visit_payload(row)
            self._store_idempotency(
                endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body, status_code=200,
                payload=payload, tenant_id=scope.tenant_id, actor_employee_id=claims.employee_id,
            )
        return 200, payload


def _visit_write_conflict(exc: IntegrityError) -> ApiError:
    detail = str(getattr(exc, "orig", exc))
    if "ix_routes_visits_open" in detail:
        return ApiError(
            409,
            "visit_already_in_progress",
            "End the active visit before starting another visit.",
        )
    raise exc

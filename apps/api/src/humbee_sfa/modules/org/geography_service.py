"""Geography master reads and per-employee geography assignment (M03 §3a).

Why this lives inside `org` rather than in a `geography` module of its own: the capability is
defined entirely in terms of `org` internals. It writes `org_geography_scope_assignments` (FK to
`org_employees`), authorises through `org.scope`'s `ScopeContext` /
`OrgResource.GEOGRAPHY_ASSIGNMENT`, and M03 §3b.2 lists geography assignment as a *row-scoped org
resource* alongside employee records. A separate module would have to reach across the boundary
for all three, which the architecture forbids. It is a sibling capability of the employee service,
not a separate domain.

OPEN, UNRESOLVED — the Humbee `Location` level. STOP before implementing anything Location-shaped.
    Humbee exposes Zone / State / District only. Screens in the geography lane also want a
    `Location` level, which the upstream master does not provide. That is a product / master-data
    decision that has not been made:
      - `epics/humbee-sfa-build/EPIC.md` — "Humbee G-1 does not currently provide the `Location`
        level required by geography assignment."
      - `epics/humbee-sfa-build/01-organization-identity-access.md` Story 1.2 — "Resolve the
        missing Humbee `Location` level before Location-dependent behavior is released."
      - `docs/rpi/2026-08-22-backend-epic-restructure/research.md` §Location — the decision belongs
        to organization/master-data and blocks *only* Location-dependent assignment behaviour.
    Everything in this module is deliberately Location-free: no Location column, no Location id in
    `GeoScope`, no Location level in `integration/humbee/geography.py`. Fabricating one would mean guessing at
    an API shape Humbee does not expose. Location-dependent behaviour stays out of scope until the
    decision lands in `docs/features/M03-org-workforce-and-geography.md` §3a.

No shop categories, no outlet counts. G-2/G-3/G-4 (SFA-API-Contract v2.2) carry neither, so
geography assignment has no category fields, outlet roll-up, or corresponding DB columns.

No local geography master cache, either. The four ACL-written cache tables
(`org_zone_clusters`/`org_state_clusters`/`org_district_clusters`/`org_shop_categories`) were
retired in epic 07 Story 7.2 — every read goes straight through `HumbeeGeographyMasterProvider`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy.orm import Session

from humbee_sfa.core.clock import Clock, SystemClock
from humbee_sfa.core.db import transaction
from humbee_sfa.core.deps import AccessTokenClaims
from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.core.settings import Settings, get_settings
from humbee_sfa.integration.humbee.geography import (
    DistrictOption,
    GeographyMasterUnavailable,
    HumbeeGeographyMasterProvider,
    StateOption,
    ZoneOption,
)
from humbee_sfa.modules.org import events, geography_repository, geography_schemas, repository
from humbee_sfa.modules.org.scope import (
    OrgResource,
    Scope,
    ScopeContext,
    ScopeResolver,
    internal_routing_scope,
)
from humbee_sfa.platform.audit import AuditLogService
from humbee_sfa.platform.domain_events import DomainEventPublisher

logger = structlog.get_logger("humbee_sfa.org.geography")

AUDIT_ENTITY = "org_geography_scope"


def list_employee_zone_labels(session: Session, *, tenant_id: str) -> dict[str, str]:
    """Primary assigned zone name per employee, for reporting region rollups.

    `dim_employee.region_name` is never populated — Humbee has Zone/State/District, not Region.
    This reads the assignment snapshot (`geo_labels.zones[0].name`) instead.
    """

    rows = geography_repository.list_assignments_in_scope(
        session, scope=internal_routing_scope(tenant_id)
    )
    labels: dict[str, str] = {}
    for row in rows:
        zones = (row.geo_labels or {}).get("zones") or []
        if not zones:
            continue
        name = zones[0].get("name") if isinstance(zones[0], dict) else None
        if name:
            labels[row.employee_id] = str(name)
    return labels


def list_employee_geography_labels(session: Session, *, tenant_id: str) -> dict[str, dict[str, list[str]]]:
    """Every employee's full assigned zone/state/district names, for the admin geography
    mapping report. Unlike `list_employee_zone_labels`, keeps the whole list per level rather
    than just the first zone.
    """

    rows = geography_repository.list_assignments_in_scope(
        session, scope=internal_routing_scope(tenant_id)
    )
    labels: dict[str, dict[str, list[str]]] = {}
    for row in rows:
        geo_labels = row.geo_labels or {}
        labels[row.employee_id] = {
            "zones": [
                str(item.get("name")) for item in geo_labels.get("zones") or [] if isinstance(item, dict) and item.get("name")
            ],
            "states": [
                str(item.get("name")) for item in geo_labels.get("states") or [] if isinstance(item, dict) and item.get("name")
            ],
            "districts": [
                str(item.get("name")) for item in geo_labels.get("districts") or [] if isinstance(item, dict) and item.get("name")
            ],
        }
    return labels


def list_district_labels(session: Session, *, tenant_id: str) -> dict[str, str]:
    """District id → display name from assignment snapshots.

    Union of `geo_labels.districts` on `org_geography_scope_assignments`. An id with no
    snapshot name maps to itself so a fact-table district still renders.
    """

    rows = geography_repository.list_assignments_in_scope(
        session, scope=internal_routing_scope(tenant_id)
    )
    labels: dict[str, str] = {}
    for row in rows:
        for district_id in row.district_cluster_ids or []:
            labels.setdefault(str(district_id), str(district_id))
        districts = (row.geo_labels or {}).get("districts") or []
        for item in districts:
            if not isinstance(item, dict):
                continue
            district_id = item.get("id")
            if not district_id:
                continue
            name = item.get("name")
            labels[str(district_id)] = str(name) if name else str(district_id)
    return labels


def list_employee_assignment_details(
    session: Session, *, tenant_id: str
) -> dict[str, dict[str, Any]]:
    """Every employee's raw assigned district cluster ids (not names) plus `assigned_at`, for
    the admin geography mapping report's overlap detection, outlet-in-scope counts (an id-based
    match against `outlets.humbee_district_id`) and "Assigned On" column.
    """

    rows = geography_repository.list_assignments_in_scope(
        session, scope=internal_routing_scope(tenant_id)
    )
    return {
        row.employee_id: {
            "district_ids": list(row.district_cluster_ids or []),
            "assigned_at": row.assigned_at,
        }
        for row in rows
    }


def district_geography_labels(session: Session, *, tenant_id: str) -> dict[str, dict[str, str]]:
    """District id → `{name, state_id, state_name}`, from the snapshot every assignment stores
    per district (see `_validate_and_label`). Same source rows as `list_district_labels`, kept
    whole instead of collapsed to one field.

    The **keys of the returned dict are the tenant's actual operating districts** — the union of
    every employee's assigned territory — not Humbee's global district master (which is
    unscoped and nationwide: fetching *that* and searching outlets across all of it is what made
    the unassigned-outlets report effectively never finish). This is the right scope for "every
    geography the tenant covers" without a live, unbounded Humbee geography walk.
    """

    rows = geography_repository.list_assignments_in_scope(
        session, scope=internal_routing_scope(tenant_id)
    )
    labels: dict[str, dict[str, str]] = {}
    for row in rows:
        for item in (row.geo_labels or {}).get("districts") or []:
            if not isinstance(item, dict):
                continue
            district_id = item.get("id")
            if not district_id:
                continue
            labels[str(district_id)] = {
                "name": str(item.get("name") or district_id),
                "state_id": str(item.get("state_id") or ""),
                "state_name": str(item.get("state_name") or ""),
            }
    return labels


# R-ORG-39. Named here rather than in `events.py` because geography is the only publisher.
GEO_SCOPE_ASSIGNED = "geo_scope_assigned"


class GeographyService:
    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        clock: Clock | None = None,
        master_port: HumbeeGeographyMasterProvider | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._clock = clock or SystemClock()
        self._master_port = master_port
        self._audit = AuditLogService(session)
        self._events = DomainEventPublisher(session, self._clock)

    # -- scope -------------------------------------------------------------

    def _scope(self, claims: AccessTokenClaims) -> ScopeContext:
        return ScopeResolver.resolve_from_claims(claims, OrgResource.GEOGRAPHY_ASSIGNMENT)

    def _require_assign(self, scope: ScopeContext) -> None:
        """R-ORG-38: assignment is Admin-only; a Manager's picker is read-only."""

        if not scope.can_write or scope.scope is not Scope.ORG:
            raise ApiError(403, "forbidden", "Geography assignment is Admin-only.")

    def _employee_in_scope(self, claims: AccessTokenClaims, employee_id: str) -> None:
        """Out of scope and non-existent are the same 404, so a Manager cannot probe the org."""

        employee_scope = ScopeResolver.resolve_from_claims(claims, OrgResource.EMPLOYEE)
        if repository.get_by_id(self._session, scope=employee_scope, employee_id=employee_id) is None:
            raise ApiError(404, "employee_not_found", "Employee was not found.")

    # -- picker (G-2/G-3/G-4) -----------------------------------------------

    def _port(self) -> HumbeeGeographyMasterProvider:
        return self._master_port or HumbeeGeographyMasterProvider(self._settings)

    def list_zones(self, *, claims: AccessTokenClaims) -> dict[str, Any]:
        """G-2 drill-down — the picker's first click. Unfiltered master data; the caller's
        salesperson-specific geoscope is fetched separately and filtered on the UI."""

        scope = self._scope(claims)
        zones = self._fetch_zones(scope.tenant_id)
        return geography_schemas.ZonesResponse(
            zones=[geography_schemas.ZoneOption(id=z.external_id, name=z.name) for z in zones]
        ).model_dump(mode="json")

    def list_states(self, *, claims: AccessTokenClaims, zone_ids: list[str]) -> dict[str, Any]:
        """G-3 drill-down — states under the zones picked in `list_zones`."""

        scope = self._scope(claims)
        states = self._fetch_states(scope.tenant_id, _dedupe(zone_ids))
        return geography_schemas.StatesResponse(
            states=[
                geography_schemas.StateOption(
                    id=s.external_id, zone_id=s.zone_external_id, name=s.name
                )
                for s in states
            ]
        ).model_dump(mode="json")

    def list_districts(self, *, claims: AccessTokenClaims, state_ids: list[str]) -> dict[str, Any]:
        """G-4 drill-down — districts under the states picked in `list_states`."""

        scope = self._scope(claims)
        districts = self._fetch_districts(scope.tenant_id, _dedupe(state_ids))
        return geography_schemas.DistrictsResponse(
            districts=[
                geography_schemas.DistrictOption(
                    id=d.external_id, state_id=d.state_external_id, name=d.name
                )
                for d in districts
            ]
        ).model_dump(mode="json")

    def _fetch_zones(self, tenant_id: str) -> list[ZoneOption]:
        try:
            return list(self._port().fetch_zones(tenant_id=tenant_id))
        except GeographyMasterUnavailable as exc:
            logger.error("geography_zones_unavailable", tenant_id=tenant_id, reason=str(exc))
            raise ApiError(
                503, "geography_master_unavailable", "Geography zones are not available right now."
            ) from exc

    def _fetch_states(self, tenant_id: str, zone_ids: list[str]) -> list[StateOption]:
        try:
            return list(self._port().fetch_states(tenant_id=tenant_id, zone_ids=zone_ids))
        except GeographyMasterUnavailable as exc:
            logger.error("geography_states_unavailable", tenant_id=tenant_id, reason=str(exc))
            raise ApiError(
                503, "geography_master_unavailable", "Geography states are not available right now."
            ) from exc

    def _fetch_districts(self, tenant_id: str, state_ids: list[str]) -> list[DistrictOption]:
        try:
            return list(self._port().fetch_districts(tenant_id=tenant_id, state_ids=state_ids))
        except GeographyMasterUnavailable as exc:
            logger.error("geography_districts_unavailable", tenant_id=tenant_id, reason=str(exc))
            raise ApiError(
                503,
                "geography_master_unavailable",
                "Geography districts are not available right now.",
            ) from exc

    # -- assignment reads --------------------------------------------------

    def get_geography_scope(
        self, *, claims: AccessTokenClaims, employee_id: str
    ) -> dict[str, Any]:
        scope = self._scope(claims)
        self._employee_in_scope(claims, employee_id)
        assignment = geography_repository.get_assignment(
            self._session, scope=scope, employee_id=employee_id
        )
        if assignment is None:
            raise ApiError(
                404,
                "geography_scope_not_assigned",
                "No geography scope has been assigned to this employee.",
            )
        return geography_schemas.GeoScopeResponse(
            employee_id=assignment.employee_id,
            zones=list(assignment.zone_cluster_ids),
            states=list(assignment.state_cluster_ids),
            districts=list(assignment.district_cluster_ids),
            geo_labels=geography_schemas.GeoLabels.model_validate(assignment.geo_labels),
            assigned_by=assignment.assigned_by,
            assigned_at=assignment.assigned_at,
        ).model_dump(mode="json")

    # -- assignment write --------------------------------------------------

    def assign_geography_scope(
        self,
        *,
        claims: AccessTokenClaims,
        employee_id: str,
        body: geography_schemas.AssignGeoScopeBody,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """S-ORG6 — full replacement of one employee's scope in one transaction with its audit row
        and `GeoScopeAssigned` event (R-ORG-39). Naturally idempotent: the body is the whole scope.
        """

        scope = self._scope(claims)
        self._require_assign(scope)
        with transaction(self._session):
            self._employee_in_scope(claims, employee_id)
            selection, labels = self._validate_and_label(body, tenant_id=scope.tenant_id)

            previous = geography_repository.get_assignment(
                self._session, scope=scope, employee_id=employee_id
            )
            previous_districts = list(previous.district_cluster_ids) if previous else []

            assignment = geography_repository.upsert_assignment(
                self._session,
                scope=scope,
                employee_id=employee_id,
                zone_cluster_ids=selection.zones,
                state_cluster_ids=selection.states,
                district_cluster_ids=selection.districts,
                geo_labels=labels,
                at=self._clock.now_utc(),
            )

            self._audit.record_transition(
                tenant_id=scope.tenant_id,
                entity_type=AUDIT_ENTITY,
                entity_id=assignment.id,
                from_state="assigned" if previous is not None else None,
                to_state="assigned",
                actor_employee_id=scope.actor_employee_id,
                request_id=request_id,
                change_payload={
                    "transition": GEO_SCOPE_ASSIGNED,
                    "employee_id": employee_id,
                    "from_district_cluster_ids": previous_districts,
                    "to_district_cluster_ids": selection.districts,
                },
            )
            events.publish_org_event(
                self._events,
                tenant_id=scope.tenant_id,
                event_type=GEO_SCOPE_ASSIGNED,
                aggregate_id=employee_id,
                payload={
                    "employee_id": employee_id,
                    "zone_cluster_ids": selection.zones,
                    "state_cluster_ids": selection.states,
                    "district_cluster_ids": selection.districts,
                },
                actor_employee_id=scope.actor_employee_id,
                request_id=request_id,
            )
            payload = geography_schemas.GeoScopeResponse(
                employee_id=assignment.employee_id,
                zones=list(assignment.zone_cluster_ids),
                states=list(assignment.state_cluster_ids),
                districts=list(assignment.district_cluster_ids),
                geo_labels=geography_schemas.GeoLabels.model_validate(assignment.geo_labels),
                assigned_by=assignment.assigned_by,
                assigned_at=assignment.assigned_at,
            ).model_dump(mode="json")

        logger.info(
            "geography_scope_assigned",
            employee_id=employee_id,
            district_count=len(selection.districts),
            actor_employee_id=scope.actor_employee_id,
        )
        return payload

    # -- validation ----------------------------------------------------------

    @dataclass(frozen=True)
    class _Selection:
        zones: list[str]
        states: list[str]
        districts: list[str]

    def _validate_and_label(
        self, body: geography_schemas.AssignGeoScopeBody, *, tenant_id: str
    ) -> tuple[_Selection, dict[str, list[dict[str, Any]]]]:
        """Server-side mirror of the picker cascade (R-ORG-31…R-ORG-33, R-ORG-35), and the
        `{id, name}` label snapshot taken at assignment time (epic 07 Story 7.2) — combined so
        neither state nor district is fetched twice.

        Each level is fetched scoped to the *submitted* parent ids — `fetch_states(zone_ids=...)`,
        `fetch_districts(state_ids=...)` — the same narrow calls a beat-creation picker makes,
        never a full-country read. A submitted id that doesn't come back in its parent's scoped
        result is rejected as unknown, whether that's because the id doesn't exist at all or
        because it belongs to a different, non-submitted parent (an orphan) — G-3/G-4's own
        "an id outside the filter contributes no group" contract makes the two indistinguishable,
        and for a hand-rolled request they deserve the same 422 either way.
        """

        zones = _dedupe(body.zones)
        states = _dedupe(body.states)
        districts = _dedupe(body.districts)

        zones_known = self._fetch_zones(tenant_id)
        zones_by_id = {z.external_id: z for z in zones_known}
        self._reject_unknown(zones, set(zones_by_id), "zone")

        states_known = self._fetch_states(tenant_id, zones)
        states_by_id = {s.external_id: s for s in states_known}
        self._reject_unknown(states, set(states_by_id), "state")

        districts_known = self._fetch_districts(tenant_id, states)
        districts_by_id = {d.external_id: d for d in districts_known}
        self._reject_unknown(districts, set(districts_by_id), "district")

        selection = self._Selection(zones=zones, states=states, districts=districts)
        labels = {
            "zones": [{"id": z, "name": zones_by_id[z].name} for z in zones],
            "states": [{"id": s, "name": states_by_id[s].name} for s in states],
            "districts": [
                {
                    "id": d,
                    "name": districts_by_id[d].name,
                    "state_id": districts_by_id[d].state_external_id,
                    "state_name": states_by_id[districts_by_id[d].state_external_id].name,
                }
                for d in districts
            ],
        }
        return selection, labels

    @staticmethod
    def _reject_unknown(selected: list[str], known: set[str], label: str) -> None:
        unknown = [value for value in selected if value not in known]
        if unknown:
            raise ApiError(
                422,
                "geography_unknown_identifier",
                f"One or more {label} cluster identifiers are not in the geography master, or "
                "don't belong to a selected parent cluster.",
                details={"unknown": unknown},
            )


def _dedupe(values: list[str]) -> list[str]:
    """Order-preserving de-duplication."""

    seen: set[str] = set()
    return [value for value in values if not (value in seen or seen.add(value))]


__all__ = ["GEO_SCOPE_ASSIGNED", "GeographyService", "list_district_labels"]

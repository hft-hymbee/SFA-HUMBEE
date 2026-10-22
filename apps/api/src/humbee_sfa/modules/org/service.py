"""Org business logic: employee lifecycle, hierarchy mutation, and the scoped read surface.

Transaction ownership lives here, not in the router (architecture: a service owns one transaction
per state transition together with its audit and domain-event writes).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from humbee_sfa.core.clock import Clock, SystemClock
from humbee_sfa.core.db import transaction
from humbee_sfa.core.deps import AccessTokenClaims
from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.core.security import decrypt_phone, encrypt_phone, hmac_phone
from humbee_sfa.core.settings import Settings, get_settings
from humbee_sfa.modules.org import events, policies, repository, schemas
from humbee_sfa.modules.org.models import Employee
from humbee_sfa.modules.org.scope import (
    OrgResource,
    Scope,
    ScopeContext,
    ScopeResolver,
    authentication_scope,
    can_have_reports,
    internal_routing_scope,
    is_hierarchy_member,
    maintenance_scope,
)
from humbee_sfa.platform.audit import AuditLogService
from humbee_sfa.platform.domain_events import DomainEventPublisher
from humbee_sfa.platform.idempotency import IdempotencyService

logger = structlog.get_logger("humbee_sfa.org")

AUDIT_ENTITY = "org_employee"
_PATH_SEPARATOR = "."


# ---------------------------------------------------------------------------
# Read slice consumed by identity (pre-authentication; no actor exists yet)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EmployeeProjection:
    id: str
    first_name: str
    full_name: str
    role_code: str
    designation_code: str
    status: str
    phone_e164: str
    manager_employee_id: str | None


@dataclass(frozen=True)
class HierarchyMemberProjection:
    id: str
    full_name: str
    display_initials: str
    role_code: str


def _to_projection(employee: Employee) -> EmployeeProjection:
    return EmployeeProjection(
        id=employee.id,
        first_name=employee.first_name,
        full_name=employee.full_name,
        role_code=employee.role_code,
        designation_code=employee.designation_code,
        status=employee.status,
        phone_e164=decrypt_phone(employee.phone_e164_enc),
        manager_employee_id=employee.manager_employee_id,
    )


def find_employee_by_phone(
    session: Session, *, tenant_id: str, phone_e164: str
) -> EmployeeProjection | None:
    phone_hash = hmac_phone(phone_e164)
    employee = repository.get_by_phone_hmac(
        session, scope=authentication_scope(tenant_id), phone_hmac=phone_hash
    )
    if employee is None:
        return None
    return _to_projection(employee)


def get_employee(session: Session, *, tenant_id: str, employee_id: str) -> EmployeeProjection:
    employee = repository.get_active_by_id(
        session, scope=authentication_scope(tenant_id), employee_id=employee_id
    )
    if employee is None:
        raise ApiError(404, "employee_not_found", "Employee was not found.")
    return _to_projection(employee)


def list_employee_names(
    session: Session, *, tenant_id: str, employee_ids: Sequence[str]
) -> dict[str, str]:
    """`{employee_id: full_name}` for a whole page of rows in one query. Ids that no longer
    resolve are absent from the result; the caller decides what to render for them."""

    return repository.list_names_by_ids(
        session, scope=authentication_scope(tenant_id), employee_ids=employee_ids
    )


def get_employee_phone_e164(session: Session, *, tenant_id: str, employee_id: str) -> str:
    employee = repository.get_active_by_id(
        session, scope=authentication_scope(tenant_id), employee_id=employee_id
    )
    if employee is None:
        raise ApiError(404, "employee_not_found", "Employee was not found.")
    return decrypt_phone(employee.phone_e164_enc)


def get_manager_contact(
    session: Session, *, tenant_id: str, employee_id: str
) -> tuple[str, str] | None:
    scope = authentication_scope(tenant_id)
    # A deactivated employee may still use this narrowly-authorised pre-auth flow
    # to find their active manager and request their account be restored.
    employee = repository.get_by_id(session, scope=scope, employee_id=employee_id)
    if employee is None or employee.manager_employee_id is None:
        return None

    manager = repository.get_active_by_id(
        session, scope=scope, employee_id=employee.manager_employee_id
    )
    if manager is None:
        return None
    return manager.full_name, decrypt_phone(manager.phone_e164_enc)


def get_employee_in_scope(
    session: Session, *, scope: ScopeContext, employee_id: str
) -> EmployeeProjection:
    """Scoped single-employee read for another module.

    Out of scope and non-existent are deliberately indistinguishable — a manager must not be able
    to probe for employees outside their tree — so both raise 404. Use this, not `get_employee`,
    whenever the caller is acting on behalf of an actor rather than doing internal routing.
    """

    employee = repository.get_by_id(session, scope=scope, employee_id=employee_id)
    if employee is None:
        raise ApiError(404, "employee_not_found", "Employee was not found.")
    return _to_projection(employee)


@dataclass(frozen=True)
class EmployeeDimensionProjection:
    """The slice `reporting.dim_employee` needs — `EmployeeProjection` (identity/pre-auth) is
    missing `employee_code`/`display_initials`/`hierarchy_path`, so this is its own small
    projection rather than growing that one for an unrelated consumer."""

    id: str
    employee_code: str
    full_name: str
    first_name: str
    display_initials: str
    role_code: str
    is_active: bool
    manager_employee_id: str | None
    hierarchy_path: str | None


def _to_dimension_projection(employee: Employee) -> EmployeeDimensionProjection:
    return EmployeeDimensionProjection(
        id=employee.id,
        employee_code=employee.employee_code,
        full_name=employee.full_name,
        first_name=employee.first_name,
        display_initials=employee.display_initials,
        role_code=employee.role_code,
        is_active=employee.status == "active",
        manager_employee_id=employee.manager_employee_id,
        hierarchy_path=employee.hierarchy_path,
    )


def get_employee_dimension_fields(
    session: Session, *, scope: ScopeContext, employee_id: str
) -> EmployeeDimensionProjection | None:
    """Read-model fields for the reporting `dim_employee` projector — `None` if the employee no
    longer exists (never raises; the caller is a background fold, not a request)."""

    employee = repository.get_by_id(session, scope=scope, employee_id=employee_id)
    return _to_dimension_projection(employee) if employee is not None else None


def list_employee_dimension_fields(
    session: Session, *, scope: ScopeContext
) -> list[EmployeeDimensionProjection]:
    """Every hierarchy-role employee in scope, for the reporting `dim_employee` backfill/sync —
    mirrors `rebuild_hierarchy`'s own use of `list_hierarchy_members`, unpaginated because the
    caller is a background job, not a paginated API response."""

    return [
        _to_dimension_projection(employee)
        for employee in repository.list_hierarchy_members(session, scope=scope)
    ]


def list_designations_by_employee_id(
    session: Session, *, scope: ScopeContext, designation_codes: Sequence[str]
) -> dict[str, str]:
    """`{employee_id: designation_code}` for employees in `scope`'s tree holding one of
    `designation_codes` — for another module's (reporting) rollup that scopes itself to a
    set of hierarchy levels and orders its rows by level."""

    return repository.list_designations_by_employee_id(
        session, scope=scope, designation_codes=designation_codes
    )


def list_subtree_ids_by_manager(
    session: Session, *, scope: ScopeContext, manager_ids: Sequence[str]
) -> dict[str, list[str]]:
    """For each id in `manager_ids`, every employee in their own subtree (self plus
    every descendant) — for another module's (reporting) rollup that must show a
    manager's team activity on the manager's own row, not the manager's own
    (typically empty) fact data."""

    return repository.list_subtree_ids_by_manager(session, scope=scope, manager_ids=manager_ids)


def parent_of(session: Session, *, tenant_id: str, employee_id: str) -> str | None:
    """The direct manager, or `None` at the org root — for system routing only (the approval
    engine climbs the hierarchy one manager at a time to find an escalation target).
    There is no actor to scope against here; `internal_routing_scope` makes that explicit.
    """

    scope = internal_routing_scope(tenant_id)
    for ancestor_id, depth in repository.ancestors_of(
        session, scope=scope, descendant_employee_id=employee_id
    ):
        if depth == 1:
            return ancestor_id
    return None


def rebuild_hierarchy(session: Session, *, tenant_id: str) -> tuple[int, int]:
    """Re-derive `org_hierarchy_edges` and `hierarchy_path` from `manager_employee_id`.

    Adjacency is the editable truth; the closure table and the ltree path are indexes over it. A
    writer that sets one without the other leaves managers with an empty team and approvals
    routing to nobody, while the row itself looks correct. Returns `(members, edges)`; the caller
    owns the transaction.
    """

    scope = maintenance_scope(tenant_id)
    members = repository.list_hierarchy_members(session, scope=scope)
    parent_by_id = {member.id: member.manager_employee_id for member in members}

    def chain(employee_id: str) -> list[str]:
        """`[self, parent, grandparent, ...]`, stopping at the root, a cycle, or a parent that
        holds no position in the tree."""

        walked: list[str] = []
        seen: set[str] = set()
        current: str | None = employee_id
        while current is not None and current in parent_by_id and current not in seen:
            walked.append(current)
            seen.add(current)
            current = parent_by_id[current]
        return walked

    edges: list[tuple[str, str, int]] = []
    paths: dict[str, str] = {}
    for member in members:
        walked = chain(member.id)
        edges.extend((ancestor_id, member.id, depth) for depth, ancestor_id in enumerate(walked))
        paths[member.id] = _PATH_SEPARATOR.join(reversed(walked))

    repository.delete_all_edges(session, scope=scope)
    repository.insert_edges(session, scope=scope, edges=edges)
    repository.set_hierarchy_paths(session, scope=scope, paths=paths)
    return len(members), len(edges)


# ---------------------------------------------------------------------------
# Derivations
# ---------------------------------------------------------------------------


def _first_name(full_name: str) -> str:
    tokens = full_name.split()
    return tokens[0][:120] if tokens else full_name[:120]


def _display_initials(full_name: str) -> str:
    # Initials derive from `full_name`; the column is NOT NULL so the derived value is
    # persisted rather than recomputed per read, and is re-derived on every name change.
    tokens = [token for token in full_name.split() if token]
    return "".join(token[0].upper() for token in tokens[:2])[:3] or full_name[:1].upper()


def _request_fingerprint(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()


def _response_fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _employee_payload(employee: Employee, *, depth: int | None = None) -> dict[str, Any]:
    return schemas.EmployeeResponse(
        id=employee.id,
        employee_code=employee.employee_code,
        full_name=employee.full_name,
        first_name=employee.first_name,
        display_initials=employee.display_initials,
        role_code=employee.role_code,
        designation_code=employee.designation_code,
        status=employee.status,
        login_enabled=employee.login_enabled,
        manager_employee_id=employee.manager_employee_id,
        joined_on=employee.joined_on,
        phone_e164=decrypt_phone(employee.phone_e164_enc),
        depth=depth,
    ).model_dump(mode="json")


class OrgService:
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

    # -- scope -------------------------------------------------------------

    def _employee_scope(self, claims: AccessTokenClaims) -> ScopeContext:
        return ScopeResolver.resolve_from_claims(claims, OrgResource.EMPLOYEE)

    def _employee_write_scope(self, claims: AccessTokenClaims) -> ScopeContext:
        scope = self._employee_scope(claims)
        policies.require_employee_write(scope)
        return scope

    def _mutation_scope(self, claims: AccessTokenClaims) -> ScopeContext:
        # Raises 403 for non-Admin before any row is touched.
        return ScopeResolver.resolve_from_claims(claims, OrgResource.HIERARCHY_MUTATION)

    def _load_in_scope(self, scope: ScopeContext, employee_id: str) -> Employee:
        employee = repository.get_by_id(self._session, scope=scope, employee_id=employee_id)
        if employee is None:
            # Out of scope and non-existent are indistinguishable on purpose: a Manager must not
            # be able to probe for employees outside their tree.
            raise ApiError(404, "employee_not_found", "Employee was not found.")
        return employee

    # -- idempotency -------------------------------------------------------

    def _check_idempotency(
        self, *, endpoint: str, idempotency_key: str, raw_body: bytes, tenant_id: str
    ) -> tuple[int, dict[str, Any]] | None:
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
            request_fingerprint=_request_fingerprint(raw_body),
            response_fingerprint=_response_fingerprint(payload),
            status_code=status_code,
            response_payload=payload,
            actor_employee_id=scope.actor_employee_id,
        )

    # -- reads -------------------------------------------------------------

    def list_employees(
        self,
        *,
        claims: AccessTokenClaims,
        search: str | None,
        role_code: str | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        scope = self._employee_scope(claims)
        rows, total = repository.list_employees(
            self._session,
            scope=scope,
            search=search,
            role_code=role_code,
            status=status,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
        return schemas.EmployeeListResponse(
            items=[schemas.EmployeeResponse(**_employee_payload(row)) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        ).model_dump(mode="json")

    def list_all_employees(
        self,
        *,
        claims: AccessTokenClaims,
        role_code: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """The whole scoped roster, never a page — for aggregations that must see every employee."""

        scope = self._employee_scope(claims)
        rows, _total = repository.list_employees(
            self._session,
            scope=scope,
            search=None,
            role_code=role_code,
            status=status,
            limit=None,
            offset=0,
        )
        return [
            schemas.EmployeeResponse(**_employee_payload(row)).model_dump(mode="json")
            for row in rows
        ]

    def list_employees_for_report(self, *, claims: AccessTokenClaims) -> list[dict[str, Any]]:
        """Admin-only bulk export: full roster with decrypted phone, manager name and hierarchy
        span (direct reports / total team size) — for the employee-hierarchy, geography-mapping
        and attendance admin reports. Team size is computed in Python off `manager_employee_id`
        adjacency already loaded for the roster, avoiding one closure-table query per employee."""

        scope = self._employee_scope(claims)
        rows, _total = repository.list_employees(
            self._session,
            scope=scope,
            search=None,
            role_code=None,
            status=None,
            limit=None,
            offset=0,
        )
        names_by_id = {row.id: row.full_name for row in rows}
        direct_report_counts: dict[str, int] = {}
        children_by_manager: dict[str, list[str]] = {}
        for row in rows:
            if row.manager_employee_id:
                direct_report_counts[row.manager_employee_id] = (
                    direct_report_counts.get(row.manager_employee_id, 0) + 1
                )
                children_by_manager.setdefault(row.manager_employee_id, []).append(row.id)

        team_size_cache: dict[str, int] = {}

        def _team_size(employee_id: str) -> int:
            if employee_id in team_size_cache:
                return team_size_cache[employee_id]
            total = 0
            for child_id in children_by_manager.get(employee_id, []):
                total += 1 + _team_size(child_id)
            team_size_cache[employee_id] = total
            return total

        return [
            {
                "employee_id": row.id,
                "employee_code": row.employee_code,
                "full_name": row.full_name,
                "phone_e164": decrypt_phone(row.phone_e164_enc),
                "role_code": row.role_code,
                "designation_code": row.designation_code,
                "status": row.status,
                "joined_on": row.joined_on,
                "manager_employee_id": row.manager_employee_id,
                "manager_name": names_by_id.get(row.manager_employee_id, "")
                if row.manager_employee_id
                else "",
                "direct_reports": direct_report_counts.get(row.id, 0),
                "team_size": _team_size(row.id),
            }
            for row in rows
        ]

    def list_active_hierarchy_members(
        self, *, claims: AccessTokenClaims
    ) -> list[HierarchyMemberProjection]:
        scope = self._employee_scope(claims)
        rows = repository.list_active_hierarchy_members(self._session, scope=scope)
        return [
            HierarchyMemberProjection(
                id=row.id,
                full_name=row.full_name,
                display_initials=row.display_initials,
                role_code=row.role_code,
            )
            for row in rows
        ]

    def get_employee_detail(
        self, *, claims: AccessTokenClaims, employee_id: str
    ) -> dict[str, Any]:
        scope = self._employee_scope(claims)
        employee = self._load_in_scope(scope, employee_id)
        return _employee_payload(employee)

    def list_move_candidates(
        self, *, claims: AccessTokenClaims, employee_id: str
    ) -> dict[str, Any]:
        scope = self._mutation_scope(claims)
        policies.require_hierarchy_mutation(scope)
        self._load_in_scope(scope, employee_id)
        subtree_ids = {
            row[0] for row in repository.subtree_of(
                self._session, scope=scope, ancestor_employee_id=employee_id
            )
        }
        subtree_ids.add(employee_id)
        candidates = repository.list_move_candidates(
            self._session, scope=scope, excluded_employee_ids=subtree_ids
        )
        return schemas.MoveCandidateListResponse(
            items=[
                schemas.MoveCandidateResponse(
                    id=row.id, full_name=row.full_name, role_code=row.role_code
                )
                for row in candidates
            ]
        ).model_dump(mode="json")

    def get_tree(self, *, claims: AccessTokenClaims) -> dict[str, Any]:
        """An Admin sees every tree in the tenant; a Manager roots at themself.

        An Admin holds no position in the tree, so it has no self-row to root at — it reads the
        forest instead. A tenant may legitimately hold more than one top-level manager, and the
        subtrees are disjoint, so no node is returned twice.
        """

        scope = self._employee_scope(claims)
        root_ids = (
            repository.list_root_ids(self._session, scope=scope)
            if scope.scope is Scope.ORG
            else [claims.employee_id]
        )
        nodes = repository.list_tree(self._session, scope=scope, root_employee_ids=root_ids)
        parent_ids = {employee.manager_employee_id for employee, _ in nodes}

        def make_node(employee: Employee, depth: int) -> schemas.TreeNodeResponse:
            return schemas.TreeNodeResponse(
                id=employee.id,
                full_name=employee.full_name,
                role_code=employee.role_code,
                designation_code=employee.designation_code,
                status=employee.status,
                depth=depth,
                is_actor=employee.id == claims.employee_id,
                has_children=employee.id in parent_ids,
                children=[],
            )

        node_by_id: dict[str, schemas.TreeNodeResponse] = {}
        roots: list[schemas.TreeNodeResponse] = []
        for employee, depth in nodes:
            node = make_node(employee, depth)
            node_by_id[employee.id] = node
            if depth == 0 or employee.manager_employee_id is None:
                roots.append(node)
                continue
            parent = node_by_id.get(employee.manager_employee_id)
            if parent is None:
                roots.append(node)
            else:
                parent.children.append(node)
        return schemas.TreeResponse(roots=roots).model_dump(mode="json")

    # -- mutations ---------------------------------------------------------

    def create_employee(
        self,
        *,
        claims: AccessTokenClaims,
        body: schemas.CreateEmployeeBody,
        idempotency_key: str,
        raw_body: bytes,
        request_id: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """One transaction: validate, insert, closure rows, audit, event."""

        return self._create_employee(
            scope=self._employee_write_scope(claims),
            body=body,
            endpoint="/api/v1/org/employees",
            idempotency_key=idempotency_key,
            raw_body=raw_body,
            request_id=request_id,
        )

    def create_admin(
        self,
        *,
        body: schemas.CreateAdminBody,
        idempotency_key: str,
        raw_body: bytes,
        request_id: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """Create an Admin from the API-key-protected, actorless bootstrap endpoint."""

        employee_body = schemas.CreateEmployeeBody(
            **body.model_dump(),
            role_code="admin",
            designation_code="admin",
            manager_employee_id=None,
        )
        return self._create_employee(
            scope=maintenance_scope(self._settings.tenant_id),
            body=employee_body,
            endpoint="/api/v1/org/admins",
            idempotency_key=idempotency_key,
            raw_body=raw_body,
            request_id=request_id,
        )

    def _create_employee(
        self,
        *,
        scope: ScopeContext,
        body: schemas.CreateEmployeeBody,
        endpoint: str,
        idempotency_key: str,
        raw_body: bytes,
        request_id: str | None,
    ) -> tuple[int, dict[str, Any]]:
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

                self._reject_designation_mismatch(
                    role_code=body.role_code, designation_code=body.designation_code
                )
                manager = self._resolve_new_parent(
                    scope,
                    subject_role_code=body.role_code,
                    new_manager_employee_id=body.manager_employee_id,
                )
                self._reject_duplicate_identity(
                    scope, employee_code=body.employee_code, phone_e164=body.phone_e164
                )

                employee = repository.insert_employee(
                    self._session,
                    scope=scope,
                    employee_code=body.employee_code,
                    full_name=body.full_name,
                    first_name=_first_name(body.full_name),
                    display_initials=_display_initials(body.full_name),
                    role_code=body.role_code,
                    designation_code=body.designation_code,
                    login_enabled=body.login_enabled,
                    manager_employee_id=manager.id if manager is not None else None,
                    joined_on=body.joined_on,
                    phone_e164_hmac=hmac_phone(body.phone_e164),
                    phone_e164_enc=encrypt_phone(body.phone_e164),
                    phone_last4=body.phone_e164[-4:],
                    hierarchy_path=None,
                )

                # Closure rows: the self-row plus every ancestor of the new parent, depth summed.
                # `depth` is stored for ancestor/subtree queries and is never compared against a
                # ceiling — the 5-level cap was withdrawn 2026-08-21.
                edges: list[tuple[str, str, int]] = [(employee.id, employee.id, 0)]
                if manager is not None:
                    edges.extend(
                        (ancestor_id, employee.id, depth + 1)
                        for ancestor_id, depth in self._ancestors_of_parent(scope, manager)
                    )
                repository.insert_edges(self._session, scope=scope, edges=edges)

                path_prefix = manager.hierarchy_path if manager is not None else None
                repository.set_hierarchy_paths(
                    self._session,
                    scope=scope,
                    paths={employee.id: _join_path(path_prefix, employee.id)},
                )
                self._session.refresh(employee)
                from humbee_sfa.modules.leave import service as leave_service

                leave_service.provision_employee_join_year_balances(
                    self._session,
                    scope=scope,
                    employee_id=employee.id,
                    joined_on=employee.joined_on,
                    privileged_leave_days=body.privileged_leave_days,
                    casual_leave_days=body.casual_leave_days,
                    sick_leave_days=body.sick_leave_days,
                    clock=self._clock,
                    settings=self._settings,
                )

                payload = _employee_payload(employee)
                self._audit.record_transition(
                    tenant_id=scope.tenant_id,
                    entity_type=AUDIT_ENTITY,
                    entity_id=employee.id,
                    from_state=None,
                    to_state="active",
                    actor_employee_id=scope.actor_employee_id,
                    request_id=request_id,
                    change_payload={
                        "transition": events.EMPLOYEE_CREATED,
                        "employee_code": employee.employee_code,
                        "role_code": employee.role_code,
                        "designation_code": employee.designation_code,
                        "manager_employee_id": employee.manager_employee_id,
                    },
                )
                events.publish_org_event(
                    self._events,
                    tenant_id=scope.tenant_id,
                    event_type=events.EMPLOYEE_CREATED,
                    aggregate_id=employee.id,
                    payload={
                        "employee_id": employee.id,
                        "role_code": employee.role_code,
                        "manager_employee_id": employee.manager_employee_id,
                    },
                    actor_employee_id=scope.actor_employee_id,
                    request_id=request_id,
                )
                self._store_idempotency(
                    endpoint=endpoint,
                    idempotency_key=idempotency_key,
                    raw_body=raw_body,
                    status_code=201,
                    payload=payload,
                    scope=scope,
                )
        except IntegrityError as exc:
            raise self._identity_conflict(exc) from exc

        logger.info(
            "employee_created",
            employee_id=payload["id"],
            role_code=payload["role_code"],
            manager_employee_id=payload["manager_employee_id"],
            actor_employee_id=scope.actor_employee_id,
        )
        return 201, payload

    def update_employee(
        self,
        *,
        claims: AccessTokenClaims,
        employee_id: str,
        body: schemas.UpdateEmployeeBody,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        scope = self._employee_write_scope(claims)
        try:
            with transaction(self._session):
                employee = self._load_in_scope(scope, employee_id)
                changes: dict[str, object] = {}
                if body.employee_code is not None and body.employee_code != employee.employee_code:
                    changes["employee_code"] = body.employee_code
                if body.full_name is not None and body.full_name != employee.full_name:
                    changes["full_name"] = body.full_name
                    changes["first_name"] = _first_name(body.full_name)
                    changes["display_initials"] = _display_initials(body.full_name)
                if body.role_code is not None and body.role_code != employee.role_code:
                    self._reject_unsafe_role_change(
                        scope, employee=employee, new_role_code=body.role_code
                    )
                    changes["role_code"] = body.role_code
                if (
                    body.designation_code is not None
                    and body.designation_code != employee.designation_code
                ):
                    changes["designation_code"] = body.designation_code
                if "role_code" in changes or "designation_code" in changes:
                    self._reject_designation_mismatch(
                        role_code=body.role_code or employee.role_code,
                        designation_code=body.designation_code or employee.designation_code,
                    )
                if body.login_enabled is not None and body.login_enabled != employee.login_enabled:
                    changes["login_enabled"] = body.login_enabled
                if body.joined_on is not None and body.joined_on != employee.joined_on:
                    changes["joined_on"] = body.joined_on

                if not changes:
                    # Everything above this point is a read, so returning commits an empty
                    # transaction. A bare `rollback()` here read as error handling and was not.
                    return _employee_payload(employee)

                repository.apply_employee_updates(
                    self._session, scope=scope, employee=employee, changes=changes
                )
                self._audit.record_transition(
                    tenant_id=scope.tenant_id,
                    entity_type=AUDIT_ENTITY,
                    entity_id=employee.id,
                    from_state=employee.status,
                    to_state=employee.status,
                    actor_employee_id=scope.actor_employee_id,
                    request_id=request_id,
                    change_payload={
                        "transition": events.EMPLOYEE_UPDATED,
                        "fields": sorted(changes.keys()),
                    },
                )
                events.publish_org_event(
                    self._events,
                    tenant_id=scope.tenant_id,
                    event_type=events.EMPLOYEE_UPDATED,
                    aggregate_id=employee.id,
                    payload={"employee_id": employee.id, "fields": sorted(changes.keys())},
                    actor_employee_id=scope.actor_employee_id,
                    request_id=request_id,
                )
                payload = _employee_payload(employee)
        except IntegrityError as exc:
            raise self._identity_conflict(exc) from exc
        return payload

    def move_employee(
        self,
        *,
        claims: AccessTokenClaims,
        employee_id: str,
        new_manager_employee_id: str | None,
        idempotency_key: str,
        raw_body: bytes,
        request_id: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """The closure rewrite, in one transaction."""

        scope = self._mutation_scope(claims)
        policies.require_hierarchy_mutation(scope)
        endpoint = f"/api/v1/org/employees/{employee_id}/move"
        with transaction(self._session):
            replay = self._check_idempotency(
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                raw_body=raw_body,
                tenant_id=scope.tenant_id,
            )
            if replay is not None:
                return replay

            employee = self._load_in_scope(scope, employee_id)
            previous_manager_id = employee.manager_employee_id

            # 1. Load the moved node's subtree from the closure table.
            subtree = repository.subtree_of(
                self._session, scope=scope, ancestor_employee_id=employee_id
            )
            subtree_ids = [descendant_id for descendant_id, _depth in subtree]
            if employee_id not in subtree_ids:
                subtree_ids.append(employee_id)
                subtree.append((employee_id, 0))

            # 2. Reject a new parent that sits inside that subtree.
            if new_manager_employee_id is not None and new_manager_employee_id in subtree_ids:
                raise ApiError(
                    409,
                    "cycle_detected",
                    "The new manager is inside this employee's own reporting tree.",
                )

            manager = self._resolve_new_parent(
                scope,
                subject_role_code=employee.role_code,
                new_manager_employee_id=new_manager_employee_id,
            )
            if previous_manager_id == (manager.id if manager is not None else None):
                payload = _employee_payload(employee)
                self._store_idempotency(
                    endpoint=endpoint,
                    idempotency_key=idempotency_key,
                    raw_body=raw_body,
                    status_code=200,
                    payload=payload,
                    scope=scope,
                )
                return 200, payload

            # 3-4. Cut the subtree loose from its old ancestors.
            repository.delete_edges_above_subtree(
                self._session, scope=scope, subtree_employee_ids=subtree_ids
            )

            # 5. Insert the cross-product of the new ancestors × the subtree, depths summed.
            if manager is not None:
                new_ancestors = self._ancestors_of_parent(scope, manager)
                repository.insert_edges(
                    self._session,
                    scope=scope,
                    edges=[
                        (ancestor_id, descendant_id, ancestor_depth + 1 + descendant_depth)
                        for ancestor_id, ancestor_depth in new_ancestors
                        for descendant_id, descendant_depth in subtree
                    ],
                )

            # 6. Adjacency (the editable truth) and the display path follow.
            repository.set_manager(
                self._session,
                scope=scope,
                employee=employee,
                new_manager_employee_id=manager.id if manager is not None else None,
            )
            self._rewrite_subtree_paths(scope, subtree_ids=subtree_ids)
            self._session.refresh(employee)
            payload = _employee_payload(employee)

            # 7. Audit + `EmployeeMoved`, same transaction as the closure rewrite.
            self._audit.record_transition(
                tenant_id=scope.tenant_id,
                entity_type=AUDIT_ENTITY,
                entity_id=employee.id,
                from_state=employee.status,
                to_state=employee.status,
                actor_employee_id=scope.actor_employee_id,
                request_id=request_id,
                change_payload={
                    "transition": events.EMPLOYEE_MOVED,
                    "from_manager_employee_id": previous_manager_id,
                    "to_manager_employee_id": employee.manager_employee_id,
                    "subtree_size": len(subtree_ids),
                },
            )
            events.publish_org_event(
                self._events,
                tenant_id=scope.tenant_id,
                event_type=events.EMPLOYEE_MOVED,
                aggregate_id=employee.id,
                payload={
                    "employee_id": employee.id,
                    "from_manager_employee_id": previous_manager_id,
                    "to_manager_employee_id": employee.manager_employee_id,
                    "subtree_employee_ids": subtree_ids,
                },
                actor_employee_id=scope.actor_employee_id,
                request_id=request_id,
            )
            self._store_idempotency(
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                raw_body=raw_body,
                status_code=200,
                payload=payload,
                scope=scope,
            )

        logger.info(
            "employee_moved",
            employee_id=employee_id,
            from_manager_employee_id=previous_manager_id,
            to_manager_employee_id=payload["manager_employee_id"],
            subtree_size=len(subtree_ids),
            actor_employee_id=scope.actor_employee_id,
        )
        return 200, payload

    def deactivate_employee(
        self,
        *,
        claims: AccessTokenClaims,
        employee_id: str,
        reason: str | None,
        idempotency_key: str,
        raw_body: bytes,
        request_id: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        scope = self._employee_write_scope(claims)
        endpoint = f"/api/v1/org/employees/{employee_id}/deactivate"
        with transaction(self._session):
            replay = self._check_idempotency(
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                raw_body=raw_body,
                tenant_id=scope.tenant_id,
            )
            if replay is not None:
                return replay

            employee = self._load_in_scope(scope, employee_id)
            if employee.id == scope.actor_employee_id:
                raise ApiError(
                    409, "self_deactivation_forbidden", "You cannot deactivate your own account."
                )
            previous_status = employee.status
            if previous_status != "inactive":
                repository.deactivate_employee(
                    self._session,
                    scope=scope,
                    employee=employee,
                    at=self._clock.now_utc(),
                )
                self._audit.record_transition(
                    tenant_id=scope.tenant_id,
                    entity_type=AUDIT_ENTITY,
                    entity_id=employee.id,
                    from_state=previous_status,
                    to_state="inactive",
                    actor_employee_id=scope.actor_employee_id,
                    reason=reason,
                    request_id=request_id,
                    change_payload={"transition": events.EMPLOYEE_DEACTIVATED},
                )
                events.publish_org_event(
                    self._events,
                    tenant_id=scope.tenant_id,
                    event_type=events.EMPLOYEE_DEACTIVATED,
                    aggregate_id=employee.id,
                    payload={
                        "employee_id": employee.id,
                        "manager_employee_id": employee.manager_employee_id,
                    },
                    actor_employee_id=scope.actor_employee_id,
                    request_id=request_id,
                )

            payload = _employee_payload(employee)
            self._store_idempotency(
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                raw_body=raw_body,
                status_code=200,
                payload=payload,
                scope=scope,
            )

        if previous_status != "inactive":
            logger.info(
                "employee_deactivated",
                employee_id=employee_id,
                actor_employee_id=scope.actor_employee_id,
            )
        return 200, payload

    # -- shared mutation helpers ------------------------------------------

    def _resolve_new_parent(
        self, scope: ScopeContext, *, subject_role_code: str, new_manager_employee_id: str | None
    ) -> Employee | None:
        if not is_hierarchy_member(subject_role_code):
            # An Admin is a permission level, not a position, so it takes no parent.
            if new_manager_employee_id is not None:
                raise ApiError(
                    422, "invalid_manager", "An Admin does not report into the hierarchy."
                )
            return None

        if new_manager_employee_id is None:
            return None

        manager = repository.get_by_id(
            self._session, scope=scope, employee_id=new_manager_employee_id
        )
        if manager is None or not manager.is_active:
            raise ApiError(404, "manager_not_found", "The selected manager was not found.")
        if not can_have_reports(manager.role_code):
            # Closes the direct-API path that the move-candidate list already filters out.
            raise ApiError(
                422, "invalid_manager", "The selected employee cannot hold direct reports."
            )
        return manager

    @staticmethod
    def _reject_designation_mismatch(*, role_code: str, designation_code: str) -> None:
        if designation_code not in schemas.DESIGNATIONS_BY_ROLE[role_code]:
            raise ApiError(
                422,
                "designation_role_mismatch",
                f"Designation '{designation_code}' is not valid for role '{role_code}'.",
            )

    def _reject_unsafe_role_change(
        self, scope: ScopeContext, *, employee: Employee, new_role_code: str
    ) -> None:
        """A role change is also a hierarchy change. Crossing in or out of the tree belongs to
        `POST /move`, which rewrites the closure rows; this endpoint does not.
        """

        if is_hierarchy_member(employee.role_code) != is_hierarchy_member(new_role_code):
            raise ApiError(
                409,
                "role_change_moves_hierarchy",
                "This role change would move the employee in or out of the reporting tree. "
                "Change their reporting line first.",
            )
        if not can_have_reports(new_role_code) and repository.count_direct_reports(
            self._session, scope=scope, employee_id=employee.id
        ):
            raise ApiError(
                409,
                "employee_has_reports",
                "Reassign this employee's direct reports before changing their role.",
            )

    def _ancestors_of_parent(
        self, scope: ScopeContext, manager: Employee
    ) -> list[tuple[str, int]]:
        """The parent's closure rows, self-row included — the basis for the child's own edges.

        Empty means the parent has no depth-0 self-row; deriving from that would attach the child
        to nobody, invisible to `OWN_TREE` and read by approval routing as "top of hierarchy".
        """

        ancestors = repository.ancestors_of(
            self._session, scope=scope, descendant_employee_id=manager.id
        )
        if not ancestors:
            raise ApiError(
                409,
                "hierarchy_not_indexed",
                "The selected manager is missing from the hierarchy index. "
                "Rebuild it with scripts/rebuild_org_hierarchy.py before assigning reports.",
            )
        return ancestors

    def _reject_duplicate_identity(
        self, scope: ScopeContext, *, employee_code: str, phone_e164: str
    ) -> None:
        # A friendly pre-check; the unique constraints in `org_employees` are what actually make
        # this race-safe — see `_identity_conflict`.
        if repository.employee_code_exists(
            self._session, scope=scope, employee_code=employee_code
        ):
            raise ApiError(409, "employee_code_taken", "That employee code is already in use.")
        if repository.phone_hmac_exists(
            self._session, scope=scope, phone_hmac=hmac_phone(phone_e164)
        ):
            raise ApiError(409, "phone_already_registered", "That phone number is already in use.")

    @staticmethod
    def _identity_conflict(exc: IntegrityError) -> ApiError:
        detail = str(getattr(exc, "orig", exc))
        if "uq_org_employees_tenant_code" in detail:
            return ApiError(409, "employee_code_taken", "That employee code is already in use.")
        if "uq_org_employees_tenant_phone" in detail:
            return ApiError(409, "phone_already_registered", "That phone number is already in use.")
        return ApiError(409, "conflict", "The employee could not be saved.")

    def _rewrite_subtree_paths(self, scope: ScopeContext, *, subtree_ids: list[str]) -> None:
        chains = repository.ancestor_chains(
            self._session, scope=scope, descendant_employee_ids=subtree_ids
        )
        paths = {
            employee_id: _PATH_SEPARATOR.join(chain)
            for employee_id, chain in chains.items()
            if chain
        }
        repository.set_hierarchy_paths(self._session, scope=scope, paths=paths)


def _join_path(prefix: str | None, employee_id: str) -> str:
    return f"{prefix}{_PATH_SEPARATOR}{employee_id}" if prefix else employee_id


__all__ = [
    "EmployeeProjection",
    "OrgService",
    "find_employee_by_phone",
    "get_employee",
    "get_employee_in_scope",
    "get_employee_phone_e164",
    "get_manager_contact",
    "parent_of",
    "rebuild_hierarchy",
]

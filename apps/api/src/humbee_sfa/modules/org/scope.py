"""The one place row scoping is decided — M03 §3b.2, `02-rbac-and-scoping.md` §2.

Public surface other modules consume (R-ORG-17, R-ORG-22):

    from humbee_sfa.modules.org.scope import (
        OrgResource, Scope, ScopeContext, ScopeResolver, apply_scope,
    )

    ctx = ScopeResolver.resolve_from_claims(claims, OrgResource.ACTIVITY_DATA)
    stmt = apply_scope(
        select(AttendanceDay), ctx,
        tenant_column=AttendanceDay.tenant_id,
        employee_id_column=AttendanceDay.employee_id,
    )

`ScopeContext` is the predicate; a repository method that does not take one cannot be
tenant-safe, so every org repository function requires it. The closure table stays private to
this module — callers hand in their own `employee_id` column and never join `org_hierarchy_edges`
themselves.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from sqlalchemy import ColumnElement, Select, or_, select, true
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnClause

from humbee_sfa.core.deps import AccessTokenClaims
from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.modules.org.models import HierarchyEdge


class Scope(StrEnum):
    SELF = "self"
    OWN_TREE = "own_tree"
    ORG = "org"


class Role(StrEnum):
    SALES_PERSON = "sales_person"
    MANAGER = "manager"
    ADMIN = "admin"


class OrgResource(StrEnum):
    """Resource families in the M03 §3b.2 resolution table."""

    EMPLOYEE = "employee"
    GEOGRAPHY_ASSIGNMENT = "geography_assignment"
    ACTIVITY_DATA = "activity_data"
    HIERARCHY_MUTATION = "hierarchy_mutation"


# M03 §3b.2 resolution table. Managers read their tree and write nothing (R-ORG-20);
# Sales Persons read only themselves (R-ORG-21); hierarchy mutation is Admin-only.
_SCOPE_BY_ROLE: dict[Role, Scope] = {
    Role.SALES_PERSON: Scope.SELF,
    Role.MANAGER: Scope.OWN_TREE,
    Role.ADMIN: Scope.ORG,
}

# The structural counterpart to `_SCOPE_BY_ROLE`: role -> position in the reporting line. Admin
# resolves to `ORG` from its role alone, so it needs no hierarchy edge to see anything and holds
# no position. Structural queries read these instead of naming a role.
HIERARCHY_ROLES: tuple[Role, ...] = (Role.SALES_PERSON, Role.MANAGER)
MANAGING_ROLES: tuple[Role, ...] = (Role.MANAGER,)


def is_hierarchy_member(role_code: str) -> bool:
    """Whether `role_code` occupies a node in the reporting tree."""

    return role_code in HIERARCHY_ROLES


def can_have_reports(role_code: str) -> bool:
    """Whether `role_code` may be a parent in the reporting tree."""

    return role_code in MANAGING_ROLES


_AUTHENTICATION_ROLE = "system"


@dataclass(frozen=True)
class ScopeContext:
    """A resolved predicate. Repositories accept this, never a raw role string."""

    tenant_id: str
    actor_employee_id: str | None
    actor_role: str
    resource: OrgResource
    scope: Scope
    can_write: bool

    @property
    def is_authentication(self) -> bool:
        return self.actor_role == _AUTHENTICATION_ROLE


class ScopeResolver:
    """Maps `(actor, resource)` onto exactly one of SELF / OWN_TREE / ORG (R-ORG-17)."""

    @staticmethod
    def resolve(
        *,
        tenant_id: str,
        actor_employee_id: str,
        actor_role: str,
        resource: OrgResource,
    ) -> ScopeContext:
        try:
            role = Role(actor_role)
        except ValueError as exc:
            raise ApiError(403, "forbidden", "Actor role is not recognised.") from exc

        if resource is OrgResource.HIERARCHY_MUTATION and role is not Role.ADMIN:
            raise ApiError(403, "forbidden", "Hierarchy changes are Admin-only.")

        return ScopeContext(
            tenant_id=tenant_id,
            actor_employee_id=actor_employee_id,
            actor_role=role.value,
            resource=resource,
            scope=_SCOPE_BY_ROLE[role],
            can_write=role is Role.ADMIN,
        )

    @staticmethod
    def resolve_from_claims(claims: AccessTokenClaims, resource: OrgResource) -> ScopeContext:
        return ScopeResolver.resolve(
            tenant_id=claims.tenant_id,
            actor_employee_id=claims.employee_id,
            actor_role=claims.role,
            resource=resource,
        )


def authentication_scope(tenant_id: str) -> ScopeContext:
    """Tenant-only scope for the pre-authentication identity lookup.

    The only context in this codebase where no actor exists yet: `identity` resolves a phone
    number to an employee *before* a session is issued, so there is nobody to scope against.
    Tenant filtering still applies. Named explicitly so it is greppable and cannot be reached
    by accident from an authenticated request path.
    """

    return ScopeContext(
        tenant_id=tenant_id,
        actor_employee_id=None,
        actor_role=_AUTHENTICATION_ROLE,
        resource=OrgResource.EMPLOYEE,
        scope=Scope.ORG,
        can_write=False,
    )


def internal_routing_scope(tenant_id: str) -> ScopeContext:
    """Tenant-only scope for cross-module system routines with no human actor — e.g. approvals
    walking the hierarchy to find an escalation target (M06 §3b.1). Same shape as
    `authentication_scope`, kept as its own named function so each call site stays greppable and
    neither can be reached by accident from an authenticated request path.
    """

    return ScopeContext(
        tenant_id=tenant_id,
        actor_employee_id=None,
        actor_role=_AUTHENTICATION_ROLE,
        resource=OrgResource.EMPLOYEE,
        scope=Scope.ORG,
        can_write=False,
    )


def maintenance_scope(tenant_id: str) -> ScopeContext:
    """Tenant-wide *write* scope for offline maintenance with no human actor — rebuilding the
    closure table from adjacency. Named, like the two above, so it stays greppable and cannot be
    reached from a request path by accident.
    """

    return ScopeContext(
        tenant_id=tenant_id,
        actor_employee_id=None,
        actor_role=_AUTHENTICATION_ROLE,
        resource=OrgResource.EMPLOYEE,
        scope=Scope.ORG,
        can_write=True,
    )


def own_tree_employee_ids(context: ScopeContext) -> Select[tuple[str]]:
    """Subquery of every employee id inside the actor's tree, via the closure table."""

    return select(HierarchyEdge.descendant_employee_id).where(
        HierarchyEdge.tenant_id == context.tenant_id,
        HierarchyEdge.ancestor_employee_id == context.actor_employee_id,
    )


def employee_scope_condition(
    context: ScopeContext, employee_id_column: ColumnElement[str] | InstrumentedAttribute[str]
) -> ColumnElement[bool]:
    """The SQL predicate for `context` against a column holding an employee id."""

    if context.scope is Scope.ORG:
        # `ORG` adds no row restriction beyond the tenant predicate applied alongside it.
        return true()

    if context.actor_employee_id is None:
        raise ApiError(403, "forbidden", "Scope requires an authenticated actor.")

    if context.scope is Scope.SELF:
        return employee_id_column == context.actor_employee_id

    # R-ORG-19: OWN_TREE includes the actor. The closure self-row (depth 0) already carries
    # them, but asserting it structurally means a missing self-row cannot blank a manager's
    # own data.
    return or_(
        employee_id_column == context.actor_employee_id,
        employee_id_column.in_(own_tree_employee_ids(context)),
    )


def apply_scope(
    statement: Select[Any],
    context: ScopeContext,
    *,
    tenant_column: ColumnClause[str],
    employee_id_column: ColumnClause[str],
) -> Select[Any]:
    """Apply tenant + row scope to `statement`. The only sanctioned way to scope a query."""

    return statement.where(
        tenant_column == context.tenant_id,
        employee_scope_condition(context, employee_id_column),
    )

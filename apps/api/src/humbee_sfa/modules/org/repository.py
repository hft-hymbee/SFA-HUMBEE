"""Org persistence. Every function here takes a resolved `ScopeContext`.

Scope is applied *here* and nowhere else, so a new endpoint cannot forget it — a repository
function that took no scope argument would be unreviewable.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

from sqlalchemy import ColumnElement, Select, delete, func, or_, select, update
from sqlalchemy.orm import Session

from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.modules.org.models import Employee, HierarchyEdge
from humbee_sfa.modules.org.scope import (
    HIERARCHY_ROLES,
    MANAGING_ROLES,
    Scope,
    ScopeContext,
    apply_scope,
    employee_scope_condition,
)

# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------


def _require_org_write(scope: ScopeContext) -> None:
    """A row that does not exist yet cannot be scope-tested, so inserts demand ORG write."""

    if not scope.can_write or scope.scope is not Scope.ORG:
        raise ApiError(403, "forbidden", "Write is outside the caller's scope.")


def _scoped_employees(scope: ScopeContext) -> Select[tuple[Employee]]:
    return apply_scope(
        select(Employee),
        scope,
        tenant_column=Employee.tenant_id,
        employee_id_column=Employee.id,
    )


# ---------------------------------------------------------------------------
# Employee reads
# ---------------------------------------------------------------------------


def get_by_phone_hmac(
    session: Session, *, scope: ScopeContext, phone_hmac: str
) -> Employee | None:
    """Login-identity lookup, including deactivated employees.

    Identity needs to distinguish an inactive known employee from an unknown phone
    number so it can direct the former to their manager-contact flow.
    """

    stmt = _scoped_employees(scope).where(
        Employee.phone_e164_hmac == phone_hmac,
    )
    return session.execute(stmt).scalar_one_or_none()


def get_active_by_id(
    session: Session, *, scope: ScopeContext, employee_id: str
) -> Employee | None:
    """Live employees only — the session/authorisation path, not the management roster."""

    stmt = _scoped_employees(scope).where(
        Employee.id == employee_id,
        Employee.is_active.is_(True),
    )
    return session.execute(stmt).scalar_one_or_none()


def get_by_id(session: Session, *, scope: ScopeContext, employee_id: str) -> Employee | None:
    """Management read. Includes deactivated employees: the record is never
    removed and still appears to in-scope actors under the "Inactive" filter."""

    stmt = _scoped_employees(scope).where(Employee.id == employee_id)
    return session.execute(stmt).scalar_one_or_none()


def list_names_by_ids(
    session: Session, *, scope: ScopeContext, employee_ids: Sequence[str]
) -> dict[str, str]:
    """`{employee_id: full_name}` for a batch of ids — the display-name lookup another module's
    paginated list needs, so it resolves a page of rows in one query instead of one per row.
    Deactivated employees are included: their historical rows still render with a name."""

    if not employee_ids:
        return {}
    stmt = apply_scope(
        select(Employee.id, Employee.full_name),
        scope,
        tenant_column=Employee.tenant_id,
        employee_id_column=Employee.id,
    ).where(Employee.id.in_(employee_ids))
    return {str(employee_id): str(full_name) for employee_id, full_name in session.execute(stmt)}


def list_designations_by_employee_id(
    session: Session, *, scope: ScopeContext, designation_codes: Sequence[str]
) -> dict[str, str]:
    """Active employees in `scope`'s tree holding one of `designation_codes`, as
    `{employee_id: designation_code}` — a hierarchy-level restrictor for another
    module's rollup, not a management listing.

    Selects only the two columns (not the full `Employee` row via `_scoped_employees`):
    the caller restricts and orders by level, and needs nothing else off this row."""

    stmt = apply_scope(
        select(Employee.id, Employee.designation_code),
        scope,
        tenant_column=Employee.tenant_id,
        employee_id_column=Employee.id,
    ).where(
        Employee.designation_code.in_(designation_codes),
        Employee.is_active.is_(True),
    )
    return {str(employee_id): str(code) for employee_id, code in session.execute(stmt)}


def list_subtree_ids_by_manager(
    session: Session, *, scope: ScopeContext, manager_ids: Sequence[str]
) -> dict[str, list[str]]:
    """For each id in `manager_ids`, every employee in their own subtree (self plus
    every descendant), via the hierarchy closure table — lets another module
    (reporting) roll a manager's team activity up to the manager's own row, since a
    manager's own fact rows are typically empty (they do not do field activity).
    """
    if not manager_ids:
        return {}

    result: dict[str, list[str]] = {str(manager_id): [str(manager_id)] for manager_id in manager_ids}
    rows = session.execute(
        select(HierarchyEdge.ancestor_employee_id, HierarchyEdge.descendant_employee_id).where(
            HierarchyEdge.tenant_id == scope.tenant_id,
            HierarchyEdge.ancestor_employee_id.in_(manager_ids),
        )
    ).all()
    for ancestor_id, descendant_id in rows:
        members = result.setdefault(str(ancestor_id), [str(ancestor_id)])
        if str(descendant_id) not in members:
            members.append(str(descendant_id))
    return result


def list_employees(
    session: Session,
    *,
    scope: ScopeContext,
    search: str | None = None,
    role_code: str | None = None,
    status: str | None = None,
    limit: int | None,
    offset: int,
) -> tuple[list[Employee], int]:
    """Rows and total from the *same* scoped predicate.

    Admins hold no position in the reporting tree and are not roster rows (the roster offers no
    Admin facet).
    """

    conditions: list[ColumnElement[bool]] = [Employee.role_code.in_(HIERARCHY_ROLES)]
    if scope.scope is Scope.OWN_TREE and scope.actor_employee_id is not None:
        conditions.append(Employee.id != scope.actor_employee_id)
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(Employee.full_name.ilike(pattern), Employee.employee_code.ilike(pattern))
        )
    if role_code:
        conditions.append(Employee.role_code == role_code)
    if status:
        conditions.append(Employee.status == status)

    rows_stmt = (
        _scoped_employees(scope)
        .where(*conditions)
        .order_by(Employee.full_name, Employee.id)
        .limit(limit)
        .offset(offset)
    )
    count_stmt = apply_scope(
        select(func.count()).select_from(Employee),
        scope,
        tenant_column=Employee.tenant_id,
        employee_id_column=Employee.id,
    ).where(*conditions)

    rows = list(session.execute(rows_stmt).scalars().all())
    total = session.execute(count_stmt).scalar_one()
    return rows, total


def list_active_hierarchy_members(session: Session, *, scope: ScopeContext) -> list[Employee]:
    conditions = [
        Employee.role_code.in_(HIERARCHY_ROLES),
        Employee.status == "active",
    ]
    if scope.scope is Scope.OWN_TREE and scope.actor_employee_id is not None:
        conditions.append(Employee.id != scope.actor_employee_id)
    stmt = (
        _scoped_employees(scope)
        .where(*conditions)
        .order_by(Employee.full_name, Employee.id)
    )
    return list(session.execute(stmt).scalars().all())


def list_hierarchy_members(session: Session, *, scope: ScopeContext) -> list[Employee]:
    """Every employee occupying a node in the reporting tree — the input to a rebuild.

    `status = 'inactive'` stays indexed (deactivated employees stay visible under the
    "Inactive" filter); only soft-deleted rows drop out.
    """

    stmt = _scoped_employees(scope).where(
        Employee.role_code.in_(HIERARCHY_ROLES), Employee.is_active.is_(True)
    )
    return list(session.execute(stmt).scalars().all())


def count_direct_reports(session: Session, *, scope: ScopeContext, employee_id: str) -> int:
    """Live direct reports, read off adjacency so it answers even if the closure has drifted."""

    stmt = apply_scope(
        select(func.count()).select_from(Employee),
        scope,
        tenant_column=Employee.tenant_id,
        employee_id_column=Employee.id,
    ).where(Employee.manager_employee_id == employee_id, Employee.is_active.is_(True))
    return session.execute(stmt).scalar_one()


def list_root_ids(session: Session, *, scope: ScopeContext) -> list[str]:
    """Tree members with no parent — where an Admin's tree view starts.

    Restricting to `HIERARCHY_ROLES` is the point: an Admin has no parent either, so without it
    the tenant grows a phantom root with nothing under it.
    """

    stmt = (
        _scoped_employees(scope)
        .where(
            Employee.manager_employee_id.is_(None),
            Employee.is_active.is_(True),
            Employee.role_code.in_(HIERARCHY_ROLES),
        )
        .order_by(Employee.full_name, Employee.id)
    )
    return [row.id for row in session.execute(stmt).scalars().all()]


def phone_hmac_exists(session: Session, *, scope: ScopeContext, phone_hmac: str) -> bool:
    stmt = _scoped_employees(scope).where(Employee.phone_e164_hmac == phone_hmac)
    return session.execute(stmt).scalars().first() is not None


def employee_code_exists(session: Session, *, scope: ScopeContext, employee_code: str) -> bool:
    stmt = _scoped_employees(scope).where(Employee.employee_code == employee_code)
    return session.execute(stmt).scalars().first() is not None


def list_move_candidates(
    session: Session, *, scope: ScopeContext, excluded_employee_ids: set[str]
) -> list[Employee]:
    """Legal new managers: every role that may hold reports, except the moved employee's own
    subtree (cycle). There is no depth-based exclusion."""

    stmt = (
        _scoped_employees(scope)
        .where(
            Employee.is_active.is_(True),
            Employee.status == "active",
            Employee.role_code.in_(MANAGING_ROLES),
        )
        .order_by(Employee.full_name, Employee.id)
    )
    if excluded_employee_ids:
        stmt = stmt.where(Employee.id.notin_(excluded_employee_ids))
    return list(session.execute(stmt).scalars().all())


def list_tree(
    session: Session, *, scope: ScopeContext, root_employee_ids: list[str]
) -> list[tuple[Employee, int]]:
    """Flat, pre-ordered subtree for the org tree — one query, no N+1.

    Ordered by `hierarchy_path`, which is exactly what that column exists for: rendering an
    indented tree. It is a display aid, never the authorisation input — the scope
    predicate on the joined employee row is.
    """

    if not root_employee_ids:
        return []

    stmt = (
        select(Employee, HierarchyEdge.depth)
        .join(HierarchyEdge, HierarchyEdge.descendant_employee_id == Employee.id)
        .where(
            HierarchyEdge.tenant_id == scope.tenant_id,
            HierarchyEdge.ancestor_employee_id.in_(root_employee_ids),
            Employee.tenant_id == scope.tenant_id,
            Employee.role_code.in_(HIERARCHY_ROLES),
            employee_scope_condition(scope, Employee.id),
        )
        .order_by(Employee.hierarchy_path, Employee.full_name)
    )
    return [(row[0], row[1]) for row in session.execute(stmt).all()]


# ---------------------------------------------------------------------------
# Employee writes
# ---------------------------------------------------------------------------


def insert_employee(
    session: Session,
    *,
    scope: ScopeContext,
    employee_code: str,
    full_name: str,
    first_name: str,
    display_initials: str,
    role_code: str,
    designation_code: str,
    login_enabled: bool,
    manager_employee_id: str | None,
    joined_on: date | None,
    phone_e164_hmac: str,
    phone_e164_enc: bytes,
    phone_last4: str,
    hierarchy_path: str | None,
) -> Employee:
    _require_org_write(scope)
    row = Employee(
        tenant_id=scope.tenant_id,
        employee_code=employee_code,
        full_name=full_name,
        first_name=first_name,
        display_initials=display_initials,
        role_code=role_code,
        designation_code=designation_code,
        status="active",
        login_enabled=login_enabled,
        manager_employee_id=manager_employee_id,
        joined_on=joined_on,
        hierarchy_path=hierarchy_path,
        phone_e164_hmac=phone_e164_hmac,
        phone_e164_enc=phone_e164_enc,
        phone_last4=phone_last4,
        created_by_employee_id=scope.actor_employee_id,
    )
    session.add(row)
    session.flush()
    return row


def apply_employee_updates(
    session: Session, *, scope: ScopeContext, employee: Employee, changes: dict[str, object]
) -> None:
    _require_org_write(scope)
    for field, value in changes.items():
        setattr(employee, field, value)
    session.flush()


def deactivate_employee(
    session: Session, *, scope: ScopeContext, employee: Employee, at: datetime
) -> None:
    """Soft only. The row, and every visit/order/attendance record pointing at it,
    survive; the employee simply cannot hold a session any more."""

    _require_org_write(scope)
    employee.status = "inactive"
    employee.login_enabled = False
    employee.is_active = False
    employee.deactivated_at = at
    employee.deactivated_by = scope.actor_employee_id
    session.flush()


def set_manager(
    session: Session,
    *,
    scope: ScopeContext,
    employee: Employee,
    new_manager_employee_id: str | None,
) -> None:
    _require_org_write(scope)
    employee.manager_employee_id = new_manager_employee_id
    session.flush()


def set_hierarchy_paths(
    session: Session, *, scope: ScopeContext, paths: dict[str, str]
) -> None:
    _require_org_write(scope)
    for employee_id, path in paths.items():
        session.execute(
            update(Employee)
            .where(Employee.tenant_id == scope.tenant_id, Employee.id == employee_id)
            .values(hierarchy_path=path)
        )


# ---------------------------------------------------------------------------
# Closure table
# ---------------------------------------------------------------------------


def subtree_of(
    session: Session, *, scope: ScopeContext, ancestor_employee_id: str
) -> list[tuple[str, int]]:
    """`(descendant_id, depth)` for the whole subtree, including the self-row at depth 0."""

    stmt = (
        select(HierarchyEdge.descendant_employee_id, HierarchyEdge.depth)
        .where(
            HierarchyEdge.tenant_id == scope.tenant_id,
            HierarchyEdge.ancestor_employee_id == ancestor_employee_id,
            employee_scope_condition(scope, HierarchyEdge.descendant_employee_id),
        )
        .order_by(HierarchyEdge.depth)
    )
    return [(row[0], row[1]) for row in session.execute(stmt).all()]


def ancestors_of(
    session: Session, *, scope: ScopeContext, descendant_employee_id: str
) -> list[tuple[str, int]]:
    """`(ancestor_id, depth)` for one employee, including their own self-row at depth 0."""

    stmt = (
        select(HierarchyEdge.ancestor_employee_id, HierarchyEdge.depth)
        .where(
            HierarchyEdge.tenant_id == scope.tenant_id,
            HierarchyEdge.descendant_employee_id == descendant_employee_id,
            employee_scope_condition(scope, HierarchyEdge.ancestor_employee_id),
        )
        .order_by(HierarchyEdge.depth)
    )
    return [(row[0], row[1]) for row in session.execute(stmt).all()]


def ancestor_chains(
    session: Session, *, scope: ScopeContext, descendant_employee_ids: list[str]
) -> dict[str, list[str]]:
    """Root-first ancestor chain per employee, in one query — the input to a path rewrite.

    Scope constrains which employees' paths may be rewritten (the descendant side). The ancestor
    side is intentionally unfiltered: a path must name every node up to the root, including nodes
    above the caller, and `hierarchy_path` is a display string, never an authorisation input.
    """

    if not descendant_employee_ids:
        return {}

    stmt = (
        select(
            HierarchyEdge.descendant_employee_id,
            HierarchyEdge.ancestor_employee_id,
            HierarchyEdge.depth,
        )
        .where(
            HierarchyEdge.tenant_id == scope.tenant_id,
            HierarchyEdge.descendant_employee_id.in_(descendant_employee_ids),
            employee_scope_condition(scope, HierarchyEdge.descendant_employee_id),
        )
        .order_by(HierarchyEdge.descendant_employee_id, HierarchyEdge.depth.desc())
    )
    chains: dict[str, list[str]] = {}
    for descendant_id, ancestor_id, _depth in session.execute(stmt).all():
        chains.setdefault(descendant_id, []).append(ancestor_id)
    return chains


def insert_edges(
    session: Session, *, scope: ScopeContext, edges: list[tuple[str, str, int]]
) -> None:
    """Bulk-insert `(ancestor_id, descendant_id, depth)` rows."""

    _require_org_write(scope)
    if not edges:
        return
    session.add_all(
        [
            HierarchyEdge(
                tenant_id=scope.tenant_id,
                ancestor_employee_id=ancestor_id,
                descendant_employee_id=descendant_id,
                depth=depth,
                created_by_employee_id=scope.actor_employee_id,
            )
            for ancestor_id, descendant_id, depth in edges
        ]
    )
    session.flush()


def delete_all_edges(session: Session, *, scope: ScopeContext) -> None:
    """Drop every closure row for the tenant — the first half of a rebuild from adjacency."""

    _require_org_write(scope)
    session.execute(delete(HierarchyEdge).where(HierarchyEdge.tenant_id == scope.tenant_id))
    session.flush()


def delete_edges_above_subtree(
    session: Session, *, scope: ScopeContext, subtree_employee_ids: list[str]
) -> None:
    """Cut the moved subtree loose from its old ancestors.

    A real DELETE, unlike everywhere else in this schema: closure rows are *derived* data, and
    soft-deleting them would collide with `uq_org_hierarchy_edges` the next time the same
    ancestor/descendant pair legitimately reappears after another move.
    """

    _require_org_write(scope)
    if not subtree_employee_ids:
        return
    session.execute(
        delete(HierarchyEdge).where(
            HierarchyEdge.tenant_id == scope.tenant_id,
            HierarchyEdge.descendant_employee_id.in_(subtree_employee_ids),
            HierarchyEdge.ancestor_employee_id.notin_(subtree_employee_ids),
        )
    )

"""Geography persistence: per-employee territory assignments.

The four master cache tables (`org_zone_clusters`, `org_state_clusters`, `org_district_clusters`,
`org_shop_categories`) were retired in epic 07 Story 7.2 — the geography master is read live from
Humbee (`integration/humbee/geography.py`) and never persisted locally. Only
`org_geography_scope_assignments` remains here; it carries `employee_id` and goes through
`apply_scope` exactly like every other employee-keyed table (R-ORG-22).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.modules.org.models import GeographyScopeAssignment
from humbee_sfa.modules.org.scope import Scope, ScopeContext, apply_scope

# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------


def _scoped_assignments(scope: ScopeContext):  # type: ignore[no-untyped-def]
    return apply_scope(
        select(GeographyScopeAssignment),
        scope,
        tenant_column=GeographyScopeAssignment.tenant_id,
        employee_id_column=GeographyScopeAssignment.employee_id,
    ).where(GeographyScopeAssignment.is_active.is_(True))


def get_assignment(
    session: Session, *, scope: ScopeContext, employee_id: str
) -> GeographyScopeAssignment | None:
    stmt = _scoped_assignments(scope).where(GeographyScopeAssignment.employee_id == employee_id)
    return session.execute(stmt).scalar_one_or_none()


def list_assignments_in_scope(
    session: Session, *, scope: ScopeContext
) -> list[GeographyScopeAssignment]:
    """Every assignment the caller may see — the input to their assigned pool (R-ORG-34)."""

    return list(session.execute(_scoped_assignments(scope)).scalars().all())


def upsert_assignment(
    session: Session,
    *,
    scope: ScopeContext,
    employee_id: str,
    zone_cluster_ids: list[str],
    state_cluster_ids: list[str],
    district_cluster_ids: list[str],
    geo_labels: dict[str, Any],
    at: datetime,
) -> GeographyScopeAssignment:
    """Full replacement of one employee's scope. One row per employee (`uq_org_geo_scope_employee`).

    Assignment is Admin-only (R-ORG-38); an unscoped insert cannot be scope-tested after the fact,
    so ORG write is demanded up front, exactly as `repository._require_org_write` does.
    """

    if not scope.can_write or scope.scope is not Scope.ORG:
        raise ApiError(403, "forbidden", "Geography assignment is Admin-only.")

    existing = session.execute(
        select(GeographyScopeAssignment).where(
            GeographyScopeAssignment.tenant_id == scope.tenant_id,
            GeographyScopeAssignment.employee_id == employee_id,
        )
    ).scalar_one_or_none()

    if existing is None:
        existing = GeographyScopeAssignment(
            tenant_id=scope.tenant_id,
            employee_id=employee_id,
            created_by_employee_id=scope.actor_employee_id,
        )
        session.add(existing)

    existing.zone_cluster_ids = zone_cluster_ids
    existing.state_cluster_ids = state_cluster_ids
    existing.district_cluster_ids = district_cluster_ids
    existing.geo_labels = geo_labels
    existing.assigned_by = scope.actor_employee_id or employee_id
    existing.assigned_at = at
    existing.is_active = True
    existing.deactivated_at = None
    session.flush()
    return existing

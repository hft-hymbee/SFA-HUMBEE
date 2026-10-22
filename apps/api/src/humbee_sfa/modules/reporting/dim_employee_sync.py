"""Keeps `dim_employee` (SCD2) in sync with `org`'s employee records.

Two entry points share the same fold logic:
- `sync_employee` — called by `producers/org_dim_employee_rollup.py` on every
  `employee_created`/`employee_updated`/`employee_moved`/`employee_deactivated` event, keyed by
  `event.aggregate_id`. Versions the dimension going forward as org changes arrive.
- `backfill_missing` — called once per projector tick (cheap, idempotent: only inserts for
  employees with no current row) to seed employees that already existed before this projector
  shipped. Their `employee_created` events predate the projector's lateness window and
  will never be replayed, so nothing but a direct seed will ever give them a dimension row.

Both read `org` only through its service module (`org.service`) — never `org.models` or
`org.repository` — per `pyproject.toml`'s "Modules must not import each other's internals"
contract, the same boundary every other producer in this package respects.

Geography columns (`humbee_region_id`, `region_name`, `zone_clusters`, `state_clusters`,
`district_clusters`, `shop_categories`, `beat_area_label`) have no source anywhere in `org` today
(confirmed: no such concept exists in `org.models` or `org.service`/`geography_service`) — they are
left at their empty defaults here, not fabricated. Nothing in the current fact-table pipeline reads
them; they exist on `dim_employee` for geography-scoped KPIs that aren't built yet.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from humbee_sfa.core.clock import Clock, SystemClock
from humbee_sfa.modules.org.scope import ScopeContext, internal_routing_scope
from humbee_sfa.modules.org.service import (
    EmployeeDimensionProjection,
    get_employee_dimension_fields,
    list_employee_dimension_fields,
)
from humbee_sfa.modules.reporting.models import DimEmployee

_TRACKED_FIELDS = (
    "employee_code",
    "full_name",
    "first_name",
    "display_initials",
    "role_code",
    "is_active",
    "manager_employee_id",
    "hierarchy_path",
)


def _has_changed(current: DimEmployee, fresh: EmployeeDimensionProjection) -> bool:
    return (
        current.employee_code != fresh.employee_code
        or current.display_name != fresh.full_name
        or current.short_name != fresh.first_name
        or current.initials != fresh.display_initials
        or current.role_code != fresh.role_code
        or current.is_active != fresh.is_active
        or current.manager_employee_id != fresh.manager_employee_id
        or (current.hierarchy_path or None) != (fresh.hierarchy_path or None)
    )


def _new_row(*, tenant_id: str, fresh: EmployeeDimensionProjection, valid_from: datetime) -> DimEmployee:
    return DimEmployee(
        tenant_id=tenant_id,
        employee_id=fresh.id,
        employee_code=fresh.employee_code,
        display_name=fresh.full_name,
        short_name=fresh.first_name,
        initials=fresh.display_initials,
        role_code=fresh.role_code,
        manager_employee_id=fresh.manager_employee_id,
        hierarchy_path=fresh.hierarchy_path,
        humbee_region_id=None,
        region_name=None,
        zone_clusters=[],
        state_clusters=[],
        district_clusters=[],
        shop_categories=[],
        beat_area_label=None,
        is_active=fresh.is_active,
        valid_from=valid_from,
        valid_to=None,
    )


def _current_row(session: Session, *, tenant_id: str, employee_id: str) -> DimEmployee | None:
    return session.execute(
        select(DimEmployee).where(
            DimEmployee.tenant_id == tenant_id,
            DimEmployee.employee_id == employee_id,
            DimEmployee.valid_to.is_(None),
        )
    ).scalar_one_or_none()


def sync_employee(
    session: Session, *, tenant_id: str, employee_id: str, occurred_at: datetime
) -> None:
    """Version `dim_employee` for one employee against org's current state. No-ops if nothing
    tracked actually changed, so a replay or an unrelated `employee_updated` field never opens a
    pointless new row."""

    scope: ScopeContext = internal_routing_scope(tenant_id)
    fresh = get_employee_dimension_fields(session, scope=scope, employee_id=employee_id)
    if fresh is None:
        return

    current = _current_row(session, tenant_id=tenant_id, employee_id=employee_id)
    if current is not None and not _has_changed(current, fresh):
        return
    if current is not None:
        current.valid_to = occurred_at
    session.add(_new_row(tenant_id=tenant_id, fresh=fresh, valid_from=occurred_at))


def backfill_missing(session: Session, *, tenant_id: str, clock: Clock | None = None) -> int:
    """Seed a current row for every employee that doesn't have one yet. Safe to call every tick."""

    scope: ScopeContext = internal_routing_scope(tenant_id)
    employees = list_employee_dimension_fields(session, scope=scope)
    if not employees:
        return 0

    existing_ids = set(
        session.execute(
            select(DimEmployee.employee_id).where(
                DimEmployee.tenant_id == tenant_id,
                DimEmployee.valid_to.is_(None),
            )
        )
        .scalars()
        .all()
    )
    valid_from = (clock or SystemClock()).now_utc()
    created = 0
    for fresh in employees:
        if fresh.id in existing_ids:
            continue
        session.add(_new_row(tenant_id=tenant_id, fresh=fresh, valid_from=valid_from))
        created += 1
    return created

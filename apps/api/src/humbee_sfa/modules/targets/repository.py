"""Targets persistence — `targets`, `targets_manufacturer_lines`, `targets_leads`.

Parent queries are scoped through `apply_scope`. The lines table carries no scope predicate of
its own: a `target_id` only ever arrives from a parent read that was already scope-filtered, and
its declared FK to `targets` is what keeps that true. Writes `flush()` and never commit.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from humbee_sfa.modules.org.scope import ScopeContext, apply_scope
from humbee_sfa.modules.targets.models import (
    Lead,
    Target,
    TargetManufacturerLine,
)


def _scoped(scope: ScopeContext) -> Select[tuple[Target]]:
    return apply_scope(
        select(Target),
        scope,
        tenant_column=Target.tenant_id,
        employee_id_column=Target.employee_id,
    )


def get_target(session: Session, *, scope: ScopeContext, target_id: str) -> Target | None:
    return session.execute(
        _scoped(scope).where(Target.id == target_id)
    ).scalar_one_or_none()


def get_target_for_update(
    session: Session, *, scope: ScopeContext, target_id: str
) -> Target | None:
    """Row-locked load for the update and remove transitions, so two managers saving the same
    target serialise rather than both reading version N."""

    return session.execute(
        _scoped(scope).where(Target.id == target_id).with_for_update()
    ).scalar_one_or_none()


def find_active(
    session: Session,
    *,
    scope: ScopeContext,
    employee_id: str,
    target_type: str,
    period_month: date,
) -> Target | None:
    """The one active target for this employee, type and month, if any."""

    return session.execute(
        _scoped(scope).where(
            Target.employee_id == employee_id,
            Target.target_type == target_type,
            Target.period_month == period_month,
            Target.status == "active",
        )
    ).scalar_one_or_none()


def list_active(
    session: Session,
    *,
    scope: ScopeContext,
    employee_id: str,
    period_month: date,
    target_type: str | None = None,
) -> list[Target]:
    stmt = _scoped(scope).where(
        Target.employee_id == employee_id,
        Target.period_month == period_month,
        Target.status == "active",
    )
    if target_type is not None:
        stmt = stmt.where(Target.target_type == target_type)
    return list(session.execute(stmt.order_by(Target.target_type)).scalars().all())


def count_active_by_employee(
    session: Session,
    *,
    scope: ScopeContext,
    period_month: date,
    employee_ids: list[str],
) -> dict[str, int]:
    if not employee_ids:
        return {}
    stmt = (
        apply_scope(
            select(Target.employee_id, func.count()),
            scope,
            tenant_column=Target.tenant_id,
            employee_id_column=Target.employee_id,
        )
        .where(
            Target.period_month == period_month,
            Target.status == "active",
            Target.employee_id.in_(employee_ids),
        )
        .group_by(Target.employee_id)
    )
    return {employee_id: int(count) for employee_id, count in session.execute(stmt).all()}


def list_active_in_scope(
    session: Session,
    *,
    scope: ScopeContext,
    period_month: date,
    target_type: str | None = None,
) -> list[Target]:
    """Every active target in the caller's tree/org for the month — one scoped query."""

    stmt = _scoped(scope).where(
        Target.period_month == period_month,
        Target.status == "active",
    )
    if target_type is not None:
        stmt = stmt.where(Target.target_type == target_type)
    return list(
        session.execute(stmt.order_by(Target.employee_id, Target.target_type)).scalars().all()
    )


def insert_target(
    session: Session,
    *,
    scope: ScopeContext,
    target_id: str,
    employee_id: str,
    target_type: str,
    period_month: date,
    target_value: int | None,
    outlet_category_scope: str | None,
) -> Target:
    target = Target(
        id=target_id,
        tenant_id=scope.tenant_id,
        employee_id=employee_id,
        target_type=target_type,
        period_type="month",
        period_month=period_month,
        target_value=target_value,
        outlet_category_scope=outlet_category_scope,
        status="active",
        version=1,
        created_by_employee_id=scope.actor_employee_id,
    )
    session.add(target)
    session.flush()
    return target


def replace_lines(
    session: Session,
    *,
    scope: ScopeContext,
    target_id: str,
    lines: list[tuple[str, str, str, str, int]],
    now: datetime,
) -> None:
    """Whole-line replacement for a sales target. Each line is
    `(manufacturer_id, label, basis, uom_label, value)`.

    Nothing is hard-deleted (`core/db.py` forbids it): a dropped manufacturer is deactivated and
    re-selecting it later reactivates the same row, which is what keeps `uq_targets_lines` from
    colliding on a manufacturer that was removed and added back.
    """

    existing = {
        row.humbee_manufacturer_id: row
        for row in session.execute(
            select(TargetManufacturerLine).where(TargetManufacturerLine.target_id == target_id)
        ).scalars()
    }
    wanted = {manufacturer_id for manufacturer_id, _label, _basis, _uom, _value in lines}

    for manufacturer_id, row in existing.items():
        if manufacturer_id not in wanted and row.is_active:
            row.is_active = False
            row.deactivated_at = now
            row.deactivated_by = scope.actor_employee_id

    for manufacturer_id, label, basis, uom_label, value in lines:
        current = existing.get(manufacturer_id)
        if current is None:
            session.add(
                TargetManufacturerLine(
                    tenant_id=scope.tenant_id,
                    target_id=target_id,
                    humbee_manufacturer_id=manufacturer_id,
                    manufacturer_label_snapshot=label,
                    line_basis=basis,
                    uom_label_snapshot=uom_label,
                    line_value=value,
                    created_by_employee_id=scope.actor_employee_id,
                )
            )
        else:
            current.is_active = True
            current.deactivated_at = None
            current.manufacturer_label_snapshot = label
            current.line_basis = basis
            current.uom_label_snapshot = uom_label
            current.line_value = value
    session.flush()


def lines_for(session: Session, *, target_ids: list[str]) -> dict[str, list[TargetManufacturerLine]]:
    if not target_ids:
        return {}
    rows = session.execute(
        select(TargetManufacturerLine)
        .where(
            TargetManufacturerLine.target_id.in_(target_ids),
            TargetManufacturerLine.is_active.is_(True),
        )
        .order_by(TargetManufacturerLine.manufacturer_label_snapshot)
    ).scalars()
    grouped: dict[str, list[TargetManufacturerLine]] = {}
    for row in rows:
        grouped.setdefault(row.target_id, []).append(row)
    return grouped


def insert_lead(
    session: Session,
    *,
    lead_id: str,
    tenant_id: str,
    captured_by_employee_id: str,
    prospect_name: str,
    contact_designation: str | None,
    contact_mobile_hmac: str,
    contact_mobile_enc: bytes,
    contact_mobile_last4: str,
    contact_email: str,
    company_name: str,
    associated_manufacturer_names: list[str],
    annual_turnover_cr: float | None,
    head_office_location: str | None,
    notes: str | None,
    occurred_at: datetime,
    received_at: datetime,
    business_date: date,
) -> Lead:
    lead = Lead(
        id=lead_id,
        tenant_id=tenant_id,
        captured_by_employee_id=captured_by_employee_id,
        prospect_name=prospect_name,
        contact_designation=contact_designation,
        contact_mobile_hmac=contact_mobile_hmac,
        contact_mobile_enc=contact_mobile_enc,
        contact_mobile_last4=contact_mobile_last4,
        contact_email=contact_email,
        company_name=company_name,
        associated_manufacturer_names=associated_manufacturer_names,
        annual_turnover_cr=annual_turnover_cr,
        head_office_location=head_office_location,
        interest_level="hot",
        notes=notes,
        status="captured",
        occurred_at=occurred_at,
        received_at=received_at,
        business_date=business_date,
        created_by_employee_id=captured_by_employee_id,
    )
    session.add(lead)
    session.flush()
    return lead


def count_leads_in_scope(
    session: Session, *, scope: ScopeContext, from_date: date, to_date: date
) -> int:
    """Leads captured within `scope`'s tree and window, excluding `rejected` — the same
    not-rejected rule `ix_targets_leads_month` applies for a `leads` target."""

    stmt = apply_scope(
        select(func.count(Lead.id)),
        scope,
        tenant_column=Lead.tenant_id,
        employee_id_column=Lead.captured_by_employee_id,
    ).where(
        Lead.business_date >= from_date,
        Lead.business_date <= to_date,
        Lead.status != "rejected",
    )
    return int(session.scalar(stmt) or 0)


def count_leads_for_day(
    session: Session, *, tenant_id: str, employee_id: str, business_date: date
) -> int:
    stmt = select(func.count(Lead.id)).where(
        Lead.tenant_id == tenant_id,
        Lead.captured_by_employee_id == employee_id,
        Lead.business_date == business_date,
        Lead.status != "rejected",
    )
    return int(session.scalar(stmt) or 0)

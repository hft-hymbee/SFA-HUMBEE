"""Reporting read-model repository helpers for dashboard endpoints."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from humbee_sfa.modules.org.scope import ScopeContext, employee_scope_condition
from humbee_sfa.modules.reporting.models import (
    DimEmployee,
    FactEmployeeDay,
    FactEmployeeManufacturerDay,
    FactEmployeeOutletDay,
)

_VISITED = (FactEmployeeOutletDay.visits_physical + FactEmployeeOutletDay.visits_telephonic) > 0


def _merge_qty_by_uom(target: dict[str, int], quantities: dict[str, Any] | None) -> None:
    for label, raw_qty in (quantities or {}).items():
        qty = int(raw_qty or 0)
        if qty > 0:
            target[str(label)] = target.get(str(label), 0) + qty


def _scoped_window(
    model: Any, scope: ScopeContext, from_date: date, to_date: date
) -> tuple[Any, ...]:
    return (
        model.tenant_id == scope.tenant_id,
        employee_scope_condition(scope, model.employee_id),
        model.business_date >= from_date,
        model.business_date <= to_date,
    )


def _current_display_names(
    session: Session, *, tenant_id: str, employee_ids: set[str]
) -> dict[str, str]:
    if not employee_ids:
        return {}
    rows = session.execute(
        select(DimEmployee.employee_id, DimEmployee.display_name).where(
            DimEmployee.tenant_id == tenant_id,
            DimEmployee.valid_to.is_(None),
            DimEmployee.employee_id.in_(employee_ids),
        )
    ).all()
    return {str(employee_id): str(display_name) for employee_id, display_name in rows}


def list_display_names(
    session: Session, *, tenant_id: str, employee_ids: set[str]
) -> dict[str, str]:
    return _current_display_names(session, tenant_id=tenant_id, employee_ids=employee_ids)


def count_distinct_outlets(
    session: Session, *, scope: ScopeContext, from_date: date, to_date: date
) -> int:
    value = session.scalar(
        select(func.count(FactEmployeeOutletDay.humbee_outlet_id.distinct())).where(
            *_scoped_window(FactEmployeeOutletDay, scope, from_date, to_date), _VISITED
        )
    )
    return int(value or 0)


def count_zero_order_outlets(
    session: Session, *, scope: ScopeContext, from_date: date, to_date: date
) -> int:
    ordered = select(FactEmployeeOutletDay.humbee_outlet_id).where(
        *_scoped_window(FactEmployeeOutletDay, scope, from_date, to_date),
        FactEmployeeOutletDay.orders_count > 0,
    )
    value = session.scalar(
        select(func.count(FactEmployeeOutletDay.humbee_outlet_id.distinct())).where(
            *_scoped_window(FactEmployeeOutletDay, scope, from_date, to_date),
            _VISITED,
            FactEmployeeOutletDay.humbee_outlet_id.not_in(ordered),
        )
    )
    return int(value or 0)


def count_distinct_outlets_ordered(
    session: Session, *, scope: ScopeContext, from_date: date, to_date: date
) -> int:
    value = session.scalar(
        select(func.count(FactEmployeeOutletDay.humbee_outlet_id.distinct())).where(
            *_scoped_window(FactEmployeeOutletDay, scope, from_date, to_date),
            FactEmployeeOutletDay.orders_count > 0,
        )
    )
    return int(value or 0)


def count_outlets_multi_employee(
    session: Session, *, scope: ScopeContext, from_date: date, to_date: date
) -> int:
    overlapped = (
        select(FactEmployeeOutletDay.humbee_outlet_id)
        .where(*_scoped_window(FactEmployeeOutletDay, scope, from_date, to_date))
        .group_by(FactEmployeeOutletDay.humbee_outlet_id)
        .having(func.count(FactEmployeeOutletDay.employee_id.distinct()) >= 2)
        .subquery()
    )
    value = session.scalar(select(func.count()).select_from(overlapped))
    return int(value or 0)


def count_new_outlets(
    session: Session,
    *,
    scope: ScopeContext,
    from_date: date,
    to_date: date,
    prior_from: date,
    prior_to: date,
) -> int:
    prior_outlets = select(FactEmployeeOutletDay.humbee_outlet_id).where(
        *_scoped_window(FactEmployeeOutletDay, scope, prior_from, prior_to)
    )
    value = session.scalar(
        select(func.count(FactEmployeeOutletDay.humbee_outlet_id.distinct())).where(
            *_scoped_window(FactEmployeeOutletDay, scope, from_date, to_date),
            FactEmployeeOutletDay.humbee_outlet_id.not_in(prior_outlets),
        )
    )
    return int(value or 0)


def sum_money_by_window(
    session: Session,
    *,
    scope: ScopeContext,
    from_date: date,
    to_date: date,
    manufacturer_id: str | None = None,
) -> int:
    if manufacturer_id is not None:
        value = session.scalar(
            select(
                func.coalesce(func.sum(FactEmployeeManufacturerDay.net_value_paise), 0)
            ).where(
                *_scoped_window(FactEmployeeManufacturerDay, scope, from_date, to_date),
                FactEmployeeManufacturerDay.humbee_manufacturer_id == manufacturer_id,
            )
        )
    else:
        value = session.scalar(
            select(func.coalesce(func.sum(FactEmployeeDay.order_net_value_paise), 0)).where(
                *_scoped_window(FactEmployeeDay, scope, from_date, to_date)
            )
        )
    return int(value or 0)


def list_employee_totals(
    session: Session,
    *,
    scope: ScopeContext,
    from_date: date,
    to_date: date,
    manufacturer_id: str | None = None,
    employee_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Per-employee money, visits, and distinct outlets.

    Money is FEMD when `manufacturer_id` is set, else FED. Visits and outlets
    always come from FED / FEOD — they do not change with the manufacturer scoper.
    `employee_ids`, when given, restricts every query to that set (e.g. a
    designation-level filter) instead of the caller's whole scope tree.
    """
    if employee_ids is not None and not employee_ids:
        return []

    def _employee_clause(model: Any) -> tuple[Any, ...]:
        return () if employee_ids is None else (model.employee_id.in_(employee_ids),)

    day_rows = session.execute(
        select(
            FactEmployeeDay.employee_id,
            func.coalesce(func.sum(FactEmployeeDay.visits_total), 0),
            func.coalesce(func.sum(FactEmployeeDay.productive_visits), 0),
            func.coalesce(func.sum(FactEmployeeDay.order_net_value_paise), 0),
        )
        .where(
            *_scoped_window(FactEmployeeDay, scope, from_date, to_date),
            *_employee_clause(FactEmployeeDay),
        )
        .group_by(FactEmployeeDay.employee_id)
    ).all()
    visits: dict[str, tuple[int, int]] = {}
    money: dict[str, int] = {}
    qty_by_uom: dict[str, dict[str, int]] = {}
    for employee_id, visits_total, productive_visits, net_value_paise in day_rows:
        eid = str(employee_id)
        visits[eid] = (int(visits_total or 0), int(productive_visits or 0))
        if manufacturer_id is None:
            money[eid] = int(net_value_paise or 0)

    if manufacturer_id is not None:
        money_rows: dict[str, int] = {}
        for employee_id, net_value_paise in session.execute(
            select(
                FactEmployeeManufacturerDay.employee_id,
                func.coalesce(func.sum(FactEmployeeManufacturerDay.net_value_paise), 0),
            )
            .where(
                *_scoped_window(FactEmployeeManufacturerDay, scope, from_date, to_date),
                FactEmployeeManufacturerDay.humbee_manufacturer_id == manufacturer_id,
                *_employee_clause(FactEmployeeManufacturerDay),
            )
            .group_by(FactEmployeeManufacturerDay.employee_id)
        ).all():
            money_rows[str(employee_id)] = int(net_value_paise or 0)
        money.update(money_rows)
        # `qty_by_uom` is a JSONB map per day-row — merged in Python (never summed in SQL, which
        # would blend UOMs) so each row's per-UOM quantities stay attributable to that UOM.
        for employee_id, day_map in session.execute(
            select(
                FactEmployeeManufacturerDay.employee_id,
                FactEmployeeManufacturerDay.qty_by_uom,
            ).where(
                *_scoped_window(FactEmployeeManufacturerDay, scope, from_date, to_date),
                FactEmployeeManufacturerDay.humbee_manufacturer_id == manufacturer_id,
                *_employee_clause(FactEmployeeManufacturerDay),
            )
        ).all():
            merged = qty_by_uom.setdefault(str(employee_id), {})
            _merge_qty_by_uom(merged, day_map)

    outlet_rows = session.execute(
        select(
            FactEmployeeOutletDay.employee_id,
            func.count(FactEmployeeOutletDay.humbee_outlet_id.distinct()).filter(_VISITED),
            func.count(FactEmployeeOutletDay.humbee_outlet_id.distinct()).filter(
                FactEmployeeOutletDay.orders_count > 0
            ),
            func.count(FactEmployeeOutletDay.humbee_outlet_id.distinct()).filter(
                _VISITED, FactEmployeeOutletDay.orders_count > 0
            ),
        )
        .where(
            *_scoped_window(FactEmployeeOutletDay, scope, from_date, to_date),
            *_employee_clause(FactEmployeeOutletDay),
        )
        .group_by(FactEmployeeOutletDay.employee_id)
    ).all()
    outlets: dict[str, tuple[int, int, int]] = {}
    for employee_id, outlets_visited, outlets_ordered, outlets_converted in outlet_rows:
        outlets[str(employee_id)] = (
            int(outlets_visited or 0), int(outlets_ordered or 0), int(outlets_converted or 0)
        )

    all_employee_ids = set(visits) | set(money) | set(outlets)
    names = _current_display_names(
        session, tenant_id=scope.tenant_id, employee_ids=all_employee_ids
    )
    return [
        {
            "employee_id": employee_id,
            "name": names.get(employee_id, employee_id),
            "net_value_paise": money.get(employee_id, 0),
            "qty_by_uom": qty_by_uom.get(employee_id, {}),
            "visits_total": visits.get(employee_id, (0, 0))[0],
            "productive_visits": visits.get(employee_id, (0, 0))[1],
            "outlets_visited": outlets.get(employee_id, (0, 0, 0))[0],
            "outlets_ordered": outlets.get(employee_id, (0, 0, 0))[1],
            "outlets_converted": outlets.get(employee_id, (0, 0, 0))[2],
        }
        for employee_id in all_employee_ids
    ]


def list_manufacturer_totals(
    session: Session,
    *,
    scope: ScopeContext,
    from_date: date,
    to_date: date,
    manufacturer_id: str | None = None,
    employee_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    manufacturer_clause = (
        ()
        if manufacturer_id is None
        else (FactEmployeeManufacturerDay.humbee_manufacturer_id == manufacturer_id,)
    )
    employee_clause = (
        ()
        if employee_ids is None
        else (FactEmployeeManufacturerDay.employee_id.in_(employee_ids),)
    )
    rows = session.execute(
        select(
            FactEmployeeManufacturerDay.humbee_manufacturer_id,
            func.max(FactEmployeeManufacturerDay.manufacturer_label),
            func.coalesce(func.sum(FactEmployeeManufacturerDay.net_value_paise), 0),
            func.coalesce(func.sum(FactEmployeeManufacturerDay.lines_count), 0),
        )
        .where(
            *_scoped_window(FactEmployeeManufacturerDay, scope, from_date, to_date),
            *manufacturer_clause,
            *employee_clause,
        )
        .group_by(FactEmployeeManufacturerDay.humbee_manufacturer_id)
    ).all()
    # Merged in Python, same reasoning as `list_employee_totals`: a JSONB per-UOM map can't be
    # summed in SQL without blending UOMs together.
    qty_rows = session.execute(
        select(
            FactEmployeeManufacturerDay.humbee_manufacturer_id,
            FactEmployeeManufacturerDay.qty_by_uom,
        ).where(
            *_scoped_window(FactEmployeeManufacturerDay, scope, from_date, to_date),
            *manufacturer_clause,
            *employee_clause,
        )
    ).all()
    qty_by_uom_by_id: dict[str, dict[str, int]] = {}
    for mid, day_map in qty_rows:
        _merge_qty_by_uom(qty_by_uom_by_id.setdefault(str(mid), {}), day_map)
    return [
        {
            "manufacturer_id": str(mid),
            "label": str(label or mid),
            "net_value_paise": int(net_value_paise or 0),
            "qty_by_uom": qty_by_uom_by_id.get(str(mid), {}),
            "lines_count": int(lines_count or 0),
        }
        for mid, label, net_value_paise, lines_count in rows
    ]


def list_employee_manufacturer_money(
    session: Session,
    *,
    scope: ScopeContext,
    from_date: date,
    to_date: date,
    manufacturer_ids: set[str] | None = None,
) -> dict[tuple[str, str], int]:
    """FEMD net value keyed by `(employee_id, manufacturer_id)` — one query.

    The target-pace summary needs every (employee, manufacturer) cell at once; asking
    `list_employee_totals` per manufacturer would be a query fan-out over the whole org.
    """

    manufacturer_clause = (
        ()
        if not manufacturer_ids
        else (FactEmployeeManufacturerDay.humbee_manufacturer_id.in_(manufacturer_ids),)
    )
    rows = session.execute(
        select(
            FactEmployeeManufacturerDay.employee_id,
            FactEmployeeManufacturerDay.humbee_manufacturer_id,
            func.coalesce(func.sum(FactEmployeeManufacturerDay.net_value_paise), 0),
        )
        .where(
            *_scoped_window(FactEmployeeManufacturerDay, scope, from_date, to_date),
            *manufacturer_clause,
        )
        .group_by(
            FactEmployeeManufacturerDay.employee_id,
            FactEmployeeManufacturerDay.humbee_manufacturer_id,
        )
    ).all()
    return {
        (str(employee_id), str(manufacturer_id)): int(net_value_paise or 0)
        for employee_id, manufacturer_id, net_value_paise in rows
    }


def list_district_totals(
    session: Session,
    *,
    scope: ScopeContext,
    from_date: date,
    to_date: date,
    manufacturer_id: str | None = None,
) -> list[dict[str, Any]]:
    """FEOD money grouped by `humbee_district_id` (null district is a real bucket).

    `manufacturer_id` is accepted for call-site symmetry and is not applied.
    District × manufacturer is not representable: FEOD has no manufacturer, FEMD
    has no district. Do not invent a district×manufacturer fact.
    """

    _ = manufacturer_id
    rows = session.execute(
        select(
            FactEmployeeOutletDay.humbee_district_id,
            func.coalesce(func.sum(FactEmployeeOutletDay.net_value_paise), 0),
        )
        .where(*_scoped_window(FactEmployeeOutletDay, scope, from_date, to_date))
        .group_by(FactEmployeeOutletDay.humbee_district_id)
    ).all()
    return [
        {
            "district_id": None if district_id is None else str(district_id),
            "net_value_paise": int(net_value_paise or 0),
        }
        for district_id, net_value_paise in rows
    ]


def list_employee_net_values(
    session: Session,
    *,
    tenant_id: str,
    from_date: date,
    to_date: date,
    manufacturer_id: str | None = None,
    scope: ScopeContext | None = None,
) -> list[tuple[str, str | None, int]]:
    """Per-employee net value, plus `dim_employee.region_name` when it is set.

    Unfiltered money is `FactEmployeeDay.order_net_value_paise`. When
    `manufacturer_id` is set, money is `FactEmployeeManufacturerDay.net_value_paise`
    for that manufacturer. `scope` is optional so existing tenant-only callers
    (`_region_leaderboard`) stay valid.
    """

    if manufacturer_id is not None:
        fact: Any = FactEmployeeManufacturerDay
        money = FactEmployeeManufacturerDay.net_value_paise
        extra: tuple[Any, ...] = (
            FactEmployeeManufacturerDay.humbee_manufacturer_id == manufacturer_id,
        )
    else:
        fact = FactEmployeeDay
        money = FactEmployeeDay.order_net_value_paise
        extra = ()

    stmt = (
        select(
            fact.employee_id,
            DimEmployee.region_name,
            func.coalesce(func.sum(money), 0).label("net_value_paise"),
        )
        .join(
            DimEmployee,
            and_(
                fact.tenant_id == DimEmployee.tenant_id,
                fact.employee_id == DimEmployee.employee_id,
                DimEmployee.valid_to.is_(None),
            ),
        )
        .where(
            fact.tenant_id == tenant_id,
            fact.business_date >= from_date,
            fact.business_date <= to_date,
            *extra,
        )
        .group_by(fact.employee_id, DimEmployee.region_name)
    )
    if scope is not None:
        stmt = stmt.where(employee_scope_condition(scope, fact.employee_id))
    rows = session.execute(stmt).all()
    return [
        (str(employee_id), str(region_name) if region_name else None, int(net_value_paise or 0))
        for employee_id, region_name, net_value_paise in rows
    ]


def last_visit_dates(
    session: Session,
    *,
    tenant_id: str,
    employee_id: str,
) -> dict[str, date]:
    rows = session.execute(
        select(
            FactEmployeeOutletDay.humbee_outlet_id,
            func.max(FactEmployeeOutletDay.business_date),
        ).where(
            FactEmployeeOutletDay.tenant_id == tenant_id,
            FactEmployeeOutletDay.employee_id == employee_id,
            _VISITED,
        ).group_by(FactEmployeeOutletDay.humbee_outlet_id)
    ).all()
    return {str(outlet_id): last_visit for outlet_id, last_visit in rows if last_visit is not None}


def calls_totals_by_employee(
    session: Session,
    *,
    tenant_id: str,
    employee_ids: list[str],
    from_date: date,
    to_date: date,
) -> dict[str, dict[str, int]]:
    """Per-employee TC / PC / SC over `[from_date, to_date]`.

    `tc` = visits, `pc` = productive visits, `sc` = planned outlets. UTC is not here: a
    distinct-outlet count cannot be summed up a hierarchy, so it comes from
    `calls_outlets_by_employee` as a set the caller unions. Employees with no fact rows come
    back zero-filled so the roster can render a row for every active sales person, not just
    the ones who logged activity.
    """

    if not employee_ids:
        return {}

    def _zero() -> dict[str, int]:
        return {"tc": 0, "pc": 0, "sc": 0}

    totals = {employee_id: _zero() for employee_id in employee_ids}

    day_rows = session.execute(
        select(
            FactEmployeeDay.employee_id,
            func.coalesce(func.sum(FactEmployeeDay.visits_total), 0),
            func.coalesce(func.sum(FactEmployeeDay.productive_visits), 0),
            func.coalesce(func.sum(FactEmployeeDay.planned_outlets), 0),
        )
        .where(
            FactEmployeeDay.tenant_id == tenant_id,
            FactEmployeeDay.employee_id.in_(employee_ids),
            FactEmployeeDay.business_date >= from_date,
            FactEmployeeDay.business_date <= to_date,
        )
        .group_by(FactEmployeeDay.employee_id)
    ).all()
    for employee_id, tc, pc, sc in day_rows:
        row = totals[str(employee_id)]
        row["tc"] = int(tc or 0)
        row["pc"] = int(pc or 0)
        row["sc"] = int(sc or 0)

    return totals


def calls_outlets_by_employee(
    session: Session,
    *,
    tenant_id: str,
    employee_ids: list[str],
    from_date: date,
    to_date: date,
) -> dict[str, set[str]]:
    """Per-employee set of outlets covered over `[from_date, to_date]`.

    UTC is a distinct-outlet count, so a manager's value is the size of the union over their
    reps — never the sum of their reps' own counts, which double-counts any outlet two reps
    both visited. Returning the sets lets every level of a hierarchy union instead of add.
    """

    if not employee_ids:
        return {}

    outlets: dict[str, set[str]] = {employee_id: set() for employee_id in employee_ids}
    rows = session.execute(
        select(
            FactEmployeeOutletDay.employee_id,
            FactEmployeeOutletDay.humbee_outlet_id,
        )
        .where(
            FactEmployeeOutletDay.tenant_id == tenant_id,
            FactEmployeeOutletDay.employee_id.in_(employee_ids),
            FactEmployeeOutletDay.business_date >= from_date,
            FactEmployeeOutletDay.business_date <= to_date,
            _VISITED,
        )
        .distinct()
    ).all()
    for employee_id, outlet_id in rows:
        outlets[str(employee_id)].add(str(outlet_id))

    return outlets


def outlet_activity_summary(
    session: Session, *, tenant_id: str
) -> dict[str, dict[str, Any]]:
    """Per-outlet last-visit and last-order date, tenant-wide across
    every employee who ever touched the outlet — for the beat/beat-outlet/unassigned-outlet
    admin reports. Reads `fact_employee_outlet_day` directly (this module's own read model)."""

    visited_date = func.max(
        case(
            (
                (FactEmployeeOutletDay.visits_physical > 0)
                | (FactEmployeeOutletDay.visits_telephonic > 0),
                FactEmployeeOutletDay.business_date,
            )
        )
    )
    ordered_date = func.max(
        case((FactEmployeeOutletDay.orders_count > 0, FactEmployeeOutletDay.business_date))
    )
    stmt = (
        select(
            FactEmployeeOutletDay.humbee_outlet_id,
            visited_date,
            ordered_date,
        )
        .where(FactEmployeeOutletDay.tenant_id == tenant_id)
        .group_by(FactEmployeeOutletDay.humbee_outlet_id)
    )
    result: dict[str, dict[str, Any]] = {}
    for outlet_id, last_visit_date, last_order_date in session.execute(stmt).all():
        result[str(outlet_id)] = {
            "last_visit_date": last_visit_date,
            "last_order_date": last_order_date,
        }
    return result


def fact_employee_days_map(
    session: Session, *, tenant_id: str, employee_ids: list[str], from_date: date, to_date: date
) -> dict[tuple[str, date], FactEmployeeDay]:
    """One `FactEmployeeDay` row per (employee, business_date) in range, for the admin
    attendance report's distance/visits/orders columns."""

    if not employee_ids:
        return {}
    stmt = select(FactEmployeeDay).where(
        FactEmployeeDay.tenant_id == tenant_id,
        FactEmployeeDay.employee_id.in_(employee_ids),
        FactEmployeeDay.business_date >= from_date,
        FactEmployeeDay.business_date <= to_date,
    )
    return {
        (row.employee_id, row.business_date): row for row in session.execute(stmt).scalars().all()
    }

"""Orders producer rollup — stream `orders` (M11 §3b.2, epic 05 Story 5.1 checkbox 5).

Recomputes `fact_employee_day` / `fact_employee_outlet_day` / `fact_employee_manufacturer_day`
order columns from the order's own *current* state, read through `orders.service`'s reporting projections
(`get_order_reporting_fields` / `list_order_reporting_fields_for_day`) — never `orders.models` or
`orders.repository` directly (forbidden by `pyproject.toml`'s "Modules must not import each other's
internals" contract) — and never a `+= 1` counter (M11 §3b.3 rule 2): every fold re-derives the
full day's totals from every order the employee has on that business date, whatever their current
status is.

Reading through the order's live row rather than only `order_submitted`'s event payload also means
an order submitted before that event existed (or before its payload carried enough — both true for
every order in this tenant as of 2026-09-07) still folds correctly the moment any of its later
`dp_order_*` events processes: the event only tells this producer *which* employee/day to
recompute, `orders.service` supplies the numbers.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from humbee_sfa.modules.orders.service import (
    OrderReportingProjection,
    get_order_reporting_fields,
    list_order_reporting_fields_for_day,
)
from humbee_sfa.modules.outlets.service import OutletReadService
from humbee_sfa.modules.reporting.projector import (
    clear_stale_outlet_day_orders,
    drop_stale_manufacturer_days,
    upsert_fact_employee_day,
    upsert_fact_employee_manufacturer_day,
    upsert_fact_employee_outlet_day,
)
from humbee_sfa.platform.models import DomainEvent

STREAM = "orders"

ORDER_SUBMITTED = "order_submitted"
DP_ORDER_APPROVED = "dp_order_approved"
DP_ORDER_REJECTED = "dp_order_rejected"
DP_ORDER_WITHDRAWN = "dp_order_withdrawn"

_TRACKED_EVENT_TYPES = (ORDER_SUBMITTED, DP_ORDER_APPROVED, DP_ORDER_REJECTED, DP_ORDER_WITHDRAWN)

# Never counted as a real submitted order: never left the cart, or never landed downstream.
_EXCLUDED_STATUSES = ("draft", "submission_failed", "cancelled")
_APPROVED_STATUSES = ("approved", "approved_with_edits", "dp_creation_pending", "dp_created")


def fold_orders_for_employee_day(
    session: Session,
    *,
    tenant_id: str,
    employee_id: str,
    business_date: date,
    day_orders: list[OrderReportingProjection],
    last_event_at: datetime | None,
) -> None:
    """Recompute FED / FEMD / FEOD order columns for one employee-day.

    Takes every order the employee has on that date and drops the uncountable statuses itself,
    so the projector `apply` path and the manufacturer/district backfill cannot disagree about
    what counts. `last_event_at` is `None` for the backfill (it folds no event).
    """

    day_orders = [row for row in day_orders if row.status not in _EXCLUDED_STATUSES]

    approved_orders = [row for row in day_orders if row.status in _APPROVED_STATUSES]

    def _bucket(row: OrderReportingProjection) -> str:
        if row.status == "rejected":
            return "rejected"
        if row.status in _APPROVED_STATUSES:
            return "approved"
        return "pending"

    upsert_fact_employee_day(
        session,
        tenant_id=tenant_id,
        employee_id=employee_id,
        business_date=business_date,
        last_event_at=last_event_at,
        fields={
            "orders_submitted_count": len(day_orders),
            "order_lines_count": sum(row.lines_count for row in approved_orders),
            "order_net_value_paise": sum(row.approved_gross_value_paise for row in approved_orders),
            "order_gross_value_paise": sum(
                row.approved_gross_value_paise for row in approved_orders
            ),
            "orders_approved_count": sum(1 for row in day_orders if _bucket(row) == "approved"),
            "orders_rejected_count": sum(1 for row in day_orders if _bucket(row) == "rejected"),
        },
    )

    by_manufacturer: dict[str, list[OrderReportingProjection]] = {}
    for row in approved_orders:
        by_manufacturer.setdefault(row.humbee_manufacturer_id, []).append(row)
    for manufacturer_id, rows in by_manufacturer.items():
        manufacturer_label = next(
            (row.manufacturer_name_snapshot for row in rows if row.manufacturer_name_snapshot),
            rows[0].manufacturer_name_snapshot,
        )
        qty_by_uom: dict[str, int] = {}
        for row in rows:
            for label, qty in row.approved_qty_by_uom.items():
                qty_by_uom[label] = qty_by_uom.get(label, 0) + qty
        upsert_fact_employee_manufacturer_day(
            session,
            tenant_id=tenant_id,
            employee_id=employee_id,
            business_date=business_date,
            humbee_manufacturer_id=manufacturer_id,
            manufacturer_label=manufacturer_label,
            fields={
                "orders_count": len(rows),
                "lines_count": sum(row.approved_lines_count for row in rows),
                "net_value_paise": sum(row.approved_gross_value_paise for row in rows),
                "qty_by_uom": qty_by_uom,
                "manufacturer_label": manufacturer_label,
            },
        )
    drop_stale_manufacturer_days(
        session,
        tenant_id=tenant_id,
        employee_id=employee_id,
        business_date=business_date,
        keep_manufacturer_ids=set(by_manufacturer),
    )

    by_outlet: dict[str, list[OrderReportingProjection]] = {}
    for row in approved_orders:
        by_outlet.setdefault(row.humbee_outlet_id, []).append(row)
    projected = OutletReadService(session).get_projected_outlets(
        tenant_id=tenant_id,
        outlet_ids=list(by_outlet),
    )
    district_by_outlet = {
        item.record.external_id: item.record.district_external_id for item in projected
    }
    for outlet_id, rows in by_outlet.items():
        upsert_fact_employee_outlet_day(
            session,
            tenant_id=tenant_id,
            employee_id=employee_id,
            business_date=business_date,
            humbee_outlet_id=outlet_id,
            fields={
                "orders_count": len(rows),
                "net_value_paise": sum(row.approved_gross_value_paise for row in rows),
                "lines_count": sum(row.lines_count for row in rows),
                "humbee_district_id": district_by_outlet.get(outlet_id),
            },
        )
    clear_stale_outlet_day_orders(
        session,
        tenant_id=tenant_id,
        employee_id=employee_id,
        business_date=business_date,
        keep_outlet_ids=set(by_outlet),
    )


def apply(session: Session, event: DomainEvent) -> None:
    """Fold order events into fact tables by recomputing that employee/day's order totals."""

    if event.event_type not in _TRACKED_EVENT_TYPES:
        return

    order = get_order_reporting_fields(session, tenant_id=event.tenant_id, order_id=event.aggregate_id)
    if order is None:
        return

    fold_orders_for_employee_day(
        session,
        tenant_id=event.tenant_id,
        employee_id=order.employee_id,
        business_date=order.business_date,
        day_orders=list_order_reporting_fields_for_day(
            session,
            tenant_id=event.tenant_id,
            employee_id=order.employee_id,
            business_date=order.business_date,
        ),
        last_event_at=event.occurred_at,
    )

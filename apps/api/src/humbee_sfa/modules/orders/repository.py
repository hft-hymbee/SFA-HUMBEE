"""Orders/cart persistence. Thin, no business decisions."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from humbee_sfa.modules.orders.models.cart_draft import CartDraft
from humbee_sfa.modules.orders.models.cart_line import CartLine
from humbee_sfa.modules.orders.models.order import Order
from humbee_sfa.modules.orders.models.order_line import OrderLine
from humbee_sfa.modules.orders.models.status_event import StatusEvent
from humbee_sfa.modules.orders.models.submission_attempt import SubmissionAttempt
from humbee_sfa.modules.org.scope import ScopeContext, apply_scope


def get_open_cart(
    session: Session,
    *,
    tenant_id: str,
    employee_id: str,
    visit_id: str,
    outlet_id: str,
    manufacturer_id: str,
) -> CartDraft | None:
    stmt = select(CartDraft).where(
        CartDraft.tenant_id == tenant_id,
        CartDraft.employee_id == employee_id,
        CartDraft.visit_id == visit_id,
        CartDraft.humbee_outlet_id == outlet_id,
        CartDraft.humbee_manufacturer_id == manufacturer_id,
        CartDraft.status == "open",
        CartDraft.is_active.is_(True),
    )
    return session.execute(stmt).scalar_one_or_none()


def get_cart(session: Session, *, tenant_id: str, cart_id: str) -> CartDraft | None:
    stmt = select(CartDraft).where(
        CartDraft.tenant_id == tenant_id, CartDraft.id == cart_id, CartDraft.is_active.is_(True)
    )
    return session.execute(stmt).scalar_one_or_none()


def list_lines(session: Session, *, cart_draft_id: str) -> list[CartLine]:
    stmt = (
        select(CartLine)
.where(CartLine.cart_draft_id == cart_draft_id, CartLine.is_active.is_(True))
.order_by(CartLine.created_at)
    )
    return list(session.execute(stmt).scalars().all())


def get_line(session: Session, *, cart_draft_id: str, product_id: str) -> CartLine | None:
    stmt = select(CartLine).where(
        CartLine.cart_draft_id == cart_draft_id,
        CartLine.humbee_product_id == product_id,
    )
    return session.execute(stmt).scalar_one_or_none()


# -- orders --------------------------------------------------


def get_order(session: Session, *, tenant_id: str, order_id: str) -> Order | None:
    stmt = select(Order).where(
        Order.tenant_id == tenant_id, Order.id == order_id, Order.is_active.is_(True)
    )
    return session.execute(stmt).scalar_one_or_none()


def get_order_by_id_or_cart(session: Session, *, tenant_id: str, order_id: str) -> Order | None:
    # Approval subject_id is the cart, not the order (submit_order / DpOrderAdapter).
    return get_order(session, tenant_id=tenant_id, order_id=order_id) or get_order_by_cart(
        session, tenant_id=tenant_id, cart_draft_id=order_id
    )


def get_order_by_cart(session: Session, *, tenant_id: str, cart_draft_id: str) -> Order | None:
    """The subject-lookup path for `DpOrderAdapter`: the approval subject is the cart, the mutable
    row is the order (avoids the order-row-before-approval-request chicken-
    and-egg — see `orders.service.OrderService.submit_order`)."""

    stmt = select(Order).where(
        Order.tenant_id == tenant_id, Order.cart_draft_id == cart_draft_id, Order.is_active.is_(True)
    )
    return session.execute(stmt).scalar_one_or_none()


def get_order_by_cart_global(session: Session, *, cart_draft_id: str) -> Order | None:
    """Tenant-agnostic sibling of `get_order_by_cart`, for the two `ApprovalSubjectAdapter`
    Protocol methods (`editable_fields`, `advisories`) that receive no tenant/viewer. Safe because
    `cart_draft_id` is a globally-unique ULID, the same reasoning every ULID PK in this schema
    already relies on."""

    stmt = select(Order).where(Order.cart_draft_id == cart_draft_id, Order.is_active.is_(True))
    return session.execute(stmt).scalar_one_or_none()


def order_ids_by_visit(
    session: Session, *, tenant_id: str, visit_ids: list[str]
) -> dict[str, list[str]]:
    if not visit_ids:
        return {}
    stmt = (
        select(Order.visit_id, Order.id)
        .where(
            Order.tenant_id == tenant_id,
            Order.visit_id.in_(visit_ids),
            Order.is_active.is_(True),
        )
        .order_by(Order.visit_id, Order.created_at)
    )
    ids_by_visit: dict[str, list[str]] = {}
    for row_visit_id, order_id in session.execute(stmt).all():
        ids_by_visit.setdefault(str(row_visit_id), []).append(str(order_id))
    return ids_by_visit


def list_orders_for_employee_day(
    session: Session, *, tenant_id: str, employee_id: str, business_date: date
) -> list[Order]:
    """Every non-deleted order an employee submitted on one business date — the reporting
    projector's read, keyed the same way `fact_employee_day` is (tenant, employee, day). A
    background fold, not an actor-scoped read, so this filters directly rather than through
    `apply_scope`/`ScopeContext`."""

    stmt = (
        select(Order)
        .where(
            Order.tenant_id == tenant_id,
            Order.employee_id == employee_id,
            Order.business_date == business_date,
            Order.is_active.is_(True),
        )
        .order_by(Order.created_at)
    )
    return list(session.execute(stmt).scalars().all())


def list_order_employee_days(session: Session, *, tenant_id: str) -> list[tuple[str, date]]:
    """Distinct `(employee_id, business_date)` pairs that have an active order — the
    reporting backfill enumerator. Background fold, not an actor-scoped read."""

    stmt = (
        select(Order.employee_id, Order.business_date)
        .where(Order.tenant_id == tenant_id, Order.is_active.is_(True))
        .distinct()
        .order_by(Order.employee_id, Order.business_date)
    )
    return [(employee_id, business_date) for employee_id, business_date in session.execute(stmt)]


def list_order_lines(session: Session, *, order_id: str) -> list[OrderLine]:
    stmt = (
        select(OrderLine)
.where(OrderLine.order_id == order_id, OrderLine.is_active.is_(True))
.order_by(OrderLine.line_no)
    )
    return list(session.execute(stmt).scalars().all())


def list_orders(
    session: Session, *, scope: ScopeContext, status: str | None, cursor: str | None, limit: int
) -> list[Order]:
    """Scoped via the shared `ScopeResolver` (SELF for a Sales Person, OWN_TREE
    for a Manager) rather than a hand-rolled `employee_id` check."""

    stmt: Select[tuple[Order]] = select(Order).where(Order.is_active.is_(True))
    stmt = apply_scope(
        stmt, scope, tenant_column=Order.tenant_id, employee_id_column=Order.employee_id
    )
    if status is not None:
        stmt = stmt.where(Order.status == status)
    if cursor is not None:
        stmt = stmt.where(Order.id < cursor)
    stmt = stmt.order_by(Order.business_date.desc(), Order.id.desc()).limit(limit)
    return list(session.execute(stmt).scalars().all())


def get_order_in_scope(session: Session, *, scope: ScopeContext, order_id: str) -> Order | None:
    """`404`, never `403`, on out-of-scope — the caller treats a
    `None` the same as "not found"."""

    # Approval subject_id is the cart, not the order (submit_order / DpOrderAdapter).
    for column in (Order.id, Order.cart_draft_id):
        stmt: Select[tuple[Order]] = select(Order).where(
            column == order_id, Order.is_active.is_(True)
        )
        stmt = apply_scope(
            stmt, scope, tenant_column=Order.tenant_id, employee_id_column=Order.employee_id
        )
        order = session.execute(stmt).scalar_one_or_none()
        if order is not None:
            return order
    return None


def next_status_event_seq(session: Session, *, order_id: str) -> int:
    stmt = select(func.coalesce(func.max(StatusEvent.seq), 0)).where(
        StatusEvent.order_id == order_id
    )
    return session.execute(stmt).scalar_one() + 1


def count_orders(
    session: Session, *, scope: ScopeContext, status: str
) -> int:
    stmt = select(func.count()).select_from(Order).where(
        Order.is_active.is_(True),
        Order.status == status,
    )
    stmt = apply_scope(
        stmt, scope, tenant_column=Order.tenant_id, employee_id_column=Order.employee_id
    )
    return int(session.execute(stmt).scalar_one())


def list_ordered_outlet_manufacturers(
    session: Session,
    *,
    scope: ScopeContext,
    from_date: date,
    to_date: date,
    statuses: tuple[str, ...],
) -> list[tuple[str, str, str]]:
    stmt = select(
        Order.humbee_manufacturer_id,
        Order.manufacturer_name_snapshot,
        Order.humbee_outlet_id,
    ).where(
        Order.is_active.is_(True),
        Order.business_date >= from_date,
        Order.business_date <= to_date,
        Order.status.in_(statuses),
    )
    stmt = apply_scope(
        stmt, scope, tenant_column=Order.tenant_id, employee_id_column=Order.employee_id
    )
    return [
        (str(manufacturer_id), str(manufacturer_name), str(outlet_id))
        for manufacturer_id, manufacturer_name, outlet_id in session.execute(stmt).all()
    ]


def latest_attempt(session: Session, *, order_id: str) -> SubmissionAttempt | None:
    stmt = (
        select(SubmissionAttempt)
.where(SubmissionAttempt.order_id == order_id)
.order_by(SubmissionAttempt.attempt_no.desc())
.limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()

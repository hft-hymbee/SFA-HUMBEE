"""`orders_po_references` — the purchase order an order draws down.

A PO is a line-level document: this row snapshots its value totals as of the moment the
order was raised, with `orders_po_reference_lines` carrying the per-SKU detail. `uq_orders_po_order`
enforces at most one PO per order.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class PoReference(Base, ConventionsMixin):
    __tablename__ = "orders_po_references"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_orders_po_order"),  # one PO per order
        Index("ix_orders_po_humbee", "tenant_id", "humbee_po_id"),
        CheckConstraint("po_net_value_paise_snapshot >= 0", name="orders_po_net_value_chk"),
        CheckConstraint("po_balance_value_paise_snapshot >= 0", name="orders_po_balance_value_chk"),
    )

    order_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    humbee_po_id: Mapped[str] = mapped_column(String(64), nullable=False)
    po_number_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    po_status_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    po_manufacturer_id_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    po_manufacturer_name_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    po_date_snapshot: Mapped[date] = mapped_column(Date, nullable=False)
    po_valid_until_snapshot: Mapped[date | None] = mapped_column(Date, nullable=True)
    po_payment_terms_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    po_credit_days_snapshot: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    po_net_value_paise_snapshot: Mapped[int] = mapped_column(BigInteger, nullable=False)
    po_balance_value_paise_snapshot: Mapped[int] = mapped_column(BigInteger, nullable=False)
    po_as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_value_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

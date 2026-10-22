"""`orders_po_reference_lines` — per-SKU snapshot of the referenced PO's lines. database-design.md
§10, §10.1.

`balance_qty_snapshot` (with `orders_po_lines_balance_chk` pinning it to
`ordered - fulfilled`) is the evidence that stock headroom existed when the order was submitted —
the fact in dispute whenever Humbee later rejects for insufficient balance. `order_line_id` is
nullable: a PO line the sales person did not order still gets a row, for completeness of the
snapshot.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class PoReferenceLine(Base, ConventionsMixin):
    __tablename__ = "orders_po_reference_lines"
    __table_args__ = (
        UniqueConstraint("po_reference_id", "humbee_po_line_id", name="uq_orders_po_lines"),
        Index("ix_orders_po_lines_order_line", "order_line_id"),
        CheckConstraint(
            "ordered_qty_snapshot >= 0 AND fulfilled_qty_snapshot >= 0 AND balance_qty_snapshot >= 0",
            name="orders_po_lines_qty_chk",
        ),
        CheckConstraint(
            "balance_qty_snapshot = ordered_qty_snapshot - fulfilled_qty_snapshot",
            name="orders_po_lines_balance_chk",
        ),
        CheckConstraint("rate_per_unit_net_paise > 0", name="orders_po_lines_rate_chk"),
        CheckConstraint(
            "gst_rate_bp_snapshot BETWEEN 0 AND 10000", name="orders_po_lines_gst_rate_chk"
        ),
    )

    po_reference_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("orders_po_references.id", ondelete="CASCADE"), nullable=False
    )
    order_line_id: Mapped[str | None] = mapped_column(
        String(26), nullable=True
    )  # REFERENCES orders_lines(id); null: PO line not ordered
    humbee_po_line_id: Mapped[str] = mapped_column(String(64), nullable=False)
    humbee_product_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sku_code_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    sku_name_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    hsn_code_snapshot: Mapped[str] = mapped_column(String(16), nullable=False)
    uom_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    ordered_qty_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    fulfilled_qty_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_qty_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    rate_per_unit_net_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    gst_rate_bp_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)

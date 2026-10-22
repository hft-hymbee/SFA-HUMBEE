"""`orders_lines` — per-SKU lines of an order. database-design.md §10, §10.1.

GST lives here, not on `orders`, because it is per-HSN and a basket is nearly always mixed
(§10.1). `orders_lines_net_chk`/`orders_lines_approved_net_chk` make money arithmetic a database
fact, and `orders_lines_po_line_chk` makes `price_source`/`humbee_po_line_id` an unbreakable pair
so a PO-priced line can always be traced back to the contract line it drew against.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class OrderLine(Base, ConventionsMixin):
    __tablename__ = "orders_lines"
    __table_args__ = (
        UniqueConstraint("order_id", "humbee_product_id", name="uq_orders_lines_product"),
        UniqueConstraint("order_id", "line_no", name="uq_orders_lines_no"),
        CheckConstraint("line_no >= 1", name="orders_lines_line_no_chk"),
        CheckConstraint("requested_qty >= 1", name="orders_lines_qty_chk"),
        CheckConstraint(
            "unit_price_net_paise IS NULL OR unit_price_net_paise > 0",
            name="orders_lines_price_chk",
        ),
        CheckConstraint(
            "line_net_paise = unit_price_net_paise * requested_qty", name="orders_lines_net_chk"
        ),
        CheckConstraint(
            "approved_qty IS NULL OR approved_qty BETWEEN 0 AND requested_qty",
            name="orders_lines_approved_qty_chk",
        ),
        CheckConstraint(
            "approved_qty IS NULL OR approved_line_net_paise = unit_price_net_paise * approved_qty",
            name="orders_lines_approved_net_chk",
        ),
        CheckConstraint(
            "stock_status_at_add IN ('in_stock','low_stock','out_of_stock','unavailable')",
            name="orders_lines_stock_chk",
        ),
        CheckConstraint("scheme_line_discount_paise >= 0", name="orders_lines_scheme_chk"),
        CheckConstraint(
            "product_line_discount_paise >= 0", name="orders_lines_product_discount_chk"
        ),
        CheckConstraint("gst_rate_bp BETWEEN 0 AND 10000", name="orders_lines_gst_rate_chk"),
        CheckConstraint("line_gst_amount_paise >= 0", name="orders_lines_gst_amount_chk"),
        CheckConstraint(
            "price_source IN ('po_line','price_master')", name="orders_lines_price_source_chk"
        ),
        # a PO-priced line must name the PO line it drew down; a master-priced line must not
        CheckConstraint(
            "(price_source = 'po_line') = (humbee_po_line_id IS NOT NULL)",
            name="orders_lines_po_line_chk",
        ),
        CheckConstraint(
            "form_type IS NULL OR form_type IN ('STRAIGHT','BEND')",
            name="orders_lines_form_type_chk",
        ),
    )

    order_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    line_no: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    humbee_product_id: Mapped[str] = mapped_column(String(64), nullable=False)
    product_name_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    category_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    form_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Both dropped from Humbee's product response on 26 Aug 2026 (§9) — null rather than a
    # fabricated placeholder.
    pack_size_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    uom_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    humbee_manufacturer_id_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    hsn_code_snapshot: Mapped[str | None] = mapped_column(String(16), nullable=True)
    gst_rate_bp: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # per line, from the SKU's HSN
    price_source: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # 'po_line' | 'price_master'
    humbee_po_line_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # set when price_source = 'po_line'
    unit_price_net_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    unit_price_as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    requested_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    approved_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_net_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    line_gst_amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    approved_line_net_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    approved_line_gst_amount_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    stock_status_at_add: Mapped[str] = mapped_column(String(16), nullable=False)
    scheme_code_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheme_line_discount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    product_line_discount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

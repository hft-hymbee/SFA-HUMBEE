"""`orders_cart_drafts` — the provisional basket before submit. database-design.md §10.

`order_path`/`seller_type_snapshot` here are provisional and re-resolved at submit time against a
fresh seller-linkage read, so they carry no CHECK tying them to the frozen
`orders` row. One open cart per (employee, visit, outlet, manufacturer) is enforced by
`uq_orders_cart_open` so re-entering S-ORD1 resumes the same draft instead of forking a duplicate.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class CartDraft(Base, ConventionsMixin):
    __tablename__ = "orders_cart_drafts"
    __table_args__ = (
        Index(
            "uq_orders_cart_open",
            "tenant_id",
            "employee_id",
            "visit_id",
            "humbee_outlet_id",
            "humbee_manufacturer_id",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
        Index("ix_orders_cart_expiry", "expires_at", postgresql_where=text("status = 'open'")),
        CheckConstraint("order_path IN ('po_backed','direct')", name="orders_cart_path_chk"),
        CheckConstraint(
            "status IN ('open','converted','abandoned','expired')", name="orders_cart_status_chk"
        ),
        CheckConstraint(
            "(status = 'converted') = (converted_order_id IS NOT NULL)",
            name="orders_cart_converted_chk",
        ),
    )

    employee_id: Mapped[str] = mapped_column(
        String(26), nullable=False
    )  # REFERENCES org_employees(id)
    visit_id: Mapped[str | None] = mapped_column(
        String(26), nullable=True
    )  # logical → routes_visits
    humbee_outlet_id: Mapped[str] = mapped_column(String(64), nullable=False)
    order_path: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # provisional; re-resolved at submit
    seller_type_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    humbee_manufacturer_id: Mapped[str] = mapped_column(String(64), nullable=False)
    humbee_seller_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # The outlet's own ESI against this seller (buyer_esi_id on C-10). Resolved once at cart
    # creation from `SellerRecord.outlet_esi_records`, same lifecycle as humbee_seller_id.
    humbee_buyer_esi_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # The seller's own ESI (seller_esi_id on C-10) — always null when the seller is a manufacturer.
    humbee_seller_esi_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    humbee_po_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ship_to_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ship_to_humbee_outlet_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ship_to_humbee_esi_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    shipping_address_line1: Mapped[str | None] = mapped_column(String(250), nullable=True)
    shipping_address_line2: Mapped[str | None] = mapped_column(String(250), nullable=True)
    shipping_address_state_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    shipping_address_district_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    shipping_address_pincode: Mapped[str | None] = mapped_column(String(6), nullable=True)
    scheme_discount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    scheme_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_discount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    gross_total_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    converted_order_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

"""`orders` — the highest-risk table in the whole design.

The path/money CHECKs below are the single most valuable block of DDL in this schema.
`order_path` is SFA's own binary route classification, sourced from the chosen seller's
`requires_purchase_order` (`integration/humbee/seller.py`) — never from an
outlet tier or classification, which the verified Humbee build does not expose at outlet level at
all. `requires_approval` is sourced
independently from the same seller's `manager_approval_required` and is **not** implied by
`order_path` — a seller can require approval without requiring a PO, or vice versa, so there is no
longer a CHECK binding the two together. `seller_type_snapshot` is Humbee's seller type
(`MANUFACTURER` / `R1` / `R2` / `R3` / `R4`) and deliberately carries no CHECK.
GST is per line, so there is no order-level rate column here — `gst_amount_paise` is the
sum of `orders_lines.line_gst_amount_paise`.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CHAR,
    BigInteger,
    CheckConstraint,
    DateTime,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin, FieldEventTimingMixin
from humbee_sfa.core.db import Base


class Order(Base, ConventionsMixin, FieldEventTimingMixin):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "order_number", name="uq_orders_number"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_orders_idem"),
        Index(
            "uq_orders_downstream",
            "tenant_id",
            "downstream_dp_order_ref",
            unique=True,
            postgresql_where=text("downstream_dp_order_ref IS NOT NULL"),
        ),
        Index("ix_orders_mine", "tenant_id", "employee_id", text("business_date DESC")),
        Index("ix_orders_status", "tenant_id", "status", text("business_date DESC")),
        Index("ix_orders_visit", "tenant_id", "visit_id"),
        Index("ix_orders_outlet", "tenant_id", "humbee_outlet_id", text("business_date DESC")),
        # the SLA sweeper: approved orders whose DP order is not yet created
        Index(
            "ix_orders_sla_watch",
            "dp_sla_deadline_at",
            postgresql_where=text(
                "status IN ('approved','approved_with_edits','dp_creation_pending') "
                "AND dp_created_at IS NULL"
            ),
        ),
        # the ops queue behind the order detail's retry banner
        Index(
            "ix_orders_failed",
            "tenant_id",
            text("business_date DESC"),
            postgresql_where=text("status = 'submission_failed'"),
        ),
        CheckConstraint("order_path IN ('po_backed','direct')", name="orders_path_chk"),
        CheckConstraint(
            "status IN ("
            "'draft','submitted','pending_approval','approved','approved_with_edits','rejected',"
            "'dp_creation_pending','dp_created','submission_failed','cancelled')",
            name="orders_status_chk",
        ),
        # no CHECK on seller_type_snapshot: Humbee's open set
        CheckConstraint(
            "ship_to_type IS NULL OR ship_to_type IN ('self','dealer')", name="orders_ship_to_chk"
        ),
        CheckConstraint("currency = 'INR'", name="orders_currency_chk"),
        # route invariants, keyed on the chosen seller's `requires_purchase_order`, never on an
        # outlet tier
        CheckConstraint(
            "order_path <> 'po_backed' OR humbee_po_id IS NOT NULL",
            name="orders_po_backed_needs_po_chk",
        ),
        CheckConstraint(
            "order_path <> 'direct' OR humbee_po_id IS NULL", name="orders_direct_no_po_chk"
        ),
        CheckConstraint(
            "order_path <> 'po_backed' OR ship_to_type IS NOT NULL",
            name="orders_po_backed_ship_to_chk",
        ),
        CheckConstraint(
            "ship_to_type <> 'dealer' OR ship_to_humbee_outlet_id IS NOT NULL",
            name="orders_ship_to_dealer_chk",
        ),
        CheckConstraint(
            "requires_approval = false OR approval_request_id IS NOT NULL",
            name="orders_approval_handle_chk",
        ),
        # money arithmetic
        CheckConstraint(
            "subtotal_net_paise >= 0 AND scheme_discount_paise >= 0 AND product_discount_paise >= 0 "
            "AND taxable_base_paise >= 0 AND gst_amount_paise >= 0 AND gross_total_paise >= 0",
            name="orders_money_nonneg_chk",
        ),
        CheckConstraint(
            "taxable_base_paise = subtotal_net_paise - scheme_discount_paise - product_discount_paise",
            name="orders_taxable_base_chk",
        ),
        CheckConstraint(
            "gross_total_paise = taxable_base_paise + gst_amount_paise",
            name="orders_gross_total_chk",
        ),
        CheckConstraint(
            "scheme_discount_paise <= subtotal_net_paise", name="orders_scheme_bound_chk"
        ),
        # no DP order without proof
        CheckConstraint(
            "status <> 'dp_created' OR downstream_dp_order_ref IS NOT NULL",
            name="orders_dp_created_ref_chk",
        ),
        CheckConstraint("retry_budget_remaining >= 0", name="orders_retry_budget_chk"),
    )

    order_number: Mapped[str] = mapped_column(Text, nullable=False)
    order_path: Mapped[str] = mapped_column(String(32), nullable=False)  # 'po_backed' | 'direct'
    seller_type_snapshot: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # Humbee's, open set
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    sub_status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cart_draft_id: Mapped[str | None] = mapped_column(
        String(26), nullable=True
    )  # REFERENCES orders_cart_drafts(id)
    employee_id: Mapped[str] = mapped_column(
        String(26), nullable=False
    )  # REFERENCES org_employees(id)
    visit_id: Mapped[str | None] = mapped_column(
        String(26), nullable=True
    )  # logical → routes_visits
    beat_id: Mapped[str | None] = mapped_column(
        String(26), nullable=True
    )  # denormalised for reporting scope

    # Humbee snapshots
    humbee_outlet_id: Mapped[str] = mapped_column(String(64), nullable=False)
    outlet_name_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    outlet_locality_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    humbee_manufacturer_id: Mapped[str] = mapped_column(String(64), nullable=False)
    manufacturer_name_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    # The seller chosen for this (outlet, brand) — replaces the former outlet-classification-
    # driven "distribution partner" concept entirely.
    humbee_seller_id: Mapped[str] = mapped_column(String(64), nullable=False)
    seller_name_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    humbee_buyer_esi_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    humbee_seller_esi_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    humbee_po_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ship_to_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ship_to_humbee_outlet_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ship_to_humbee_esi_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ship_to_label_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    shipping_address_line1: Mapped[str | None] = mapped_column(String(250), nullable=True)
    shipping_address_line2: Mapped[str | None] = mapped_column(String(250), nullable=True)
    shipping_address_state_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    shipping_address_district_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    shipping_address_pincode: Mapped[str | None] = mapped_column(String(6), nullable=True)
    # Was the seller relationship re-verified live at submission, not assumed from the
    # cart's provisional snapshot (was `classification_confirmed_live`).
    seller_confirmed_live: Mapped[bool] = mapped_column(nullable=False, default=False)
    snapshot_taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    snapshot_source_as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # approval
    requires_approval: Mapped[bool] = mapped_column(nullable=False)
    approval_request_id: Mapped[str | None] = mapped_column(
        String(26), nullable=True
    )  # logical → approvals_requests
    approver_employee_id_snapshot: Mapped[str | None] = mapped_column(String(26), nullable=True)
    approver_name_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # money
    subtotal_net_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    scheme_discount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    scheme_label_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_discount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    taxable_base_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    gst_amount_paise: Mapped[int] = mapped_column(
        BigInteger, nullable=False
    )  # Σ of line GST; no order-level rate
    gross_total_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, default="INR")
    approved_subtotal_net_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    approved_gross_total_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # downstream
    dp_sla_deadline_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dp_sla_breached_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dp_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    downstream_dp_order_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_budget_remaining: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=5)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)

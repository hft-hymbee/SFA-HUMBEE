"""`routes_visit_outcomes` — 1:1 close-out record per visit. database-design.md §8.

`photo_attachment_id` is a logical pointer to `platform_attachments` (§12.3); `order_ids` holds
SFA order ids (M10), logical only.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class RouteVisitOutcome(Base, ConventionsMixin):
    __tablename__ = "routes_visit_outcomes"
    __table_args__ = (
        Index("uq_routes_visit_outcomes_visit", "visit_id", unique=True),  # 1:1
        CheckConstraint("outcome IN ('order_placed','no_order')", name="outcome_chk"),
        CheckConstraint(
            "no_order_reason IS NULL OR no_order_reason IN "
            "('shop_closed','no_requirement','stock_full','revisit_later','credit_issue','other')",
            name="reason_chk",
        ),
        # R-RTE-16: a no-order close-out is always reason-coded
        CheckConstraint(
            "outcome <> 'no_order' OR no_order_reason IS NOT NULL", name="no_order_chk"
        ),
        CheckConstraint(
            "outcome <> 'order_placed' OR cardinality(order_ids) >= 1", name="order_chk"
        ),
    )

    visit_id: Mapped[str] = mapped_column(String(26), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    no_order_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    no_order_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_attachment_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    order_ids: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'")
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

"""`orders_status_events` — append-only order timeline.

The timeline terminates at registration ("Sent to PO/DP"): SFA's job ends at taking the
order, so there is no downstream-status section here and no event kind beyond that node.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class StatusEvent(Base, ConventionsMixin):
    __tablename__ = "orders_status_events"
    __table_args__ = (
        UniqueConstraint("order_id", "seq", name="uq_orders_status_events_seq"),
        Index(
            "ix_orders_status_events_sp", "order_id", "seq", postgresql_where=text("visible_to_sp")
        ),
        CheckConstraint("seq >= 1", name="orders_status_events_seq_chk"),
        CheckConstraint(
            "timeline_state IN ('done','current','edited','rejected','todo')",
            name="orders_status_events_state_chk",
        ),
    )

    order_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timeline_state: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_employee_id: Mapped[str | None] = mapped_column(
        String(26), nullable=True
    )  # REFERENCES org_employees(id)
    attempt_id: Mapped[str | None] = mapped_column(
        String(26), nullable=True
    )  # REFERENCES orders_submission_attempts(id)
    visible_to_sp: Mapped[bool] = mapped_column(nullable=False, default=True)

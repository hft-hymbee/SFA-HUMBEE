"""`orders_approval_edits` — audit trail of manager quantity edits made during approval.

`field` is constrained to `'qty'` because quantity is the only thing an approver may edit today;
`orders_approval_edits_change_chk` rejects a no-op "edit" so this table only ever records an actual
change.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class ApprovalEdit(Base, ConventionsMixin):
    __tablename__ = "orders_approval_edits"
    __table_args__ = (
        Index("ix_orders_approval_edits_order", "order_id", "edited_at"),
        CheckConstraint("field = 'qty'", name="orders_approval_edits_field_chk"),
        CheckConstraint("before_value <> after_value", name="orders_approval_edits_change_chk"),
    )

    order_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    order_line_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("orders_lines.id", ondelete="CASCADE"), nullable=False
    )
    approval_decision_id: Mapped[str] = mapped_column(
        String(26), nullable=False
    )  # logical → approvals_decisions
    product_name_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    field: Mapped[str] = mapped_column(String(16), nullable=False)
    before_value: Mapped[int] = mapped_column(Integer, nullable=False)
    after_value: Mapped[int] = mapped_column(Integer, nullable=False)
    edited_by_employee_id: Mapped[str] = mapped_column(
        String(26), nullable=False
    )  # REFERENCES org_employees(id)
    edited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

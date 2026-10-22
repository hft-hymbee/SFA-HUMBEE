"""`attendance_punch_events` — append-only punch log. database-design.md §9.

`gps_fix_id` is `NOT NULL` (R-ATT-04): a punch without a fix cannot exist, made a database fact
rather than a nullable column that quietly fills with nulls.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin, FieldEventTimingMixin
from humbee_sfa.core.db import Base


class PunchEvent(Base, ConventionsMixin, FieldEventTimingMixin):
    __tablename__ = "attendance_punch_events"
    __table_args__ = (
        Index("uq_attendance_punch_idem", "tenant_id", "idempotency_key", unique=True),
        Index("ix_attendance_punch_day", "attendance_day_id", "occurred_at"),
        Index("ix_attendance_punch_emp", "tenant_id", "employee_id", "business_date", "direction"),
        CheckConstraint("direction IN ('in','out')", name="direction_chk"),
    )

    employee_id: Mapped[str] = mapped_column(String(26), nullable=False)
    attendance_day_id: Mapped[str] = mapped_column(String(26), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    gps_fix_id: Mapped[str] = mapped_column(String(26), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)

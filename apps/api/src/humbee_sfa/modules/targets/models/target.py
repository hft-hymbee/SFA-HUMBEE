"""`targets` — the per-employee, per-month target record. database-design.md §11.2.

`target_value` for `sales` targets is stored derived (Σ lines) and re-derived on every write per
R-TGT-09. Achievement is never a column here (`INV-14`) — it is read live from Humbee.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class Target(Base, ConventionsMixin):
    __tablename__ = "targets"
    __table_args__ = (
        # R-TGT-08: one active target per (employee, type, month)
        Index(
            "uq_targets_active",
            "tenant_id",
            "employee_id",
            "target_type",
            "period_month",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "ix_targets_period",
            "tenant_id",
            "period_month",
            "target_type",
            postgresql_where=text("status = 'active'"),
        ),
        CheckConstraint("target_type IN ('sales','outlets','leads')", name="targets_type_chk"),
        CheckConstraint("period_type = 'month'", name="targets_period_type_chk"),
        CheckConstraint("status IN ('active','removed')", name="targets_status_chk"),
        CheckConstraint("date_trunc('month', period_month) = period_month", name="targets_month_start_chk"),
        CheckConstraint("target_value IS NULL OR target_value > 0", name="targets_value_chk"),
        CheckConstraint(
            "(target_type = 'outlets' AND outlet_category_scope IS NOT NULL) OR "
            "(target_type <> 'outlets' AND outlet_category_scope IS NULL)",
            name="targets_category_scope_chk",
        ),
        CheckConstraint("(status = 'removed') = (removed_at IS NOT NULL)", name="targets_removed_chk"),
    )

    employee_id: Mapped[str] = mapped_column(String(26), nullable=False)
    target_type: Mapped[str] = mapped_column(String(16), nullable=False)
    period_type: Mapped[str] = mapped_column(String(16), nullable=False, default="month")
    period_month: Mapped[date] = mapped_column(Date, nullable=False)  # first day of month, IST
    target_value: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    outlet_category_scope: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    removed_by: Mapped[str | None] = mapped_column(String(26), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

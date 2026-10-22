"""`platform_sweep_runs` — one row per scheduled-job run.

The unique index is the idempotency guarantee: one run per sweep type per
business date.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class SweepRun(Base, ConventionsMixin):
    __tablename__ = "platform_sweep_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sweep_type", "business_date", name="uq_platform_sweep_run"),
        CheckConstraint("status IN ('running','succeeded','failed','partial')", name="status_chk"),
    )

    sweep_type: Mapped[str] = mapped_column(String(64), nullable=False)  # 'eod_visit_sweep','approval_reroute',...
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    rows_affected: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

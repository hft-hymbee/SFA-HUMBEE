"""`routes_missed_visit_audits` — written only by the EOD sweep.

`sweep_run_id` is a logical pointer into `platform_sweep_runs`.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class RouteMissedVisitAudit(Base, ConventionsMixin):
    __tablename__ = "routes_missed_visit_audits"
    __table_args__ = (
        Index("uq_routes_missed_visit", "visit_id", unique=True),  # idempotency
        Index("ix_routes_missed_day", "tenant_id", "employee_id", "business_date"),
    )

    visit_id: Mapped[str] = mapped_column(String(26), nullable=False)
    employee_id: Mapped[str] = mapped_column(String(26), nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    humbee_outlet_id: Mapped[str] = mapped_column(String(64), nullable=False)
    planned_visit_type: Mapped[str] = mapped_column(String(16), nullable=False)
    swept_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sweep_run_id: Mapped[str] = mapped_column(String(26), nullable=False)  # logical -> platform_sweep_runs

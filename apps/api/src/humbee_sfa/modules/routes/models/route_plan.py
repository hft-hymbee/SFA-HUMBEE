"""`routes_plans` — one plan per employee per business date.

`beat_id`/`beat_version_id` are logical references into `beats` (module boundary) — never
declared FKs.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class RoutePlan(Base, ConventionsMixin):
    __tablename__ = "routes_plans"
    __table_args__ = (
        # One live plan per employee per business date
        Index(
            "uq_routes_plans_employee_date",
            "tenant_id",
            "employee_id",
            "business_date",
            unique=True,
        ),
        Index(
            "ix_routes_plans_sweep",
            "tenant_id",
            "business_date",
            postgresql_where=text("state IN ('scheduled','in_progress')"),
        ),
        CheckConstraint("state IN ('draft','scheduled','in_progress','closed')", name="state_chk"),
    )

    employee_id: Mapped[str] = mapped_column(String(26), nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    beat_id: Mapped[str] = mapped_column(String(26), nullable=False)  # logical -> beats
    beat_version_id: Mapped[str] = mapped_column(String(26), nullable=False)  # snapshot
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    swept_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

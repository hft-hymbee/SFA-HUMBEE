"""`outlets_business_profiler_history` — every change of an outlet's business profiler %.

Humbee computes the % on read and keeps no history, so SFA records each value it learns (Humbee's
push, a live fetch, the day-close pull) with the instant it took effect. Reporting reads "the % at
the end of day D" from here; see `outlets.service.business_profiler_as_of`.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Index, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base

SOURCES = ("push", "fetch", "day_close")


class OutletBusinessProfilerHistory(Base, ConventionsMixin):
    __tablename__ = "outlets_business_profiler_history"
    __table_args__ = (
        Index("ix_outlets_bp_history_lookup", "tenant_id", "humbee_outlet_id", "effective_at"),
        Index("ix_outlets_bp_history_day_close", "tenant_id", "for_business_date"),
        CheckConstraint("source IN ('push','fetch','day_close')", name="source_chk"),
        CheckConstraint(
            "(source = 'day_close') = (for_business_date IS NOT NULL)", name="day_close_chk"
        ),
    )

    humbee_outlet_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # Null: Humbee has no % for the outlet (no admin user, no profile) — counts as not filled.
    pct: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    # Set only on `day_close` rows: the business date that pull froze.
    for_business_date: Mapped[date | None] = mapped_column(Date, nullable=True)

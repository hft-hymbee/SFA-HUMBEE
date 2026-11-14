"""`outlets` — the tenant-scoped local projection of Humbee's outlet master."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class Outlet(Base, ConventionsMixin):
    __tablename__ = "outlets"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "humbee_outlet_id", name="uq_outlets_tenant_humbee_outlet"
        ),
    )

    humbee_outlet_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    pan: Mapped[str | None] = mapped_column(String(10), nullable=True)
    humbee_shop_category_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    humbee_district_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Last live value from Humbee (outlet detail or the business-profiler batch), served when Humbee is
    # unreachable. Null until the first live read.
    business_profiler_pct: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    business_profiler_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

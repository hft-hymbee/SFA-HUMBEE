"""`routes_outlet_coordinate_corrections` — durable queue for O-4 field pin corrections (epic 07
Story 7.3). database-design.md conventions.

Committed before the Humbee `PATCH /outlets/{id}/coordinates` call is attempted, mirroring the H7
write-path rule (`docs/features/03-humbee-integration-contract.md` §5): a crash mid-call must not
lose a correction the sales person already captured. `captured_at` (device clock, possibly offline)
orders the queue; `submitted_at` (server clock) is `NULL` until the Humbee call resolves.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class RouteOutletCoordinateCorrection(Base, ConventionsMixin):
    __tablename__ = "routes_outlet_coordinate_corrections"
    __table_args__ = (
        Index("ix_routes_coord_corr_outlet", "tenant_id", "humbee_outlet_id", "captured_at"),
        Index("ix_routes_coord_corr_visit", "tenant_id", "visit_id"),
        CheckConstraint("status IN ('pending','accepted','rejected','failed')", name="status_chk"),
        CheckConstraint("provider IN ('gps','network','fused')", name="provider_chk"),
        CheckConstraint("accuracy_m >= 0", name="accuracy_chk"),
    )

    visit_id: Mapped[str] = mapped_column(String(26), nullable=False)
    humbee_outlet_id: Mapped[str] = mapped_column(String(64), nullable=False)
    employee_id: Mapped[str] = mapped_column(String(26), nullable=False)
    latitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    accuracy_m: Mapped[float] = mapped_column(Numeric(7, 2), nullable=False)
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'pending'"))
    # Verbatim from Humbee's `data.rejection_code` — never translated or summarised.
    rejection_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

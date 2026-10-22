"""`attendance_gps_fixes` — append-only, raw GPS evidence.

Both the `numeric` lat/lng and the PostGIS `point` are stored: `numeric` is the raw evidence the
device reported, `point` is the derived spatial index key — collapsing to only `point` would make
"was this punch real?" unanswerable later.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import CheckConstraint, DateTime, Index, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class GpsFix(Base, ConventionsMixin):
    __tablename__ = "attendance_gps_fixes"
    __table_args__ = (
        Index("ix_attendance_gps_point", "point", postgresql_using="gist"),
        Index(
            "ix_attendance_gps_pending",
            "tenant_id",
            postgresql_where=text("geocode_status = 'pending'"),
        ),
        # Backs `latest_gps_fixes_for_employees` (the coverage drill-down's latest-fix lookup) — DISTINCT ON
        # (created_by_employee_id) ORDER BY created_by_employee_id, captured_at DESC over a
        # tenant/employee/time window, without this the table's append-only growth means a full
        # scan per coverage request.
        Index(
            "ix_attendance_gps_latest_fix",
            "tenant_id", "created_by_employee_id", "captured_at",
        ),
        CheckConstraint("provider IN ('gps','network','fused')", name="provider_chk"),
        CheckConstraint("geocode_status IN ('ok','failed','pending')", name="geocode_chk"),
        CheckConstraint("accuracy_m >= 0", name="accuracy_chk"),
    )

    latitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    # spatial_index=False: the explicit ix_attendance_gps_point index below is the declared one;
    # geoalchemy2 would otherwise also add a duplicate.
    point: Mapped[Any] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False
    )
    accuracy_m: Mapped[float] = mapped_column(Numeric(7, 2), nullable=False)
    altitude_m: Mapped[float | None] = mapped_column(Numeric(7, 2), nullable=True)
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    is_mock_location: Mapped[bool] = mapped_column(nullable=False, default=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    geocode_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")

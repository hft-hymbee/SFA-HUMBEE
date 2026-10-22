"""`routes_stops` — snapshotted stop list for a plan. database-design.md §8.

Snapshots are retained even when locality is unavailable, so running a route makes no Humbee call
and historical stops never drift with the current outlet projection. `visit_id` is a logical
pointer into `routes_visits` (created after this table) — never a declared FK.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import CheckConstraint, DateTime, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class RouteStop(Base, ConventionsMixin):
    __tablename__ = "routes_stops"
    __table_args__ = (
        UniqueConstraint("route_plan_id", "humbee_outlet_id", name="uq_routes_stops_outlet"),
        # drag-to-reorder (S-ROUTE2a) rewrites several sequence_no values in one transaction;
        # a non-deferrable unique index would fail on the first intermediate collision.
        UniqueConstraint(
            "route_plan_id",
            "sequence_no",
            name="uq_routes_stops_sequence",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint("sequence_no >= 1", name="sequence_chk"),
        CheckConstraint("run_origin IN ('assigned_beat','unplanned_beat')", name="origin_chk"),
    )

    route_plan_id: Mapped[str] = mapped_column(String(26), nullable=False)
    humbee_outlet_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    beat_id: Mapped[str] = mapped_column(String(26), nullable=False)  # logical -> beats
    beat_version_id: Mapped[str] = mapped_column(String(26), nullable=False)  # snapshot, R-RTE-07
    run_origin: Mapped[str] = mapped_column(String(32), nullable=False)
    distance_from_prev_km: Mapped[float | None] = mapped_column(
        Numeric(5, 1), nullable=True
    )  # derived from snapshot_point via PostGIS
    snapshot_name: Mapped[str] = mapped_column(String(255), nullable=False)
    snapshot_locality: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # DDL declares no index on this column (unlike checkin_gps/point/anchor_point elsewhere) —
    # spatial_index=False to avoid geoalchemy2 silently adding one that isn't in the design.
    snapshot_point: Mapped[Any | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=True
    )
    snapshot_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    snapshot_as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    visit_id: Mapped[str | None] = mapped_column(String(26), nullable=True)  # logical -> routes_visits

"""`routes_visits` — the visit lifecycle. database-design.md §8.

`route_plan_id`/`route_stop_id` are declared references within the `routes` context;
`combined_visit_id` has no `REFERENCES` in the DDL (forward pointer into
`routes_combined_visits`, created later) and is logical only. INV-06 (no visit without a same-day
punch-in) spans `attendance` and is enforced in `routes.service`, not here.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import CheckConstraint, Date, DateTime, Index, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin, FieldEventTimingMixin
from humbee_sfa.core.db import Base


class RouteVisit(Base, ConventionsMixin, FieldEventTimingMixin):
    __tablename__ = "routes_visits"
    __table_args__ = (
        Index("ix_routes_visits_day", "tenant_id", "employee_id", "business_date"),
        Index("ix_routes_visits_plan", "route_plan_id", "state"),
        Index(
            "ix_routes_visits_outlet",
            "tenant_id",
            "humbee_outlet_id",
            text("business_date DESC"),
        ),
        Index(
            "ix_routes_visits_gps",
            "checkin_gps",
            postgresql_using="gist",
            postgresql_where=text("checkin_gps IS NOT NULL"),
        ),
        Index(
            "ix_routes_visits_open",
            "tenant_id",
            "employee_id",
            unique=True,
            postgresql_where=text("state = 'in_progress'"),
        ),
        CheckConstraint(
            "state IN ('scheduled','in_progress','visited_with_order','visited_no_order',"
            "'missed','cancelled')",
            name="state_chk",
        ),
        CheckConstraint("origin IN ('planned','unplanned')", name="origin_chk"),
        CheckConstraint("visit_type IN ('physical','telephonic')", name="type_chk"),
        # R-RTE-14: telephonic visits capture no GPS
        CheckConstraint(
            "visit_type <> 'telephonic' OR checkin_gps IS NULL", name="telephonic_no_gps_chk"
        ),
        # R-RTE-13: unplanned visits never pass through `scheduled`
        CheckConstraint(
            "origin <> 'unplanned' OR state <> 'scheduled'", name="unplanned_state_chk"
        ),
        CheckConstraint(
            "origin <> 'planned' OR route_stop_id IS NOT NULL", name="planned_stop_chk"
        ),
        CheckConstraint(
            "(state = 'missed') = (missed_at IS NOT NULL)", name="missed_chk"
        ),
    )

    employee_id: Mapped[str] = mapped_column(String(26), nullable=False)
    route_plan_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    route_stop_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    humbee_outlet_id: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    origin: Mapped[str] = mapped_column(String(16), nullable=False)
    visit_type: Mapped[str] = mapped_column(String(16), nullable=False)  # INV-07: never null
    planned_for_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checked_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # spatial_index=False: the partial gist index below (ix_routes_visits_gps) is the declared
    # index; geoalchemy2 would otherwise also add its own unconditional one.
    checkin_gps: Mapped[Any | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=True
    )
    checkin_gps_accuracy_m: Mapped[float | None] = mapped_column(Numeric(7, 2), nullable=True)
    checkin_gps_provider: Mapped[str | None] = mapped_column(String(16), nullable=True)
    checkin_gps_is_mock: Mapped[bool | None] = mapped_column(nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    combined_visit_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    missed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

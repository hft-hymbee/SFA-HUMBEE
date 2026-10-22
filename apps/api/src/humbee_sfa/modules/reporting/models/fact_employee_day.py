"""`fact_employee_day` — daily employee grain fact, one row per (tenant, employee, business_date).
database-design.md §13.

Exempt from `ConventionsMixin` (§2.4 rule 2, §13 header): derived and droppable, the durable truth
is `platform_domain_events`. The primary key is the natural composite key
`(tenant_id, employee_id, business_date)` — no ULID `id`, no actor/soft-delete columns.

Design notes:
- MTD is never stored here — it is always summed over this table's day rows at query time.
- The projector recomputes whole rows from the event log rather than incrementing counters;
  `revision` proves a recompute happened, it is not a counter of updates.
- `formula_version` is written on every row (see `projector.FORMULA_VERSION`) so a future formula
  change has a marker to enqueue against. No replay/recompute pipeline reads it yet — that pipeline
  (`reporting_recompute_queue`, `is_dirty`) was removed as unreachable scaffolding; re-add both
  together if a formula ever actually needs to change.
"""

from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.db import Base


class FactEmployeeDay(Base):
    __tablename__ = "fact_employee_day"
    __table_args__ = (
        Index(
            "ix_fact_employee_day_scope",
            "tenant_id",
            "business_date",
            "employee_key",
        ),
        Index(
            "ix_fact_employee_day_mtd",
            "tenant_id",
            "employee_id",
            text("business_date DESC"),
        ),
    )

    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    employee_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    business_date: Mapped[date] = mapped_column(primary_key=True)
    employee_key: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("dim_employee.employee_key"), nullable=False
    )

    punched_in: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    first_punch_in_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    first_punch_in_local_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    last_punch_out_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_late_punch_in: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    on_duty_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    official_work_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    official_work_task_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_leave_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    leave_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    punch_in_location_label: Mapped[str | None] = mapped_column(Text, nullable=True)

    planned_outlets: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    visited_planned_outlets: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unplanned_visits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    visits_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    visits_physical: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    visits_telephonic: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    productive_visits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missed_visits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outlet_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    travel_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idle_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    distance_metres: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    orders_submitted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    order_lines_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    order_net_value_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    order_gross_value_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    orders_approved_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    orders_rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    orders_edited_on_approval_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    orders_submission_failed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    leads_captured_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outlets_onboarded_submitted_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    outlets_onboarded_verified_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    formula_version: Mapped[int] = mapped_column(Integer, nullable=False)
    last_event_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

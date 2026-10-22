"""`attendance_days` — one row per employee per business date.

`first_punch_in_id`/`last_punch_out_id` are logical pointers into `attendance_punch_events`
(reverse reference would create a cycle); `leave_request_id` is a logical pointer into
`leave_requests` (cross-module).
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, Date, DateTime, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class AttendanceStatus(StrEnum):
    PRESENT = "present"
    LATE = "late"
    ABSENT = "absent"
    LEAVE = "leave"
    NO_RECORD = "no_record"


_STATUS_VALUES_SQL = "', '".join(status.value for status in AttendanceStatus)


class AttendanceDay(Base, ConventionsMixin):
    __tablename__ = "attendance_days"
    __table_args__ = (
        UniqueConstraint("tenant_id", "employee_id", "business_date", name="uq_attendance_days"),
        Index("ix_attendance_days_date", "tenant_id", "business_date", "status"),
        CheckConstraint(f"status IN ('{_STATUS_VALUES_SQL}')", name="status_chk"),
        CheckConstraint(
            f"(status = '{AttendanceStatus.LEAVE.value}') = (leave_request_id IS NOT NULL)",
            name="leave_chk",
        ),
        CheckConstraint(
            "on_duty = (first_punch_in_id IS NOT NULL AND last_punch_out_id IS NULL)",
            name="on_duty_chk",
        ),
        CheckConstraint(
            "punched_out_at IS NULL OR punched_in_at IS NULL OR punched_out_at >= punched_in_at",
            name="punch_order_chk",
        ),
    )

    employee_id: Mapped[str] = mapped_column(String(26), nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    first_punch_in_id: Mapped[str | None] = mapped_column(
        String(26), nullable=True
    )  # logical -> attendance_punch_events (cycle)
    last_punch_out_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    punched_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    punched_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    punch_in_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    on_duty: Mapped[bool] = mapped_column(nullable=False, default=False)
    is_late: Mapped[bool] = mapped_column(nullable=False, default=False)
    leave_request_id: Mapped[str | None] = mapped_column(String(26), nullable=True)  # logical -> leave_requests

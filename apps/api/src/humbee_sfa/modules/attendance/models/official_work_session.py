"""`attendance_official_work_sessions` — meeting/training/collection time tracking.

`duration_seconds` is persisted even though derivable: the server-computed
duration is authoritative over the client tick counter, and storing it is how that decision becomes
auditable. `form_definition_id` is a logical pointer into `platform_form_definitions`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin, FieldEventTimingMixin
from humbee_sfa.core.db import Base


class OfficialWorkSession(Base, ConventionsMixin, FieldEventTimingMixin):
    __tablename__ = "attendance_official_work_sessions"
    __table_args__ = (
        Index("uq_attendance_official_idem", "tenant_id", "idempotency_key", unique=True),
        # At most one running session per employee
        Index(
            "uq_attendance_official_running",
            "tenant_id",
            "employee_id",
            unique=True,
            postgresql_where=text("status = 'running'"),
        ),
        Index("ix_attendance_official_day", "tenant_id", "employee_id", "business_date"),
        CheckConstraint(
            "work_type IN ('meeting','training','collection','other')", name="type_chk"
        ),
        CheckConstraint("status IN ('running','completed')", name="status_chk"),
        CheckConstraint("(status = 'completed') = (ended_at IS NOT NULL)", name="end_chk"),
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0", name="duration_chk"
        ),
        CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="order_chk"),
    )

    employee_id: Mapped[str] = mapped_column(String(26), nullable=False)
    work_type: Mapped[str] = mapped_column(String(32), nullable=False)
    form_definition_id: Mapped[str] = mapped_column(String(26), nullable=False)  # -> platform_form_definitions
    form_response: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)  # purpose, notes, future fields
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    start_gps_fix_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    end_gps_fix_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)

"""`attendance_export_jobs` — async org-wide attendance export requests."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class ExportJob(Base, ConventionsMixin):
    __tablename__ = "attendance_export_jobs"
    __table_args__ = (
        Index(
            "ix_attendance_export_queue",
            "status",
            "requested_at",
            postgresql_where=text("status IN ('queued','running')"),
        ),
        CheckConstraint("scope = 'org'", name="scope_chk"),
        CheckConstraint("format IN ('csv','xlsx','pdf')", name="format_chk"),
        CheckConstraint(
            "status IN ('queued','running','ready','failed')", name="status_chk"
        ),
        CheckConstraint("date_to >= date_from", name="range_chk"),
        CheckConstraint(
            "status <> 'ready' OR artifact_url IS NOT NULL", name="ready_chk"
        ),
    )

    requested_by: Mapped[str] = mapped_column(String(26), nullable=False)
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default="org")
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
    format: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    artifact_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

"""`approvals_requests` — the single approval-request table serving beat create/edit, DP orders,
leave and outlet verification.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class Request(Base, ConventionsMixin):
    __tablename__ = "approvals_requests"
    __table_args__ = (
        # At most one pending request per subject. The single most important index here.
        Index(
            "uq_approvals_one_pending_per_subject",
            "tenant_id",
            "subject_type",
            "subject_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index(
            "ix_approvals_inbox",
            "tenant_id",
            "assigned_approver_id",
            "status",
            text("submitted_at DESC"),
        ),
        Index("ix_approvals_mine", "tenant_id", "requester_id", text("submitted_at DESC")),
        Index("ix_approvals_subject", "tenant_id", "subject_type", "subject_id"),
        # Backs the daily re-routing sweep, which scans every pending request once per IST day.
        Index(
            "ix_approvals_sweep",
            "tenant_id",
            "submitted_business_date",
            postgresql_where=text("status = 'pending'"),
        ),
        CheckConstraint(
            "subject_type IN ('beat_create','beat_edit','dp_order','leave','outlet_verification')",
            name="subject_type_chk",
        ),
        CheckConstraint(
            "status IN "
            "('pending','approved','approved_with_edits','auto_approved','rejected','withdrawn','expired')",
            name="status_chk",
        ),
        CheckConstraint(
            "routing_reason IN ('direct_parent','escalated_parent_on_leave','auto_top_of_hierarchy')",
            name="routing_reason_chk",
        ),
        # Unbounded, superseded 2026-08-21 — NOT the old "BETWEEN 0 AND 4".
        CheckConstraint("escalation_depth >= 0", name="escalation_depth_chk"),
        CheckConstraint("amount_paise IS NULL OR amount_paise >= 0", name="amount_chk"),
        # A pending request always has an approver; auto-approved never does.
        CheckConstraint(
            "status <> 'pending' OR assigned_approver_id IS NOT NULL", name="pending_has_approver_chk"
        ),
        CheckConstraint(
            "status <> 'auto_approved' OR assigned_approver_id IS NULL", name="auto_no_approver_chk"
        ),
        # Rejection requires a reason.
        CheckConstraint(
            "status <> 'rejected' OR (decision_note IS NOT NULL AND length(btrim(decision_note)) > 0)",
            name="reject_note_chk",
        ),
        # Terminal states carry a decision timestamp.
        CheckConstraint("status = 'pending' OR decided_at IS NOT NULL", name="terminal_decided_chk"),
        CheckConstraint(
            "routing_reason <> 'escalated_parent_on_leave' OR escalated_from_id IS NOT NULL",
            name="escalation_pair_chk",
        ),
    )

    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(26), nullable=False)  # logical FK into another module
    subject_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    requester_id: Mapped[str] = mapped_column(String(26), ForeignKey("org_employees.id"), nullable=False)
    # Snapshot at submission.
    requester_manager_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("org_employees.id"), nullable=True
    )
    assigned_approver_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("org_employees.id"), nullable=True
    )
    routing_reason: Mapped[str] = mapped_column(String(32), nullable=False)
    escalated_from_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("org_employees.id"), nullable=True
    )
    escalation_depth: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)  # denormalised from adapter.summary()
    subtitle: Mapped[str] = mapped_column(String(200), nullable=False)
    amount_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_business_date: Mapped[date] = mapped_column(Date, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("org_employees.id"), nullable=True
    )
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    edit_applied: Mapped[bool] = mapped_column(nullable=False, default=False)
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

"""`orders_submission_attempts` — append-only log of every Humbee submission attempt.

`request_idempotency_key` must be byte-identical on every attempt for an order (it equals
`orders.order_number`) — a fresh key per retry is exactly how a retry becomes a duplicate order at
Humbee. That invariant cannot be a CHECK (the reference value lives on the parent row); the
submission worker owns it and it is covered by a flow test instead.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CHAR,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class SubmissionAttempt(Base, ConventionsMixin):
    __tablename__ = "orders_submission_attempts"
    __table_args__ = (
        UniqueConstraint("order_id", "attempt_no", name="uq_orders_attempt_no"),
        Index("ix_orders_attempt_order", "order_id", text("attempt_no DESC")),
        Index(
            "ix_orders_attempt_retry",
            "next_retry_at",
            postgresql_where=text("outcome IN ('failed_retryable','timeout','circuit_open')"),
        ),
        CheckConstraint("attempt_no >= 1", name="orders_attempt_no_chk"),
        CheckConstraint(
            "trigger IN ('outbox_auto','sla_sweeper','manual_sp_retry','manual_admin_retry','reconciliation')",
            name="orders_attempt_trigger_chk",
        ),
        CheckConstraint(
            "outcome IS NULL OR outcome IN ('success','failed_retryable','failed_terminal','timeout','circuit_open')",
            name="orders_attempt_outcome_chk",
        ),
        CheckConstraint(
            "(completed_at IS NULL) = (outcome IS NULL)", name="orders_attempt_complete_chk"
        ),
        CheckConstraint(
            "outcome IS NULL OR outcome = 'success' OR sfa_display_reason IS NOT NULL",
            name="orders_attempt_reason_chk",
        ),
    )

    order_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    attempt_no: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    trigger: Mapped[str] = mapped_column(String(32), nullable=False)
    triggered_by_employee_id: Mapped[str | None] = mapped_column(
        String(26), nullable=True
    )  # REFERENCES org_employees(id)
    request_idempotency_key: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # = orders.order_number, IDENTICAL on every attempt
    request_payload_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
    failure_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    humbee_error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    humbee_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    humbee_http_status: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    sfa_display_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    downstream_dp_order_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Reconciliation: the total Humbee accepted, compared against the manager-approved total.
    # Null when the response carried none (unverified shape) or a null `unit_price_net_paise`
    # left nothing on the SFA side to compare — a missing total is "not checked", not a mismatch.
    humbee_accepted_gross_total_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)

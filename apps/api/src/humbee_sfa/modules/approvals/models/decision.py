"""`approvals_decisions` — append-only audit trail of every action taken on an approval request.
database-design.md §6. `ApprovalTimelineStep`/`ApprovalAdvisory` are projections computed from this
table at read time, not separate tables.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class Decision(Base, ConventionsMixin):
    __tablename__ = "approvals_decisions"
    __table_args__ = (
        UniqueConstraint("request_id", "sequence", name="uq_approvals_decisions_seq"),
        Index("ix_approvals_decisions_request", "request_id", "sequence"),
        CheckConstraint(
            "action IN "
            "('submitted','routed','escalated','edited','approved','rejected','auto_approved','withdrawn')",
            name="action_chk",
        ),
        CheckConstraint("sequence >= 1", name="sequence_chk"),
    )

    request_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("approvals_requests.id"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("org_employees.id"), nullable=True
    )  # NULL = system actor
    actor_role: Mapped[str | None] = mapped_column(String(32), nullable=True)  # snapshot at decision time
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    edit_patch: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

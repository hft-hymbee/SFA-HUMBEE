"""`beats_activation_events` — append-only audit trail of beat deactivate/reactivate actions.
database-design.md §7.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class BeatActivationEvent(Base, ConventionsMixin):
    __tablename__ = "beats_activation_events"
    __table_args__ = (
        Index("ix_beats_activation_beat", "beat_id", text("occurred_at DESC")),
        CheckConstraint("action IN ('deactivated','reactivated')", name="action_chk"),
    )

    beat_id: Mapped[str] = mapped_column(String(26), ForeignKey("beats.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_employee_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("org_employees.id"), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

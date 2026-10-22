"""`beats_edit_requests` — a proposed edit to an approved beat, pending approval against a base and
proposed version. `diff` is server-computed (`BeatDiff[]`), never client-set.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class BeatEditRequest(Base, ConventionsMixin):
    __tablename__ = "beats_edit_requests"
    __table_args__ = (
        # At most one pending edit per beat.
        Index(
            "uq_beats_edit_one_pending",
            "beat_id",
            unique=True,
            postgresql_where=text("state = 'pending_approval'"),
        ),
        CheckConstraint(
            "state IN ('pending_approval','applied','rejected','withdrawn')", name="state_chk"
        ),
        CheckConstraint(
            "(state = 'pending_approval') = (resolved_at IS NULL)", name="resolved_chk"
        ),
    )

    beat_id: Mapped[str] = mapped_column(String(26), ForeignKey("beats.id"), nullable=False)
    base_version_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("beats_versions.id"), nullable=False
    )
    proposed_version_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("beats_versions.id"), nullable=False
    )
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    approval_request_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    diff: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_by_employee_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("org_employees.id"), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

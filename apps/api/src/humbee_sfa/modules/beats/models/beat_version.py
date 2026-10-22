"""`beats_versions` — versioned snapshot of a beat's territory and cadence.
`geo_scope`/`frequency` are `jsonb` value objects (GeoScope, BeatFrequency),
always read whole with their version, never queried across beats.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class BeatVersion(Base, ConventionsMixin):
    __tablename__ = "beats_versions"
    __table_args__ = (
        UniqueConstraint("beat_id", "version_no", name="uq_beats_versions_no"),
        # Exactly one approved version per beat.
        Index(
            "uq_beats_versions_one_approved",
            "beat_id",
            unique=True,
            postgresql_where=text("state = 'approved'"),
        ),
        Index(
            "uq_beats_versions_one_pending",
            "beat_id",
            unique=True,
            postgresql_where=text("state = 'pending_approval'"),
        ),
        CheckConstraint(
            "state IN ('draft','pending_approval','approved','superseded','rejected','withdrawn')",
            name="state_chk",
        ),
        CheckConstraint("version_no >= 1", name="version_no_chk"),
        CheckConstraint("outlet_count >= 0", name="outlet_count_chk"),
        # At least one district cluster.
        CheckConstraint("jsonb_array_length(geo_scope -> 'districts') >= 1", name="districts_chk"),
    )

    beat_id: Mapped[str] = mapped_column(String(26), ForeignKey("beats.id"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    geo_scope: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    frequency: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    outlet_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_employee_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("org_employees.id"), nullable=True
    )
    approval_request_id: Mapped[str | None] = mapped_column(
        String(26), nullable=True
    )  # logical → approvals_requests

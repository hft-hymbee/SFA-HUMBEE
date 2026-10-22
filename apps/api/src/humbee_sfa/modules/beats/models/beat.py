"""`beats` — the beat master. database-design.md §7. `current_version_id`/`draft_version_id` are
logical, not declared FKs: `beats` and `beats_versions` reference each other, and declaring both
would create a circular dependency that buys no correctness.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class Beat(Base, ConventionsMixin):
    __tablename__ = "beats"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_beats_tenant_code"),
        Index("ix_beats_owner", "tenant_id", "owner_employee_id", "lifecycle_state"),
        # S-ROUTE2's beat picker: approved + active only.
        Index(
            "ix_beats_plannable",
            "tenant_id",
            "owner_employee_id",
            postgresql_where=text("lifecycle_state = 'approved' AND activation_state = 'active'"),
        ),
        CheckConstraint(
            "lifecycle_state IN ('draft','pending_approval','approved','rejected')", name="lifecycle_chk"
        ),
        CheckConstraint("activation_state IN ('active','inactive')", name="activation_chk"),
        # R-BEAT-15 / M07 §3a.3: a live version exists iff the beat is approved.
        CheckConstraint(
            "(lifecycle_state = 'approved') = (current_version_id IS NOT NULL)",
            name="current_version_chk",
        ),
    )

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    owner_employee_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("org_employees.id"), nullable=False
    )
    lifecycle_state: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    activation_state: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    current_version_id: Mapped[str | None] = mapped_column(String(26), nullable=True)  # logical → beats_versions
    draft_version_id: Mapped[str | None] = mapped_column(String(26), nullable=True)  # logical → beats_versions
    deactivation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

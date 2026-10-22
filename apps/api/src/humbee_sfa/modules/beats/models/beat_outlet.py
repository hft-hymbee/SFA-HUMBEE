"""`beats_outlets` — versioned membership of locally projected outlets in a beat."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class BeatOutlet(Base, ConventionsMixin):
    __tablename__ = "beats_outlets"
    __table_args__ = (
        UniqueConstraint("beat_version_id", "outlet_id", name="uq_beats_outlets"),
        Index("ix_beats_outlets_outlet", "tenant_id", "outlet_id"),
    )

    beat_version_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("beats_versions.id"), nullable=False
    )
    outlet_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("outlets.id"), nullable=False
    )
    sequence_hint: Mapped[int | None] = mapped_column(Integer, nullable=True)

"""`platform_event_quarantine` — events older than the lateness window, or otherwise
unprocessable, land here instead of being silently dropped or silently applied.
database-design.md §12.2 (implements M11 §3b.4).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class EventQuarantine(Base, ConventionsMixin):
    __tablename__ = "platform_event_quarantine"
    __table_args__ = (
        Index(
            "ix_platform_event_quarantine_open",
            "tenant_id",
            "quarantined_at",
            postgresql_where=text("released_at IS NULL"),
        ),
    )

    domain_event_id: Mapped[str] = mapped_column(String(26), nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)  # 'beyond_lateness_window','unknown_event_type',...
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    quarantined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

"""`platform_rate_limit_counters` — per-IP/per-endpoint rate limiting.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class RateLimitCounter(Base, ConventionsMixin):
    __tablename__ = "platform_rate_limit_counters"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "scope", "counter_key", "window_start", name="uq_platform_rate_limits_scope_key_window",
        ),
    )

    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    counter_key: Mapped[str] = mapped_column(String(128), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

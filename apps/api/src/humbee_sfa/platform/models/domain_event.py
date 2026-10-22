"""`platform_domain_events` — the event-log spine the reporting projector replays.
database-design.md §12.1, §3 reconciliation item 4 (adds `stream`/`partition`/`event_seq`
ordering) and item 3 (JSON → JSONB).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Identity,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class DomainEvent(Base, ConventionsMixin):
    __tablename__ = "platform_domain_events"
    __table_args__ = (
        UniqueConstraint("stream", "partition", "event_seq", name="uq_platform_domain_events_seq"),
        Index(
            "ix_platform_domain_events_replay",
            "stream",
            "partition",
            "event_seq",
            postgresql_include=["aggregate_id", "business_date"],
        ),
        Index("ix_platform_domain_events_aggregate", "aggregate_type", "aggregate_id", "occurred_at"),
        Index("ix_platform_domain_events_day", "tenant_id", "stream", "event_type", "business_date"),
        Index(
            "ix_platform_domain_events_plan",
            "tenant_id",
            "stream",
            "event_type",
            text("(payload ->> 'employee_id')"),
            text("(payload ->> 'business_date')"),
        ),
        CheckConstraint(
            "stream IN ('org','identity','attendance','routes','beats','orders','approvals',"
            "'leave','targets','outlets')",
            name="stream_chk",
        ),
    )

    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stream: Mapped[str] = mapped_column(String(32), nullable=False)
    partition: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    event_seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True), nullable=False)
    # clock-skew clamp from M11 §3b.4 — a device with a bad clock is visible, not silently applied
    occurred_at_adjusted: Mapped[bool] = mapped_column(nullable=False, default=False)

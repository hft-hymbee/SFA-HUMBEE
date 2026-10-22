"""`reporting_projector_offset` — per-stream/partition checkpoint for the reporting projector.
database-design.md §13.

Exempt from `ConventionsMixin` (§2.4 rule 2, §13 header): derived and droppable, the durable truth
is `platform_domain_events` — this table only tracks how far the projector has consumed that log.
Primary key is the natural composite key `(stream, partition)` — no ULID `id`, no
tenant/actor/soft-delete columns (a projector offset is not tenant-scoped data).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.db import Base


class ProjectorOffset(Base):
    __tablename__ = "reporting_projector_offset"

    stream: Mapped[str] = mapped_column(String(32), primary_key=True)
    partition: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    last_event_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

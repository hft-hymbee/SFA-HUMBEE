"""`platform_idempotency_records`. database-design.md §12.1, §3 reconciliation item 3
(JSON → JSONB). Keys are scoped per endpoint, not globally (`endpoint` added, unique index
rescoped from `(tenant_id, idempotency_key)` to `(tenant_id, endpoint, idempotency_key)`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class IdempotencyRecord(Base, ConventionsMixin):
    __tablename__ = "platform_idempotency_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "endpoint", "idempotency_key", name="uq_platform_idempotency"),
        Index("ix_platform_idempotency_expiry", "expires_at"),
    )

    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    response_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

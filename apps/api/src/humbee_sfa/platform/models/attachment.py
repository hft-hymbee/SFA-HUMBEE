"""`platform_attachments` — the one place every uploaded file is checksummed and retained.
database-design.md §12.2. Deliberate deviation from M08/M14's inline-key/undefined-FK
approaches — `routes_visit_outcomes.photo_attachment_id` etc. point here.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class Attachment(Base, ConventionsMixin):
    __tablename__ = "platform_attachments"
    __table_args__ = (
        UniqueConstraint("object_key", name="uq_platform_attachments_key"),
        Index("ix_platform_attachments_subject", "tenant_id", "subject_type", "subject_id"),
        CheckConstraint("byte_size > 0", name="size_chk"),
    )

    object_key: Mapped[str] = mapped_column(Text, nullable=False)  # S3-compatible key
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(64), nullable=False)  # 'outlet_onboarding','visit_outcome',...
    subject_id: Mapped[str] = mapped_column(String(26), nullable=False)
    contains_pii: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

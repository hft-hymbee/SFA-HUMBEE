"""`identity_otp_challenges`. database-design.md §5, §3 reconciliation item 8 (adds `purpose`,
`employee_id`, `requester_ip`, and the partial unique index on the live challenge per phone).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CHAR, CheckConstraint, DateTime, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class OtpChallenge(Base, ConventionsMixin):
    __tablename__ = "identity_otp_challenges"
    __table_args__ = (
        Index("ix_identity_otp_phone", "tenant_id", "phone_e164_hmac", "issued_at"),
        Index(
            "uq_identity_otp_live",
            "tenant_id",
            "phone_e164_hmac",
            "purpose",
            unique=True,
            postgresql_where=text("consumed_at IS NULL"),
        ),
        CheckConstraint("purpose IN ('login','reauth')", name="purpose_chk"),
        CheckConstraint("attempts_used BETWEEN 0 AND max_attempts", name="attempts_chk"),
        CheckConstraint("expires_at > issued_at", name="expiry_chk"),
    )

    phone_e164_hmac: Mapped[str] = mapped_column(CHAR(64), nullable=False)  # never the plaintext phone
    employee_id: Mapped[str | None] = mapped_column(String(26), nullable=True)  # NULL: unregistered phone
    purpose: Mapped[str] = mapped_column(String(16), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)  # Argon2id
    code_length: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resend_available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    requester_ip: Mapped[str | None] = mapped_column(INET, nullable=True)

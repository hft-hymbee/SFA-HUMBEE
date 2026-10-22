"""`outlets_owner_otp_challenges` — phone verification for a prospective firm owner ahead of
ON-3 `onboard-firm`. Deliberately separate from `identity_otp_challenges`: the phone here belongs
to an external firm owner, never an `org_employees` row, and no session is ever issued from it.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CHAR, CheckConstraint, DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class OwnerOtpChallenge(Base, ConventionsMixin):
    __tablename__ = "outlets_owner_otp_challenges"
    __table_args__ = (
        Index("ix_outlets_owner_otp_phone", "tenant_id", "phone_e164_hmac", "issued_at"),
        CheckConstraint("attempts_used BETWEEN 0 AND max_attempts", name="owner_otp_attempts_chk"),
        CheckConstraint("expires_at > issued_at", name="owner_otp_expiry_chk"),
    )

    phone_e164_hmac: Mapped[str] = mapped_column(CHAR(64), nullable=False)  # never the plaintext phone
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)  # Argon2id
    code_length: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resend_available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    requester_ip: Mapped[str | None] = mapped_column(INET, nullable=True)

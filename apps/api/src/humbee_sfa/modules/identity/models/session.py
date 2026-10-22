"""`identity_sessions`. database-design.md §5, §3 reconciliation item 7: access tokens are
stateless (no `access_token_hash` stored); only refresh rotation and revocation need a row.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class Session(Base, ConventionsMixin):
    __tablename__ = "identity_sessions"
    __table_args__ = (
        UniqueConstraint("refresh_token_hash", name="uq_identity_sessions_refresh"),
        Index(
            "ix_identity_sessions_live",
            "tenant_id",
            "employee_id",
            postgresql_where=text("revoked_at IS NULL"),
        ),
        CheckConstraint(
            "revocation_reason IS NULL OR revocation_reason IN "
            "('user_logout','deactivated','admin_revoke','token_reuse','refresh_expired')",
            name="revocation_chk",
        ),
        CheckConstraint("(revoked_at IS NULL) = (revocation_reason IS NULL)", name="revoked_pair_chk"),
    )

    employee_id: Mapped[str] = mapped_column(String(26), nullable=False)
    device_id: Mapped[str] = mapped_column(String(26), nullable=False)
    access_token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    refresh_token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)

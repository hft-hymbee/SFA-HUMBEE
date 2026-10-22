"""`identity_auth_audit_events`. Append-only; drives re-login vs deactivated-account routing
via `revocation_reason` on the related session, not stored here.
"""

from __future__ import annotations

from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin, FieldEventTimingMixin
from humbee_sfa.core.db import Base


class AuthAuditEvent(Base, ConventionsMixin, FieldEventTimingMixin):
    __tablename__ = "identity_auth_audit_events"
    __table_args__ = (
        Index("ix_identity_auth_audit_phone", "tenant_id", "phone_e164_hmac", "occurred_at"),
        Index("ix_identity_auth_audit_employee", "tenant_id", "employee_id", "business_date"),
    )

    employee_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    phone_e164_hmac: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    requester_ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

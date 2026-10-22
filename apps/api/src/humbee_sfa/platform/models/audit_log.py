"""`platform_audit_logs` — the INV-13 landing zone: every state transition writes a row here.
database-design.md §12.1, §3 reconciliation item 3 (JSON → JSONB). Not partitioned (§17.1) —
append-only but low-volume relative to `platform_domain_events`, retained indefinitely (INV-12).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class AuditLog(Base, ConventionsMixin):
    __tablename__ = "platform_audit_logs"
    __table_args__ = (
        Index("ix_platform_audit_entity", "tenant_id", "entity_type", "entity_id", "created_at"),
        Index("ix_platform_audit_actor", "tenant_id", "created_by_employee_id", "created_at"),
    )

    entity_type: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    from_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    to_state: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    change_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

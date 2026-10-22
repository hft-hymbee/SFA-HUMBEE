"""`notifications` — the in-app notification feed. database-design.md §6. `uq_notifications_dedupe`
is what makes the notification-producing outbox safely at-least-once (R-AP-24): a redelivery hits
the unique index and is discarded rather than duplicating the row.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class Notification(Base, ConventionsMixin):
    __tablename__ = "notifications"
    __table_args__ = (
        Index(
            "uq_notifications_dedupe",
            "tenant_id",
            "recipient_id",
            "dedupe_key",
            unique=True,
        ),
        Index("ix_notifications_feed", "tenant_id", "recipient_id", text("created_at DESC")),
        # Backs the bell badge, which every screen polls (D-004, in-app only).
        Index(
            "ix_notifications_unread",
            "tenant_id",
            "recipient_id",
            postgresql_where=text("read_at IS NULL"),
        ),
        # M06 §3.5 lists seven kinds; `withdrawn` is the eighth, added because Flow 6 requires the
        # waiting approver to be notified when a requester withdraws and none of the seven names
        # that outcome. Keep this list and `notifications.service.KINDS` identical.
        CheckConstraint(
            "kind IN ('submitted','approved','edited','rejected','auto_approved','escalated',"
            "'beat','withdrawn')",
            name="kind_chk",
        ),
        CheckConstraint(
            "deep_link_type IS NULL OR deep_link_type IN "
            "('order','beat','leave','outlet','approval_request')",
            name="deep_link_chk",
        ),
        CheckConstraint(
            "(deep_link_type IS NULL) = (deep_link_id IS NULL)", name="deep_link_pair_chk"
        ),
    )

    recipient_id: Mapped[str] = mapped_column(String(26), ForeignKey("org_employees.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(200), nullable=True)
    deep_link_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    deep_link_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    source_request_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("approvals_requests.id"), nullable=True
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False)

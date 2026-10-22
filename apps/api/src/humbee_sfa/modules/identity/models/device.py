from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class Device(Base, ConventionsMixin):
    __tablename__ = "identity_devices"
    __table_args__ = (
        UniqueConstraint("tenant_id", "client_device_id", name="uq_identity_devices"),
        CheckConstraint("platform IN ('web_pwa','android','ios')", name="platform_chk"),
    )

    employee_id: Mapped[str] = mapped_column(String(26), nullable=False)
    client_device_id: Mapped[str] = mapped_column(String(255), nullable=False)  # client-generated, stable per install
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    app_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

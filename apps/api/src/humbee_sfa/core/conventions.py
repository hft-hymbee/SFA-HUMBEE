"""Schema conventions shared by all baseline tables."""

from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column

try:
    from ulid import ULID  # type: ignore[import-not-found]

    def generate_ulid() -> str:
        return str(ULID())

except ImportError:  # pragma: no cover - fallback only for constrained local environments.
    def generate_ulid() -> str:
        return uuid4().hex


class ULIDPrimaryKeyMixin:
    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )


class ActorMixin:
    created_by_employee_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    on_behalf_of_employee_id: Mapped[str | None] = mapped_column(String(26), nullable=True)


class SoftDeleteMixin:
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deactivated_by: Mapped[str | None] = mapped_column(String(26), nullable=True)


class TenantMixin:
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class FieldEventTimingMixin:
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)


class ConventionsMixin(
    ULIDPrimaryKeyMixin,
    TimestampMixin,
    ActorMixin,
    SoftDeleteMixin,
    TenantMixin,
):
    """Composite mixin with baseline table conventions."""

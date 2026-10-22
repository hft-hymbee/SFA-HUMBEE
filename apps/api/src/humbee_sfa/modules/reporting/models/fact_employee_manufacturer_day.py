"""`fact_employee_manufacturer_day` — manufacturer-grain daily fact, one row per (tenant, employee, business_date, humbee_manufacturer_id).

Exempt from `ConventionsMixin` — same rationale as `FactEmployeeDay`: derived from `platform_domain_events`,
no ULID id or soft-delete. The composite key is natural: `(tenant_id, employee_id, business_date, humbee_manufacturer_id)`.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.db import Base


class FactEmployeeManufacturerDay(Base):
    __tablename__ = "fact_employee_manufacturer_day"
    __table_args__ = (
        Index(
            "ix_femd_scope",
            "tenant_id",
            "business_date",
            "humbee_manufacturer_id",
        ),
    )

    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    employee_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    business_date: Mapped[date] = mapped_column(primary_key=True)
    humbee_manufacturer_id: Mapped[str] = mapped_column(String(64), primary_key=True)

    manufacturer_label: Mapped[str] = mapped_column(Text, nullable=False)
    orders_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lines_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    net_value_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # Quantity keyed by the product-line UOM it was actually recorded in (never summed across
    # UOMs — a manufacturer's target lives in exactly one UOM, and its own catalog can still
    # carry lines snapshotted in a different one; only reporting, which knows the target's UOM,
    # can pick the matching key).
    qty_by_uom: Mapped[dict[str, int]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

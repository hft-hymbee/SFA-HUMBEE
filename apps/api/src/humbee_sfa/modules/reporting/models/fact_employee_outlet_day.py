"""`fact_employee_outlet_day` — outlet-grain daily fact, one row per (tenant, employee, business_date, humbee_outlet_id).

Exempt from `ConventionsMixin` — same rationale as `FactEmployeeDay`: derived from `platform_domain_events`,
no ULID id or soft-delete. The composite key is natural: `(tenant_id, employee_id, business_date, humbee_outlet_id)`.

Enables accurate distinct-outlet counts (not additive across day rows) and outlet-specific KPIs.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.db import Base


class FactEmployeeOutletDay(Base):
    __tablename__ = "fact_employee_outlet_day"
    __table_args__ = (
        Index(
            "ix_fact_employee_outlet_day_key",
            "tenant_id",
            "employee_id",
            "business_date",
        ),
        Index(
            "ix_fact_employee_outlet_day_outlet",
            "tenant_id",
            "humbee_outlet_id",
            "business_date",
        ),
        Index(
            "ix_feod_district",
            "tenant_id",
            "business_date",
            "humbee_district_id",
        ),
    )

    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    employee_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    business_date: Mapped[date] = mapped_column(primary_key=True)
    humbee_outlet_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    humbee_district_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    visits_physical: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    visits_telephonic: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_scheduled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    orders_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    net_value_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    lines_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

"""`routes_combined_visits` — manager/sales-person joint visit tracking. database-design.md §8.

`beat_id` is a logical pointer into `beats`.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import CheckConstraint, Date, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class RouteCombinedVisit(Base, ConventionsMixin):
    __tablename__ = "routes_combined_visits"
    __table_args__ = (
        Index(
            "ix_routes_combined_sp",
            "tenant_id",
            "sales_person_employee_id",
            "scheduled_business_date",
        ),
        Index(
            "ix_routes_combined_manager",
            "tenant_id",
            "manager_employee_id",
            "scheduled_business_date",
        ),
        CheckConstraint(
            "state IN ('scheduled','completed','feedback_pending','feedback_submitted','cancelled')",
            name="state_chk",
        ),
        CheckConstraint(
            "manager_employee_id <> sales_person_employee_id", name="distinct_chk"
        ),
    )

    manager_employee_id: Mapped[str] = mapped_column(String(26), nullable=False)
    sales_person_employee_id: Mapped[str] = mapped_column(String(26), nullable=False)
    beat_id: Mapped[str] = mapped_column(String(26), nullable=False)  # logical -> beats
    humbee_outlet_id: Mapped[str] = mapped_column(String(64), nullable=False)
    scheduled_business_date: Mapped[date] = mapped_column(Date, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    visit_id: Mapped[str | None] = mapped_column(String(26), nullable=True)

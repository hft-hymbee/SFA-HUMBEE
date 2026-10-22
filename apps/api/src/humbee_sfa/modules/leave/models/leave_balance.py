"""`leave_balances` — per-employee, per-type, per-year entitlement ledger."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import CheckConstraint, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base
from humbee_sfa.modules.leave.leave_type import LEAVE_TYPE_VALUES_SQL


class LeaveBalance(Base, ConventionsMixin):
    __tablename__ = "leave_balances"
    __table_args__ = (
        Index(
            "uq_leave_balances",
            "tenant_id",
            "employee_id",
            "leave_type",
            "period_year",
            unique=True,
        ),
        CheckConstraint(
            f"leave_type IN ('{LEAVE_TYPE_VALUES_SQL}')", name="leave_balances_type_chk"
        ),
        CheckConstraint(
            "entitled_days >= 0 AND consumed_days >= 0 AND pending_days >= 0",
            name="leave_balances_nonneg_chk",
        ),
    )

    employee_id: Mapped[str] = mapped_column(String(26), nullable=False)
    leave_type: Mapped[str] = mapped_column(String(16), nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)  # calendar year (Jan-Dec)
    entitled_days: Mapped[Decimal] = mapped_column(Numeric(4, 1), nullable=False)
    consumed_days: Mapped[Decimal] = mapped_column(Numeric(4, 1), nullable=False, default=0)
    pending_days: Mapped[Decimal] = mapped_column(Numeric(4, 1), nullable=False, default=0)

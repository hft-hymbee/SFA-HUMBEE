"""`leave_requests` — the leave-application record. database-design.md §11.1.

The exclusion constraint is the `is_on_leave()` oracle: it prevents overlapping live/granted leave
for the same employee at the database level rather than a check-then-insert race in the service.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Numeric,
    String,
    Text,
    func,
    literal_column,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base
from humbee_sfa.modules.leave.leave_type import LEAVE_TYPE_VALUES_SQL


class LeaveRequest(Base, ConventionsMixin):
    __tablename__ = "leave_requests"
    __table_args__ = (
        Index("uq_leave_approval_request", "approval_request_id", unique=True),
        Index("ix_leave_mine", "tenant_id", "employee_id", text("from_date DESC")),
        # Granted-leave availability reads for attendance and route planning.
        Index(
            "ix_leave_on_leave_oracle",
            "tenant_id",
            "employee_id",
            "from_date",
            "to_date",
            postgresql_where=text("status IN ('approved','auto_approved')"),
        ),
        CheckConstraint(f"leave_type IN ('{LEAVE_TYPE_VALUES_SQL}')", name="leave_type_chk"),
        CheckConstraint(
            "status IN "
            "('pending','approved','approved_with_edits','auto_approved','rejected','withdrawn','expired')",
            name="leave_status_chk",
        ),
        CheckConstraint("to_date >= from_date", name="leave_date_order_chk"),
        CheckConstraint("day_count > 0", name="leave_day_count_chk"),
        CheckConstraint("NOT is_half_day OR from_date = to_date", name="leave_half_day_chk"),
        # R-LV-08: no overlapping live or granted leave for the same employee. Columns are
        # referenced via literal_column, not LeaveRequest.from_date/.to_date, because __table_args__
        # is evaluated while this class body is still executing — the class object doesn't exist
        # yet to attribute-access into. literal_column emits the bare column name, which is all
        # `daterange()` needs; the requires btree_gist extension (database-design.md §2.7).
        ExcludeConstraint(
            ("tenant_id", "="),
            ("employee_id", "="),
            (func.daterange(literal_column("from_date"), literal_column("to_date"), text("'[]'")), "&&"),
            name="leave_no_overlap_excl",
            using="gist",
            where=text("status IN ('pending','approved','auto_approved')"),
        ),
    )

    employee_id: Mapped[str] = mapped_column(String(26), nullable=False)
    leave_type: Mapped[str] = mapped_column(String(16), nullable=False)
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date] = mapped_column(Date, nullable=False)
    day_count: Mapped[Decimal] = mapped_column(Numeric(4, 1), nullable=False)
    is_half_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # mirrored from M06, never independent
    approval_request_id: Mapped[str] = mapped_column(String(26), nullable=False)  # logical → approvals_requests
    balance_before: Mapped[Decimal] = mapped_column(Numeric(4, 1), nullable=False)
    balance_after_projected: Mapped[Decimal] = mapped_column(Numeric(4, 1), nullable=False)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    applied_business_date: Mapped[date] = mapped_column(Date, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)

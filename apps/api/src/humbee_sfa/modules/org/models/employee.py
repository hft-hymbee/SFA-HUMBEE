"""`org_employees` — the employee master. database-design.md §4, §3 reconciliation item 1.

Moved here from `identity` (was `identity_employees`) per §3 item 1: identity reads employees
through `org.service`, never its own model.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base
from humbee_sfa.core.pg_types import LtreeType


class Employee(Base, ConventionsMixin):
    __tablename__ = "org_employees"
    __table_args__ = (
        UniqueConstraint("tenant_id", "phone_e164_hmac", name="uq_org_employees_tenant_phone"),
        UniqueConstraint("tenant_id", "employee_code", name="uq_org_employees_tenant_code"),
        Index("ix_org_employees_manager", "tenant_id", "manager_employee_id"),
        Index(
            "ix_org_employees_role",
            "tenant_id",
            "role_code",
            postgresql_where=text("status = 'active'"),
        ),
        CheckConstraint("role_code IN ('sales_person','manager','admin')", name="role_chk"),
        CheckConstraint("status IN ('active','inactive')", name="status_chk"),
        CheckConstraint("manager_employee_id <> id", name="no_self_parent_chk"),
        # An Admin is a permission level, not a position in the reporting line
        # (`org.scope.HIERARCHY_ROLES`), so it never carries a parent.
        CheckConstraint(
            "role_code <> 'admin' OR manager_employee_id IS NULL", name="admin_has_no_parent_chk"
        ),
        # Designation is a job-title axis, separate from role_code (permission/hierarchy), used
        # for employee-report filtering — but each role only carries its own designations.
        CheckConstraint(
            "(role_code = 'admin' AND designation_code = 'admin') "
            "OR (role_code = 'manager' AND designation_code IN "
            "('national_sales_head','segment_business_head','regional_sales_manager','area_sales_manager')) "
            "OR (role_code = 'sales_person' AND designation_code IN "
            "('network_officer_salesperson','territory_development_officer_salesperson'))",
            name="designation_role_chk",
        ),
    )

    employee_code: Mapped[str] = mapped_column(String(64), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    display_initials: Mapped[str] = mapped_column(String(3), nullable=False)
    role_code: Mapped[str] = mapped_column(String(32), nullable=False)
    designation_code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active", server_default=text("'active'")
    )
    login_enabled: Mapped[bool] = mapped_column(
        nullable=False, default=True, server_default=text("true")
    )
    manager_employee_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("org_employees.id", name="fk_org_employees_manager"), nullable=True
    )
    joined_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    # ltree — display/debugging path only, never an authorisation input (§2.2).
    hierarchy_path: Mapped[str | None] = mapped_column(LtreeType(), nullable=True)
    phone_e164_hmac: Mapped[str] = mapped_column(CHAR(64), nullable=False)  # see §17.3
    phone_e164_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    phone_last4: Mapped[str] = mapped_column(CHAR(4), nullable=False)
    geo_scope_id: Mapped[str | None] = mapped_column(String(26), nullable=True)  # logical → org_geography_scope_assignments

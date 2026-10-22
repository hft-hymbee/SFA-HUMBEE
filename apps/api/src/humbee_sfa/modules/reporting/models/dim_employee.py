"""`dim_employee` — SCD type 2 employee dimension. database-design.md §13.

Exempt from `ConventionsMixin` (§2.4 rule 2, §13 header): this whole module is derived and
droppable, the durable truth is `platform_domain_events`. No ULID `id`, no actor columns, no
soft-delete — the surrogate key is `employee_key` (identity bigint), and history is modelled via
`valid_from`/`valid_to` rather than an `is_active`/timestamp convention column set.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Identity,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.db import Base
from humbee_sfa.core.pg_types import LtreeType


class DimEmployee(Base):
    __tablename__ = "dim_employee"
    __table_args__ = (
        # Rendered name via Base's naming_convention: ck_dim_employee_window_chk (matches the
        # DDL's `dim_employee_window_chk`, same short-suffix convention as org_employees' checks).
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="window_chk",
        ),
        Index(
            "uq_dim_employee_current",
            "tenant_id",
            "employee_id",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
        Index(
            "ix_dim_employee_natural",
            "tenant_id",
            "employee_id",
            text("valid_from DESC"),
        ),
        Index("ix_dim_employee_path", "hierarchy_path", postgresql_using="gist"),
    )

    employee_key: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    employee_id: Mapped[str] = mapped_column(String(26), nullable=False)
    employee_code: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    short_name: Mapped[str] = mapped_column(Text, nullable=False)
    initials: Mapped[str] = mapped_column(String(3), nullable=False)
    role_code: Mapped[str] = mapped_column(String(32), nullable=False)
    manager_employee_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    hierarchy_path: Mapped[str | None] = mapped_column(LtreeType(), nullable=True)
    humbee_region_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    region_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    zone_clusters: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'")
    )
    state_clusters: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'")
    )
    district_clusters: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'")
    )
    shop_categories: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'")
    )
    beat_area_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

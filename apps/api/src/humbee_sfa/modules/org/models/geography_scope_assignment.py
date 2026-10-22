"""`org_geography_scope_assignments`. database-design.md §4, §3 reconciliation item 5.

Cluster-id columns are `text[]` + GIN (not JSON) so "which employees cover district X" is a
reverse lookup, not a table scan.

`geo_labels` snapshots `{id, name}` for every zone/state/district in this assignment at the
moment it was picked — district entries also carry `state_id`/`state_name`, since district names
are not unique across states. The four master cache tables that used to let a stored id resolve
back to a label are retired, so this is the only place a label can still come from later.

No shop-category or outlet-count columns: G-2/G-3/G-4 (SFA-API-Contract v2.2) carry neither a
category taxonomy nor a district outlet count.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class GeographyScopeAssignment(Base, ConventionsMixin):
    __tablename__ = "org_geography_scope_assignments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "employee_id", name="uq_org_geo_scope_employee"),
        Index("ix_org_geo_scope_districts_gin", "district_cluster_ids", postgresql_using="gin"),
        CheckConstraint("cardinality(district_cluster_ids) >= 1", name="districts_chk"),  # R-ORG-30
    )

    employee_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("org_employees.id", name="fk_org_geo_scope_employee"), nullable=False
    )
    zone_cluster_ids: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'::text[]")
    )
    state_cluster_ids: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'::text[]")
    )
    district_cluster_ids: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'::text[]")
    )
    geo_labels: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    assigned_by: Mapped[str] = mapped_column(
        String(26), ForeignKey("org_employees.id", name="fk_org_geo_scope_assigner"), nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

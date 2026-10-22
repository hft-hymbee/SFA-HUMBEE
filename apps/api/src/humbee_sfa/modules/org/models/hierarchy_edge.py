"""`org_hierarchy_edges` — the closure table.

Carries the self-row (x, x, 0) for every employee. No upper bound on `depth` — the ≤5-level cap
was removed 2026-08-21 for multi-tenant SaaS.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class HierarchyEdge(Base, ConventionsMixin):
    __tablename__ = "org_hierarchy_edges"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "ancestor_employee_id",
            "descendant_employee_id",
            name="uq_org_hierarchy_edges",
        ),
        Index("ix_org_hierarchy_edges_descendant", "tenant_id", "descendant_employee_id", "depth"),
        Index("ix_org_hierarchy_edges_tree", "tenant_id", "ancestor_employee_id", "depth"),
        CheckConstraint("depth >= 0", name="depth_chk"),  # no upper bound, see module docstring
    )

    ancestor_employee_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("org_employees.id", name="fk_org_hierarchy_ancestor"), nullable=False
    )
    descendant_employee_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("org_employees.id", name="fk_org_hierarchy_descendant"),
        nullable=False,
    )
    depth: Mapped[int] = mapped_column(Integer, nullable=False)

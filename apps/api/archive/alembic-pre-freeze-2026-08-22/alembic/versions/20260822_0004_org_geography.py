"""Complete Org ownership and geography constraints.

Revision ID: 20260822_0004
Revises: 20260822_0003
Create Date: 2026-08-22 00:04:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260822_0004"
down_revision = "20260822_0003"
branch_labels = None
depends_on = None


def _replace_unique_constraint(table_name: str, old_name: str, new_name: str) -> None:
    op.drop_constraint(old_name, table_name, type_="unique")
    op.create_unique_constraint(new_name, table_name, ["tenant_id", "external_id"])


def upgrade() -> None:
    op.alter_column(
        "org_employees",
        "status",
        existing_type=sa.String(16),
        server_default=sa.text("'active'"),
    )
    op.alter_column(
        "org_employees",
        "login_enabled",
        existing_type=sa.Boolean(),
        server_default=sa.text("true"),
    )
    op.create_foreign_key(
        "fk_org_employees_manager",
        "org_employees",
        "org_employees",
        ["manager_employee_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_org_hierarchy_ancestor",
        "org_hierarchy_edges",
        "org_employees",
        ["ancestor_employee_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_org_hierarchy_descendant",
        "org_hierarchy_edges",
        "org_employees",
        ["descendant_employee_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_org_geo_scope_employee",
        "org_geography_scope_assignments",
        "org_employees",
        ["employee_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_org_geo_scope_assigner",
        "org_geography_scope_assignments",
        "org_employees",
        ["assigned_by"],
        ["id"],
    )

    _replace_unique_constraint(
        "org_zone_clusters",
        "uq_org_zone_clusters_tenant_external",
        "uq_org_zone_clusters",
    )
    _replace_unique_constraint(
        "org_state_clusters",
        "uq_org_state_clusters_tenant_external",
        "uq_org_state_clusters",
    )
    op.alter_column(
        "org_state_clusters",
        "zone_external_id",
        existing_type=sa.String(64),
        nullable=False,
    )
    op.drop_index(
        "ix_org_state_clusters_zone_external_id",
        table_name="org_state_clusters",
    )
    op.create_index(
        "ix_org_state_clusters_zone",
        "org_state_clusters",
        ["tenant_id", "zone_external_id"],
    )

    _replace_unique_constraint(
        "org_district_clusters",
        "uq_org_district_clusters_tenant_external",
        "uq_org_district_clusters",
    )
    op.alter_column(
        "org_district_clusters",
        "state_external_id",
        existing_type=sa.String(64),
        nullable=False,
    )
    op.drop_index(
        "ix_org_district_clusters_state_external_id",
        table_name="org_district_clusters",
    )
    op.create_index(
        "ix_org_district_clusters_state",
        "org_district_clusters",
        ["tenant_id", "state_external_id"],
    )

    _replace_unique_constraint(
        "org_shop_categories",
        "uq_org_shop_categories_tenant_external",
        "uq_org_shop_categories",
    )


def downgrade() -> None:
    _replace_unique_constraint(
        "org_shop_categories",
        "uq_org_shop_categories",
        "uq_org_shop_categories_tenant_external",
    )

    op.drop_index(
        "ix_org_district_clusters_state",
        table_name="org_district_clusters",
    )
    op.create_index(
        "ix_org_district_clusters_state_external_id",
        "org_district_clusters",
        ["state_external_id"],
    )
    op.alter_column(
        "org_district_clusters",
        "state_external_id",
        existing_type=sa.String(64),
        nullable=True,
    )
    _replace_unique_constraint(
        "org_district_clusters",
        "uq_org_district_clusters",
        "uq_org_district_clusters_tenant_external",
    )

    op.drop_index("ix_org_state_clusters_zone", table_name="org_state_clusters")
    op.create_index(
        "ix_org_state_clusters_zone_external_id",
        "org_state_clusters",
        ["zone_external_id"],
    )
    op.alter_column(
        "org_state_clusters",
        "zone_external_id",
        existing_type=sa.String(64),
        nullable=True,
    )
    _replace_unique_constraint(
        "org_state_clusters",
        "uq_org_state_clusters",
        "uq_org_state_clusters_tenant_external",
    )
    _replace_unique_constraint(
        "org_zone_clusters",
        "uq_org_zone_clusters",
        "uq_org_zone_clusters_tenant_external",
    )

    op.drop_constraint(
        "fk_org_geo_scope_assigner",
        "org_geography_scope_assignments",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_org_geo_scope_employee",
        "org_geography_scope_assignments",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_org_hierarchy_descendant",
        "org_hierarchy_edges",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_org_hierarchy_ancestor",
        "org_hierarchy_edges",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_org_employees_manager",
        "org_employees",
        type_="foreignkey",
    )
    op.alter_column(
        "org_employees",
        "login_enabled",
        existing_type=sa.Boolean(),
        server_default=None,
    )
    op.alter_column(
        "org_employees",
        "status",
        existing_type=sa.String(16),
        server_default=None,
    )

"""Reconcile the shipped baseline with canonical platform, Identity, and Org models.

Revision ID: 20260822_0002
Revises: 20260822_0001
Create Date: 2026-08-22 00:02:00
"""

from __future__ import annotations

from collections.abc import Iterable

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from humbee_sfa.core.pg_types import LtreeType
from humbee_sfa.core.security import encrypt_phone, hmac_phone

# revision identifiers, used by Alembic.
revision = "20260822_0002"
down_revision = "20260822_0001"
branch_labels = None
depends_on = None

_PLATFORM_JSON_COLUMNS = (
    ("platform_domain_events", "payload"),
    ("platform_outbox_entries", "payload"),
    ("platform_audit_logs", "change_payload"),
    ("platform_idempotency_records", "response_payload"),
    ("platform_form_definitions", "schema_payload"),
    ("platform_form_responses", "response_payload"),
    ("platform_runtime_configs", "config_value"),
    ("platform_feature_flags", "rollout_rules"),
)
_SCOPE_ARRAY_COLUMNS = (
    "zone_cluster_ids",
    "state_cluster_ids",
    "district_cluster_ids",
    "shop_category_ids",
)


def _alter_json_columns(target_type: sa.types.TypeEngine, using_type: str) -> None:
    for table_name, column_name in _PLATFORM_JSON_COLUMNS:
        op.alter_column(
            table_name,
            column_name,
            type_=target_type,
            postgresql_using=f"{column_name}::{using_type}",
        )


def _employee_identity(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split()
    first_name = parts[0] if parts else "Employee"
    initials = "".join(part[0] for part in parts[:3]).upper() or "E"
    return first_name[:120], initials[:3]


def _backfill_employee_pii() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, phone_e164, full_name, login_enabled "
            "FROM org_employees FOR UPDATE"
        )
    ).mappings()
    update = sa.text(
        "UPDATE org_employees SET "
        "phone_e164_hmac = :phone_hmac, phone_e164_enc = :phone_enc, "
        "phone_last4 = :phone_last4, first_name = :first_name, "
        "display_initials = :initials, status = :status "
        "WHERE id = :employee_id"
    )
    for row in rows:
        phone = row["phone_e164"]
        first_name, initials = _employee_identity(row["full_name"])
        bind.execute(
            update,
            {
                "employee_id": row["id"],
                "phone_hmac": hmac_phone(phone),
                "phone_enc": encrypt_phone(phone),
                "phone_last4": phone[-4:],
                "first_name": first_name,
                "initials": initials,
                "status": "active" if row["login_enabled"] else "inactive",
            },
        )


def _backfill_otp_identity() -> None:
    bind = op.get_bind()
    employee_by_phone = {
        row["phone_e164_hmac"]: row["id"]
        for row in bind.execute(
            sa.text("SELECT id, phone_e164_hmac FROM org_employees")
        ).mappings()
    }
    rows = bind.execute(
        sa.text(
            "SELECT id, phone_e164, created_at FROM identity_otp_challenges FOR UPDATE"
        )
    ).mappings()
    update = sa.text(
        "UPDATE identity_otp_challenges SET "
        "phone_e164_hmac = :phone_hmac, employee_id = :employee_id, "
        "issued_at = :issued_at WHERE id = :challenge_id"
    )
    for row in rows:
        phone_hash = hmac_phone(row["phone_e164"])
        bind.execute(
            update,
            {
                "challenge_id": row["id"],
                "phone_hmac": phone_hash,
                "employee_id": employee_by_phone.get(phone_hash),
                "issued_at": row["created_at"],
            },
        )


def _replace_scope_json_with_arrays() -> None:
    for column_name in _SCOPE_ARRAY_COLUMNS:
        temporary = f"{column_name}_array"
        op.add_column(
            "org_geography_scope_assignments",
            sa.Column(
                temporary,
                postgresql.ARRAY(sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::text[]"),
            ),
        )
        op.execute(
            sa.text(
                f"UPDATE org_geography_scope_assignments "
                f"SET {temporary} = ARRAY("
                f"SELECT json_array_elements_text({column_name})"
                f")"
            )
        )
        op.drop_column("org_geography_scope_assignments", column_name)
        op.alter_column(
            "org_geography_scope_assignments",
            temporary,
            new_column_name=column_name,
        )


def _add_cluster_freshness(table_names: Iterable[str]) -> None:
    for table_name in table_names:
        op.add_column(
            table_name,
            sa.Column(
                "as_of",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
        op.add_column(
            table_name,
            sa.Column(
                "expires_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
        op.add_column(table_name, sa.Column("source_version", sa.String(64), nullable=True))
        op.alter_column(table_name, "as_of", server_default=None)
        op.alter_column(table_name, "expires_at", server_default=None)


def upgrade() -> None:
    _alter_json_columns(postgresql.JSONB(), "jsonb")

    op.add_column(
        "platform_domain_events",
        sa.Column(
            "stream",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'identity'"),
        ),
    )
    op.add_column(
        "platform_domain_events",
        sa.Column("partition", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "platform_domain_events",
        sa.Column("event_seq", sa.BigInteger(), sa.Identity(always=True), nullable=False),
    )
    op.alter_column("platform_domain_events", "stream", server_default=None)
    op.create_unique_constraint(
        "uq_platform_domain_events_seq",
        "platform_domain_events",
        ["stream", "partition", "event_seq"],
    )
    op.create_index(
        "ix_platform_domain_events_replay",
        "platform_domain_events",
        ["stream", "partition", "event_seq"],
        postgresql_include=["aggregate_id", "business_date"],
    )

    op.rename_table("identity_employees", "org_employees")
    op.drop_constraint(
        "uq_identity_employees_tenant_phone", "org_employees", type_="unique"
    )
    for index_name in (
        "ix_identity_employees_tenant_id",
        "ix_identity_employees_employee_code",
        "ix_identity_employees_role_code",
        "ix_identity_employees_manager_employee_id",
    ):
        op.drop_index(index_name, table_name="org_employees")
    op.add_column("org_employees", sa.Column("first_name", sa.String(120), nullable=True))
    op.add_column("org_employees", sa.Column("display_initials", sa.String(3), nullable=True))
    op.add_column(
        "org_employees",
        sa.Column(
            "status",
            sa.String(16),
            nullable=True,
            server_default=sa.text("'active'"),
        ),
    )
    op.add_column("org_employees", sa.Column("joined_on", sa.Date(), nullable=True))
    op.add_column("org_employees", sa.Column("hierarchy_path", LtreeType(), nullable=True))
    op.add_column("org_employees", sa.Column("phone_e164_hmac", sa.CHAR(64), nullable=True))
    op.add_column("org_employees", sa.Column("phone_e164_enc", sa.LargeBinary(), nullable=True))
    op.add_column("org_employees", sa.Column("phone_last4", sa.CHAR(4), nullable=True))
    op.add_column("org_employees", sa.Column("geo_scope_id", sa.String(26), nullable=True))
    _backfill_employee_pii()
    for column_name in (
        "first_name",
        "display_initials",
        "status",
        "phone_e164_hmac",
        "phone_e164_enc",
        "phone_last4",
    ):
        op.alter_column("org_employees", column_name, nullable=False)
    op.alter_column("org_employees", "status", server_default=None)
    op.alter_column(
        "org_employees",
        "role_code",
        existing_type=sa.String(64),
        type_=sa.String(32),
    )
    op.drop_column("org_employees", "phone_e164")
    op.create_unique_constraint(
        "uq_org_employees_tenant_phone",
        "org_employees",
        ["tenant_id", "phone_e164_hmac"],
    )
    op.create_unique_constraint(
        "uq_org_employees_tenant_code",
        "org_employees",
        ["tenant_id", "employee_code"],
    )
    op.create_check_constraint(
        "role_chk",
        "org_employees",
        "role_code IN ('sales_person','manager','admin')",
    )
    op.create_check_constraint(
        "status_chk",
        "org_employees",
        "status IN ('active','inactive')",
    )
    op.create_check_constraint(
        "no_self_parent_chk",
        "org_employees",
        "manager_employee_id <> id",
    )
    op.create_index("ix_org_employees_tenant_id", "org_employees", ["tenant_id"])
    op.create_index(
        "ix_org_employees_manager",
        "org_employees",
        ["tenant_id", "manager_employee_id"],
    )
    op.create_index(
        "ix_org_employees_role",
        "org_employees",
        ["tenant_id", "role_code"],
        postgresql_where=sa.text("status = 'active'"),
    )

    op.drop_constraint("depth_gte_zero", "org_hierarchy_edges", type_="check")
    op.drop_constraint("depth_lte_five", "org_hierarchy_edges", type_="check")
    op.drop_constraint(
        "uq_org_hierarchy_edges_tenant_ancestor_descendant",
        "org_hierarchy_edges",
        type_="unique",
    )
    op.drop_index(
        "ix_org_hierarchy_edges_ancestor_employee_id",
        table_name="org_hierarchy_edges",
    )
    op.drop_index(
        "ix_org_hierarchy_edges_descendant_employee_id",
        table_name="org_hierarchy_edges",
    )
    op.create_check_constraint("depth_chk", "org_hierarchy_edges", "depth >= 0")
    op.create_unique_constraint(
        "uq_org_hierarchy_edges",
        "org_hierarchy_edges",
        ["tenant_id", "ancestor_employee_id", "descendant_employee_id"],
    )
    op.create_index(
        "ix_org_hierarchy_edges_descendant",
        "org_hierarchy_edges",
        ["tenant_id", "descendant_employee_id", "depth"],
    )
    op.create_index(
        "ix_org_hierarchy_edges_tree",
        "org_hierarchy_edges",
        ["tenant_id", "ancestor_employee_id", "depth"],
    )

    _replace_scope_json_with_arrays()
    op.drop_constraint(
        "uq_org_geography_scope_tenant_employee",
        "org_geography_scope_assignments",
        type_="unique",
    )
    op.add_column(
        "org_geography_scope_assignments",
        sa.Column(
            "outlet_count_cached",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "org_geography_scope_assignments",
        sa.Column("outlet_count_as_of", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "org_geography_scope_assignments",
        sa.Column("assigned_by", sa.String(26), nullable=True),
    )
    op.add_column(
        "org_geography_scope_assignments",
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE org_geography_scope_assignments "
        "SET assigned_by = employee_id, assigned_at = updated_at"
    )
    op.alter_column("org_geography_scope_assignments", "assigned_by", nullable=False)
    op.alter_column("org_geography_scope_assignments", "assigned_at", nullable=False)
    op.create_unique_constraint(
        "uq_org_geo_scope_employee",
        "org_geography_scope_assignments",
        ["tenant_id", "employee_id"],
    )
    op.create_check_constraint(
        "districts_chk",
        "org_geography_scope_assignments",
        "cardinality(district_cluster_ids) >= 1",
    )
    op.create_check_constraint(
        "outlet_count_chk",
        "org_geography_scope_assignments",
        "outlet_count_cached >= 0",
    )
    op.create_index(
        "ix_org_geo_scope_districts_gin",
        "org_geography_scope_assignments",
        ["district_cluster_ids"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_org_geo_scope_cats_gin",
        "org_geography_scope_assignments",
        ["shop_category_ids"],
        postgresql_using="gin",
    )

    cluster_tables = (
        "org_zone_clusters",
        "org_state_clusters",
        "org_district_clusters",
        "org_shop_categories",
    )
    _add_cluster_freshness(cluster_tables)
    op.add_column(
        "org_district_clusters",
        sa.Column(
            "outlet_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "org_shop_categories",
        sa.Column("share_of_outlets", sa.Numeric(4, 3), nullable=True),
    )

    op.drop_index(
        "ix_identity_otp_challenges_phone_e164",
        table_name="identity_otp_challenges",
    )
    op.alter_column(
        "identity_otp_challenges",
        "otp_hash",
        new_column_name="code_hash",
    )
    op.add_column(
        "identity_otp_challenges",
        sa.Column("phone_e164_hmac", sa.CHAR(64), nullable=True),
    )
    op.add_column(
        "identity_otp_challenges",
        sa.Column("employee_id", sa.String(26), nullable=True),
    )
    op.add_column(
        "identity_otp_challenges",
        sa.Column(
            "purpose",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'login'"),
        ),
    )
    op.add_column(
        "identity_otp_challenges",
        sa.Column(
            "code_length",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("6"),
        ),
    )
    op.add_column(
        "identity_otp_challenges",
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "identity_otp_challenges",
        sa.Column("requester_ip", postgresql.INET(), nullable=True),
    )
    _backfill_otp_identity()
    op.alter_column("identity_otp_challenges", "phone_e164_hmac", nullable=False)
    op.alter_column("identity_otp_challenges", "issued_at", nullable=False)
    op.alter_column("identity_otp_challenges", "purpose", server_default=None)
    op.drop_column("identity_otp_challenges", "phone_e164")
    op.create_check_constraint(
        "purpose_chk",
        "identity_otp_challenges",
        "purpose IN ('login','reauth')",
    )
    op.create_check_constraint(
        "attempts_chk",
        "identity_otp_challenges",
        "attempts_used BETWEEN 0 AND max_attempts",
    )
    op.create_check_constraint(
        "expiry_chk",
        "identity_otp_challenges",
        "expires_at > issued_at",
    )
    op.create_index(
        "ix_identity_otp_phone",
        "identity_otp_challenges",
        ["tenant_id", "phone_e164_hmac", "issued_at"],
    )
    op.create_index(
        "uq_identity_otp_live",
        "identity_otp_challenges",
        ["tenant_id", "phone_e164_hmac", "purpose"],
        unique=True,
        postgresql_where=sa.text("consumed_at IS NULL"),
    )

    op.drop_column("identity_sessions", "access_token_hash")
    op.alter_column(
        "identity_sessions",
        "expires_at",
        new_column_name="refresh_token_expires_at",
    )
    op.add_column(
        "identity_sessions",
        sa.Column("access_token_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE identity_sessions "
        "SET access_token_expires_at = refresh_token_expires_at"
    )
    op.alter_column("identity_sessions", "access_token_expires_at", nullable=False)
    op.add_column(
        "identity_sessions",
        sa.Column("revocation_reason", sa.String(32), nullable=True),
    )
    op.execute(
        "UPDATE identity_sessions SET revocation_reason = 'admin_revoke' "
        "WHERE revoked_at IS NOT NULL"
    )
    op.create_unique_constraint(
        "uq_identity_sessions_refresh",
        "identity_sessions",
        ["refresh_token_hash"],
    )
    op.create_check_constraint(
        "revocation_chk",
        "identity_sessions",
        "revocation_reason IS NULL OR revocation_reason IN "
        "('user_logout','deactivated','admin_revoke','token_reuse','refresh_expired')",
    )
    op.create_check_constraint(
        "revoked_pair_chk",
        "identity_sessions",
        "(revoked_at IS NULL) = (revocation_reason IS NULL)",
    )
    op.create_index(
        "ix_identity_sessions_live",
        "identity_sessions",
        ["tenant_id", "employee_id"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def _require_empty_identity_data() -> None:
    bind = op.get_bind()
    table_names = (
        "org_employees",
        "identity_otp_challenges",
        "identity_sessions",
    )
    for table_name in table_names:
        count = bind.execute(sa.text(f"SELECT count(*) FROM {table_name}")).scalar_one()
        if count:
            raise RuntimeError(
                "reconcile_baseline downgrade is data-destructive; "
                f"{table_name} must be empty"
            )


def downgrade() -> None:
    _require_empty_identity_data()

    op.drop_index("ix_identity_sessions_live", table_name="identity_sessions")
    op.drop_constraint("revoked_pair_chk", "identity_sessions", type_="check")
    op.drop_constraint("revocation_chk", "identity_sessions", type_="check")
    op.drop_constraint(
        "uq_identity_sessions_refresh", "identity_sessions", type_="unique"
    )
    op.drop_column("identity_sessions", "revocation_reason")
    op.drop_column("identity_sessions", "access_token_expires_at")
    op.alter_column(
        "identity_sessions",
        "refresh_token_expires_at",
        new_column_name="expires_at",
    )
    op.add_column(
        "identity_sessions",
        sa.Column("access_token_hash", sa.String(255), nullable=False),
    )

    op.drop_index("uq_identity_otp_live", table_name="identity_otp_challenges")
    op.drop_index("ix_identity_otp_phone", table_name="identity_otp_challenges")
    op.drop_constraint("expiry_chk", "identity_otp_challenges", type_="check")
    op.drop_constraint("attempts_chk", "identity_otp_challenges", type_="check")
    op.drop_constraint("purpose_chk", "identity_otp_challenges", type_="check")
    op.add_column(
        "identity_otp_challenges",
        sa.Column("phone_e164", sa.String(20), nullable=False),
    )
    for column_name in (
        "requester_ip",
        "issued_at",
        "code_length",
        "purpose",
        "employee_id",
        "phone_e164_hmac",
    ):
        op.drop_column("identity_otp_challenges", column_name)
    op.alter_column(
        "identity_otp_challenges",
        "code_hash",
        new_column_name="otp_hash",
    )
    op.create_index(
        "ix_identity_otp_challenges_phone_e164",
        "identity_otp_challenges",
        ["phone_e164"],
    )

    op.drop_column("org_shop_categories", "share_of_outlets")
    op.drop_column("org_district_clusters", "outlet_count")
    for table_name in (
        "org_shop_categories",
        "org_district_clusters",
        "org_state_clusters",
        "org_zone_clusters",
    ):
        op.drop_column(table_name, "source_version")
        op.drop_column(table_name, "expires_at")
        op.drop_column(table_name, "as_of")

    op.drop_index(
        "ix_org_geo_scope_cats_gin",
        table_name="org_geography_scope_assignments",
    )
    op.drop_index(
        "ix_org_geo_scope_districts_gin",
        table_name="org_geography_scope_assignments",
    )
    op.drop_constraint(
        "outlet_count_chk",
        "org_geography_scope_assignments",
        type_="check",
    )
    op.drop_constraint(
        "districts_chk",
        "org_geography_scope_assignments",
        type_="check",
    )
    op.drop_constraint(
        "uq_org_geo_scope_employee",
        "org_geography_scope_assignments",
        type_="unique",
    )
    for column_name in (
        "assigned_at",
        "assigned_by",
        "outlet_count_as_of",
        "outlet_count_cached",
    ):
        op.drop_column("org_geography_scope_assignments", column_name)
    for column_name in _SCOPE_ARRAY_COLUMNS:
        op.alter_column(
            "org_geography_scope_assignments",
            column_name,
            type_=sa.JSON(),
            postgresql_using=f"to_json({column_name})",
            server_default=None,
        )
    op.create_unique_constraint(
        "uq_org_geography_scope_tenant_employee",
        "org_geography_scope_assignments",
        ["tenant_id", "employee_id"],
    )

    op.drop_index("ix_org_hierarchy_edges_tree", table_name="org_hierarchy_edges")
    op.drop_index(
        "ix_org_hierarchy_edges_descendant",
        table_name="org_hierarchy_edges",
    )
    op.drop_constraint(
        "uq_org_hierarchy_edges", "org_hierarchy_edges", type_="unique"
    )
    op.drop_constraint("depth_chk", "org_hierarchy_edges", type_="check")
    op.create_check_constraint(
        "depth_gte_zero", "org_hierarchy_edges", "depth >= 0"
    )
    op.create_check_constraint(
        "depth_lte_five", "org_hierarchy_edges", "depth <= 5"
    )
    op.create_unique_constraint(
        "uq_org_hierarchy_edges_tenant_ancestor_descendant",
        "org_hierarchy_edges",
        ["tenant_id", "ancestor_employee_id", "descendant_employee_id"],
    )
    op.create_index(
        "ix_org_hierarchy_edges_ancestor_employee_id",
        "org_hierarchy_edges",
        ["ancestor_employee_id"],
    )
    op.create_index(
        "ix_org_hierarchy_edges_descendant_employee_id",
        "org_hierarchy_edges",
        ["descendant_employee_id"],
    )

    op.drop_index("ix_org_employees_role", table_name="org_employees")
    op.drop_index("ix_org_employees_manager", table_name="org_employees")
    op.drop_index("ix_org_employees_tenant_id", table_name="org_employees")
    op.drop_constraint("no_self_parent_chk", "org_employees", type_="check")
    op.drop_constraint("status_chk", "org_employees", type_="check")
    op.drop_constraint("role_chk", "org_employees", type_="check")
    op.drop_constraint(
        "uq_org_employees_tenant_code", "org_employees", type_="unique"
    )
    op.drop_constraint(
        "uq_org_employees_tenant_phone", "org_employees", type_="unique"
    )
    op.add_column("org_employees", sa.Column("phone_e164", sa.String(20), nullable=False))
    for column_name in (
        "geo_scope_id",
        "phone_last4",
        "phone_e164_enc",
        "phone_e164_hmac",
        "hierarchy_path",
        "joined_on",
        "status",
        "display_initials",
        "first_name",
    ):
        op.drop_column("org_employees", column_name)
    op.alter_column(
        "org_employees",
        "role_code",
        existing_type=sa.String(32),
        type_=sa.String(64),
    )
    op.create_unique_constraint(
        "uq_identity_employees_tenant_phone",
        "org_employees",
        ["tenant_id", "phone_e164"],
    )
    op.create_index(
        "ix_identity_employees_manager_employee_id",
        "org_employees",
        ["manager_employee_id"],
    )
    op.create_index(
        "ix_identity_employees_role_code", "org_employees", ["role_code"]
    )
    op.create_index(
        "ix_identity_employees_employee_code", "org_employees", ["employee_code"]
    )
    op.create_index(
        "ix_identity_employees_tenant_id", "org_employees", ["tenant_id"]
    )
    op.rename_table("org_employees", "identity_employees")

    op.drop_index(
        "ix_platform_domain_events_replay",
        table_name="platform_domain_events",
    )
    op.drop_constraint(
        "uq_platform_domain_events_seq",
        "platform_domain_events",
        type_="unique",
    )
    op.drop_column("platform_domain_events", "event_seq")
    op.drop_column("platform_domain_events", "partition")
    op.drop_column("platform_domain_events", "stream")
    _alter_json_columns(sa.JSON(), "json")

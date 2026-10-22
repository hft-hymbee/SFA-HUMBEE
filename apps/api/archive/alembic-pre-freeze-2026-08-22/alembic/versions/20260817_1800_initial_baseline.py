"""Initial baseline schema for stories 0.2 and 0.4.

Revision ID: 20260817_1800
Revises:
Create Date: 2026-08-17 18:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260817_1800"
down_revision = None
branch_labels = None
depends_on = None


def _convention_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(length=26), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_by_employee_id", sa.String(length=26), nullable=True),
        sa.Column("on_behalf_of_employee_id", sa.String(length=26), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivated_by", sa.String(length=26), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "platform_domain_events",
        *_convention_columns(),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("aggregate_type", sa.String(length=64), nullable=False),
        sa.Column("aggregate_id", sa.String(length=26), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
    )
    op.create_index(op.f("ix_platform_domain_events_tenant_id"), "platform_domain_events", ["tenant_id"])
    op.create_index(op.f("ix_platform_domain_events_aggregate_id"), "platform_domain_events", ["aggregate_id"])
    op.create_index(op.f("ix_platform_domain_events_business_date"), "platform_domain_events", ["business_date"])

    op.create_table(
        "platform_outbox_entries",
        *_convention_columns(),
        sa.Column("topic", sa.String(length=128), nullable=False),
        sa.Column("partition_key", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    op.create_index(op.f("ix_platform_outbox_entries_tenant_id"), "platform_outbox_entries", ["tenant_id"])
    op.create_index(op.f("ix_platform_outbox_entries_topic"), "platform_outbox_entries", ["topic"])
    op.create_index(op.f("ix_platform_outbox_entries_partition_key"), "platform_outbox_entries", ["partition_key"])

    op.create_table(
        "platform_audit_logs",
        *_convention_columns(),
        sa.Column("entity_type", sa.String(length=128), nullable=False),
        sa.Column("entity_id", sa.String(length=26), nullable=False),
        sa.Column("from_state", sa.String(length=64), nullable=True),
        sa.Column("to_state", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("change_payload", sa.JSON(), nullable=True),
    )
    op.create_index(op.f("ix_platform_audit_logs_tenant_id"), "platform_audit_logs", ["tenant_id"])
    op.create_index(op.f("ix_platform_audit_logs_entity_id"), "platform_audit_logs", ["entity_id"])

    op.create_table(
        "platform_idempotency_records",
        *_convention_columns(),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("response_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_platform_idempotency_tenant_key"),
    )
    op.create_index(
        op.f("ix_platform_idempotency_records_tenant_id"),
        "platform_idempotency_records",
        ["tenant_id"],
    )

    op.create_table(
        "platform_form_definitions",
        *_convention_columns(),
        sa.Column("form_key", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("schema_payload", sa.JSON(), nullable=False),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("tenant_id", "form_key", "version", name="uq_platform_form_definitions_key_version"),
    )
    op.create_index(
        op.f("ix_platform_form_definitions_tenant_id"),
        "platform_form_definitions",
        ["tenant_id"],
    )

    op.create_table(
        "platform_form_responses",
        *_convention_columns(),
        sa.Column("form_definition_id", sa.String(length=26), nullable=False),
        sa.Column("subject_type", sa.String(length=64), nullable=False),
        sa.Column("subject_id", sa.String(length=26), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=False),
    )
    op.create_index(op.f("ix_platform_form_responses_tenant_id"), "platform_form_responses", ["tenant_id"])
    op.create_index(
        op.f("ix_platform_form_responses_form_definition_id"),
        "platform_form_responses",
        ["form_definition_id"],
    )

    op.create_table(
        "platform_rate_limit_counters",
        *_convention_columns(),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("counter_key", sa.String(length=128), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_seconds", sa.Integer(), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "scope",
            "counter_key",
            "window_start",
            name="uq_platform_rate_limits_scope_key_window",
        ),
    )
    op.create_index(
        op.f("ix_platform_rate_limit_counters_tenant_id"),
        "platform_rate_limit_counters",
        ["tenant_id"],
    )

    op.create_table(
        "platform_runtime_configs",
        *_convention_columns(),
        sa.Column("config_key", sa.String(length=128), nullable=False),
        sa.Column("config_value", sa.JSON(), nullable=False),
        sa.Column("config_type", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.UniqueConstraint("tenant_id", "config_key", name="uq_platform_runtime_configs_tenant_key"),
    )
    op.create_index(op.f("ix_platform_runtime_configs_tenant_id"), "platform_runtime_configs", ["tenant_id"])

    op.create_table(
        "platform_feature_flags",
        *_convention_columns(),
        sa.Column("flag_key", sa.String(length=128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("rollout_rules", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("tenant_id", "flag_key", name="uq_platform_feature_flags_tenant_key"),
    )
    op.create_index(op.f("ix_platform_feature_flags_tenant_id"), "platform_feature_flags", ["tenant_id"])

    op.create_table(
        "identity_employees",
        *_convention_columns(),
        sa.Column("employee_code", sa.String(length=64), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("role_code", sa.String(length=64), nullable=False),
        sa.Column("phone_e164", sa.String(length=20), nullable=False),
        sa.Column("manager_employee_id", sa.String(length=26), nullable=True),
        sa.Column("login_enabled", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("tenant_id", "phone_e164", name="uq_identity_employees_tenant_phone"),
    )
    op.create_index(op.f("ix_identity_employees_tenant_id"), "identity_employees", ["tenant_id"])
    op.create_index(op.f("ix_identity_employees_employee_code"), "identity_employees", ["employee_code"])
    op.create_index(op.f("ix_identity_employees_role_code"), "identity_employees", ["role_code"])
    op.create_index(
        op.f("ix_identity_employees_manager_employee_id"),
        "identity_employees",
        ["manager_employee_id"],
    )

    op.create_table(
        "identity_otp_challenges",
        *_convention_columns(),
        sa.Column("phone_e164", sa.String(length=20), nullable=False),
        sa.Column("otp_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resend_available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("attempts_used", sa.Integer(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(op.f("ix_identity_otp_challenges_tenant_id"), "identity_otp_challenges", ["tenant_id"])
    op.create_index(op.f("ix_identity_otp_challenges_phone_e164"), "identity_otp_challenges", ["phone_e164"])

    op.create_table(
        "identity_sessions",
        *_convention_columns(),
        sa.Column("employee_id", sa.String(length=26), nullable=False),
        sa.Column("device_id", sa.String(length=26), nullable=True),
        sa.Column("access_token_hash", sa.String(length=255), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(op.f("ix_identity_sessions_tenant_id"), "identity_sessions", ["tenant_id"])
    op.create_index(op.f("ix_identity_sessions_employee_id"), "identity_sessions", ["employee_id"])
    op.create_index(op.f("ix_identity_sessions_device_id"), "identity_sessions", ["device_id"])

    op.create_table(
        "identity_devices",
        *_convention_columns(),
        sa.Column("employee_id", sa.String(length=26), nullable=False),
        sa.Column("device_fingerprint", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("platform", sa.String(length=64), nullable=False),
        sa.Column("app_version", sa.String(length=64), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "device_fingerprint", name="uq_identity_devices_tenant_fingerprint"),
    )
    op.create_index(op.f("ix_identity_devices_tenant_id"), "identity_devices", ["tenant_id"])
    op.create_index(op.f("ix_identity_devices_employee_id"), "identity_devices", ["employee_id"])

    op.create_table(
        "identity_auth_audit_events",
        *_convention_columns(),
        sa.Column("employee_id", sa.String(length=26), nullable=True),
        sa.Column("phone_e164", sa.String(length=20), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
    )
    op.create_index(op.f("ix_identity_auth_audit_events_tenant_id"), "identity_auth_audit_events", ["tenant_id"])
    op.create_index(
        op.f("ix_identity_auth_audit_events_employee_id"),
        "identity_auth_audit_events",
        ["employee_id"],
    )
    op.create_index(
        op.f("ix_identity_auth_audit_events_phone_e164"),
        "identity_auth_audit_events",
        ["phone_e164"],
    )
    op.create_index(
        op.f("ix_identity_auth_audit_events_business_date"),
        "identity_auth_audit_events",
        ["business_date"],
    )

    op.create_table(
        "org_hierarchy_edges",
        *_convention_columns(),
        sa.Column("ancestor_employee_id", sa.String(length=26), nullable=False),
        sa.Column("descendant_employee_id", sa.String(length=26), nullable=False),
        sa.Column("depth", sa.Integer(), nullable=False),
        sa.CheckConstraint("depth >= 0", name="depth_gte_zero"),
        sa.CheckConstraint("depth <= 5", name="depth_lte_five"),
        sa.UniqueConstraint(
            "tenant_id",
            "ancestor_employee_id",
            "descendant_employee_id",
            name="uq_org_hierarchy_edges_tenant_ancestor_descendant",
        ),
    )
    op.create_index(op.f("ix_org_hierarchy_edges_tenant_id"), "org_hierarchy_edges", ["tenant_id"])
    op.create_index(
        op.f("ix_org_hierarchy_edges_ancestor_employee_id"),
        "org_hierarchy_edges",
        ["ancestor_employee_id"],
    )
    op.create_index(
        op.f("ix_org_hierarchy_edges_descendant_employee_id"),
        "org_hierarchy_edges",
        ["descendant_employee_id"],
    )

    op.create_table(
        "org_geography_scope_assignments",
        *_convention_columns(),
        sa.Column("employee_id", sa.String(length=26), nullable=False),
        sa.Column("zone_cluster_ids", sa.JSON(), nullable=False),
        sa.Column("state_cluster_ids", sa.JSON(), nullable=False),
        sa.Column("district_cluster_ids", sa.JSON(), nullable=False),
        sa.Column("shop_category_ids", sa.JSON(), nullable=False),
        sa.UniqueConstraint("tenant_id", "employee_id", name="uq_org_geography_scope_tenant_employee"),
    )
    op.create_index(
        op.f("ix_org_geography_scope_assignments_tenant_id"),
        "org_geography_scope_assignments",
        ["tenant_id"],
    )
    op.create_index(
        op.f("ix_org_geography_scope_assignments_employee_id"),
        "org_geography_scope_assignments",
        ["employee_id"],
    )

    op.create_table(
        "org_zone_clusters",
        *_convention_columns(),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("tenant_id", "external_id", name="uq_org_zone_clusters_tenant_external"),
    )
    op.create_index(op.f("ix_org_zone_clusters_tenant_id"), "org_zone_clusters", ["tenant_id"])

    op.create_table(
        "org_state_clusters",
        *_convention_columns(),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("zone_external_id", sa.String(length=64), nullable=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("tenant_id", "external_id", name="uq_org_state_clusters_tenant_external"),
    )
    op.create_index(op.f("ix_org_state_clusters_tenant_id"), "org_state_clusters", ["tenant_id"])
    op.create_index(op.f("ix_org_state_clusters_zone_external_id"), "org_state_clusters", ["zone_external_id"])

    op.create_table(
        "org_district_clusters",
        *_convention_columns(),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("state_external_id", sa.String(length=64), nullable=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("tenant_id", "external_id", name="uq_org_district_clusters_tenant_external"),
    )
    op.create_index(op.f("ix_org_district_clusters_tenant_id"), "org_district_clusters", ["tenant_id"])
    op.create_index(
        op.f("ix_org_district_clusters_state_external_id"),
        "org_district_clusters",
        ["state_external_id"],
    )

    op.create_table(
        "org_shop_categories",
        *_convention_columns(),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("tenant_id", "external_id", name="uq_org_shop_categories_tenant_external"),
    )
    op.create_index(op.f("ix_org_shop_categories_tenant_id"), "org_shop_categories", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("org_shop_categories")
    op.drop_table("org_district_clusters")
    op.drop_table("org_state_clusters")
    op.drop_table("org_zone_clusters")
    op.drop_table("org_geography_scope_assignments")
    op.drop_table("org_hierarchy_edges")
    op.drop_table("identity_auth_audit_events")
    op.drop_table("identity_devices")
    op.drop_table("identity_sessions")
    op.drop_table("identity_otp_challenges")
    op.drop_table("identity_employees")
    op.drop_table("platform_feature_flags")
    op.drop_table("platform_runtime_configs")
    op.drop_table("platform_rate_limit_counters")
    op.drop_table("platform_form_responses")
    op.drop_table("platform_form_definitions")
    op.drop_table("platform_idempotency_records")
    op.drop_table("platform_audit_logs")
    op.drop_table("platform_outbox_entries")
    op.drop_table("platform_domain_events")

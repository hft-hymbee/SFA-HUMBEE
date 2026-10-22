"""Add platform delivery, sweep, attachment, and quarantine primitives.

Revision ID: 20260822_0003
Revises: 20260822_0002
Create Date: 2026-08-22 00:03:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260822_0003"
down_revision = "20260822_0002"
branch_labels = None
depends_on = None


def _convention_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(26), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("created_by_employee_id", sa.String(26), nullable=True),
        sa.Column("on_behalf_of_employee_id", sa.String(26), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivated_by", sa.String(26), nullable=True),
    ]


def upgrade() -> None:
    op.add_column(
        "platform_domain_events",
        sa.Column(
            "occurred_at_adjusted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_check_constraint(
        "stream_chk",
        "platform_domain_events",
        "stream IN ('org','identity','attendance','routes','beats','orders',"
        "'approvals','leave','targets','outlets')",
    )
    op.create_index(
        "ix_platform_domain_events_aggregate",
        "platform_domain_events",
        ["aggregate_type", "aggregate_id", "occurred_at"],
    )
    op.alter_column(
        "platform_domain_events",
        "occurred_at_adjusted",
        server_default=None,
    )

    op.add_column(
        "platform_outbox_entries",
        sa.Column("dedupe_key", sa.String(200), nullable=True),
    )
    op.add_column(
        "platform_outbox_entries",
        sa.Column(
            "max_attempts",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("10"),
        ),
    )
    op.create_check_constraint(
        "status_chk",
        "platform_outbox_entries",
        "status IN ('pending','claimed','succeeded','failed','dead_letter')",
    )
    op.create_index(
        "uq_platform_outbox_dedupe",
        "platform_outbox_entries",
        ["tenant_id", "topic", "dedupe_key"],
        unique=True,
        postgresql_where=sa.text("dedupe_key IS NOT NULL"),
    )
    op.create_index(
        "ix_platform_outbox_claim",
        "platform_outbox_entries",
        ["available_at", "id"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "ix_platform_outbox_depth",
        "platform_outbox_entries",
        ["topic"],
        postgresql_where=sa.text("status IN ('pending','claimed')"),
    )
    op.alter_column("platform_outbox_entries", "max_attempts", server_default=None)

    op.drop_constraint(
        "uq_platform_idempotency_tenant_key",
        "platform_idempotency_records",
        type_="unique",
    )
    op.add_column(
        "platform_idempotency_records",
        sa.Column(
            "endpoint",
            sa.String(128),
            nullable=False,
            server_default=sa.text("'legacy'"),
        ),
    )
    op.create_unique_constraint(
        "uq_platform_idempotency",
        "platform_idempotency_records",
        ["tenant_id", "endpoint", "idempotency_key"],
    )
    op.create_index(
        "ix_platform_idempotency_expiry",
        "platform_idempotency_records",
        ["expires_at"],
    )
    op.alter_column("platform_idempotency_records", "endpoint", server_default=None)

    op.create_index(
        "ix_platform_audit_entity",
        "platform_audit_logs",
        ["tenant_id", "entity_type", "entity_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_platform_audit_actor",
        "platform_audit_logs",
        ["tenant_id", "created_by_employee_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "platform_sweep_runs",
        *_convention_columns(),
        sa.Column("sweep_type", sa.String(64), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("rows_affected", sa.Integer(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.UniqueConstraint(
            "tenant_id",
            "sweep_type",
            "business_date",
            name="uq_platform_sweep_run",
        ),
        sa.CheckConstraint(
            "status IN ('running','succeeded','failed','partial')",
            name="status_chk",
        ),
    )
    op.create_index(
        "ix_platform_sweep_runs_tenant_id",
        "platform_sweep_runs",
        ["tenant_id"],
    )

    op.create_table(
        "platform_attachments",
        *_convention_columns(),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("subject_type", sa.String(64), nullable=False),
        sa.Column("subject_id", sa.String(26), nullable=False),
        sa.Column("contains_pii", sa.Boolean(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("object_key", name="uq_platform_attachments_key"),
        sa.CheckConstraint("byte_size > 0", name="size_chk"),
    )
    op.create_index(
        "ix_platform_attachments_tenant_id",
        "platform_attachments",
        ["tenant_id"],
    )
    op.create_index(
        "ix_platform_attachments_subject",
        "platform_attachments",
        ["tenant_id", "subject_type", "subject_id"],
    )

    op.create_table(
        "platform_event_quarantine",
        *_convention_columns(),
        sa.Column("domain_event_id", sa.String(26), nullable=False),
        sa.Column("reason", sa.String(64), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("quarantined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_platform_event_quarantine_tenant_id",
        "platform_event_quarantine",
        ["tenant_id"],
    )
    op.create_index(
        "ix_platform_event_quarantine_open",
        "platform_event_quarantine",
        ["tenant_id", "quarantined_at"],
        postgresql_where=sa.text("released_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("platform_event_quarantine")
    op.drop_table("platform_attachments")
    op.drop_table("platform_sweep_runs")

    op.drop_index("ix_platform_audit_actor", table_name="platform_audit_logs")
    op.drop_index("ix_platform_audit_entity", table_name="platform_audit_logs")

    op.drop_index(
        "ix_platform_idempotency_expiry",
        table_name="platform_idempotency_records",
    )
    op.drop_constraint(
        "uq_platform_idempotency",
        "platform_idempotency_records",
        type_="unique",
    )
    op.drop_column("platform_idempotency_records", "endpoint")
    op.create_unique_constraint(
        "uq_platform_idempotency_tenant_key",
        "platform_idempotency_records",
        ["tenant_id", "idempotency_key"],
    )

    op.drop_index(
        "ix_platform_outbox_depth",
        table_name="platform_outbox_entries",
    )
    op.drop_index(
        "ix_platform_outbox_claim",
        table_name="platform_outbox_entries",
    )
    op.drop_index(
        "uq_platform_outbox_dedupe",
        table_name="platform_outbox_entries",
    )
    op.drop_constraint("status_chk", "platform_outbox_entries", type_="check")
    op.drop_column("platform_outbox_entries", "max_attempts")
    op.drop_column("platform_outbox_entries", "dedupe_key")

    op.drop_index(
        "ix_platform_domain_events_aggregate",
        table_name="platform_domain_events",
    )
    op.drop_constraint("stream_chk", "platform_domain_events", type_="check")
    op.drop_column("platform_domain_events", "occurred_at_adjusted")

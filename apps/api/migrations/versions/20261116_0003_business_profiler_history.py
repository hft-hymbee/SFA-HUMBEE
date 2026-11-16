"""Business profiler history and the reporting columns frozen from it.

Revision ID: 0003_business_profiler_history
Revises: 0002_outlets_business_profiler
Create Date: 2026-11-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_business_profiler_history"
down_revision = "0002_outlets_business_profiler"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outlets_business_profiler_history",
        sa.Column("id", sa.String(26), nullable=False),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("humbee_outlet_id", sa.String(64), nullable=False),
        sa.Column("pct", sa.SmallInteger(), nullable=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("for_business_date", sa.Date(), nullable=True),
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
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivated_by", sa.String(26), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_outlets_business_profiler_history"),
        sa.CheckConstraint(
            "source IN ('push','fetch','day_close')",
            name="ck_outlets_business_profiler_history_source_chk",
        ),
        sa.CheckConstraint(
            "(source = 'day_close') = (for_business_date IS NOT NULL)",
            name="ck_outlets_business_profiler_history_day_close_chk",
        ),
    )
    op.create_index(
        "ix_outlets_business_profiler_history_tenant_id",
        "outlets_business_profiler_history",
        ["tenant_id"],
    )
    op.create_index(
        "ix_outlets_bp_history_lookup",
        "outlets_business_profiler_history",
        ["tenant_id", "humbee_outlet_id", "effective_at"],
    )
    op.create_index(
        "ix_outlets_bp_history_day_close",
        "outlets_business_profiler_history",
        ["tenant_id", "for_business_date"],
    )
    op.add_column(
        "fact_employee_outlet_day", sa.Column("business_profiler_pct", sa.SmallInteger(), nullable=True)
    )
    op.add_column(
        "fact_employee_outlet_day", sa.Column("business_profiler_filled", sa.Boolean(), nullable=True)
    )
    op.add_column(
        "fact_employee_day",
        sa.Column("business_profiler_filled_outlet_count", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("fact_employee_day", "business_profiler_filled_outlet_count")
    op.drop_column("fact_employee_outlet_day", "business_profiler_filled")
    op.drop_column("fact_employee_outlet_day", "business_profiler_pct")
    op.drop_index("ix_outlets_bp_history_day_close", "outlets_business_profiler_history")
    op.drop_index("ix_outlets_bp_history_lookup", "outlets_business_profiler_history")
    op.drop_index("ix_outlets_business_profiler_history_tenant_id", "outlets_business_profiler_history")
    op.drop_table("outlets_business_profiler_history")

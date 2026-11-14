"""Last known business profiler % on the outlet projection.

Revision ID: 0002_outlets_business_profiler
Revises: 0001_baseline
Create Date: 2026-11-15
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_outlets_business_profiler"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("outlets", sa.Column("business_profiler_pct", sa.SmallInteger(), nullable=True))
    op.add_column(
        "outlets", sa.Column("business_profiler_as_of", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("outlets", "business_profiler_as_of")
    op.drop_column("outlets", "business_profiler_pct")

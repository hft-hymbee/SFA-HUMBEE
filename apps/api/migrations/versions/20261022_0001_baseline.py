"""Baseline schema at the first production release.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-22
"""
from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

BASELINE = Path(__file__).resolve().parents[1] / "baseline"


def upgrade() -> None:
    driver = op.get_bind().connection.driver_connection
    driver.execute((BASELINE / "00_extensions.sql").read_text(encoding="utf-8"))
    driver.execute((BASELINE / "01_schema.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    raise NotImplementedError("The baseline cannot be downgraded.")

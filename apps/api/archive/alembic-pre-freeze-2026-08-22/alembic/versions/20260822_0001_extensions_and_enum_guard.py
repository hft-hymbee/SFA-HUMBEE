"""Install database extensions required by the canonical schema.

Revision ID: 20260822_0001
Revises: 20260817_1800
Create Date: 2026-08-22 00:01:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260822_0001"
down_revision = "20260817_1800"
branch_labels = None
depends_on = None

_REQUIRED_EXTENSIONS = ("postgis", "btree_gist", "ltree", "pgcrypto")


def upgrade() -> None:
    for extension in _REQUIRED_EXTENSIONS:
        op.execute(f'CREATE EXTENSION IF NOT EXISTS "{extension}"')


def downgrade() -> None:
    # Extensions can be shared with schemas outside this application. Removing them during an
    # application rollback could destroy unrelated objects, so downgrade intentionally preserves
    # these database-level capabilities.
    pass

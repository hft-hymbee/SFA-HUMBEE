"""`platform_feature_flags`. §3 reconciliation item 3 (JSON → JSONB). Not detailed in
database-design.md's numbered sections; scope is set by epic Story 0.2.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class FeatureFlag(Base, ConventionsMixin):
    __tablename__ = "platform_feature_flags"
    __table_args__ = (UniqueConstraint("tenant_id", "flag_key", name="uq_platform_feature_flags_tenant_key"),)

    flag_key: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rollout_rules: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

from __future__ import annotations

from typing import Any

from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class RuntimeConfig(Base, ConventionsMixin):
    __tablename__ = "platform_runtime_configs"
    __table_args__ = (UniqueConstraint("tenant_id", "config_key", name="uq_platform_runtime_configs_tenant_key"),)

    config_key: Mapped[str] = mapped_column(String(128), nullable=False)
    config_value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    config_type: Mapped[str] = mapped_column(String(32), nullable=False, default="json")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

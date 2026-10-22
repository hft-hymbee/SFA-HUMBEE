"""`platform_form_definitions` — versioned JSON-schema forms for fields still pending from the
business (e.g. official-work/combined-visit feedback, OQ-002). §3 reconciliation item 3
(JSON → JSONB). Not detailed in database-design.md's numbered sections; scope is set by
architecture §3.10 and epic Story 0.2.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class FormDefinition(Base, ConventionsMixin):
    __tablename__ = "platform_form_definitions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "form_key", "version", name="uq_platform_form_definitions_key_version"),
    )

    form_key: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

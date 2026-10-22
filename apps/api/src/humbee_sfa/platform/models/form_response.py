"""`platform_form_responses`. See form_definition.py — a response is keyed to the version it
was submitted against, not the latest one."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class FormResponse(Base, ConventionsMixin):
    __tablename__ = "platform_form_responses"
    __table_args__ = (Index("ix_platform_form_responses_subject", "tenant_id", "subject_type", "subject_id"),)

    form_definition_id: Mapped[str] = mapped_column(String(26), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(26), nullable=False)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

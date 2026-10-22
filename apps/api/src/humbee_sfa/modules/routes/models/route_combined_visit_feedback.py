"""`routes_combined_visit_feedback` — 1:1 feedback per combined visit. database-design.md §8.

`form_definition_id` is a logical pointer into `platform_form_definitions`. `responses` is
`jsonb` + a form-version pointer instead of columns because the feedback field set is still
pending from the business (`OQ-002`) — the pending schema lands as a form version, not a
migration.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class RouteCombinedVisitFeedback(Base, ConventionsMixin):
    __tablename__ = "routes_combined_visit_feedback"
    __table_args__ = (
        Index("uq_routes_combined_feedback", "combined_visit_id", unique=True),
        CheckConstraint(
            "overall_rating IN ('good','average','needs_work')", name="rating_chk"
        ),
    )

    combined_visit_id: Mapped[str] = mapped_column(String(26), nullable=False)
    form_definition_id: Mapped[str] = mapped_column(String(26), nullable=False)  # -> platform_form_definitions
    overall_rating: Mapped[str] = mapped_column(String(16), nullable=False)
    responses: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_by_employee_id: Mapped[str] = mapped_column(String(26), nullable=False)

"""`outlets_onboarding_candidates` — a firm captured in the field, awaiting manager approval.

Humbee has no candidate stage: `POST /sfa/v1/onboard` creates a real firm, a real
organization and a real login user for the owner, immediately and irreversibly. An approval that
ran *after* that call would approve nothing, so SFA holds the submission locally, routes it through
the shared approval engine, and only calls Humbee once a manager has granted it.

The owner's phone is captured here the way `org_employees` and `targets_leads` capture one — HMAC
for lookup, Fernet ciphertext for use, last four for display — and never lands in `payload`.
`payload` carries the rest of the single `/sfa/v1/onboard` body — roles and industries included —
as a value object: it is replayed verbatim to Humbee at submission and read back for the
approver's detail view, and nothing queries inside it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base

# `pending_approval` -> `approved` -> `submitted`. `approved` is transient: the approval that
# sets it calls Humbee in the same transaction, so a committed row is `submitted` or
# `submission_failed`. `rejected` and `withdrawn` are terminal and never reach Humbee. There is
# no retry: a submission that failed before reaching Humbee is re-captured, and one that failed
# after keeps its document claim because the firm already exists upstream.
STATUSES = (
    "pending_approval",
    "approved",
    "submitted",
    "submission_failed",
    "rejected",
    "withdrawn",
)

# A candidate holds a claim on its documents and owner phone so two sales people cannot queue the
# same firm or owner. The claim is released by a rejection, a withdrawal, or a submission that
# never reached Humbee — there is no retry, so re-capturing is the only recovery and holding the
# claim would strand the firm. It is *not* released once `humbee_company_id` is set: the firm
# exists upstream at that point, and a fresh capture would only earn Humbee's `090 already
# registered`.
_CLAIMS_ACTIVE = (
    "(status IN ('pending_approval','approved','submitted') OR humbee_company_id IS NOT NULL)"
)


class OutletOnboardingCandidate(Base, ConventionsMixin):
    __tablename__ = "outlets_onboarding_candidates"
    __table_args__ = (
        Index(
            "uq_outlets_candidates_gstin",
            "tenant_id",
            "company_gstin",
            unique=True,
            postgresql_where=text(f"company_gstin IS NOT NULL AND {_CLAIMS_ACTIVE}"),
        ),
        Index(
            "uq_outlets_candidates_pan",
            "tenant_id",
            "pancard_no",
            unique=True,
            postgresql_where=text(f"pancard_no IS NOT NULL AND {_CLAIMS_ACTIVE}"),
        ),
        Index(
            "uq_outlets_candidates_phone",
            "tenant_id",
            "owner_phone_hmac",
            unique=True,
            postgresql_where=text(_CLAIMS_ACTIVE),
        ),
        Index(
            "ix_outlets_candidates_mine",
            "tenant_id",
            "captured_by_employee_id",
            text("created_at DESC"),
        ),
        Index("ix_outlets_candidates_status", "tenant_id", "status"),
        CheckConstraint(
            "status IN ('pending_approval','approved','submitted','submission_failed',"
            "'rejected','withdrawn')",
            name="outlets_candidates_status_chk",
        ),
        # ON-1/ON-3: a firm is identified by a GSTIN or a PAN, same rule the outlet projection
        # holds. An influencer (no company_name) onboards as themself with no document.
        CheckConstraint(
            "company_name IS NULL OR company_gstin IS NOT NULL OR pancard_no IS NOT NULL",
            name="outlets_candidates_document_chk",
        ),
        # ON-3 falls back to `fullname` when `company_name` is absent — that is how an influencer,
        # a person rather than a firm, is onboarded.
        CheckConstraint(
            "company_name IS NOT NULL OR fullname IS NOT NULL",
            name="outlets_candidates_named_chk",
        ),
        # `submit_candidate_to_humbee` sets `humbee_company_id` before it sets `status =
        # 'submitted'`, in the same transaction — the implication only runs one way. Mirrors
        # `orders`' INV-09.
        CheckConstraint(
            "status <> 'submitted' OR humbee_company_id IS NOT NULL",
            name="outlets_candidates_submitted_chk",
        ),
        # The same Humbee firm must never be reconciled onto two candidates.
        Index(
            "uq_outlets_candidates_company",
            "tenant_id",
            "humbee_company_id",
            unique=True,
            postgresql_where=text("humbee_company_id IS NOT NULL"),
        ),
    )

    captured_by_employee_id: Mapped[str] = mapped_column(String(26), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending_approval")
    # Self-referencing placeholder until the approval engine mints the real id, exactly as
    # `leave_requests` does — the column is NOT NULL because a candidate with no approval request
    # must not be reachable.
    approval_request_id: Mapped[str] = mapped_column(String(26), nullable=False)

    company_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    fullname: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    pancard_no: Mapped[str | None] = mapped_column(String(10), nullable=True)

    owner_phone_hmac: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    owner_phone_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    owner_phone_last4: Mapped[str] = mapped_column(CHAR(4), nullable=False)

    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    humbee_company_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submission_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

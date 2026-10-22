"""`targets_leads` — a captured prospect for manufacturers not on Humbee, named as free text in
`associated_manufacturer_names`.

`occurred_at` is capture time; `business_date` decides which month the lead counts toward for
a `leads` target.
"""

from __future__ import annotations

from geoalchemy2 import Geography
from geoalchemy2.elements import WKBElement
from sqlalchemy import (
    ARRAY,
    CHAR,
    CheckConstraint,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin, FieldEventTimingMixin
from humbee_sfa.core.db import Base


class Lead(Base, ConventionsMixin, FieldEventTimingMixin):
    __tablename__ = "targets_leads"
    __table_args__ = (
        Index("ix_targets_leads_mine", "tenant_id", "captured_by_employee_id", text("business_date DESC")),
        Index(
            "ix_targets_leads_month",
            "tenant_id",
            "captured_by_employee_id",
            "business_date",
            postgresql_where=text("status <> 'rejected'"),
        ),
        CheckConstraint("interest_level IN ('hot','warm','cold')", name="targets_leads_interest_chk"),
        CheckConstraint(
            "status IN ('captured','in_review','qualified','rejected')", name="targets_leads_status_chk"
        ),
        CheckConstraint("length(btrim(prospect_name)) >= 2", name="targets_leads_prospect_chk"),
        CheckConstraint(
            "expected_monthly_units IS NULL OR expected_monthly_units > 0", name="targets_leads_units_chk"
        ),
        CheckConstraint("length(btrim(company_name)) >= 2", name="targets_leads_company_chk"),
        CheckConstraint(
            "annual_turnover_cr IS NULL OR annual_turnover_cr > 0", name="targets_leads_turnover_chk"
        ),
        CheckConstraint(
            "cardinality(associated_manufacturer_names) >= 1", name="targets_leads_manufacturers_chk"
        ),
    )

    captured_by_employee_id: Mapped[str] = mapped_column(String(26), nullable=False)
    prospect_name: Mapped[str] = mapped_column(String(120), nullable=False)
    contact_person: Mapped[str | None] = mapped_column(String(120), nullable=True)
    contact_designation: Mapped[str | None] = mapped_column(String(120), nullable=True)
    associated_manufacturer_names: Mapped[list[str]] = mapped_column(
        ARRAY(String(120)), nullable=False, server_default=text("'{}'")
    )
    contact_mobile_hmac: Mapped[str] = mapped_column(CHAR(64), nullable=False)  # PII
    contact_mobile_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    contact_mobile_last4: Mapped[str] = mapped_column(CHAR(4), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    annual_turnover_cr: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    head_office_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    interest_level: Mapped[str] = mapped_column(String(16), nullable=False)
    expected_monthly_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_units_uom: Mapped[str | None] = mapped_column(String(32), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="captured")
    humbee_outlet_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # set if lead → outlet
    geo_point: Mapped[WKBElement | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=True
    )

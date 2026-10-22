"""Targets HTTP DTOs — M13 §3.1–§3.3, §10.

Targets are SFA-owned and optional: an employee with none sells normally (R-TGT-06). Achievement is
never a field here — it is Humbee's for `sales` and an SFA count for `outlets`/`leads` (INV-14), and
is read through its own endpoint rather than folded into a target.

Every value is a positive integer: paise or units for `sales` depending on the manufacturer's own
basis, a count for `outlets` and `leads` (R-TGT-12). A sales target has no single basis of its own —
`GET /sfa/v1/targets/manufacturers` fixes each manufacturer to `amount` or `volume`, so the client
sends only `manufacturer_id`/`line_value` per line and the server resolves `line_basis` from that
roster. The type-conditional shape below mirrors the table's own CHECK constraints one for one, so a
body that would violate the database is refused at the edge with a field error instead of a 500.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

# Matches `targets_manufacturer_lines.humbee_manufacturer_id varchar(64)`. Without the bound an
# over-long id reaches Postgres as a DataError — which is not an IntegrityError, so nothing
# catches it and the caller gets a 500 where a field error belongs.
ManufacturerId = Annotated[str, Field(min_length=1, max_length=64)]

PHONE_E164_PATTERN = r"^\+91\d{10}$"
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def _strip(value: Any) -> Any:
    return "".join(value.split()) if isinstance(value, str) else value


class TargetType(StrEnum):
    SALES = "sales"
    OUTLETS = "outlets"
    LEADS = "leads"


class TargetBasis(StrEnum):
    AMOUNT = "amount"
    VOLUME = "volume"


class OutletCategoryScope(StrEnum):
    ANY = "any"
    GROCERY = "grocery"
    WHOLESALE = "wholesale"
    CHEMIST = "chemist"


class TargetStatus(StrEnum):
    ACTIVE = "active"
    REMOVED = "removed"


class TargetLineBody(BaseModel):
    """One manufacturer's share of a `sales` target.

    The server snapshots the manufacturer's label/basis/UOM from the authoritative roster at write
    time, so the body carries only identity and value.
    """

    manufacturer_id: ManufacturerId
    line_value: int = Field(gt=0)


class TargetShape(BaseModel):
    """The type-conditional body shared by create and update."""

    target_value: int | None = Field(default=None, gt=0)
    outlet_category_scope: OutletCategoryScope | None = None
    lines: list[TargetLineBody] = Field(default_factory=list)

    def _target_type(self) -> TargetType:
        raise NotImplementedError

    @model_validator(mode="after")
    def _shape_matches_type(self) -> TargetShape:
        target_type = self._target_type()

        if target_type is TargetType.SALES:
            if not self.lines:
                raise ValueError("select at least one manufacturer")
            manufacturers = [line.manufacturer_id for line in self.lines]
            if len(set(manufacturers)) != len(manufacturers):
                raise ValueError("a manufacturer may appear only once")
            # R-TGT-09: the rollup is always derived from the lines, per-basis, so a client-sent
            # value is not merely ignored — accepting it would imply it could disagree.
            if self.target_value is not None:
                raise ValueError("target_value is derived from the lines for a sales target")

        if target_type is TargetType.OUTLETS:
            if self.outlet_category_scope is None:
                raise ValueError("outlet targets need a category scope; use 'any' for no filter")
        elif self.outlet_category_scope is not None:
            raise ValueError("outlet_category_scope applies to outlet targets only")

        if target_type is not TargetType.SALES:
            if self.lines:
                raise ValueError("manufacturer lines apply to sales targets only")
            if self.target_value is None:
                raise ValueError("enter a target greater than zero")

        return self


class CreateTargetBody(TargetShape):
    """S-TGT1 save, for an employee and month that has no active target of this type yet."""

    id: str | None = Field(default=None, min_length=26, max_length=26)
    employee_id: str = Field(min_length=1, max_length=26)
    target_type: TargetType
    period_month: date

    def _target_type(self) -> TargetType:
        return self.target_type


class UpdateTargetBody(TargetShape):
    """S-TGT1 save over an existing target. Employee, type and month are the target's identity
    (R-TGT-08) and are not editable — changing one is a different target."""

    target_type: TargetType
    version: int = Field(ge=1)

    def _target_type(self) -> TargetType:
        return self.target_type


class TargetLineOut(BaseModel):
    manufacturer_id: str
    manufacturer_label: str
    line_basis: TargetBasis
    uom_label: str
    line_value: int


class TargetOut(BaseModel):
    id: str
    employee_id: str
    target_type: TargetType
    period_month: date
    target_value: int | None
    # Sales-only rollups: each is the sum of that target's lines sharing that basis (R-TGT-09).
    # A sales target has no single basis, so at most one of the two is populated when every line
    # shares a basis, and both may be populated when the lines mix amount and volume manufacturers.
    target_value_amount_paise: int | None = None
    target_value_volume_units: int | None = None
    outlet_category_scope: OutletCategoryScope | None
    status: TargetStatus
    version: int
    created_at: datetime
    lines: list[TargetLineOut]


class TargetListResponse(BaseModel):
    targets: list[TargetOut]


class RemoveTargetResponse(BaseModel):
    target_id: str
    status: TargetStatus
    removed_at: datetime
    removed_by: str


class ManufacturerOut(BaseModel):
    manufacturer_id: str
    display_label: str
    basis: TargetBasis
    uom_label: str

    @model_validator(mode="after")
    def _measure_pair_is_supported(self) -> ManufacturerOut:
        valid_pair = (
            (self.basis is TargetBasis.VOLUME and self.uom_label == "Ton")
            or (self.basis is TargetBasis.AMOUNT and self.uom_label == "₹")
        )
        if not valid_pair:
            raise ValueError("manufacturer basis/uom must be volume/Ton or amount/₹")
        return self


class ManufacturerRosterResponse(BaseModel):
    """The roster behind a sales target's lines. Humbee owns it; SFA may
    never create, rename or delete a manufacturer (R-TGT-04). `basis`/`uom_label` say whether that
    manufacturer's line is entered in ₹ or units — the form has no separate basis choice."""

    manufacturers: list[ManufacturerOut]


class TargetRosterMember(BaseModel):
    employee_id: str
    full_name: str
    display_initials: str
    role_code: str
    zone_label: str | None
    active_target_count: int = Field(ge=0)


class TargetRosterResponse(BaseModel):
    period_month: date
    with_target: int
    total: int
    members: list[TargetRosterMember]


class LeadInterestLevel(StrEnum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


class LeadStatus(StrEnum):
    CAPTURED = "captured"
    IN_REVIEW = "in_review"
    QUALIFIED = "qualified"
    REJECTED = "rejected"


ManufacturerName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class CaptureLeadBody(BaseModel):
    """S-LEAD1 — a salesperson captures a prospective business as a lead for follow-up. Leads are
    for manufacturers not on Humbee, so they are named as free text — at least one — rather than
    picked from the Humbee roster."""

    id: str | None = Field(default=None, min_length=26, max_length=26)
    name: str = Field(min_length=2, max_length=120)
    designation: str | None = Field(default=None, max_length=120)
    mobile: str = Field(pattern=PHONE_E164_PATTERN)
    email: str = Field(pattern=EMAIL_PATTERN, max_length=255)
    company_name: str = Field(min_length=2, max_length=255)
    associated_manufacturers: list[ManufacturerName] = Field(min_length=1)
    annual_turnover_cr: float | None = Field(default=None, gt=0, le=1_000_000)
    head_office_location: str | None = Field(default=None, max_length=255)
    message: str | None = Field(default=None, max_length=500)

    @field_validator("designation", mode="before")
    @classmethod
    def _normalise_designation(cls, value: Any) -> Any:
        return (value.strip() or None) if isinstance(value, str) else value

    @field_validator("associated_manufacturers")
    @classmethod
    def _dedupe_manufacturers(cls, value: list[str]) -> list[str]:
        unique: dict[str, str] = {}
        for name in value:
            unique.setdefault(name.casefold(), name)
        return list(unique.values())

    @field_validator("mobile", mode="before")
    @classmethod
    def _normalise_mobile(cls, value: Any) -> Any:
        return _strip(value)

    @field_validator("email", mode="before")
    @classmethod
    def _normalise_email(cls, value: Any) -> Any:
        return value.strip().lower() if isinstance(value, str) else value


class LeadOut(BaseModel):
    id: str
    name: str
    designation: str | None
    mobile_last4: str
    email: str
    company_name: str
    associated_manufacturers: list[str]
    annual_turnover_cr: float | None
    head_office_location: str | None
    message: str | None
    interest_level: LeadInterestLevel
    status: LeadStatus
    captured_at: datetime

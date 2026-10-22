"""Outlets HTTP request and response DTOs — firm onboarding."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

PHONE_E164_PATTERN = r"^\+91\d{10}$"
OTP_CODE_PATTERN = r"^\d{4,8}$"
ULID_PATTERN = r"^[0-9A-HJKMNP-TV-Z]{26}$"
GSTIN_PATTERN = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[0-9A-Z]{1}Z[0-9A-Z]{1}$"
PAN_PATTERN = r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$"


def _strip(value: Any) -> Any:
    return "".join(value.split()) if isinstance(value, str) else value


class OwnerOtpRequestBody(BaseModel):
    phone_e164: str = Field(pattern=PHONE_E164_PATTERN)

    @field_validator("phone_e164", mode="before")
    @classmethod
    def _normalise_phone(cls, value: Any) -> Any:
        return _strip(value)


class OwnerOtpRequestResponse(BaseModel):
    challenge_id: str
    phone_e164: str
    resend_available_at: datetime
    expires_at: datetime


class OwnerOtpVerifyBody(BaseModel):
    challenge_id: str = Field(pattern=ULID_PATTERN)
    code: str = Field(pattern=OTP_CODE_PATTERN)

    @field_validator("code", mode="before")
    @classmethod
    def _normalise_code(cls, value: Any) -> Any:
        return _strip(value)


class OwnerOtpVerifyResponse(BaseModel):
    challenge_id: str
    verified: bool
    verified_until: datetime


class DocumentLookupResponse(BaseModel):
    """The registered address behind a GSTIN or PAN, for pre-filling the firm form.
    Only `document_type` is guaranteed; other fields are optional."""

    document_type: str
    gstin: str | None = None
    pan: str | None = None
    firm_name: str | None
    address_line_1: str | None
    address_line_2: str | None
    state_id: str | None
    state_name: str | None
    district_id: str | None
    district_name: str | None
    pincode: str | None


class ManufacturerRoleOut(BaseModel):
    role_id: str
    role_name: str
    is_gst_required: bool
    is_pan_required: bool
    is_fssai_required: bool


class ManufacturerRolesOut(BaseModel):
    manufacturer_id: str
    name: str
    vcp_roles: list[ManufacturerRoleOut]
    influencer_roles: list[ManufacturerRoleOut]


class ManufacturerRolesResponse(BaseModel):
    manufacturers: list[ManufacturerRolesOut]


class SecondaryIndustryOut(BaseModel):
    secondary_industry_id: str
    secondary_industry: str
    description: str | None


class PrimaryIndustryOut(BaseModel):
    primary_industry_id: str
    primary_industry_name: str
    description: str | None
    secondaries: list[SecondaryIndustryOut]


class IndustriesResponse(BaseModel):
    industries: list[PrimaryIndustryOut]


class OutletDetailResponse(BaseModel):
    outlet_id: str
    name: str
    locality: str | None
    district_name: str
    contact_person: str | None
    gstin: str | None
    pan: str | None
    registered_address: str | None
    is_active: bool | None
    contact_mobile: str | None
    credit_limit_paise: int | None
    credit_outstanding_paise: int | None
    latitude: float | None
    longitude: float | None
    as_of: datetime


class EsiRecordOut(BaseModel):
    esi_id: str
    esi_code: str
    geographic_info: dict[str, Any] | None = None


class OutletSellerOut(BaseModel):
    seller_id: str
    seller_type: str
    name: str
    address: str | None = None
    is_active: bool
    requires_purchase_order: bool
    manager_approval_required: bool
    seller_esi_records: list[EsiRecordOut]
    outlet_esi_records: list[EsiRecordOut]


class OutletSellersByBrandOut(BaseModel):
    brand_id: str
    brand_name: str
    sellers_filtered_by_district: bool
    sellers: list[OutletSellerOut]


class OutletSellersResponse(BaseModel):
    outlet_id: str
    outlet_address: str | None = None
    sellers_by_brand: list[OutletSellersByBrandOut]
    total_count: int
    as_of: datetime


class OutletInsightSectionResponse(BaseModel):
    """One insight section. `data` is Humbee's display tree, passed through unchanged — the
    figures are pre-formatted strings and phase 1 is placeholder, so SFA fixes no shape here."""

    outlet_id: str
    manufacturer_id: str
    outlet_esi_id: str
    data: dict[str, Any]
    as_of: datetime | None = None


class OutletInsightProfilerResponse(BaseModel):
    """`url` is pre-authenticated and PII-bearing — never log or persist it."""

    outlet_id: str
    manufacturer_id: str
    outlet_esi_id: str
    url: str


class OutletInsightEsiRecordOut(BaseModel):
    esi_id: str
    esi_code: str
    active: bool


class OutletInsightManufacturerOut(BaseModel):
    manufacturer_id: str
    manufacturer_name: str
    external_system_records: list[OutletInsightEsiRecordOut]


class OutletInsightManufacturersResponse(BaseModel):
    outlet_id: str
    manufacturers: list[OutletInsightManufacturerOut]
    as_of: datetime | None = None


class FirmAddressStateOut(BaseModel):
    state_id: str
    state_name: str


class FirmAddressStatesResponse(BaseModel):
    """The state step of the firm address form."""

    states: list[FirmAddressStateOut]


class FirmAddressDistrictOut(BaseModel):
    district_id: str
    district_name: str
    state_id: str
    state_name: str


class FirmAddressDistrictsResponse(BaseModel):
    """The district step, always bounded by one state."""

    districts: list[FirmAddressDistrictOut]


class FirmAddressLocationOut(BaseModel):
    location_id: str
    location_name: str


class FirmAddressOptionsResponse(BaseModel):
    """The locality and pincode steps. `location_id` and `pincode` are exactly the values
    `OperationalAddressBody` takes, so a picked option is copied straight into the firm body.
    Either list may legitimately be empty."""

    district_id: str
    locations: list[FirmAddressLocationOut]
    pincodes: list[str]
    as_of: datetime


class CompanyAddressBody(BaseModel):
    """Humbee requires none of the three lines. We require the first two, because an operational
    address with one line is not deliverable; the third stays optional."""

    address_line_1: str = Field(min_length=1, max_length=255)
    address_line_2: str = Field(min_length=1, max_length=255)
    address_line_3: str | None = Field(default=None, max_length=255)


class RegisteredAddressBody(BaseModel):
    company_address: CompanyAddressBody
    state_id: str = Field(min_length=1, max_length=32)
    state_name: str | None = Field(default=None, max_length=255)
    district_id: str = Field(min_length=1, max_length=32)
    district_name: str | None = Field(default=None, max_length=255)


class OperationalAddressBody(BaseModel):
    company_address: CompanyAddressBody
    state_id: str = Field(min_length=1, max_length=32)
    state_name: str | None = Field(default=None, max_length=255)
    district_id: str = Field(min_length=1, max_length=32)
    district_name: str | None = Field(default=None, max_length=255)
    location_id: str = Field(min_length=1, max_length=32)
    pincode: str = Field(pattern=r"^\d{6}$")


class CandidateRegisteredAddressBody(RegisteredAddressBody):
    state_name: str = Field(min_length=1, max_length=255)
    district_name: str = Field(min_length=1, max_length=255)


class CandidateOperationalAddressBody(OperationalAddressBody):
    state_name: str = Field(min_length=1, max_length=255)
    district_name: str = Field(min_length=1, max_length=255)


class CandidateRoleBody(BaseModel):
    manufacturer_id: str = Field(min_length=1, max_length=32)
    firm_role_id: str = Field(min_length=1, max_length=32)


class CandidateIndustryBody(BaseModel):
    primary_industry_id: str = Field(min_length=1, max_length=32)
    primary_industry_name: str = Field(min_length=1, max_length=255)
    secondary_industry_id: str = Field(min_length=1, max_length=32)
    secondary_industry: str = Field(min_length=1, max_length=255)
    role_name: str = Field(min_length=1, max_length=100)

    @field_validator("role_name", mode="before")
    @classmethod
    def _normalise_role_name(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class SubmitCandidateBody(BaseModel):
    challenge_id: str = Field(pattern=ULID_PATTERN)
    phone_number: str = Field(pattern=PHONE_E164_PATTERN)
    registered_address: CandidateRegisteredAddressBody
    operational_address: CandidateOperationalAddressBody
    company_name: str | None = Field(default=None, max_length=255)
    company_gstin: str | None = Field(default=None, pattern=GSTIN_PATTERN)
    pancard_no: str | None = Field(default=None, pattern=PAN_PATTERN)
    fullname: str | None = Field(default=None, max_length=255)
    date_of_birth: date | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    id: str | None = Field(default=None, min_length=26, max_length=26)
    roles: list[CandidateRoleBody] = Field(default_factory=list)
    industries: list[CandidateIndustryBody] = Field(default_factory=list)

    @field_validator("phone_number", mode="before")
    @classmethod
    def _normalise_phone(cls, value: Any) -> Any:
        return _strip(value)

    @model_validator(mode="after")
    def _coordinates_are_a_pair(self) -> SubmitCandidateBody:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be sent together, or not at all")
        return self

    @model_validator(mode="after")
    def _firm_is_named(self) -> SubmitCandidateBody:
        # `onboard-firm` falls back to `fullname` when `company_name` is absent — that is how an
        # influencer, a person rather than a firm, is onboarded. Neither is a refusal upstream.
        if not self.company_name and not self.fullname:
            raise ValueError("provide company_name, or fullname for an individual")
        return self

    @model_validator(mode="after")
    def _has_an_association(self) -> SubmitCandidateBody:
        if not self.roles and not self.industries:
            raise ValueError("at least one manufacturer role or industry association is required")
        return self

    @model_validator(mode="after")
    def _one_role_per_manufacturer(self) -> SubmitCandidateBody:
        manufacturer_ids = [role.manufacturer_id for role in self.roles]
        if len(manufacturer_ids) != len(set(manufacturer_ids)):
            raise ValueError("manufacturer roles must not repeat the same manufacturer")
        return self

    @model_validator(mode="after")
    def _unique_industries(self) -> SubmitCandidateBody:
        industry_ids = [industry.secondary_industry_id for industry in self.industries]
        if len(industry_ids) != len(set(industry_ids)):
            raise ValueError("industry associations must not repeat the same secondary industry")
        return self


class CandidateRoleOut(BaseModel):
    manufacturer_id: str
    firm_role_id: str


class CandidateIndustryOut(BaseModel):
    primary_industry_id: str
    primary_industry_name: str
    secondary_industry_id: str
    secondary_industry: str
    role_name: str


class CandidateListItem(BaseModel):
    id: str
    status: str
    display_name: str
    company_gstin: str | None
    pancard_no: str | None
    owner_phone_e164: str
    captured_by_employee_id: str
    approval_request_id: str
    humbee_company_id: str | None
    submission_error: str | None
    industries: list[CandidateIndustryOut]
    created_at: datetime


class CandidateListResponse(BaseModel):
    items: list[CandidateListItem]


class CandidateDetailResponse(CandidateListItem):
    registered_address: RegisteredAddressBody
    operational_address: OperationalAddressBody
    roles: list[CandidateRoleOut]
    version: int

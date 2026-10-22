"""Provider-neutral port for Humbee's onboarding and address capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from humbee_sfa.core.settings import Settings
from humbee_sfa.integration.humbee.client import (
    HumbeeAlreadyRegisteredError,
    HumbeeError,
    HumbeeInvalidDocumentFormatError,
    HumbeeNotFoundError,
    HumbeeRefusedError,
    get_humbee_client,
)


@dataclass(frozen=True)
class DocumentLookupResult:
    """The GSTIN/PAN lookup's answer: the firm's registered address, for pre-filling the
    onboarding form.

    Verified against a live `api-dev.humbee.in` response 2026-09-04. Humbee republishes its own
    `GSTDetailsResponseDTO`/`PANDetailsResponseDTO` unchanged, so the payload is flat and every
    field but `document_type` is nullable — a PAN record carries no `firm_name` or `pincode`.
    A GSTIN embeds its PAN in characters 3–12, so GSTIN lookups derive PAN from the query.
    """

    document_type: str
    gstin: str | None
    pan: str | None
    firm_name: str | None
    address_line_1: str | None
    address_line_2: str | None
    state_id: str | None
    state_name: str | None
    district_id: str | None
    district_name: str | None
    pincode: str | None


@dataclass(frozen=True)
class ManufacturerRoleOption:
    role_id: str
    role_name: str
    is_gst_required: bool
    is_pan_required: bool
    is_fssai_required: bool


@dataclass(frozen=True)
class ManufacturerRoles:
    manufacturer_id: str
    name: str
    vcp_roles: tuple[ManufacturerRoleOption, ...]
    influencer_roles: tuple[ManufacturerRoleOption, ...]


@dataclass(frozen=True)
class CompanyAddress:
    address_line_1: str
    address_line_2: str | None
    address_line_3: str | None


@dataclass(frozen=True)
class RegisteredAddress:
    company_address: CompanyAddress
    state_id: str
    district_id: str


@dataclass(frozen=True)
class OperationalAddress:
    company_address: CompanyAddress
    state_id: str
    district_id: str
    location_id: str
    pincode: str


@dataclass(frozen=True)
class FirmAddressState:
    state_id: str
    state_name: str


@dataclass(frozen=True)
class FirmAddressDistrict:
    district_id: str
    district_name: str
    state_id: str
    state_name: str


@dataclass(frozen=True)
class FirmAddressLocation:
    location_id: str
    location_name: str


@dataclass(frozen=True)
class FirmAddressOptions:
    """The locality and pincode choices inside one district.

    Both lists feed `OperationalAddress`, and the field names match what onboarding consumes, so a
    picked value is copied straight through. Humbee returns each pincode as a `{pincode_id,
    pincode_name}` pair holding the same six-digit string twice; only the one value is carried.
    """

    district_id: str
    locations: tuple[FirmAddressLocation, ...]
    pincodes: tuple[str, ...]
    as_of: datetime


@dataclass(frozen=True)
class RoleEntry:
    manufacturer_id: str
    firm_role_id: str


@dataclass(frozen=True)
class IndustryEntry:
    primary_industry_id: str
    secondary_industry_id: str
    role_name: str


@dataclass(frozen=True)
class OnboardRequest:
    phone_number: str  # bare 10-digit, already stripped of the +91 prefix by the caller
    registered_address: RegisteredAddress
    operational_address: OperationalAddress
    onboarded_by: str
    roles: tuple[RoleEntry, ...]
    industries: tuple[IndustryEntry, ...]
    company_name: str | None = None
    company_gstin: str | None = None
    pancard_no: str | None = None
    fullname: str | None = None
    date_of_birth: date | None = None
    latitude: float | None = None
    longitude: float | None = None


@dataclass(frozen=True)
class SecondaryIndustry:
    secondary_industry_id: str
    secondary_industry: str
    description: str | None


@dataclass(frozen=True)
class PrimaryIndustry:
    primary_industry_id: str
    primary_industry_name: str
    description: str | None
    secondaries: tuple[SecondaryIndustry, ...]


class OnboardingUnavailable(RuntimeError):
    pass


def _address_body(address: CompanyAddress) -> dict[str, Any]:
    body = {"address_line_1": address.address_line_1}
    if address.address_line_2:
        body["address_line_2"] = address.address_line_2
    if address.address_line_3:
        body["address_line_3"] = address.address_line_3
    return body


def _registered_address_body(address: RegisteredAddress) -> dict[str, Any]:
    return {
        "company_address": _address_body(address.company_address),
        "state_id": address.state_id,
        "district_id": address.district_id,
    }


def _operational_address_body(address: OperationalAddress) -> dict[str, Any]:
    return {
        "company_address": _address_body(address.company_address),
        "state_id": address.state_id,
        "district_id": address.district_id,
        "location_id": address.location_id,
        "pincode": address.pincode,
    }


def _opt_str(value: Any) -> str | None:
    """The GSTIN/PAN lookup is the one SFA response whose geography ids arrive as JSON numbers
    rather than strings. Normalise them back to opaque strings so the rest of the codebase sees one
    type."""

    return None if value is None else str(value)


def _role_option(item: dict[str, Any]) -> ManufacturerRoleOption:
    return ManufacturerRoleOption(
        role_id=str(item["role_id"]),
        role_name=item.get("role_name") or "",
        is_gst_required=bool(item.get("is_gst_required")),
        is_pan_required=bool(item.get("is_pan_required")),
        is_fssai_required=bool(item.get("is_fssai_required")),
    )


class HumbeeOnboardingProvider:
    def __init__(self, settings: Settings) -> None:
        self._client = get_humbee_client(settings)

    def lookup_document(self, *, gstin: str | None, pan: str | None) -> DocumentLookupResult:
        params: dict[str, Any] = {}
        if gstin:
            params["gstin"] = gstin
        if pan:
            params["pan"] = pan
        data = self._client.call(
            "onboarding.document_lookup",
            "GET",
            "/sfa/v1/gstin-pan-details",
            route="/gstin-pan-details",
            params=params,
        )
        try:
            return DocumentLookupResult(
                document_type=str(data["document_type"]),
                gstin=_opt_str(data.get("gstin") or data.get("company_gstin")) or gstin,
                pan=gstin[2:12] if gstin else pan,
                firm_name=data.get("firm_name"),
                address_line_1=data.get("address_line_1"),
                address_line_2=data.get("address_line_2"),
                state_id=_opt_str(data.get("state_id")),
                state_name=data.get("state_name"),
                district_id=_opt_str(data.get("district_id")),
                district_name=data.get("district_name"),
                pincode=data.get("pincode"),
            )
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise OnboardingUnavailable(f"unexpected document lookup response shape: {exc}") from exc

    def list_manufacturer_roles(self) -> list[ManufacturerRoles]:
        data = self._client.call(
            "onboarding.manufacturer_roles",
            "GET",
            "/sfa/v1/manufacturer-roles",
            route="/manufacturer-roles",
            timeout_s=3.0,
        )
        try:
            return [
                ManufacturerRoles(
                    manufacturer_id=str(item["manufacturer_id"]),
                    name=item.get("name") or "",
                    vcp_roles=tuple(_role_option(role) for role in item.get("vcp_roles") or []),
                    influencer_roles=tuple(
                        _role_option(role) for role in item.get("influencer_roles") or []
                    ),
                )
                for item in data
            ]
        except (KeyError, TypeError, ValueError) as exc:
            raise OnboardingUnavailable(f"unexpected manufacturer-roles response shape: {exc}") from exc

    def is_phone_registered(self, phone: str) -> bool:
        try:
            self._client.call(
                "onboarding.verify_phone",
                "GET",
                "/sfa/v1/verify/phone-number",
                route="/verify/phone-number",
                params={"phone_number": phone},
                timeout_s=3.0,
                max_retries=1,
            )
            return False
        except HumbeeAlreadyRegisteredError:
            return True

    def list_industries(self) -> tuple[PrimaryIndustry, ...]:
        data = self._client.call(
            "onboarding.industries",
            "GET",
            "/sfa/v1/industries",
            route="/industries",
            timeout_s=3.0,
            max_retries=1,
        )
        try:
            return tuple(
                PrimaryIndustry(
                    primary_industry_id=str(item["primary_industry_id"]),
                    primary_industry_name=str(item["primary_industry_name"]),
                    description=item.get("description"),
                    secondaries=tuple(
                        SecondaryIndustry(
                            secondary_industry_id=str(row["secondary_industry_id"]),
                            secondary_industry=str(row["secondary_industry"]),
                            description=row.get("description"),
                        )
                        for row in item["secondary_industries"]
                    ),
                )
                for item in data["industries"]
            )
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise OnboardingUnavailable(f"unexpected industries response shape: {exc}") from exc

    def list_firm_address_states(self) -> tuple[FirmAddressState, ...]:
        """Every active state, flat. `manufacturer_id` is deliberately not sent: an address
        exists before any manufacturer is chosen, and sending one would narrow the form to that
        brand's territory."""

        data = self._client.call(
            "onboarding.address_states", "GET", "/sfa/v1/states", route="/states"
        )
        try:
            return tuple(
                FirmAddressState(
                    state_id=str(row["state_id"]), state_name=row.get("state_name") or ""
                )
                for row in data["states"]
            )
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise OnboardingUnavailable(f"unexpected address states response shape: {exc}") from exc

    def list_firm_address_districts(self, *, state_id: str) -> tuple[FirmAddressDistrict, ...]:
        """The districts of one state. `state_id` bounds the answer and is required upstream;
        there is no national district listing."""

        data = self._client.call(
            "onboarding.address_districts",
            "GET",
            "/sfa/v1/districts",
            route="/districts",
            params={"state_id": state_id},
        )
        try:
            return tuple(
                FirmAddressDistrict(
                    district_id=str(row["district_id"]),
                    district_name=row.get("district_name") or "",
                    state_id=str(row["state_id"]),
                    state_name=row.get("state_name") or "",
                )
                for row in data["districts"]
            )
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise OnboardingUnavailable(
                f"unexpected address districts response shape: {exc}"
            ) from exc

    def list_firm_address_options(
        self, *, district_id: str, pincode: str | None = None, location_id: str | None = None
    ) -> FirmAddressOptions:
        """The localities and pincodes inside one district, for onboarding's mandatory
        `operational_address.location_id` and `pincode`.

        The two optional arguments cross-filter the *opposite* list, which is what keeps a locality
        picker and a pincode picker agreeing with each other: `pincode` narrows the localities,
        `location_id` narrows the pincodes. Either list coming back empty is an answer rather than
        a failure — 556 active pincodes have no locality mapped to them.
        """

        params: dict[str, Any] = {"district_id": district_id}
        if pincode:
            params["pincode_id"] = pincode
        if location_id:
            params["location_id"] = location_id
        data = self._client.call(
            "onboarding.address_options",
            "GET",
            "/sfa/v1/locations",
            route="/locations",
            params=params,
        )
        try:
            return FirmAddressOptions(
                district_id=str(data["district_id"]),
                locations=tuple(
                    FirmAddressLocation(
                        location_id=str(row["location_id"]),
                        location_name=row.get("location_name") or "",
                    )
                    for row in data["location_list"]
                ),
                pincodes=tuple(str(row["pincode_id"]) for row in data["pincode_list"]),
                as_of=datetime.fromisoformat(data["as_of"]),
            )
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise OnboardingUnavailable(f"unexpected address options response shape: {exc}") from exc

    def onboard(self, request: OnboardRequest) -> str:
        body: dict[str, Any] = {
            "phone_number": request.phone_number,
            "registered_address": _registered_address_body(request.registered_address),
            "operational_address": _operational_address_body(request.operational_address),
            "onboarded_by": request.onboarded_by,
            "roles": [
                {"manufacturer_id": role.manufacturer_id, "firm_role_id": role.firm_role_id}
                for role in request.roles
            ],
            "industries": [
                {
                    "primary_industry_id": industry.primary_industry_id,
                    "secondary_industry_id": industry.secondary_industry_id,
                    "role_name": industry.role_name,
                }
                for industry in request.industries
            ],
        }
        if request.company_name:
            body["company_name"] = request.company_name
        if request.company_gstin:
            body["company_gstin"] = request.company_gstin
        if request.pancard_no:
            body["pancard_no"] = request.pancard_no
        if request.fullname:
            body["fullname"] = request.fullname
        if request.date_of_birth:
            body["date_of_birth"] = request.date_of_birth.isoformat()
        if request.latitude is not None and request.longitude is not None:
            body["latitude"] = request.latitude
            body["longitude"] = request.longitude

        data = self._client.call(
            "onboarding.onboard",
            "POST",
            "/sfa/v1/onboard",
            route="/onboard",
            json_body=body,
            max_retries=0,
        )
        try:
            return str(data["company_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise OnboardingUnavailable(f"unexpected onboard response shape: {exc}") from exc


__all__ = [
    "CompanyAddress",
    "DocumentLookupResult",
    "FirmAddressDistrict",
    "FirmAddressLocation",
    "FirmAddressOptions",
    "FirmAddressState",
    "HumbeeAlreadyRegisteredError",
    "HumbeeError",
    "HumbeeInvalidDocumentFormatError",
    "HumbeeNotFoundError",
    "HumbeeOnboardingProvider",
    "HumbeeRefusedError",
    "IndustryEntry",
    "ManufacturerRoleOption",
    "ManufacturerRoles",
    "OnboardRequest",
    "OnboardingUnavailable",
    "OperationalAddress",
    "PrimaryIndustry",
    "RegisteredAddress",
    "RoleEntry",
    "SecondaryIndustry",
]


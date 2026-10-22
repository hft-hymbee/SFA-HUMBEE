"""Outlets HTTP routes — firm onboarding and outlet profile reads.

Handlers translate HTTP only; transaction ownership and business rules are the service's.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Path, Query, Response
from fastapi import Request as HttpRequest
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from humbee_sfa.core.db import get_db_session
from humbee_sfa.core.deps import AccessTokenClaims, get_current_claims
from humbee_sfa.modules.outlets import schemas
from humbee_sfa.modules.outlets.service import OutletOnboardingService, OutletReadService
from humbee_sfa.platform.telemetry.middleware import get_request_id

router = APIRouter(tags=["Outlets"])
onboarding_router = APIRouter(prefix="/api/v1/outlets/onboarding", tags=["Outlets"])
read_router = APIRouter(prefix="/api/v1/outlets", tags=["Outlets"])

IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", max_length=128)]
OutletId = Annotated[str, Path(min_length=1, max_length=64)]
ManufacturerId = Annotated[str, Query(min_length=1, max_length=64)]
OutletEsiId = Annotated[str, Query(min_length=1, max_length=64)]


@read_router.get("/{outlet_id}", response_model=schemas.OutletDetailResponse)
def get_outlet_detail(
    outlet_id: OutletId,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Outlet profile read for the outlet page."""

    return OutletReadService(session).get_outlet_detail(claims=claims, outlet_id=outlet_id)


@read_router.get("/{outlet_id}/sellers", response_model=schemas.OutletSellersResponse)
def get_outlet_sellers(
    outlet_id: OutletId,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Seller linkage for one outlet, grouped by brand."""

    return OutletReadService(session).get_outlet_sellers(claims=claims, outlet_id=outlet_id)


@read_router.get(
    "/{outlet_id}/insights/manufacturers",
    response_model=schemas.OutletInsightManufacturersResponse,
    dependencies=[Depends(get_current_claims)],
)
def get_outlet_insight_manufacturers(
    outlet_id: OutletId,
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Manufacturers and their outlet SAP registrations for the insights picker, including
    older inactive registrations."""

    return OutletReadService(session).get_outlet_insight_manufacturers(outlet_id=outlet_id)


@read_router.get(
    "/{outlet_id}/insights/benefits",
    response_model=schemas.OutletInsightSectionResponse,
    dependencies=[Depends(get_current_claims)],
)
def get_outlet_insight_benefits(
    outlet_id: OutletId,
    manufacturer_id: ManufacturerId,
    outlet_esi_id: OutletEsiId,
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Club tier and social-security policies for one outlet under one brand."""

    return OutletReadService(session).get_outlet_insight_benefits(
        outlet_id=outlet_id,
        manufacturer_id=manufacturer_id,
        outlet_esi_id=outlet_esi_id,
    )


@read_router.get(
    "/{outlet_id}/insights/performance",
    response_model=schemas.OutletInsightSectionResponse,
    dependencies=[Depends(get_current_claims)],
)
def get_outlet_insight_performance(
    outlet_id: OutletId,
    manufacturer_id: ManufacturerId,
    outlet_esi_id: OutletEsiId,
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Sales, network reach and month-wise allocation for one outlet under one brand."""

    return OutletReadService(session).get_outlet_insight_performance(
        outlet_id=outlet_id,
        manufacturer_id=manufacturer_id,
        outlet_esi_id=outlet_esi_id,
    )


@read_router.get(
    "/{outlet_id}/insights/rewards",
    response_model=schemas.OutletInsightSectionResponse,
    dependencies=[Depends(get_current_claims)],
)
def get_outlet_insight_rewards(
    outlet_id: OutletId,
    manufacturer_id: ManufacturerId,
    outlet_esi_id: OutletEsiId,
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Gifts the outlet has given its influencers, summarised by reward class."""

    return OutletReadService(session).get_outlet_insight_rewards(
        outlet_id=outlet_id,
        manufacturer_id=manufacturer_id,
        outlet_esi_id=outlet_esi_id,
    )


@read_router.get(
    "/{outlet_id}/insights/profiler",
    response_model=schemas.OutletInsightProfilerResponse,
    dependencies=[Depends(get_current_claims)],
)
def get_outlet_insight_profiler(
    outlet_id: OutletId,
    manufacturer_id: ManufacturerId,
    outlet_esi_id: OutletEsiId,
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Pre-authenticated link into the outlet's profiler screen, for the app to open in a web
    view. The token is PII-bearing — never log, persist or cache it (R-OUT-37)."""

    response.headers["Cache-Control"] = "no-store"
    return OutletReadService(session).get_outlet_insight_profiler(
        outlet_id=outlet_id,
        manufacturer_id=manufacturer_id,
        outlet_esi_id=outlet_esi_id,
    )


@onboarding_router.post("/owner-otp/request", response_model=schemas.OwnerOtpRequestResponse)
async def request_owner_otp(
    body: schemas.OwnerOtpRequestBody,
    request: HttpRequest,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    """Send an OTP to a prospective firm owner's phone, ahead of ON-3."""

    status_code, payload = OutletOnboardingService(session).request_owner_otp(
        claims=claims,
        body=body,
        idempotency_key=idempotency_key,
        raw_body=await request.body(),
        requester_ip=request.client.host if request.client else None,
    )
    return JSONResponse(status_code=status_code, content=payload)


@onboarding_router.post("/owner-otp/verify", response_model=schemas.OwnerOtpVerifyResponse)
async def verify_owner_otp(
    body: schemas.OwnerOtpVerifyBody,
    request: HttpRequest,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    """Verify the OTP; the resulting `challenge_id` unlocks candidate capture for a short window."""

    status_code, payload = OutletOnboardingService(session).verify_owner_otp(
        claims=claims, body=body, idempotency_key=idempotency_key, raw_body=await request.body(),
    )
    return JSONResponse(status_code=status_code, content=payload)


@onboarding_router.get("/document-lookup", response_model=schemas.DocumentLookupResponse)
def document_lookup(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    gstin: Annotated[str | None, Query(max_length=15)] = None,
    pan: Annotated[str | None, Query(max_length=10)] = None,
) -> dict[str, Any]:
    """ON-1 — pre-fill the firm form from a GSTIN or PAN."""

    del claims
    return OutletOnboardingService(session).lookup_document(gstin=gstin, pan=pan)


@onboarding_router.get("/manufacturer-roles", response_model=schemas.ManufacturerRolesResponse)
def manufacturer_roles(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """ON-2 — the role picker's source."""

    del claims
    return OutletOnboardingService(session).list_manufacturer_roles()


@onboarding_router.get("/industries", response_model=schemas.IndustriesResponse)
def industries(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    del claims
    return OutletOnboardingService(session).list_industries()


@onboarding_router.get("/address/states", response_model=schemas.FirmAddressStatesResponse)
def firm_address_states(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """C-14 — the state step of the firm address form. Not the territory tree: that is
    `/api/v1/org/geography/states`, which is zone-rooted and scoped to assignment."""

    del claims
    return OutletOnboardingService(session).list_firm_address_states()


@onboarding_router.get("/address/districts", response_model=schemas.FirmAddressDistrictsResponse)
def firm_address_districts(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    state_id: Annotated[str, Query(min_length=1, max_length=32)],
) -> dict[str, Any]:
    """C-15 — the district step. `state_id` is required; there is no national district listing."""

    del claims
    return OutletOnboardingService(session).list_firm_address_districts(state_id=state_id)


@onboarding_router.get("/address/options", response_model=schemas.FirmAddressOptionsResponse)
def firm_address_options(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    district_id: Annotated[str, Query(min_length=1, max_length=32)],
    pincode: Annotated[str | None, Query(pattern=r"^\d{6}$")] = None,
    location_id: Annotated[str | None, Query(min_length=1, max_length=32)] = None,
) -> dict[str, Any]:
    """C-16 — the locality and pincode steps for the operational address. `pincode` narrows the
    locality list, `location_id` narrows the pincode list; both may be omitted."""

    del claims
    return OutletOnboardingService(session).list_firm_address_options(
        district_id=district_id, pincode=pincode, location_id=location_id
    )


@onboarding_router.post(
    "/candidates", response_model=schemas.CandidateDetailResponse, status_code=201
)
async def submit_candidate(
    body: schemas.SubmitCandidateBody,
    request: HttpRequest,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    """Capture a firm for the sales person's manager to approve. Humbee is not called here — ON-3
    runs only after the approval is granted, off this request."""

    status_code, payload = OutletOnboardingService(session).submit_candidate(
        claims=claims,
        body=body,
        idempotency_key=idempotency_key,
        raw_body=await request.body(),
        request_id=get_request_id(request),
    )
    return JSONResponse(status_code=status_code, content=payload)


@onboarding_router.get("/candidates", response_model=schemas.CandidateListResponse)
def list_candidates(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    mine_only: Annotated[bool, Query()] = True,
    candidate_status: Annotated[str | None, Query(alias="status", max_length=24)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> dict[str, Any]:
    """The sales person's own captures by default; the whole tenant's when `mine_only=false`.

    Approval visibility itself lives on the approvals inbox, which already has an `outlet` filter.
    """

    return OutletOnboardingService(session).list_candidates(
        claims=claims, mine_only=mine_only, status=candidate_status, limit=limit
    )


@onboarding_router.get(
    "/candidates/{candidate_id}", response_model=schemas.CandidateDetailResponse
)
def get_candidate(
    candidate_id: Annotated[str, Path(min_length=26, max_length=26)],
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return OutletOnboardingService(session).get_candidate(
        claims=claims, candidate_id=candidate_id
    )


router.include_router(read_router)
router.include_router(onboarding_router)

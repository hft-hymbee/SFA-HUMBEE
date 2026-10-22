"""Outlets business logic — onboarding and outlet profile reads.

The owner-phone OTP challenge is this module's own (`outlets_owner_otp_challenges`), never
`identity`'s: the phone belongs to a prospective firm owner, not an `org_employees` row, and
verifying it never issues a session.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from humbee_sfa.core.business_date import business_date_bounds_utc
from humbee_sfa.core.clock import Clock, SystemClock
from humbee_sfa.core.conventions import generate_ulid
from humbee_sfa.core.db import end_read_transaction, transaction
from humbee_sfa.core.deps import AccessTokenClaims
from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.core.security import (
    decrypt_phone,
    encrypt_phone,
    generate_otp_code,
    hash_otp_code,
    hmac_phone,
    verify_otp_code,
)
from humbee_sfa.core.settings import Settings, get_settings
from humbee_sfa.integration.humbee.onboarding import (
    CompanyAddress,
    HumbeeAlreadyRegisteredError,
    HumbeeError,
    HumbeeInvalidDocumentFormatError,
    HumbeeNotFoundError,
    HumbeeOnboardingProvider,
    HumbeeRefusedError,
    IndustryEntry,
    OnboardingUnavailable,
    OnboardRequest,
    OperationalAddress,
    PrimaryIndustry,
    RegisteredAddress,
    RoleEntry,
)
from humbee_sfa.integration.humbee.outlet import (
    HumbeeOutletMasterProvider,
    OutletMasterUnavailable,
    OutletRecord,
    OutletSearchPage,
)
from humbee_sfa.integration.humbee.outlet_insights import (
    HumbeeOutletInsightsProvider,
    InsightSectionName,
    OutletInsightsUnavailable,
)
from humbee_sfa.integration.humbee.seller import (
    HumbeeSellerLinkageProvider,
    SellerLinkageUnavailable,
)
from humbee_sfa.modules.approvals import service as approvals_service
from humbee_sfa.modules.org.scope import OrgResource, ScopeResolver
from humbee_sfa.modules.outlets import policies, repository, schemas
from humbee_sfa.modules.outlets.models import Outlet, OutletOnboardingCandidate
from humbee_sfa.platform.idempotency import IdempotencyService
from humbee_sfa.platform.sms import SmsGateway, get_sms_gateway

logger = structlog.get_logger("humbee_sfa.outlets")


def _bare_phone(phone_e164: str) -> str:
    """Humbee's own `phone_number` field is a bare 10-digit number, unlike our `+91` boundary."""

    return phone_e164.removeprefix("+91")


def _request_fingerprint(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()


def _response_fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ProjectedOutlet:
    local_id: str
    record: OutletRecord


@dataclass(frozen=True)
class LocalOutletSummary:
    local_id: str
    name: str
    district_id: str | None


def _company_address(body: schemas.CompanyAddressBody) -> CompanyAddress:
    return CompanyAddress(
        address_line_1=body.address_line_1,
        address_line_2=body.address_line_2,
        address_line_3=body.address_line_3,
    )


def _operational_address(body: schemas.OperationalAddressBody) -> OperationalAddress:
    return OperationalAddress(
        company_address=_company_address(body.company_address),
        state_id=body.state_id,
        district_id=body.district_id,
        location_id=body.location_id,
        pincode=body.pincode,
    )


def _humbee_unavailable(exc: Exception) -> ApiError:
    """An error envelope and an unparseable response mean the same thing to a caller: Humbee
    could not answer. Only the envelope carries a correlation id."""

    return ApiError(
        503,
        "humbee_unavailable",
        "Humbee is unavailable. Try again shortly.",
        details={"corr_id": getattr(exc, "corr_id", None)},
    )


class OutletOnboardingService:
    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        clock: Clock | None = None,
        sms_gateway: SmsGateway | None = None,
        onboarding_port: HumbeeOnboardingProvider | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._clock = clock or SystemClock()
        self._sms_gateway = sms_gateway or get_sms_gateway(self._settings)
        self._onboarding_port = onboarding_port or HumbeeOnboardingProvider(self._settings)
        self._idempotency = IdempotencyService(session)

    def _stored_replay(
        self, *, tenant_id: str, endpoint: str, idempotency_key: str, raw_body: bytes
    ) -> tuple[int, dict[str, Any]] | None:
        existing = self._idempotency.get(
            tenant_id=tenant_id, endpoint=endpoint, key=idempotency_key
        )
        if existing is None:
            return None
        if not self._idempotency.is_exact_replay(existing, _request_fingerprint(raw_body)):
            raise ApiError(
                409, "idempotency_conflict", "Idempotency key was already used with a different payload."
            )
        return existing.status_code, existing.response_payload

    def _check_idempotency(
        self, *, tenant_id: str, endpoint: str, idempotency_key: str, raw_body: bytes
    ) -> tuple[int, dict[str, Any]] | None:
        self._idempotency.claim(
            tenant_id=tenant_id, endpoint=endpoint, key=idempotency_key
        )
        return self._stored_replay(
            tenant_id=tenant_id,
            endpoint=endpoint,
            idempotency_key=idempotency_key,
            raw_body=raw_body,
        )

    def _store_idempotency(
        self,
        *,
        tenant_id: str,
        endpoint: str,
        idempotency_key: str,
        raw_body: bytes,
        status_code: int,
        payload: dict[str, Any],
        actor_employee_id: str,
        ttl_seconds: int,
    ) -> None:
        now = self._clock.now_utc()
        self._idempotency.save(
            tenant_id=tenant_id,
            endpoint=endpoint,
            key=idempotency_key,
            request_fingerprint=_request_fingerprint(raw_body),
            response_fingerprint=_response_fingerprint(payload),
            status_code=status_code,
            response_payload=payload,
            actor_employee_id=actor_employee_id,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )

    def _ensure_phone_available_for_onboarding(self, *, tenant_id: str, phone_e164: str) -> str:
        phone_hmac = hmac_phone(phone_e164)
        existing = repository.get_active_candidate_by_owner_phone_hmac(
            self._session, tenant_id=tenant_id, owner_phone_hmac=phone_hmac
        )
        if existing is not None:
            raise ApiError(
                409,
                "candidate_already_captured",
                "This owner number is already being onboarded.",
            )
        end_read_transaction(self._session)
        try:
            if self._onboarding_port.is_phone_registered(_bare_phone(phone_e164)):
                raise ApiError(
                    409,
                    "owner_already_on_humbee",
                    "This number already has a Humbee account.",
                )
        except (HumbeeError, OnboardingUnavailable) as exc:
            raise _humbee_unavailable(exc) from exc
        return phone_hmac

    # -- owner-phone OTP ----------------------------------------------------

    def request_owner_otp(
        self,
        *,
        claims: AccessTokenClaims,
        body: schemas.OwnerOtpRequestBody,
        idempotency_key: str,
        raw_body: bytes,
        requester_ip: str | None,
    ) -> tuple[int, dict[str, Any]]:
        endpoint = "/api/v1/outlets/onboarding/owner-otp/request"
        replay = self._stored_replay(
            tenant_id=claims.tenant_id,
            endpoint=endpoint,
            idempotency_key=idempotency_key,
            raw_body=raw_body,
        )
        if replay is not None:
            return replay
        phone_hash = self._ensure_phone_available_for_onboarding(
            tenant_id=claims.tenant_id,
            phone_e164=body.phone_e164,
        )
        with transaction(self._session, commit_on=ApiError):
            replay = self._check_idempotency(
                tenant_id=claims.tenant_id,
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                raw_body=raw_body,
            )
            if replay is not None:
                return replay

            now = self._clock.now_utc()
            live = repository.get_live_challenge(
                self._session, tenant_id=claims.tenant_id, phone_hmac=phone_hash
            )
            if live is not None:
                if live.resend_available_at > now:
                    raise ApiError(
                        429, "otp_resend_cooldown", "Please wait before requesting another OTP."
                    )
                repository.supersede_challenge(live, consumed_at=now)

            code = self._settings.local_otp_override or generate_otp_code(self._settings.otp_length)
            challenge = repository.create_challenge(
                self._session,
                tenant_id=claims.tenant_id,
                phone_hmac=phone_hash,
                code_hash=hash_otp_code(code),
                code_length=self._settings.otp_length,
                issued_at=now,
                expires_at=now + timedelta(seconds=self._settings.otp_ttl_seconds),
                resend_available_at=now
                + timedelta(seconds=self._settings.otp_resend_cooldown_seconds),
                max_attempts=self._settings.otp_max_attempts,
                requester_ip=requester_ip,
                created_by_employee_id=claims.employee_id,
            )
            if not self._settings.otp_skip_verification:
                self._sms_gateway.send_otp(
                    phone_e164=body.phone_e164, code=code, purpose="outlet_owner_verification"
                )
            payload = schemas.OwnerOtpRequestResponse(
                challenge_id=challenge.id,
                phone_e164=body.phone_e164,
                resend_available_at=challenge.resend_available_at,
                expires_at=challenge.expires_at,
            ).model_dump(mode="json")
            self._store_idempotency(
                tenant_id=claims.tenant_id,
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                raw_body=raw_body,
                status_code=200,
                payload=payload,
                actor_employee_id=claims.employee_id,
                ttl_seconds=self._settings.otp_request_idempotency_ttl_seconds,
            )
            return 200, payload

    def verify_owner_otp(
        self,
        *,
        claims: AccessTokenClaims,
        body: schemas.OwnerOtpVerifyBody,
        idempotency_key: str,
        raw_body: bytes,
    ) -> tuple[int, dict[str, Any]]:
        with transaction(self._session, commit_on=ApiError):
            endpoint = "/api/v1/outlets/onboarding/owner-otp/verify"
            replay = self._check_idempotency(
                tenant_id=claims.tenant_id,
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                raw_body=raw_body,
            )
            if replay is not None:
                return replay

            now = self._clock.now_utc()
            challenge = repository.get_challenge(
                self._session, tenant_id=claims.tenant_id, challenge_id=body.challenge_id
            )
            if (
                challenge is None
                or challenge.consumed_at is not None
                or challenge.expires_at <= now
                or challenge.attempts_used >= challenge.max_attempts
            ):
                raise ApiError(409, "challenge_expired", "Challenge has expired.")

            if not (
                self._settings.otp_skip_verification or verify_otp_code(body.code, challenge.code_hash)
            ):
                attempts_used = repository.increment_attempts(challenge)
                if attempts_used >= challenge.max_attempts:
                    raise ApiError(409, "challenge_expired", "Challenge has expired.")
                raise ApiError(
                    400,
                    "invalid_code",
                    "Invalid OTP code.",
                    details={"attempts_remaining": challenge.max_attempts - attempts_used},
                )

            repository.consume_challenge(challenge, consumed_at=now)
            verified_until = now + timedelta(seconds=self._settings.otp_ttl_seconds)
            payload = schemas.OwnerOtpVerifyResponse(
                challenge_id=challenge.id, verified=True, verified_until=verified_until
            ).model_dump(mode="json")
            self._store_idempotency(
                tenant_id=claims.tenant_id,
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                raw_body=raw_body,
                status_code=200,
                payload=payload,
                actor_employee_id=claims.employee_id,
                ttl_seconds=self._settings.otp_verify_idempotency_ttl_seconds,
            )
            return 200, payload

    # -- document lookup / role reads ----------------------------------------------------

    def lookup_document(self, *, gstin: str | None, pan: str | None) -> dict[str, Any]:
        if not gstin and not pan:
            raise ApiError(422, "gstin_or_pan_required", "Provide a GSTIN or a PAN.")
        try:
            result = self._onboarding_port.lookup_document(gstin=gstin, pan=pan)
        except HumbeeNotFoundError as exc:
            raise ApiError(
                404, "document_not_found", "No firm is registered against that GSTIN or PAN."
            ) from exc
        except HumbeeAlreadyRegisteredError as exc:
            raise ApiError(
                409,
                "firm_already_exists",
                "This firm already exists. Ask the Owner/Admin to add you as a member.",
            ) from exc
        except (HumbeeError, OnboardingUnavailable) as exc:
            raise _humbee_unavailable(exc) from exc
        return schemas.DocumentLookupResponse(
            document_type=result.document_type,
            gstin=result.gstin,
            pan=result.pan,
            firm_name=result.firm_name,
            address_line_1=result.address_line_1,
            address_line_2=result.address_line_2,
            state_id=result.state_id,
            state_name=result.state_name,
            district_id=result.district_id,
            district_name=result.district_name,
            pincode=result.pincode,
        ).model_dump(mode="json")

    def list_firm_address_states(self) -> dict[str, Any]:
        try:
            states = self._onboarding_port.list_firm_address_states()
        except (HumbeeError, OnboardingUnavailable) as exc:
            raise _humbee_unavailable(exc) from exc
        return schemas.FirmAddressStatesResponse(
            states=[
                schemas.FirmAddressStateOut(state_id=s.state_id, state_name=s.state_name)
                for s in states
            ]
        ).model_dump(mode="json")

    def list_firm_address_districts(self, *, state_id: str) -> dict[str, Any]:
        try:
            districts = self._onboarding_port.list_firm_address_districts(state_id=state_id)
        except (HumbeeError, OnboardingUnavailable) as exc:
            raise _humbee_unavailable(exc) from exc
        return schemas.FirmAddressDistrictsResponse(
            districts=[
                schemas.FirmAddressDistrictOut(
                    district_id=d.district_id,
                    district_name=d.district_name,
                    state_id=d.state_id,
                    state_name=d.state_name,
                )
                for d in districts
            ]
        ).model_dump(mode="json")

    def list_firm_address_options(
        self, *, district_id: str, pincode: str | None, location_id: str | None
    ) -> dict[str, Any]:
        try:
            options = self._onboarding_port.list_firm_address_options(
                district_id=district_id, pincode=pincode, location_id=location_id
            )
        except (HumbeeError, OnboardingUnavailable) as exc:
            raise _humbee_unavailable(exc) from exc
        return schemas.FirmAddressOptionsResponse(
            district_id=options.district_id,
            locations=[
                schemas.FirmAddressLocationOut(
                    location_id=loc.location_id, location_name=loc.location_name
                )
                for loc in options.locations
            ],
            pincodes=list(options.pincodes),
            as_of=options.as_of,
        ).model_dump(mode="json")

    def list_manufacturer_roles(self) -> dict[str, Any]:
        try:
            results = self._onboarding_port.list_manufacturer_roles()
        except (HumbeeError, OnboardingUnavailable) as exc:
            raise _humbee_unavailable(exc) from exc
        return schemas.ManufacturerRolesResponse(
            manufacturers=[
                schemas.ManufacturerRolesOut(
                    manufacturer_id=manufacturer.manufacturer_id,
                    name=manufacturer.name,
                    vcp_roles=[
                        schemas.ManufacturerRoleOut(
                            role_id=role.role_id,
                            role_name=role.role_name,
                            is_gst_required=role.is_gst_required,
                            is_pan_required=role.is_pan_required,
                            is_fssai_required=role.is_fssai_required,
                        )
                        for role in manufacturer.vcp_roles
                    ],
                    influencer_roles=[
                        schemas.ManufacturerRoleOut(
                            role_id=role.role_id,
                            role_name=role.role_name,
                            is_gst_required=role.is_gst_required,
                            is_pan_required=role.is_pan_required,
                            is_fssai_required=role.is_fssai_required,
                        )
                        for role in manufacturer.influencer_roles
                    ],
                )
                for manufacturer in results
            ]
        ).model_dump(mode="json")

    def list_industries(self) -> dict[str, Any]:
        try:
            industries = self._onboarding_port.list_industries()
        except (HumbeeError, OnboardingUnavailable) as exc:
            raise _humbee_unavailable(exc) from exc
        return schemas.IndustriesResponse(
            industries=[_primary_industry_response(industry) for industry in industries]
        ).model_dump(mode="json")

    # -- candidate capture and manager approval -------------------------------

    def submit_candidate(
        self,
        *,
        claims: AccessTokenClaims,
        body: schemas.SubmitCandidateBody,
        idempotency_key: str,
        raw_body: bytes,
        request_id: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """Capture a firm and route it to the sales person's manager.

        Nothing reaches Humbee here. `onboard-firm` creates a real firm, organization and owner login and
        cannot be undone, so it waits behind the approval — `OutletVerificationAdapter.on_approved`
        makes the call once a manager grants it.

        The owner's phone is verified now, not at approval time: the sales person is standing in
        the shop and the manager is not. The consumed challenge is the evidence, and its TTL is
        checked here rather than surviving into an approval queue.
        """

        endpoint = "/api/v1/outlets/onboarding/candidates"
        replay = self._stored_replay(
            tenant_id=claims.tenant_id,
            endpoint=endpoint,
            idempotency_key=idempotency_key,
            raw_body=raw_body,
        )
        if replay is not None:
            return replay
        phone_hmac = self._ensure_phone_available_for_onboarding(
            tenant_id=claims.tenant_id,
            phone_e164=body.phone_number,
        )
        try:
            with transaction(self._session, commit_on=ApiError):
                replay = self._check_idempotency(
                    tenant_id=claims.tenant_id,
                    endpoint=endpoint,
                    idempotency_key=idempotency_key,
                    raw_body=raw_body,
                )
                if replay is not None:
                    return replay

                now = self._clock.now_utc()
                challenge = repository.get_challenge(
                    self._session, tenant_id=claims.tenant_id, challenge_id=body.challenge_id
                )
                policies.authorize_owner_phone_verified(
                    challenge,
                    phone_hmac=phone_hmac,
                    now=now,
                    ttl_seconds=self._settings.otp_ttl_seconds,
                )
                policies.authorize_owner_date_of_birth(body.date_of_birth, now=now)

                candidate = OutletOnboardingCandidate(
                    id=body.id or generate_ulid(),
                    tenant_id=claims.tenant_id,
                    captured_by_employee_id=claims.employee_id,
                    status="pending_approval",
                    # Placeholder until the engine mints the real id below; the column is NOT NULL
                    # so a candidate with no approval request cannot exist.
                    approval_request_id=body.id or generate_ulid(),
                    company_name=body.company_name,
                    fullname=body.fullname,
                    company_gstin=body.company_gstin,
                    pancard_no=body.pancard_no,
                    owner_phone_hmac=phone_hmac,
                    owner_phone_enc=encrypt_phone(body.phone_number),
                    owner_phone_last4=body.phone_number[-4:],
                    payload=_candidate_payload(body),
                    created_by_employee_id=claims.employee_id,
                )
                candidate.approval_request_id = candidate.id
                repository.insert_candidate(self._session, candidate=candidate)

                approval = approvals_service.create(
                    self._session,
                    tenant_id=claims.tenant_id,
                    subject_type="outlet_verification",
                    subject_id=candidate.id,
                    requester_id=claims.employee_id,
                    clock=self._clock,
                    request_id=request_id,
                )
                candidate.approval_request_id = approval.id
                self._session.flush()

                payload = _candidate_detail_payload(candidate)
                self._store_idempotency(
                    tenant_id=claims.tenant_id,
                    endpoint=endpoint,
                    idempotency_key=idempotency_key,
                    raw_body=raw_body,
                    status_code=201,
                    payload=payload,
                    actor_employee_id=claims.employee_id,
                    ttl_seconds=self._settings.otp_verify_idempotency_ttl_seconds,
                )
        except IntegrityError as exc:
            raise _candidate_conflict(exc) from exc

        logger.info(
            "outlet_candidate_submitted",
            candidate_id=candidate.id,
            approval_request_id=candidate.approval_request_id,
            status=candidate.status,
        )
        return 201, payload

    def list_candidates(
        self, *, claims: AccessTokenClaims, mine_only: bool, status: str | None, limit: int
    ) -> dict[str, Any]:
        rows = repository.list_candidates(
            self._session,
            tenant_id=claims.tenant_id,
            captured_by_employee_id=claims.employee_id if mine_only else None,
            status=status,
            limit=limit,
        )
        return schemas.CandidateListResponse(
            items=[schemas.CandidateListItem(**_candidate_list_payload(row)) for row in rows]
        ).model_dump(mode="json")

    def get_candidate(self, *, claims: AccessTokenClaims, candidate_id: str) -> dict[str, Any]:
        candidate = repository.require_candidate(
            self._session, tenant_id=claims.tenant_id, candidate_id=candidate_id
        )
        return _candidate_detail_payload(candidate)


class OutletReadService:
    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        clock: Clock | None = None,
        outlet_port: HumbeeOutletMasterProvider | None = None,
        seller_port: HumbeeSellerLinkageProvider | None = None,
        insights_port: HumbeeOutletInsightsProvider | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._clock = clock or SystemClock()
        self._outlet_port = outlet_port
        self._seller_port = seller_port
        self._insights_port = insights_port

    def count_onboarded_in_scope(
        self, *, claims: AccessTokenClaims, from_date: date, to_date: date
    ) -> int:
        """Outlets onboarded within the caller's tree and window, for another module's
        (reporting) manager-dashboard rollup."""

        scope = ScopeResolver.resolve_from_claims(claims, OrgResource.EMPLOYEE)
        from_utc, _ = business_date_bounds_utc(from_date, self._settings.day_boundary_hour_ist)
        _, to_utc = business_date_bounds_utc(to_date, self._settings.day_boundary_hour_ist)
        return repository.count_onboarded(self._session, scope=scope, from_utc=from_utc, to_utc=to_utc)

    def _outlets(self) -> HumbeeOutletMasterProvider:
        try:
            return self._outlet_port or HumbeeOutletMasterProvider(self._settings)
        except RuntimeError as exc:
            raise ApiError(
                503, "upstream_unavailable", "Outlet data is unavailable right now."
            ) from exc

    def _sellers(self) -> HumbeeSellerLinkageProvider:
        try:
            return self._seller_port or HumbeeSellerLinkageProvider(self._settings)
        except RuntimeError as exc:
            raise ApiError(
                503, "upstream_unavailable", "Seller data is unavailable right now."
            ) from exc

    def _insights(self) -> HumbeeOutletInsightsProvider:
        try:
            return self._insights_port or HumbeeOutletInsightsProvider(self._settings)
        except RuntimeError as exc:
            raise ApiError(
                503, "upstream_unavailable", "Outlet insights are unavailable right now."
            ) from exc

    def search_outlets(
        self,
        *,
        tenant_id: str,
        district_ids: list[str],
        category_ids: list[str],
        query: str | None,
        actor_employee_id: str | None = None,
        upsert_refs: set[str] | None = None,
    ) -> list[OutletRecord]:
        """Run the outlet list call, then stage the projection upsert — of every record, or only `upsert_refs`
        when the caller needs just those rows. Never commits — the caller owns the transaction,
        so the refreshed outlets land with whatever command state it is writing."""

        try:
            records = self._outlets().search(
                tenant_id=tenant_id,
                district_ids=district_ids,
                category_ids=category_ids,
                query=query,
            )
        except OutletMasterUnavailable as exc:
            raise ApiError(
                503, "upstream_unavailable", "Outlet data is unavailable right now."
            ) from exc
        repository.bulk_upsert(
            self._session,
            tenant_id=tenant_id,
            records=records
            if upsert_refs is None
            else [record for record in records if record.external_id in upsert_refs],
            fetched_at=self._clock.now_utc(),
            actor_employee_id=actor_employee_id,
        )
        return records

    _HUMBEE_OUTLET_SEARCH_DISTRICT_BATCH = 20

    def search_humbee_outlets(
        self, *, tenant_id: str, district_ids: list[str]
    ) -> list[OutletRecord]:
        """Every outlet Humbee has for `district_ids`, straight from the outlet list — no local upsert.
        For the admin unassigned-outlets report, which compares Humbee's own outlet master
        against what SFA has assigned, so it must never write to the local projection as a
        side effect of being generated. A district that cannot be read fails the whole call: a
        report that silently omits a district would understate the unassigned outlets."""

        batch_size = self._HUMBEE_OUTLET_SEARCH_DISTRICT_BATCH
        try:
            return [
                record
                for start in range(0, len(district_ids), batch_size)
                for record in self._outlets().search(
                    tenant_id=tenant_id,
                    district_ids=district_ids[start : start + batch_size],
                    category_ids=[],
                    query=None,
                )
            ]
        except OutletMasterUnavailable as exc:
            raise ApiError(
                503, "upstream_unavailable", "Outlet data is unavailable right now."
            ) from exc

    def search_outlet_page(
        self,
        *,
        tenant_id: str,
        district_ids: list[str],
        category_ids: list[str],
        query: str | None,
        cursor: str | None,
        limit: int,
        actor_employee_id: str | None = None,
    ) -> OutletSearchPage:
        """One page of the outlet list, for a picker the user scrolls. Same staging contract as
        `search_outlets`: the projection upsert commits with the caller's transaction."""

        try:
            page = self._outlets().search_page(
                tenant_id=tenant_id,
                district_ids=district_ids,
                category_ids=category_ids,
                query=query,
                cursor=cursor,
                limit=limit,
            )
        except OutletMasterUnavailable as exc:
            raise ApiError(
                503, "upstream_unavailable", "Outlet data is unavailable right now."
            ) from exc
        repository.bulk_upsert(
            self._session,
            tenant_id=tenant_id,
            records=page.records,
            fetched_at=self._clock.now_utc(),
            actor_employee_id=actor_employee_id,
        )
        return page

    @staticmethod
    def _projection_record(row: Outlet) -> OutletRecord:
        return OutletRecord(
            external_id=row.humbee_outlet_id,
            name=row.name,
            locality=None,
            category=row.humbee_shop_category_id,
            district_external_id=row.humbee_district_id,
            lat=None,
            lng=None,
            gstin=row.gstin,
            pan=row.pan,
            as_of=row.as_of,
        )

    def get_projected_outlets(
        self,
        *,
        tenant_id: str,
        outlet_ids: list[str],
        ids_are_local: bool = False,
    ) -> list[ProjectedOutlet]:
        """Read projection rows in request order. Never calls Humbee."""

        rows = repository.get_projected(
            self._session,
            tenant_id=tenant_id,
            outlet_ids=outlet_ids,
            ids_are_local=ids_are_local,
        )
        return [
            ProjectedOutlet(local_id=row.id, record=self._projection_record(row))
            for row in rows
        ]

    def list_local_outlets(self, *, tenant_id: str) -> list[LocalOutletSummary]:
        """Every locally projected outlet for the tenant, for the admin unassigned-outlets
        report. Never calls Humbee."""

        rows = repository.list_all(self._session, tenant_id=tenant_id)
        return [
            LocalOutletSummary(local_id=row.id, name=row.name, district_id=row.humbee_district_id)
            for row in rows
        ]

    def refresh_outlet(
        self,
        *,
        tenant_id: str,
        outlet_id: str,
        actor_employee_id: str | None = None,
    ) -> OutletRecord | None:
        """Run exactly one outlet detail call and refresh only the fields it owns. Never commits — the
        caller owns the transaction."""

        try:
            record = self._outlets().fetch_by_id(tenant_id=tenant_id, outlet_id=outlet_id)
        except OutletMasterUnavailable as exc:
            raise ApiError(
                503, "upstream_unavailable", "Outlet data is unavailable right now."
            ) from exc
        if record is None:
            return None

        repository.upsert_detail(
            self._session,
            tenant_id=tenant_id,
            record=record,
            fetched_at=self._clock.now_utc(),
            actor_employee_id=actor_employee_id,
        )
        return record

    def get_outlet_detail(self, *, claims: AccessTokenClaims, outlet_id: str) -> dict[str, Any]:
        with transaction(self._session):
            record = self.refresh_outlet(
                tenant_id=claims.tenant_id,
                outlet_id=outlet_id,
                actor_employee_id=claims.employee_id,
            )
        if record is None:
            raise ApiError(404, "outlet_not_found", "Outlet was not found.")

        return schemas.OutletDetailResponse(
            outlet_id=record.external_id,
            name=record.name,
            locality=record.locality,
            district_name=record.district_name,
            contact_person=record.contact_person,
            gstin=record.gstin,
            pan=record.pan,
            registered_address=record.registered_address,
            is_active=record.is_active,
            contact_mobile=record.contact_mobile,
            credit_limit_paise=record.credit_limit_paise,
            credit_outstanding_paise=record.credit_outstanding_paise,
            latitude=float(record.lat) if record.lat is not None else None,
            longitude=float(record.lng) if record.lng is not None else None,
            as_of=record.as_of,
        ).model_dump(mode="json")

    def get_outlet_sellers(self, *, claims: AccessTokenClaims, outlet_id: str) -> dict[str, Any]:
        try:
            snapshot = self._sellers().get_outlet_sellers(
                tenant_id=claims.tenant_id, outlet_id=outlet_id
            )
        except SellerLinkageUnavailable as exc:
            raise ApiError(
                503, "upstream_unavailable", "Seller data is unavailable right now."
            ) from exc

        outlet_address: str | None = None
        try:
            outlet = self._outlets().fetch_by_id(tenant_id=claims.tenant_id, outlet_id=outlet_id)
        except OutletMasterUnavailable:
            outlet = None
        if outlet is not None:
            outlet_address = outlet.registered_address

        return schemas.OutletSellersResponse(
            outlet_id=snapshot.outlet_id,
            outlet_address=outlet_address,
            sellers_by_brand=[
                schemas.OutletSellersByBrandOut(
                    brand_id=brand.brand_id,
                    brand_name=brand.brand_name,
                    sellers_filtered_by_district=brand.filtered_by_district,
                    sellers=[
                        schemas.OutletSellerOut(
                            seller_id=seller.external_id,
                            seller_type=seller.seller_type,
                            name=seller.name,
                            address=seller.address,
                            is_active=seller.is_active,
                            requires_purchase_order=seller.requires_purchase_order,
                            manager_approval_required=seller.manager_approval_required,
                            seller_esi_records=[
                                schemas.EsiRecordOut(
                                    esi_id=esi.esi_id,
                                    esi_code=esi.esi_code,
                                    geographic_info=esi.geographic_info,
                                )
                                for esi in seller.seller_esi_records
                            ],
                            outlet_esi_records=[
                                schemas.EsiRecordOut(
                                    esi_id=esi.esi_id,
                                    esi_code=esi.esi_code,
                                    geographic_info=esi.geographic_info,
                                )
                                for esi in seller.outlet_esi_records
                            ],
                        )
                        for seller in brand.sellers
                    ],
                )
                for brand in snapshot.brands
            ],
            total_count=snapshot.total_count,
            as_of=snapshot.as_of,
        ).model_dump(mode="json")

    def get_outlet_insight_manufacturers(self, *, outlet_id: str) -> dict[str, Any]:
        end_read_transaction(self._session)
        try:
            snapshot = self._insights().get_manufacturers(outlet_id=outlet_id)
        except OutletInsightsUnavailable as exc:
            raise ApiError(
                503, "upstream_unavailable", "Outlet insights are unavailable right now."
            ) from exc
        return schemas.OutletInsightManufacturersResponse(
            outlet_id=outlet_id,
            manufacturers=[
                schemas.OutletInsightManufacturerOut(
                    manufacturer_id=manufacturer.manufacturer_id,
                    manufacturer_name=manufacturer.manufacturer_name,
                    external_system_records=[
                        schemas.OutletInsightEsiRecordOut(
                            esi_id=esi.esi_id,
                            esi_code=esi.esi_code,
                            active=esi.active,
                        )
                        for esi in manufacturer.external_system_records
                    ],
                )
                for manufacturer in snapshot.manufacturers
            ],
            as_of=snapshot.as_of,
        ).model_dump(mode="json")

    def _require_outlet_esi_id(
        self,
        *,
        outlet_id: str,
        manufacturer_id: str,
        outlet_esi_id: str,
    ) -> str:
        # Two upstream round trips follow this call; neither may hold the request's transaction.
        end_read_transaction(self._session)
        try:
            snapshot = self._insights().get_manufacturers(outlet_id=outlet_id)
        except OutletInsightsUnavailable as exc:
            raise ApiError(
                503, "upstream_unavailable", "Outlet insights are unavailable right now."
            ) from exc

        esi_ids = [
            esi.esi_id
            for manufacturer in snapshot.manufacturers
            if manufacturer.manufacturer_id == manufacturer_id
            for esi in manufacturer.external_system_records
        ]
        if outlet_esi_id not in esi_ids:
            raise ApiError(
                422,
                "insights_esi_unresolved",
                "This outlet has no registration with the selected manufacturer.",
            )
        return outlet_esi_id

    def _insight_section(
        self,
        *,
        outlet_id: str,
        manufacturer_id: str,
        outlet_esi_id: str,
        section: InsightSectionName,
    ) -> dict[str, Any]:
        outlet_esi_id = self._require_outlet_esi_id(
            outlet_id=outlet_id,
            manufacturer_id=manufacturer_id,
            outlet_esi_id=outlet_esi_id,
        )
        try:
            result = self._insights().get_section(
                section,
                outlet_id=outlet_id,
                manufacturer_id=manufacturer_id,
                outlet_esi_id=outlet_esi_id,
            )
        except OutletInsightsUnavailable as exc:
            raise ApiError(
                503, "upstream_unavailable", "Outlet insights are unavailable right now."
            ) from exc

        return schemas.OutletInsightSectionResponse(
            outlet_id=outlet_id,
            manufacturer_id=manufacturer_id,
            outlet_esi_id=outlet_esi_id,
            data=result.data,
            as_of=result.as_of,
        ).model_dump(mode="json")

    def get_outlet_insight_benefits(
        self,
        *,
        outlet_id: str,
        manufacturer_id: str,
        outlet_esi_id: str,
    ) -> dict[str, Any]:
        return self._insight_section(
            outlet_id=outlet_id,
            manufacturer_id=manufacturer_id,
            outlet_esi_id=outlet_esi_id,
            section="benefits",
        )

    def get_outlet_insight_performance(
        self,
        *,
        outlet_id: str,
        manufacturer_id: str,
        outlet_esi_id: str,
    ) -> dict[str, Any]:
        return self._insight_section(
            outlet_id=outlet_id,
            manufacturer_id=manufacturer_id,
            outlet_esi_id=outlet_esi_id,
            section="performance",
        )

    def get_outlet_insight_rewards(
        self,
        *,
        outlet_id: str,
        manufacturer_id: str,
        outlet_esi_id: str,
    ) -> dict[str, Any]:
        return self._insight_section(
            outlet_id=outlet_id,
            manufacturer_id=manufacturer_id,
            outlet_esi_id=outlet_esi_id,
            section="rewards",
        )

    def get_outlet_insight_profiler(
        self,
        *,
        outlet_id: str,
        manufacturer_id: str,
        outlet_esi_id: str,
    ) -> dict[str, Any]:
        outlet_esi_id = self._require_outlet_esi_id(
            outlet_id=outlet_id,
            manufacturer_id=manufacturer_id,
            outlet_esi_id=outlet_esi_id,
        )
        try:
            url = self._insights().get_profiler_url(
                outlet_id=outlet_id,
                manufacturer_id=manufacturer_id,
                outlet_esi_id=outlet_esi_id,
            )
        except OutletInsightsUnavailable as exc:
            raise ApiError(
                503, "upstream_unavailable", "Outlet insights are unavailable right now."
            ) from exc

        return schemas.OutletInsightProfilerResponse(
            outlet_id=outlet_id,
            manufacturer_id=manufacturer_id,
            outlet_esi_id=outlet_esi_id,
            url=url,
        ).model_dump(mode="json")


# ---------------------------------------------------------------------------
# Approved-candidate submission to Humbee
# ---------------------------------------------------------------------------


def display_name(candidate: OutletOnboardingCandidate) -> str:
    """`onboard-firm` falls back to `fullname` when there is no trading name — an influencer is a person."""

    return candidate.company_name or candidate.fullname or "Unnamed firm"


def _primary_industry_response(industry: PrimaryIndustry) -> schemas.PrimaryIndustryOut:
    return schemas.PrimaryIndustryOut(
        primary_industry_id=industry.primary_industry_id,
        primary_industry_name=industry.primary_industry_name,
        description=industry.description,
        secondaries=[
            schemas.SecondaryIndustryOut(
                secondary_industry_id=secondary.secondary_industry_id,
                secondary_industry=secondary.secondary_industry,
                description=secondary.description,
            )
            for secondary in industry.secondaries
        ],
    )


def _candidate_payload(body: schemas.SubmitCandidateBody) -> dict[str, Any]:
    """Everything the single `/sfa/v1/onboard` call needs, minus the owner's phone, which is
    encrypted into columns.

    Stored as sent so the call made after approval is the one the sales person composed and the
    owner confirmed — not a re-derivation from fields that may have moved in between. Address
    labels are display-only; Humbee request builders below read the ids.
    """

    return {
        "registered_address": body.registered_address.model_dump(mode="json"),
        "operational_address": body.operational_address.model_dump(mode="json"),
        "date_of_birth": body.date_of_birth.isoformat() if body.date_of_birth else None,
        "latitude": body.latitude,
        "longitude": body.longitude,
        "roles": [role.model_dump(mode="json") for role in body.roles],
        "industries": [industry.model_dump(mode="json") for industry in body.industries],
    }


def _candidate_list_payload(candidate: OutletOnboardingCandidate) -> dict[str, Any]:
    payload = candidate.payload
    return {
        "id": candidate.id,
        "status": candidate.status,
        "display_name": display_name(candidate),
        "company_gstin": candidate.company_gstin,
        "pancard_no": candidate.pancard_no,
        "owner_phone_e164": decrypt_phone(candidate.owner_phone_enc),
        "captured_by_employee_id": candidate.captured_by_employee_id,
        "approval_request_id": candidate.approval_request_id,
        "humbee_company_id": candidate.humbee_company_id,
        "submission_error": candidate.submission_error,
        "industries": [
            schemas.CandidateIndustryOut(**industry).model_dump(mode="json")
            for industry in payload.get("industries", [])
        ],
        "created_at": candidate.created_at,
    }


def _candidate_detail_payload(candidate: OutletOnboardingCandidate) -> dict[str, Any]:
    payload = candidate.payload
    return schemas.CandidateDetailResponse(
        **_candidate_list_payload(candidate),
        registered_address=schemas.RegisteredAddressBody.model_validate(
            payload["registered_address"]
        ),
        operational_address=schemas.OperationalAddressBody.model_validate(
            payload["operational_address"]
        ),
        roles=[schemas.CandidateRoleOut(**role) for role in payload.get("roles", [])],
        version=candidate.version,
    ).model_dump(mode="json")


def _candidate_conflict(exc: IntegrityError) -> ApiError:
    """A second capture of a firm that is already queued, approved or live."""

    detail = str(getattr(exc, "orig", exc))
    if (
        "uq_outlets_candidates_gstin" in detail
        or "uq_outlets_candidates_pan" in detail
        or "uq_outlets_candidates_phone" in detail
    ):
        return ApiError(
            409,
            "candidate_already_captured",
            "This firm is already being onboarded.",
        )
    raise exc


def _operational_address_from(payload: dict[str, Any]) -> OperationalAddress:
    address = payload["operational_address"]
    lines = address["company_address"]
    return OperationalAddress(
        company_address=CompanyAddress(
            address_line_1=lines["address_line_1"],
            address_line_2=lines.get("address_line_2"),
            address_line_3=lines.get("address_line_3"),
        ),
        state_id=address["state_id"],
        district_id=address["district_id"],
        location_id=address["location_id"],
        pincode=address["pincode"],
    )


def _single_call_onboard_request(candidate: OutletOnboardingCandidate) -> OnboardRequest:
    payload = candidate.payload
    registered = payload["registered_address"]
    lines = registered["company_address"]
    date_of_birth = payload.get("date_of_birth")
    return OnboardRequest(
        phone_number=_bare_phone(decrypt_phone(candidate.owner_phone_enc)),
        registered_address=RegisteredAddress(
            company_address=CompanyAddress(
                address_line_1=lines["address_line_1"],
                address_line_2=lines.get("address_line_2"),
                address_line_3=lines.get("address_line_3"),
            ),
            state_id=registered["state_id"],
            district_id=registered["district_id"],
        ),
        operational_address=_operational_address_from(payload),
        company_name=candidate.company_name,
        company_gstin=candidate.company_gstin,
        pancard_no=candidate.pancard_no,
        fullname=candidate.fullname,
        date_of_birth=date.fromisoformat(date_of_birth) if date_of_birth else None,
        latitude=payload.get("latitude"),
        longitude=payload.get("longitude"),
        onboarded_by=candidate.captured_by_employee_id,
        roles=tuple(
            RoleEntry(
                manufacturer_id=str(role["manufacturer_id"]),
                firm_role_id=str(role["firm_role_id"]),
            )
            for role in payload.get("roles", [])
        ),
        industries=tuple(
            IndustryEntry(
                primary_industry_id=str(industry["primary_industry_id"]),
                secondary_industry_id=str(industry["secondary_industry_id"]),
                role_name=str(industry["role_name"]),
            )
            for industry in payload.get("industries", [])
        ),
    )


def submit_candidate_to_humbee(
    session: Session,
    *,
    candidate: OutletOnboardingCandidate,
    clock: Clock,
    settings: Settings | None = None,
) -> None:
    """Call Humbee onboarding once from inside the approval's own transaction."""

    port = HumbeeOnboardingProvider(settings or get_settings())
    try:
        company_id = port.onboard(_single_call_onboard_request(candidate))
    except HumbeeAlreadyRegisteredError as exc:
        _mark_submission_failed(
            candidate,
            exc,
            phase="already_registered",
            user_message=(
                "This firm is already registered on Humbee."
                if exc.error_code == "090"
                else "Owner phone is already registered on Humbee."
            ),
        )
        return
    except HumbeeInvalidDocumentFormatError as exc:
        _mark_submission_failed(
            candidate,
            exc,
            phase="invalid_document_format",
            user_message="Humbee rejected the GSTIN/PAN format.",
        )
        return
    except HumbeeRefusedError as exc:
        _mark_submission_failed(
            candidate,
            exc,
            phase="humbee_refused",
            user_message=str(exc) or "Humbee could not onboard this firm.",
        )
        return
    except (HumbeeError, OnboardingUnavailable) as exc:
        _mark_submission_failed(
            candidate,
            exc,
            phase="onboard",
            user_message="Humbee could not onboard this firm.",
        )
        return

    candidate.humbee_company_id = company_id
    try:
        # Quarantined in a savepoint: uq_outlets_candidates_company refuses a firm another
        # candidate already owns, and letting that reach the caller's commit would take the
        # manager's approval decision down with it.
        with session.begin_nested():
            session.flush()
    except IntegrityError as exc:
        session.expire(candidate)
        _mark_submission_failed(
            candidate,
            exc,
            phase="reconcile_company_id",
            user_message="Humbee could not onboard this firm.",
        )
        return

    candidate.status = "submitted"
    candidate.submitted_at = clock.now_utc()
    candidate.submission_error = None
    candidate.version += 1
    session.flush()
    logger.info(
        "outlet_candidate_submitted_to_humbee",
        candidate_id=candidate.id,
        roles=len(candidate.payload.get("roles", [])),
        industries=len(candidate.payload.get("industries", [])),
    )


def _mark_submission_failed(
    candidate: OutletOnboardingCandidate,
    exc: Exception,
    *,
    phase: str,
    user_message: str,
) -> None:
    candidate.status = "submission_failed"
    candidate.submission_error = user_message
    candidate.version += 1
    logger.warning(
        "outlet_candidate_submission_failed",
        candidate_id=candidate.id,
        corr_id=getattr(exc, "corr_id", None),
        phase=phase,
    )

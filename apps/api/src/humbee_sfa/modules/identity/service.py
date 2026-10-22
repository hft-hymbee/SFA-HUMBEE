"""Identity business logic."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any

import structlog
from sqlalchemy.orm import Session

from humbee_sfa.core.clock import Clock, SystemClock
from humbee_sfa.core.db import transaction
from humbee_sfa.core.deps import AccessTokenClaims
from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.core.security import (
    generate_otp_code,
    generate_refresh_token,
    hash_otp_code,
    hash_refresh_token,
    hmac_phone,
    issue_access_token,
    verify_otp_code,
)
from humbee_sfa.core.settings import Settings, get_settings
from humbee_sfa.modules.identity import events, policies, repository, schemas
from humbee_sfa.modules.org import service as org_service
from humbee_sfa.platform.domain_events import DomainEventPublisher
from humbee_sfa.platform.idempotency import IdempotencyService
from humbee_sfa.platform.rate_limits import RateLimitService
from humbee_sfa.platform.sms import SmsGateway, get_sms_gateway

logger = structlog.get_logger("humbee_sfa.identity")


def _request_fingerprint(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()


def _response_fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _profile_payload(employee: org_service.EmployeeProjection) -> dict[str, Any]:
    return schemas.MeResponse(
        id=employee.id,
        first_name=employee.first_name,
        full_name=employee.full_name,
        phone_e164=employee.phone_e164,
        role=employee.role_code,
        status=employee.status,
    ).model_dump(mode="json")


class IdentityService:
    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        clock: Clock | None = None,
        sms_gateway: SmsGateway | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._clock = clock or SystemClock()
        self._sms_gateway = sms_gateway or get_sms_gateway(self._settings)
        self._idempotency = IdempotencyService(session)
        self._rate_limits = RateLimitService(session)
        self._event_publisher = DomainEventPublisher(session, self._clock)
        if self._settings.otp_skip_verification:
            logger.warning(
                "otp_verification_bypass_enabled",
                environment=self._settings.environment,
            )

    def _hour_window_start(self):
        now = self._clock.now_utc()
        return now.replace(minute=0, second=0, microsecond=0)

    def _reject_rate_limited(
        self,
        *,
        phone_hmac: str,
        aggregate_id: str,
        employee_id: str | None,
        purpose: str,
        requester_ip: str | None,
        user_agent: str | None,
        now,
    ) -> None:
        """R-IDN-07: one audit row, one domain event, one stable 429 for every limit."""

        repository.record_audit_event(
            self._session,
            tenant_id=self._settings.tenant_id,
            employee_id=employee_id,
            phone_hmac=phone_hmac,
            event_type=events.OTP_RATE_LIMITED,
            outcome="rate_limited",
            occurred_at=now,
            requester_ip=requester_ip,
            user_agent=user_agent,
            day_boundary_hour_ist=self._settings.day_boundary_hour_ist,
        )
        events.publish_auth_event(
            self._event_publisher,
            tenant_id=self._settings.tenant_id,
            event_type=events.OTP_RATE_LIMITED,
            aggregate_type="otp_challenge",
            aggregate_id=aggregate_id,
            payload={"purpose": purpose},
            actor_employee_id=employee_id,
            occurred_at=now,
        )
        raise ApiError(429, "otp_rate_limited", "Too many OTP requests. Try again shortly.")

    def _enforce_verify_limits(
        self,
        *,
        challenge,
        requester_ip: str | None,
        user_agent: str | None,
        now,
    ) -> None:
        """R-IDN-07 on the verify side: throttle per challenge, per phone and per IP.

        `max_attempts` alone only bounds one challenge; without these an attacker can keep
        requesting fresh challenges and spend the whole attempt budget of each.
        """

        window_start = self._hour_window_start()
        limits = (
            ("otp_verify_challenge", challenge.id, self._settings.otp_verify_rate_limit_per_challenge),
            (
                "otp_verify_phone",
                challenge.phone_e164_hmac,
                self._settings.otp_rate_limit_per_phone_per_hour,
            ),
            (
                "otp_verify_ip",
                requester_ip or "unknown",
                self._settings.otp_rate_limit_per_ip_per_hour,
            ),
        )
        allowed = True
        for scope, counter_key, max_hits in limits:
            permitted, _ = self._rate_limits.increment_and_check(
                tenant_id=self._settings.tenant_id,
                scope=scope,
                counter_key=counter_key,
                window_start=window_start,
                window_seconds=3600,
                max_hits=max_hits,
                actor_employee_id=challenge.employee_id,
            )
            allowed = allowed and permitted
        if not allowed:
            self._reject_rate_limited(
                phone_hmac=challenge.phone_e164_hmac,
                aggregate_id=challenge.id,
                employee_id=challenge.employee_id,
                purpose=challenge.purpose,
                requester_ip=requester_ip,
                user_agent=user_agent,
                now=now,
            )

    def _check_idempotency(
        self, *, endpoint: str, idempotency_key: str, raw_body: bytes
    ) -> tuple[int, dict[str, Any]] | None:
        request_fp = _request_fingerprint(raw_body)
        existing = self._idempotency.get(
            tenant_id=self._settings.tenant_id,
            endpoint=endpoint,
            key=idempotency_key,
        )
        if existing is None:
            return None
        if not self._idempotency.is_exact_replay(existing, request_fp):
            raise ApiError(
                409,
                "idempotency_conflict",
                "Idempotency key was already used with a different payload.",
            )
        return existing.status_code, existing.response_payload

    def _store_idempotency(
        self,
        *,
        endpoint: str,
        idempotency_key: str,
        raw_body: bytes,
        status_code: int,
        payload: dict[str, Any],
        actor_employee_id: str | None = None,
        expires_at: datetime | None = None,
    ) -> None:
        request_fp = _request_fingerprint(raw_body)
        self._idempotency.save(
            tenant_id=self._settings.tenant_id,
            endpoint=endpoint,
            key=idempotency_key,
            request_fingerprint=request_fp,
            response_fingerprint=_response_fingerprint(payload),
            status_code=status_code,
            response_payload=payload,
            actor_employee_id=actor_employee_id,
            expires_at=expires_at,
        )

    def request_otp(
        self,
        *,
        phone_e164: str | None,
        purpose: str,
        client_device_id: str,
        requester_ip: str | None,
        user_agent: str | None,
        idempotency_key: str,
        raw_body: bytes,
    ) -> tuple[int, dict[str, Any]]:
        with transaction(self._session, commit_on=ApiError):
            return self._request_otp(
                phone_e164=phone_e164,
                purpose=purpose,
                client_device_id=client_device_id,
                requester_ip=requester_ip,
                user_agent=user_agent,
                idempotency_key=idempotency_key,
                raw_body=raw_body,
            )

    def _request_otp(
        self,
        *,
        phone_e164: str | None,
        purpose: str,
        client_device_id: str,
        requester_ip: str | None,
        user_agent: str | None,
        idempotency_key: str,
        raw_body: bytes,
    ) -> tuple[int, dict[str, Any]]:
        replay = self._check_idempotency(
            endpoint="/api/v1/auth/otp/request",
            idempotency_key=idempotency_key,
            raw_body=raw_body,
        )
        if replay is not None:
            return replay

        now = self._clock.now_utc()
        # `purpose`/`phone_e164` shape is already guaranteed by schemas.OtpRequestBody.
        resolved_phone = phone_e164
        employee: org_service.EmployeeProjection | None = None
        if purpose == "login":
            employee = org_service.find_employee_by_phone(
                self._session,
                tenant_id=self._settings.tenant_id,
                phone_e164=resolved_phone,
            )
        else:
            device = repository.get_device_by_client_id(
                self._session,
                tenant_id=self._settings.tenant_id,
                client_device_id=client_device_id,
            )
            if device is None:
                raise ApiError(404, "phone_not_registered", "Phone number is not registered.")
            employee = org_service.get_employee(
                self._session,
                tenant_id=self._settings.tenant_id,
                employee_id=device.employee_id,
            )
            resolved_phone = employee.phone_e164

        if resolved_phone is None:
            raise ApiError(404, "phone_not_registered", "Phone number is not registered.")

        phone_hash = hmac_phone(resolved_phone)

        live = repository.get_live_challenge(
            self._session,
            tenant_id=self._settings.tenant_id,
            phone_hmac=phone_hash,
            purpose=purpose,
        )
        if live is not None:
            repository.supersede_challenge(live, consumed_at=now)

        code = self._settings.local_otp_override or generate_otp_code(
            self._settings.otp_length
        )
        challenge = repository.create_challenge(
            self._session,
            tenant_id=self._settings.tenant_id,
            phone_hmac=phone_hash,
            employee_id=employee.id if employee else None,
            purpose=purpose,
            code_hash=hash_otp_code(code),
            code_length=self._settings.otp_length,
            issued_at=now,
            expires_at=now + timedelta(seconds=self._settings.otp_ttl_seconds),
            resend_available_at=now
            + timedelta(seconds=self._settings.otp_resend_cooldown_seconds),
            max_attempts=self._settings.otp_max_attempts,
            requester_ip=requester_ip,
        )
        repository.record_audit_event(
            self._session,
            tenant_id=self._settings.tenant_id,
            employee_id=employee.id if employee else None,
            phone_hmac=phone_hash,
            event_type=events.OTP_REQUESTED,
            outcome="sent" if employee is not None else "phone_not_registered",
            occurred_at=now,
            requester_ip=requester_ip,
            user_agent=user_agent,
            day_boundary_hour_ist=self._settings.day_boundary_hour_ist,
        )
        events.publish_auth_event(
            self._event_publisher,
            tenant_id=self._settings.tenant_id,
            event_type=events.OTP_REQUESTED,
            aggregate_type="otp_challenge",
            aggregate_id=challenge.id,
            payload={"purpose": purpose},
            actor_employee_id=employee.id if employee else None,
            occurred_at=now,
        )

        if employee is None:
            raise ApiError(404, "phone_not_registered", "Phone number is not registered.")

        if employee.status != "active":
            # Do not send an OTP for a disabled login. Consume this short-lived
            # challenge so the client can immediately open its manager-contact
            # screen without allowing it to be used for authentication.
            repository.consume_challenge(challenge, consumed_at=now)
            repository.record_audit_event(
                self._session,
                tenant_id=self._settings.tenant_id,
                employee_id=employee.id,
                phone_hmac=phone_hash,
                event_type=events.LOGIN_BLOCKED_DEACTIVATED,
                outcome="blocked",
                occurred_at=now,
                requester_ip=requester_ip,
                user_agent=user_agent,
                day_boundary_hour_ist=self._settings.day_boundary_hour_ist,
            )
            events.publish_auth_event(
                self._event_publisher,
                tenant_id=self._settings.tenant_id,
                event_type=events.LOGIN_BLOCKED_DEACTIVATED,
                aggregate_type="otp_challenge",
                aggregate_id=challenge.id,
                payload={"employee_id": employee.id},
                actor_employee_id=employee.id,
                occurred_at=now,
            )
            raise ApiError(
                403,
                "account_deactivated",
                "Account is deactivated.",
                details={"challenge_id": challenge.id},
            )

        if not self._settings.otp_skip_verification:
            self._sms_gateway.send_otp(phone_e164=resolved_phone, code=code, purpose=purpose)
        payload = schemas.OtpRequestResponse(
            challenge_id=challenge.id,
            phone_e164=resolved_phone,
            resend_available_at=challenge.resend_available_at,
            expires_at=challenge.expires_at,
        ).model_dump(mode="json")
        self._store_idempotency(
            endpoint="/api/v1/auth/otp/request",
            idempotency_key=idempotency_key,
            raw_body=raw_body,
            status_code=200,
            payload=payload,
            actor_employee_id=employee.id,
            expires_at=now + timedelta(seconds=self._settings.otp_request_idempotency_ttl_seconds),
        )
        return 200, payload

    def verify_otp(
        self,
        *,
        challenge_id: str,
        code: str,
        purpose: str,
        client_device_id: str,
        platform_: str,
        app_version: str,
        requester_ip: str | None,
        user_agent: str | None,
        idempotency_key: str,
        raw_body: bytes,
    ) -> tuple[int, dict[str, Any]]:
        with transaction(self._session, commit_on=ApiError):
            return self._verify_otp(
                challenge_id=challenge_id,
                code=code,
                purpose=purpose,
                client_device_id=client_device_id,
                platform_=platform_,
                app_version=app_version,
                requester_ip=requester_ip,
                user_agent=user_agent,
                idempotency_key=idempotency_key,
                raw_body=raw_body,
            )

    def _verify_otp(
        self,
        *,
        challenge_id: str,
        code: str,
        purpose: str,
        client_device_id: str,
        platform_: str,
        app_version: str,
        requester_ip: str | None,
        user_agent: str | None,
        idempotency_key: str,
        raw_body: bytes,
    ) -> tuple[int, dict[str, Any]]:
        replay = self._check_idempotency(
            endpoint="/api/v1/auth/otp/verify",
            idempotency_key=idempotency_key,
            raw_body=raw_body,
        )
        if replay is not None:
            return replay

        now = self._clock.now_utc()
        challenge = repository.get_challenge(
            self._session, tenant_id=self._settings.tenant_id, challenge_id=challenge_id
        )
        if challenge is None or challenge.purpose != purpose:
            raise ApiError(409, "challenge_expired", "Challenge has expired.")
        if challenge.consumed_at is not None:
            raise ApiError(409, "challenge_expired", "Challenge has expired.")
        if challenge.expires_at <= now or challenge.attempts_used >= challenge.max_attempts:
            raise ApiError(409, "challenge_expired", "Challenge has expired.")

        self._enforce_verify_limits(
            challenge=challenge,
            requester_ip=requester_ip,
            user_agent=user_agent,
            now=now,
        )

        if not (self._settings.otp_skip_verification or verify_otp_code(code, challenge.code_hash)):
            attempts_used = repository.increment_attempts(challenge)
            attempts_remaining = max(challenge.max_attempts - attempts_used, 0)
            repository.record_audit_event(
                self._session,
                tenant_id=self._settings.tenant_id,
                employee_id=challenge.employee_id,
                phone_hmac=challenge.phone_e164_hmac,
                event_type=events.OTP_FAILED,
                outcome="invalid_code",
                occurred_at=now,
                requester_ip=requester_ip,
                user_agent=user_agent,
                day_boundary_hour_ist=self._settings.day_boundary_hour_ist,
            )
            events.publish_auth_event(
                self._event_publisher,
                tenant_id=self._settings.tenant_id,
                event_type=events.OTP_FAILED,
                aggregate_type="otp_challenge",
                aggregate_id=challenge.id,
                payload={"attempts_used": attempts_used},
                actor_employee_id=challenge.employee_id,
                occurred_at=now,
            )
            if attempts_used >= challenge.max_attempts:
                raise ApiError(409, "challenge_expired", "Challenge has expired.")
            raise ApiError(
                400,
                "invalid_code",
                "Invalid OTP code.",
                details={"attempts_remaining": attempts_remaining},
            )

        repository.consume_challenge(challenge, consumed_at=now)
        if challenge.employee_id is None:
            raise ApiError(404, "phone_not_registered", "Phone number is not registered.")

        employee = org_service.get_employee(
            self._session,
            tenant_id=self._settings.tenant_id,
            employee_id=challenge.employee_id,
        )
        if employee.status != "active":
            repository.record_audit_event(
                self._session,
                tenant_id=self._settings.tenant_id,
                employee_id=employee.id,
                phone_hmac=challenge.phone_e164_hmac,
                event_type=events.LOGIN_BLOCKED_DEACTIVATED,
                outcome="blocked",
                occurred_at=now,
                requester_ip=requester_ip,
                user_agent=user_agent,
                day_boundary_hour_ist=self._settings.day_boundary_hour_ist,
            )
            events.publish_auth_event(
                self._event_publisher,
                tenant_id=self._settings.tenant_id,
                event_type=events.LOGIN_BLOCKED_DEACTIVATED,
                aggregate_type="otp_challenge",
                aggregate_id=challenge.id,
                payload={"employee_id": employee.id},
                actor_employee_id=employee.id,
                occurred_at=now,
            )
            raise ApiError(403, "account_deactivated", "Account is deactivated.")

        device = repository.upsert_device(
            self._session,
            tenant_id=self._settings.tenant_id,
            employee_id=employee.id,
            client_device_id=client_device_id,
            platform=platform_,
            app_version=app_version,
            now=now,
        )

        refresh_token = generate_refresh_token()
        refresh_hash = hash_refresh_token(refresh_token)
        refresh_expires_at = now + timedelta(seconds=self._settings.refresh_token_ttl_seconds)
        access_token, access_expires_at = issue_access_token(
            employee_id=employee.id,
            session_id="",
            device_id=device.id,
            role=employee.role_code,
            tenant_id=self._settings.tenant_id,
            ttl_seconds=self._settings.access_token_ttl_seconds,
        )

        event_type = events.SESSION_CREATED
        if purpose == "reauth":
            existing_session = repository.get_live_session_by_device(
                self._session,
                tenant_id=self._settings.tenant_id,
                device_id=device.id,
                now=now,
            )
            if existing_session is None:
                raise ApiError(401, "refresh_invalid", "No active session available for re-auth.")
            token, access_expires_at = issue_access_token(
                employee_id=employee.id,
                session_id=existing_session.id,
                device_id=device.id,
                role=employee.role_code,
                tenant_id=self._settings.tenant_id,
                ttl_seconds=self._settings.access_token_ttl_seconds,
            )
            repository.rotate_session_tokens(
                existing_session,
                refresh_token_hash=refresh_hash,
                refresh_token_expires_at=refresh_expires_at,
                access_token_expires_at=access_expires_at,
                now=now,
            )
            access_token = token
            session_row = existing_session
            event_type = events.REAUTH_SUCCEEDED
        else:
            session_row = repository.create_session(
                self._session,
                tenant_id=self._settings.tenant_id,
                employee_id=employee.id,
                device_id=device.id,
                access_token_expires_at=access_expires_at,
                refresh_token_hash=refresh_hash,
                refresh_token_expires_at=refresh_expires_at,
                last_seen_at=now,
            )
            access_token, access_expires_at = issue_access_token(
                employee_id=employee.id,
                session_id=session_row.id,
                device_id=device.id,
                role=employee.role_code,
                tenant_id=self._settings.tenant_id,
                ttl_seconds=self._settings.access_token_ttl_seconds,
            )
            session_row.access_token_expires_at = access_expires_at

        repository.record_audit_event(
            self._session,
            tenant_id=self._settings.tenant_id,
            employee_id=employee.id,
            phone_hmac=challenge.phone_e164_hmac,
            event_type=events.OTP_VERIFIED,
            outcome="success",
            occurred_at=now,
            requester_ip=requester_ip,
            user_agent=user_agent,
            day_boundary_hour_ist=self._settings.day_boundary_hour_ist,
        )
        events.publish_auth_event(
            self._event_publisher,
            tenant_id=self._settings.tenant_id,
            event_type=event_type,
            aggregate_type="session",
            aggregate_id=session_row.id,
            payload={"purpose": purpose, "device_id": device.id},
            actor_employee_id=employee.id,
            occurred_at=now,
        )

        payload = schemas.TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self._settings.access_token_ttl_seconds,
            profile=_profile_payload(employee),
        ).model_dump(mode="json")
        self._store_idempotency(
            endpoint="/api/v1/auth/otp/verify",
            idempotency_key=idempotency_key,
            raw_body=raw_body,
            status_code=200,
            payload=payload,
            actor_employee_id=employee.id,
            expires_at=now + timedelta(seconds=self._settings.otp_verify_idempotency_ttl_seconds),
        )
        return 200, payload

    def refresh_token(
        self,
        *,
        refresh_token: str,
        client_device_id: str,
        requester_ip: str | None,
        user_agent: str | None,
        idempotency_key: str,
        raw_body: bytes,
    ) -> tuple[int, dict[str, Any]]:
        with transaction(self._session, commit_on=ApiError):
            return self._refresh_token(
                refresh_token=refresh_token,
                client_device_id=client_device_id,
                requester_ip=requester_ip,
                user_agent=user_agent,
                idempotency_key=idempotency_key,
                raw_body=raw_body,
            )

    def _refresh_token(
        self,
        *,
        refresh_token: str,
        client_device_id: str,
        requester_ip: str | None,
        user_agent: str | None,
        idempotency_key: str,
        raw_body: bytes,
    ) -> tuple[int, dict[str, Any]]:
        replay = self._check_idempotency(
            endpoint="/api/v1/auth/token/refresh",
            idempotency_key=idempotency_key,
            raw_body=raw_body,
        )
        if replay is not None:
            return replay

        now = self._clock.now_utc()
        row = repository.get_session_by_refresh_hash(
            self._session,
            tenant_id=self._settings.tenant_id,
            refresh_token_hash=hash_refresh_token(refresh_token),
        )
        if row is None or row.revoked_at is not None:
            raise ApiError(401, "refresh_invalid", "Refresh token is invalid.")
        if row.refresh_token_expires_at <= now:
            repository.revoke_session(row, revoked_at=now, reason="refresh_expired")
            raise ApiError(401, "refresh_invalid", "Refresh token is invalid.")

        device = repository.get_device_by_client_id(
            self._session,
            tenant_id=self._settings.tenant_id,
            client_device_id=client_device_id,
        )
        if device is None or device.id != row.device_id:
            repository.revoke_session(row, revoked_at=now, reason="token_reuse")
            raise ApiError(401, "refresh_invalid", "Refresh token is invalid.")

        employee = org_service.get_employee(
            self._session,
            tenant_id=self._settings.tenant_id,
            employee_id=row.employee_id,
        )
        employee_phone = employee.phone_e164
        new_refresh_token = generate_refresh_token()
        new_refresh_hash = hash_refresh_token(new_refresh_token)
        new_refresh_expires_at = now + timedelta(seconds=self._settings.refresh_token_ttl_seconds)
        access_token, access_expires_at = issue_access_token(
            employee_id=employee.id,
            session_id=row.id,
            device_id=row.device_id,
            role=employee.role_code,
            tenant_id=self._settings.tenant_id,
            ttl_seconds=self._settings.access_token_ttl_seconds,
        )
        repository.rotate_session_tokens(
            row,
            refresh_token_hash=new_refresh_hash,
            refresh_token_expires_at=new_refresh_expires_at,
            access_token_expires_at=access_expires_at,
            now=now,
        )
        repository.record_audit_event(
            self._session,
            tenant_id=self._settings.tenant_id,
            employee_id=employee.id,
            phone_hmac=hmac_phone(employee_phone),
            event_type=events.SESSION_REFRESHED,
            outcome="success",
            occurred_at=now,
            requester_ip=requester_ip,
            user_agent=user_agent,
            day_boundary_hour_ist=self._settings.day_boundary_hour_ist,
        )
        events.publish_auth_event(
            self._event_publisher,
            tenant_id=self._settings.tenant_id,
            event_type=events.SESSION_REFRESHED,
            aggregate_type="session",
            aggregate_id=row.id,
            payload={"device_id": row.device_id},
            actor_employee_id=employee.id,
            occurred_at=now,
        )
        payload = schemas.TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=self._settings.access_token_ttl_seconds,
            profile=None,
        ).model_dump(mode="json", exclude_none=True)
        self._store_idempotency(
            endpoint="/api/v1/auth/token/refresh",
            idempotency_key=idempotency_key,
            raw_body=raw_body,
            status_code=200,
            payload=payload,
            actor_employee_id=employee.id,
            expires_at=now + timedelta(seconds=self._settings.refresh_idempotency_ttl_seconds),
        )
        return 200, payload

    def logout(
        self,
        *,
        refresh_token: str,
        requester_ip: str | None,
        user_agent: str | None,
    ) -> tuple[int, dict[str, Any]]:
        with transaction(self._session, commit_on=ApiError):
            return self._logout(
                refresh_token=refresh_token,
                requester_ip=requester_ip,
                user_agent=user_agent,
            )

    def _logout(
        self,
        *,
        refresh_token: str,
        requester_ip: str | None,
        user_agent: str | None,
    ) -> tuple[int, dict[str, Any]]:
        now = self._clock.now_utc()
        row = repository.get_session_by_refresh_hash(
            self._session,
            tenant_id=self._settings.tenant_id,
            refresh_token_hash=hash_refresh_token(refresh_token),
        )
        if row is not None and row.revoked_at is None:
            repository.revoke_session(row, revoked_at=now, reason="user_logout")
            try:
                employee_phone = org_service.get_employee_phone_e164(
                    self._session,
                    tenant_id=self._settings.tenant_id,
                    employee_id=row.employee_id,
                )
                phone_hash = hmac_phone(employee_phone)
            except ApiError:
                phone_hash = hmac_phone("unknown")
            repository.record_audit_event(
                self._session,
                tenant_id=self._settings.tenant_id,
                employee_id=row.employee_id,
                phone_hmac=phone_hash,
                event_type=events.LOGOUT,
                outcome="success",
                occurred_at=now,
                requester_ip=requester_ip,
                user_agent=user_agent,
                day_boundary_hour_ist=self._settings.day_boundary_hour_ist,
            )
            events.publish_auth_event(
                self._event_publisher,
                tenant_id=self._settings.tenant_id,
                event_type=events.LOGOUT,
                aggregate_type="session",
                aggregate_id=row.id,
                payload={"device_id": row.device_id},
                actor_employee_id=row.employee_id,
                occurred_at=now,
            )

        return 204, {}

    def get_me(self, *, claims: AccessTokenClaims) -> dict[str, Any]:
        employee = org_service.get_employee(
            self._session,
            tenant_id=claims.tenant_id,
            employee_id=claims.employee_id,
        )
        return _profile_payload(employee)

    def get_manager_contact(self, *, challenge_id: str) -> dict[str, Any]:
        now = self._clock.now_utc()
        challenge = repository.get_challenge(
            self._session, tenant_id=self._settings.tenant_id, challenge_id=challenge_id
        )
        policies.authorize_manager_contact(
            challenge,
            challenge_id,
            now=now,
            ttl_seconds=self._settings.otp_ttl_seconds,
        )
        assert challenge is not None
        assert challenge.employee_id is not None
        contact = org_service.get_manager_contact(
            self._session,
            tenant_id=self._settings.tenant_id,
            employee_id=challenge.employee_id,
        )
        if contact is None:
            raise ApiError(404, "not_found", "Manager contact is unavailable.")
        manager_name, manager_phone = contact
        return schemas.ManagerContactResponse(
            manager_name=manager_name,
            manager_phone_e164=manager_phone,
        ).model_dump(mode="json")

    def introspect_session(self, *, claims: AccessTokenClaims) -> dict[str, Any]:
        device = repository.get_device_by_id(
            self._session,
            tenant_id=claims.tenant_id,
            device_id=claims.device_id,
        )
        if device is None:
            raise ApiError(404, "not_found", "Session device is unavailable.")
        return schemas.SessionIntrospectResponse(
            device_id=claims.device_id,
            issued_at=claims.issued_at,
            access_token_expires_at=claims.access_token_expires_at,
            platform=device.platform,
        ).model_dump(mode="json")

    # -- live-session enforcement (R-IDN-08, R-IDN-10, R-IDN-21) -----------

    def enforce_live_session(self, *, claims: AccessTokenClaims) -> None:
        """A valid signature is not a live session.

        Runs on every authenticated request: the token's session row must still exist and
        be unrevoked, and its employee must still be active. A deactivated employee's
        sessions are revoked here, inside this request, so the very next call after an
        admin deactivation resolves to `account_deactivated` (R-IDN-21) instead of waiting
        for the access token to expire.
        """

        row = repository.get_session_by_id(
            self._session, tenant_id=claims.tenant_id, session_id=claims.session_id
        )
        if row is None or row.employee_id != claims.employee_id:
            raise ApiError(
                401,
                "refresh_invalid",
                "Session is no longer valid.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if row.revoked_at is not None:
            # R-IDN-10: a revoked session never re-auths in place; it forces a full login,
            # except when the reason is deactivation, which is terminal (S-A4).
            if row.revocation_reason == "deactivated":
                raise ApiError(403, "account_deactivated", "Account is deactivated.")
            raise ApiError(
                401,
                "refresh_invalid",
                "Session is no longer valid.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            employee = org_service.get_employee(
                self._session, tenant_id=claims.tenant_id, employee_id=claims.employee_id
            )
            is_active = employee.status == "active"
        except ApiError:
            # The employee master no longer exposes them as a live employee.
            is_active = False
        if not is_active:
            self.revoke_all_sessions_for_employee(
                tenant_id=claims.tenant_id,
                employee_id=claims.employee_id,
                reason="deactivated",
            )
            raise ApiError(403, "account_deactivated", "Account is deactivated.")

    def revoke_all_sessions_for_employee(
        self,
        *,
        tenant_id: str,
        employee_id: str,
        reason: str = "deactivated",
        actor_employee_id: str | None = None,
    ) -> int:
        """Public entry point for revoking one employee's sessions (R-IDN-21).

        Owns its transaction, so `org` can call it straight after a deactivation and see
        the revocation land with the deactivation itself.
        """

        with transaction(self._session, commit_on=ApiError):
            now = self._clock.now_utc()
            rows = repository.list_live_sessions_for_employee(
                self._session, tenant_id=tenant_id, employee_id=employee_id
            )
            for row in rows:
                repository.revoke_session(row, revoked_at=now, reason=reason)
                events.publish_auth_event(
                    self._event_publisher,
                    tenant_id=tenant_id,
                    event_type=events.LOGIN_BLOCKED_DEACTIVATED,
                    aggregate_type="session",
                    aggregate_id=row.id,
                    payload={"reason": reason, "device_id": row.device_id},
                    actor_employee_id=actor_employee_id or employee_id,
                    occurred_at=now,
                )
            if rows:
                repository.record_audit_event(
                    self._session,
                    tenant_id=tenant_id,
                    employee_id=employee_id,
                    phone_hmac=hmac_phone("unknown"),
                    event_type=events.LOGIN_BLOCKED_DEACTIVATED,
                    outcome="sessions_revoked",
                    occurred_at=now,
                    requester_ip=None,
                    user_agent=None,
                    day_boundary_hour_ist=self._settings.day_boundary_hour_ist,
                )
                logger.info(
                    "sessions_revoked",
                    employee_id=employee_id,
                    reason=reason,
                    session_count=len(rows),
                )
            return len(rows)

    def get_auth_config(self) -> dict[str, Any]:
        return schemas.AuthConfigResponse(
            otp_length=self._settings.otp_length,
            resend_cooldown_seconds=self._settings.otp_resend_cooldown_seconds,
            otp_ttl_seconds=self._settings.otp_ttl_seconds,
            max_attempts=self._settings.otp_max_attempts,
        ).model_dump(mode="json")



def assert_live_session(session: Session, claims: AccessTokenClaims) -> None:
    """The session guard `core.deps` calls on every authenticated request.

    Registered from `identity.router` at import time so `core` never imports a module and
    every module's authenticated routes get the check without wiring it themselves.
    """

    IdentityService(session).enforce_live_session(claims=claims)

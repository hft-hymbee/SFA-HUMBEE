"""Identity repositories for OTP, device, session, and audit tables."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from humbee_sfa.core.business_date import to_business_date
from humbee_sfa.modules.identity.models import AuthAuditEvent, Device, OtpChallenge, Session


def create_challenge(
    session: OrmSession,
    *,
    tenant_id: str,
    phone_hmac: str,
    employee_id: str | None,
    purpose: str,
    code_hash: str,
    code_length: int,
    issued_at: datetime,
    expires_at: datetime,
    resend_available_at: datetime,
    max_attempts: int,
    requester_ip: str | None,
) -> OtpChallenge:
    challenge = OtpChallenge(
        tenant_id=tenant_id,
        phone_e164_hmac=phone_hmac,
        employee_id=employee_id,
        purpose=purpose,
        code_hash=code_hash,
        code_length=code_length,
        issued_at=issued_at,
        expires_at=expires_at,
        resend_available_at=resend_available_at,
        attempts_used=0,
        max_attempts=max_attempts,
        requester_ip=requester_ip,
    )
    session.add(challenge)
    session.flush()
    return challenge


def get_challenge(
    session: OrmSession, *, tenant_id: str, challenge_id: str
) -> OtpChallenge | None:
    stmt = select(OtpChallenge).where(
        OtpChallenge.tenant_id == tenant_id,
        OtpChallenge.id == challenge_id,
        OtpChallenge.is_active.is_(True),
    )
    return session.execute(stmt).scalar_one_or_none()


def get_live_challenge(
    session: OrmSession, *, tenant_id: str, phone_hmac: str, purpose: str
) -> OtpChallenge | None:
    stmt = (
        select(OtpChallenge)
        .where(
            OtpChallenge.tenant_id == tenant_id,
            OtpChallenge.phone_e164_hmac == phone_hmac,
            OtpChallenge.purpose == purpose,
            OtpChallenge.consumed_at.is_(None),
            OtpChallenge.is_active.is_(True),
        )
        .order_by(OtpChallenge.issued_at.desc())
    )
    return session.execute(stmt).scalars().first()


def supersede_challenge(challenge: OtpChallenge, *, consumed_at: datetime) -> None:
    challenge.consumed_at = consumed_at


def consume_challenge(challenge: OtpChallenge, *, consumed_at: datetime) -> None:
    challenge.consumed_at = consumed_at


def increment_attempts(challenge: OtpChallenge) -> int:
    challenge.attempts_used = challenge.attempts_used + 1
    return challenge.attempts_used


def upsert_device(
    session: OrmSession,
    *,
    tenant_id: str,
    employee_id: str,
    client_device_id: str,
    platform: str,
    app_version: str,
    now: datetime,
) -> Device:
    existing = get_device_by_client_id(session, tenant_id=tenant_id, client_device_id=client_device_id)
    if existing is not None:
        existing.employee_id = employee_id
        existing.platform = platform
        existing.app_version = app_version
        existing.last_seen_at = now
        return existing

    device = Device(
        tenant_id=tenant_id,
        employee_id=employee_id,
        client_device_id=client_device_id,
        platform=platform,
        app_version=app_version,
        first_seen_at=now,
        last_seen_at=now,
    )
    session.add(device)
    session.flush()
    return device


def get_device_by_client_id(
    session: OrmSession, *, tenant_id: str, client_device_id: str
) -> Device | None:
    stmt = select(Device).where(
        Device.tenant_id == tenant_id,
        Device.client_device_id == client_device_id,
        Device.is_active.is_(True),
    )
    return session.execute(stmt).scalar_one_or_none()


def get_device_by_id(session: OrmSession, *, tenant_id: str, device_id: str) -> Device | None:
    stmt = select(Device).where(
        Device.tenant_id == tenant_id,
        Device.id == device_id,
        Device.is_active.is_(True),
    )
    return session.execute(stmt).scalar_one_or_none()


def create_session(
    session: OrmSession,
    *,
    tenant_id: str,
    employee_id: str,
    device_id: str,
    access_token_expires_at: datetime,
    refresh_token_hash: str,
    refresh_token_expires_at: datetime,
    last_seen_at: datetime,
) -> Session:
    row = Session(
        tenant_id=tenant_id,
        employee_id=employee_id,
        device_id=device_id,
        access_token_expires_at=access_token_expires_at,
        refresh_token_hash=refresh_token_hash,
        refresh_token_expires_at=refresh_token_expires_at,
        last_seen_at=last_seen_at,
    )
    session.add(row)
    session.flush()
    return row


def get_live_session_by_device(
    session: OrmSession, *, tenant_id: str, device_id: str, now: datetime
) -> Session | None:
    stmt = (
        select(Session)
        .where(
            Session.tenant_id == tenant_id,
            Session.device_id == device_id,
            Session.revoked_at.is_(None),
            Session.refresh_token_expires_at > now,
            Session.is_active.is_(True),
        )
        .order_by(Session.created_at.desc())
    )
    return session.execute(stmt).scalars().first()


def get_session_by_id(session: OrmSession, *, tenant_id: str, session_id: str) -> Session | None:
    """Primary-key lookup used by the per-request live-session guard."""

    stmt = select(Session).where(
        Session.tenant_id == tenant_id,
        Session.id == session_id,
        Session.is_active.is_(True),
    )
    return session.execute(stmt).scalar_one_or_none()


def list_live_sessions_for_employee(
    session: OrmSession, *, tenant_id: str, employee_id: str
) -> list[Session]:
    stmt = select(Session).where(
        Session.tenant_id == tenant_id,
        Session.employee_id == employee_id,
        Session.revoked_at.is_(None),
        Session.is_active.is_(True),
    )
    return list(session.execute(stmt).scalars().all())


def get_session_by_refresh_hash(
    session: OrmSession, *, tenant_id: str, refresh_token_hash: str
) -> Session | None:
    stmt = select(Session).where(
        Session.tenant_id == tenant_id,
        Session.refresh_token_hash == refresh_token_hash,
        Session.is_active.is_(True),
    )
    return session.execute(stmt).scalar_one_or_none()


def revoke_session(row: Session, *, revoked_at: datetime, reason: str) -> None:
    row.revoked_at = revoked_at
    row.revocation_reason = reason


def rotate_session_tokens(
    row: Session,
    *,
    refresh_token_hash: str,
    refresh_token_expires_at: datetime,
    access_token_expires_at: datetime,
    now: datetime,
) -> None:
    row.refresh_token_hash = refresh_token_hash
    row.refresh_token_expires_at = refresh_token_expires_at
    row.access_token_expires_at = access_token_expires_at
    row.last_seen_at = now
    row.revoked_at = None
    row.revocation_reason = None


def record_audit_event(
    session: OrmSession,
    *,
    tenant_id: str,
    employee_id: str | None,
    phone_hmac: str,
    event_type: str,
    outcome: str,
    occurred_at: datetime,
    requester_ip: str | None,
    user_agent: str | None,
    day_boundary_hour_ist: int,
) -> AuthAuditEvent:
    row = AuthAuditEvent(
        tenant_id=tenant_id,
        employee_id=employee_id,
        phone_e164_hmac=phone_hmac,
        event_type=event_type,
        outcome=outcome,
        occurred_at=occurred_at,
        received_at=occurred_at,
        business_date=to_business_date(occurred_at, day_boundary_hour_ist),
        requester_ip=requester_ip,
        user_agent=user_agent,
    )
    session.add(row)
    return row


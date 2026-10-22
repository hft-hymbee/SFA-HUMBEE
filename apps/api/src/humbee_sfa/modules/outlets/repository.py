"""Tenant-scoped persistence for the outlet projection, the owner-phone OTP challenge and the
firm-onboarding candidate."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from humbee_sfa.core.conventions import generate_ulid
from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.integration.humbee.outlet import OutletRecord
from humbee_sfa.modules.org.scope import ScopeContext, employee_scope_condition
from humbee_sfa.modules.outlets.models import (
    Outlet,
    OutletOnboardingCandidate,
    OwnerOtpChallenge,
)


def get_projected(
    session: Session, *, tenant_id: str, outlet_ids: list[str], ids_are_local: bool = False
) -> list[Outlet]:
    """Return projection rows in request order, dropping ids with no row.

    `ids_are_local` selects between the local ULID and the Humbee id; beat membership holds the
    former, everything coming off a C-2 response the latter.
    """

    requested = list(dict.fromkeys(outlet_ids))
    if not requested:
        return []
    id_column = Outlet.id if ids_are_local else Outlet.humbee_outlet_id
    rows = session.execute(
        select(Outlet).where(
            Outlet.tenant_id == tenant_id,
            id_column.in_(requested),
            Outlet.is_active.is_(True),
        )
    ).scalars()
    by_requested_id = {(row.id if ids_are_local else row.humbee_outlet_id): row for row in rows}
    return [by_requested_id[outlet_id] for outlet_id in requested if outlet_id in by_requested_id]


def list_all(session: Session, *, tenant_id: str) -> list[Outlet]:
    """Every locally projected outlet for the tenant, for the admin unassigned-outlets report.
    Never calls Humbee — reads the projection as it currently stands."""

    stmt = select(Outlet).where(Outlet.tenant_id == tenant_id, Outlet.is_active.is_(True))
    return list(session.execute(stmt).scalars().all())


def bulk_upsert(
    session: Session,
    *,
    tenant_id: str,
    records: list[OutletRecord],
    fetched_at: datetime,
    actor_employee_id: str | None,
) -> None:
    """Upsert one C-2 page as the latest authoritative projection."""

    records_by_id = {record.external_id: record for record in records}
    if not records_by_id:
        return

    values = [
        {
            "id": generate_ulid(),
            "tenant_id": tenant_id,
            "humbee_outlet_id": record.external_id,
            "name": record.name,
            "gstin": record.gstin,
            "pan": record.pan,
            "humbee_shop_category_id": record.category,
            "humbee_district_id": record.district_external_id,
            "as_of": record.as_of,
            "fetched_at": fetched_at,
            "created_by_employee_id": actor_employee_id,
            "is_active": True,
        }
        for record in records_by_id.values()
    ]
    statement = insert(Outlet).values(values)
    session.execute(
        statement.on_conflict_do_update(
            constraint="uq_outlets_tenant_humbee_outlet",
            set_={
                "name": statement.excluded.name,
                "gstin": statement.excluded.gstin,
                "pan": statement.excluded.pan,
                "humbee_shop_category_id": statement.excluded.humbee_shop_category_id,
                "humbee_district_id": statement.excluded.humbee_district_id,
                "as_of": statement.excluded.as_of,
                "fetched_at": statement.excluded.fetched_at,
                "updated_at": fetched_at,
                "is_active": True,
                "deactivated_at": None,
                "deactivated_by": None,
            },
            where=statement.excluded.as_of >= Outlet.as_of,
        )
    )


def upsert_detail(
    session: Session,
    *,
    tenant_id: str,
    record: OutletRecord,
    fetched_at: datetime,
    actor_employee_id: str | None,
) -> None:
    """Apply only fields C-3 owns, preserving C-2 district and category values."""

    statement = insert(Outlet).values(
        id=generate_ulid(),
        tenant_id=tenant_id,
        humbee_outlet_id=record.external_id,
        name=record.name,
        gstin=record.gstin,
        pan=record.pan,
        humbee_shop_category_id=None,
        humbee_district_id=None,
        as_of=record.as_of,
        fetched_at=fetched_at,
        created_by_employee_id=actor_employee_id,
        is_active=True,
    )
    session.execute(
        statement.on_conflict_do_update(
            constraint="uq_outlets_tenant_humbee_outlet",
            set_={
                "name": statement.excluded.name,
                "gstin": statement.excluded.gstin,
                "pan": statement.excluded.pan,
                "as_of": statement.excluded.as_of,
                "fetched_at": statement.excluded.fetched_at,
                "updated_at": fetched_at,
            },
            where=statement.excluded.as_of >= Outlet.as_of,
        )
    )


def create_challenge(
    session: Session,
    *,
    tenant_id: str,
    phone_hmac: str,
    code_hash: str,
    code_length: int,
    issued_at: datetime,
    expires_at: datetime,
    resend_available_at: datetime,
    max_attempts: int,
    requester_ip: str | None,
    created_by_employee_id: str,
) -> OwnerOtpChallenge:
    challenge = OwnerOtpChallenge(
        tenant_id=tenant_id,
        phone_e164_hmac=phone_hmac,
        code_hash=code_hash,
        code_length=code_length,
        issued_at=issued_at,
        expires_at=expires_at,
        resend_available_at=resend_available_at,
        attempts_used=0,
        max_attempts=max_attempts,
        requester_ip=requester_ip,
        created_by_employee_id=created_by_employee_id,
    )
    session.add(challenge)
    session.flush()
    return challenge


def get_challenge(session: Session, *, tenant_id: str, challenge_id: str) -> OwnerOtpChallenge | None:
    stmt = select(OwnerOtpChallenge).where(
        OwnerOtpChallenge.tenant_id == tenant_id,
        OwnerOtpChallenge.id == challenge_id,
        OwnerOtpChallenge.is_active.is_(True),
    )
    return session.execute(stmt).scalar_one_or_none()


def get_live_challenge(
    session: Session, *, tenant_id: str, phone_hmac: str
) -> OwnerOtpChallenge | None:
    stmt = (
        select(OwnerOtpChallenge)
        .where(
            OwnerOtpChallenge.tenant_id == tenant_id,
            OwnerOtpChallenge.phone_e164_hmac == phone_hmac,
            OwnerOtpChallenge.consumed_at.is_(None),
            OwnerOtpChallenge.is_active.is_(True),
        )
        .order_by(OwnerOtpChallenge.issued_at.desc())
    )
    return session.execute(stmt).scalars().first()


def supersede_challenge(challenge: OwnerOtpChallenge, *, consumed_at: datetime) -> None:
    challenge.consumed_at = consumed_at


def consume_challenge(challenge: OwnerOtpChallenge, *, consumed_at: datetime) -> None:
    challenge.consumed_at = consumed_at


def increment_attempts(challenge: OwnerOtpChallenge) -> int:
    challenge.attempts_used = challenge.attempts_used + 1
    return challenge.attempts_used


# ---------------------------------------------------------------------------
# Onboarding candidates
# ---------------------------------------------------------------------------


def get_candidate(
    session: Session, *, tenant_id: str, candidate_id: str
) -> OutletOnboardingCandidate | None:
    return session.execute(
        select(OutletOnboardingCandidate).where(
            OutletOnboardingCandidate.tenant_id == tenant_id,
            OutletOnboardingCandidate.id == candidate_id,
        )
    ).scalar_one_or_none()


def get_active_candidate_by_owner_phone_hmac(
    session: Session, *, tenant_id: str, owner_phone_hmac: str
) -> OutletOnboardingCandidate | None:
    return session.execute(
        select(OutletOnboardingCandidate).where(
            OutletOnboardingCandidate.tenant_id == tenant_id,
            OutletOnboardingCandidate.owner_phone_hmac == owner_phone_hmac,
            (
                OutletOnboardingCandidate.status.in_(("pending_approval", "approved", "submitted"))
                | OutletOnboardingCandidate.humbee_company_id.is_not(None)
            ),
        )
    ).scalar_one_or_none()


def require_candidate(
    session: Session, *, tenant_id: str, candidate_id: str
) -> OutletOnboardingCandidate:
    candidate = get_candidate(session, tenant_id=tenant_id, candidate_id=candidate_id)
    if candidate is None:
        raise ApiError(404, "candidate_not_found", "Onboarding candidate was not found.")
    return candidate


def list_candidates(
    session: Session,
    *,
    tenant_id: str,
    captured_by_employee_id: str | None,
    status: str | None,
    limit: int,
) -> list[OutletOnboardingCandidate]:
    stmt = select(OutletOnboardingCandidate).where(
        OutletOnboardingCandidate.tenant_id == tenant_id
    )
    if captured_by_employee_id is not None:
        stmt = stmt.where(
            OutletOnboardingCandidate.captured_by_employee_id == captured_by_employee_id
        )
    if status is not None:
        stmt = stmt.where(OutletOnboardingCandidate.status == status)
    stmt = stmt.order_by(OutletOnboardingCandidate.created_at.desc()).limit(limit)
    return list(session.execute(stmt).scalars().all())


def insert_candidate(
    session: Session, *, candidate: OutletOnboardingCandidate
) -> OutletOnboardingCandidate:
    session.add(candidate)
    session.flush()
    return candidate


def count_onboarded(
    session: Session, *, scope: ScopeContext, from_utc: datetime, to_utc: datetime
) -> int:
    """Candidates successfully onboarded to Humbee (`status='submitted'`, which a check
    constraint on this table guarantees carries a real `humbee_company_id`) within `scope`'s
    tree, by submission instant."""

    value = session.scalar(
        select(func.count(OutletOnboardingCandidate.id)).where(
            OutletOnboardingCandidate.tenant_id == scope.tenant_id,
            employee_scope_condition(scope, OutletOnboardingCandidate.captured_by_employee_id),
            OutletOnboardingCandidate.status == "submitted",
            OutletOnboardingCandidate.submitted_at >= from_utc,
            OutletOnboardingCandidate.submitted_at < to_utc,
        )
    )
    return int(value or 0)

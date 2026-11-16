"""Tenant-scoped persistence for the outlet projection, the owner-phone OTP challenge and the
firm-onboarding candidate."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from humbee_sfa.core.conventions import generate_ulid
from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.integration.humbee.outlet import OutletRecord
from humbee_sfa.modules.org.scope import ScopeContext, employee_scope_condition
from humbee_sfa.modules.outlets.models import (
    Outlet,
    OutletBusinessProfilerHistory,
    OutletOnboardingCandidate,
    OwnerOtpChallenge,
)


def get_projected(
    session: Session, *, tenant_id: str, outlet_ids: list[str], ids_are_local: bool = False
) -> list[Outlet]:
    """Return projection rows in request order, dropping ids with no row.

    `ids_are_local` selects between the local ULID and the Humbee id; beat membership holds the
    former, everything coming off an outlet list response the latter.
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
    """Upsert one outlet list page as the latest authoritative projection."""

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
    """Apply only fields the outlet detail call owns, preserving the outlet list's district and
    category values."""

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


def record_business_profiler(
    session: Session,
    *,
    tenant_id: str,
    pct_by_outlet: dict[str, int | None],
    as_of: datetime,
    source: str = "fetch",
    for_business_date: date | None = None,
) -> None:
    """Store values on existing projection rows (never overwriting a newer one) and append each
    change to the history. A `push`/`fetch` value equal to the one already in effect at `as_of`
    adds no history row; a `day_close` pull always does, since it is the day's frozen evidence."""

    if not pct_by_outlet:
        return
    rows = session.execute(
        select(Outlet).where(
            Outlet.tenant_id == tenant_id, Outlet.humbee_outlet_id.in_(list(pct_by_outlet))
        )
    ).scalars()
    for row in rows:
        if row.business_profiler_as_of is None or row.business_profiler_as_of <= as_of:
            row.business_profiler_pct = pct_by_outlet[row.humbee_outlet_id]
            row.business_profiler_as_of = as_of

    changed = dict(pct_by_outlet)
    if source != "day_close":
        in_effect = _latest_history(
            session, tenant_id=tenant_id, outlet_ids=list(changed), at_or_before=as_of
        )
        changed = {
            outlet_id: pct
            for outlet_id, pct in changed.items()
            if outlet_id not in in_effect or in_effect[outlet_id].pct != pct
        }
    if changed:
        session.execute(
            insert(OutletBusinessProfilerHistory),
            [
                {
                    "id": generate_ulid(),
                    "tenant_id": tenant_id,
                    "humbee_outlet_id": outlet_id,
                    "pct": pct,
                    "effective_at": as_of,
                    "source": source,
                    "for_business_date": for_business_date,
                }
                for outlet_id, pct in changed.items()
            ],
        )


def _latest_history(
    session: Session, *, tenant_id: str, outlet_ids: list[str], at_or_before: datetime | None
) -> dict[str, OutletBusinessProfilerHistory]:
    if not outlet_ids:
        return {}
    history = OutletBusinessProfilerHistory
    conditions = [history.tenant_id == tenant_id, history.humbee_outlet_id.in_(outlet_ids)]
    if at_or_before is not None:
        conditions.append(history.effective_at <= at_or_before)
    rows = session.execute(
        select(history)
        .where(*conditions)
        .distinct(history.humbee_outlet_id)
        .order_by(history.humbee_outlet_id, history.effective_at.desc(), history.id.desc())
    ).scalars()
    return {row.humbee_outlet_id: row for row in rows}


def business_profiler_as_of(
    session: Session,
    *,
    tenant_id: str,
    outlet_ids: list[str],
    business_date: date,
    day_end_utc: datetime,
) -> dict[str, int | None]:
    """Each outlet's % at the end of `business_date` (`None`: no % known, which counts as not filled).

    The latest value in effect at `day_end_utc`, unless the day-close pull for that date recorded
    one and nothing else arrived for the outlet between the day's end and that pull: then the pull
    wins, which repairs a push lost during the day without letting a change made after midnight
    leak back into the day.
    """

    refs = list(dict.fromkeys(outlet_ids))
    if not refs:
        return {}
    history = OutletBusinessProfilerHistory
    in_effect = _latest_history(session, tenant_id=tenant_id, outlet_ids=refs, at_or_before=day_end_utc)
    day_close = {
        row.humbee_outlet_id: row
        for row in session.execute(
            select(history)
            .where(
                history.tenant_id == tenant_id,
                history.humbee_outlet_id.in_(refs),
                history.source == "day_close",
                history.for_business_date == business_date,
            )
            .distinct(history.humbee_outlet_id)
            .order_by(history.humbee_outlet_id, history.effective_at, history.id)
        ).scalars()
    }
    after_end: dict[str, list[datetime]] = {}
    if day_close:
        for outlet_id, effective_at in session.execute(
            select(history.humbee_outlet_id, history.effective_at).where(
                history.tenant_id == tenant_id,
                history.humbee_outlet_id.in_(list(day_close)),
                history.source != "day_close",
                history.effective_at > day_end_utc,
                history.effective_at <= max(row.effective_at for row in day_close.values()),
            )
        ):
            after_end.setdefault(outlet_id, []).append(effective_at)

    result: dict[str, int | None] = {}
    for ref in refs:
        pull = day_close.get(ref)
        if pull is not None and not any(at <= pull.effective_at for at in after_end.get(ref, [])):
            result[ref] = pull.pct
        else:
            row = in_effect.get(ref)
            result[ref] = row.pct if row is not None else None
    return result


def current_business_profiler(
    session: Session, *, tenant_id: str, outlet_ids: list[str]
) -> dict[str, int | None]:
    """The latest known % per outlet (`None` when none is known)."""

    refs = list(dict.fromkeys(outlet_ids))
    rows = _latest_history(session, tenant_id=tenant_id, outlet_ids=refs, at_or_before=None)
    return {ref: (rows[ref].pct if ref in rows else None) for ref in refs}


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

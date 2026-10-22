"""Beats persistence. Thin, scoped, no business decisions.

Actor-facing reads take a resolved `ScopeContext` from `org.scope` (beats are activity data: SELF
for the owning Sales Person, OWN_TREE for their manager, ORG for Admin). Engine-adjacent
reads used by the approval adapters (`beats/adapter.py`) take `tenant_id` only, mirroring
`leave/adapter.py`'s use of `internal_routing_scope`: the engine has already resolved visibility of
the approval request, and the deciding actor is not the beat's owner.

`geo_scope["districts"]` is deliberately **omitted** (not stored as `[]`) while a draft has no
district selected yet: `ck_beats_versions_districts_chk` evaluates `jsonb_array_length(NULL)` as
NULL, which Postgres CHECK constraints treat as satisfied, whereas an explicit `[]` evaluates to
`0 >= 1` and is rejected. This lets a brand-new draft (no district selected yet)
exist without lying about having a district.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, select, text
from sqlalchemy.orm import Session

from humbee_sfa.modules.beats.models.beat import Beat
from humbee_sfa.modules.beats.models.beat_activation_event import BeatActivationEvent
from humbee_sfa.modules.beats.models.beat_edit_request import BeatEditRequest
from humbee_sfa.modules.beats.models.beat_outlet import BeatOutlet
from humbee_sfa.modules.beats.models.beat_version import BeatVersion
from humbee_sfa.modules.org.scope import ScopeContext, apply_scope

STATUS_PREDICATES: dict[str, Any] = {
    # "Pending" covers a first-time submission awaiting approval *and* an approved
    # beat with a submitted edit awaiting approval — never an unsubmitted edit branch, which has
    # a `draft_version_id` too but no pending edit request.
    "approved": Beat.lifecycle_state == "approved",
    "pending": (Beat.lifecycle_state == "pending_approval")
    | (
        (Beat.lifecycle_state == "approved")
        & select(BeatEditRequest.id)
        .where(
            BeatEditRequest.beat_id == Beat.id,
            BeatEditRequest.state == "pending_approval",
        )
        .exists()
    ),
    "draft": Beat.lifecycle_state == "draft",
}


def build_geo_scope_json(
    *, zones: list[str], states: list[str], districts: list[str], cats: list[str], as_of: datetime,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "zones": zones, "states": states, "cats": cats, "as_of": as_of.isoformat(),
    }
    if districts:
        payload["districts"] = districts
    return payload


def read_districts(geo_scope: dict[str, Any]) -> list[str]:
    return list(geo_scope.get("districts") or [])


# ---------------------------------------------------------------------------
# Scoped reads (beats are activity data)
# ---------------------------------------------------------------------------


def _scoped_beats(scope: ScopeContext) -> Select[tuple[Beat]]:
    return apply_scope(
        select(Beat), scope, tenant_column=Beat.tenant_id, employee_id_column=Beat.owner_employee_id
    ).where(Beat.is_active.is_(True))


def get_beat(session: Session, *, scope: ScopeContext, beat_id: str) -> Beat | None:
    stmt = _scoped_beats(scope).where(Beat.id == beat_id)
    return session.execute(stmt).scalar_one_or_none()


def get_beat_for_update(
    session: Session, *, scope: ScopeContext, beat_id: str
) -> Beat | None:
    stmt = _scoped_beats(scope).where(Beat.id == beat_id).with_for_update()
    return session.execute(stmt).scalar_one_or_none()


def list_beats(
    session: Session, *, scope: ScopeContext, status_filter: str | None, limit: int | None, offset: int
) -> list[Beat]:
    stmt = _scoped_beats(scope).order_by(Beat.updated_at.desc()).limit(limit).offset(offset)
    if status_filter and status_filter in STATUS_PREDICATES:
        stmt = stmt.where(STATUS_PREDICATES[status_filter])
    return list(session.execute(stmt).scalars().all())


def list_active_approved_beats(session: Session, *, scope: ScopeContext) -> list[Beat]:
    stmt = _scoped_beats(scope).where(
        Beat.lifecycle_state == "approved",
        Beat.activation_state == "active",
        Beat.current_version_id.isnot(None),
    )
    return list(session.execute(stmt).scalars().all())


def count_facets(session: Session, *, scope: ScopeContext) -> dict[str, int]:
    facets: dict[str, int] = {"all": 0}
    base = _scoped_beats(scope)
    facets["all"] = int(session.execute(select(func.count()).select_from(base.subquery())).scalar_one())
    for key, predicate in STATUS_PREDICATES.items():
        stmt = select(func.count()).select_from(base.where(predicate).subquery())
        facets[key] = int(session.execute(stmt).scalar_one())
    return facets


def get_beat_by_id(session: Session, *, tenant_id: str, beat_id: str) -> Beat | None:
    """Tenant-only lookup for the approval adapters (`beats/adapter.py`) — the engine has already
    resolved visibility of the approval request, and the deciding actor is not the beat's owner."""

    stmt = select(Beat).where(Beat.tenant_id == tenant_id, Beat.id == beat_id, Beat.is_active.is_(True))
    return session.execute(stmt).scalar_one_or_none()


def get_version(
    session: Session, *, tenant_id: str, version_id: str | None
) -> BeatVersion | None:
    """`version_id` is nullable because a beat may have neither a current nor a draft version."""

    if version_id is None:
        return None
    stmt = select(BeatVersion).where(
        BeatVersion.tenant_id == tenant_id, BeatVersion.id == version_id, BeatVersion.is_active.is_(True)
    )
    return session.execute(stmt).scalar_one_or_none()


def list_versions(session: Session, *, tenant_id: str, version_ids: list[str]) -> list[BeatVersion]:
    if not version_ids:
        return []
    stmt = select(BeatVersion).where(
        BeatVersion.tenant_id == tenant_id,
        BeatVersion.id.in_(version_ids),
        BeatVersion.is_active.is_(True),
    )
    return list(session.execute(stmt).scalars().all())


def next_version_no(session: Session, *, tenant_id: str, beat_id: str) -> int:
    stmt = select(func.coalesce(func.max(BeatVersion.version_no), 0)).where(
        BeatVersion.tenant_id == tenant_id, BeatVersion.beat_id == beat_id
    )
    return int(session.execute(stmt).scalar_one()) + 1


def list_memberships(session: Session, *, version_id: str) -> list[BeatOutlet]:
    return list_memberships_for_versions(session, version_ids=[version_id])


def list_memberships_for_versions(
    session: Session, *, version_ids: list[str]
) -> list[BeatOutlet]:
    if not version_ids:
        return []
    stmt = (
        select(BeatOutlet)
        .where(
            BeatOutlet.beat_version_id.in_(version_ids),
            BeatOutlet.is_active.is_(True),
        )
        .order_by(
            BeatOutlet.beat_version_id,
            BeatOutlet.sequence_hint.asc().nulls_last(),
            BeatOutlet.id,
        )
    )
    return list(session.execute(stmt).scalars().all())


def code_taken(session: Session, *, tenant_id: str, code: str, exclude_beat_id: str) -> bool:
    """Friendly beat-code pre-check; `uq_beats_tenant_code` is the authoritative backstop, armed
    once a beat's own `code` is synced from its approved version."""

    stmt = select(Beat.id).where(
        Beat.tenant_id == tenant_id,
        Beat.code == code,
        Beat.id != exclude_beat_id,
        Beat.is_active.is_(True),
    )
    return session.execute(stmt).first() is not None




def member_outlet_ids(
    session: Session, *, version_id: str, outlet_ids: list[str]
) -> set[str]:
    if not outlet_ids:
        return set()
    stmt = select(BeatOutlet.outlet_id).where(
        BeatOutlet.beat_version_id == version_id,
        BeatOutlet.is_active.is_(True),
        BeatOutlet.outlet_id.in_(outlet_ids),
    )
    return set(session.execute(stmt).scalars())


def outlet_claims(
    session: Session,
    *,
    tenant_id: str,
    exclude_beat_id: str,
    outlet_ids: list[str],
) -> dict[str, str]:
    """Local outlet id -> holding beat's display name, for outlets on another active beat's
    approved version or on its proposal awaiting approval. An unsubmitted draft claims nothing.
    No unique constraint can express this across versions; the write path enforces it
    in-transaction behind `lock_outlet_claims`.
    """

    if not outlet_ids:
        return {}
    stmt = (
        select(BeatOutlet.outlet_id, Beat.display_name)
        .join(BeatVersion, BeatVersion.id == BeatOutlet.beat_version_id)
        .join(
            Beat,
            (BeatVersion.id == Beat.current_version_id)
            | (
                (BeatVersion.id == Beat.draft_version_id)
                & (BeatVersion.state == "pending_approval")
            ),
        )
        .where(
            Beat.tenant_id == tenant_id,
            BeatOutlet.tenant_id == tenant_id,
            Beat.id != exclude_beat_id,
            Beat.is_active.is_(True),
            Beat.activation_state == "active",
            BeatOutlet.is_active.is_(True),
            BeatOutlet.outlet_id.in_(outlet_ids),
        )
    )
    return {outlet_id: display_name for outlet_id, display_name in session.execute(stmt).all()}


def _outlet_lock_key(tenant_id: str, outlet_ref: str) -> int:
    digest = hashlib.blake2b(
        f"beats_outlet\x00{tenant_id}\x00{outlet_ref}".encode(), digest_size=8
    ).digest()
    return int.from_bytes(digest, "big", signed=True)


def lock_outlet_claims(session: Session, *, tenant_id: str, outlet_refs: list[str]) -> None:
    for lock_key in sorted({_outlet_lock_key(tenant_id, ref) for ref in outlet_refs}):
        session.execute(text("SELECT pg_advisory_xact_lock(:lock_key)"), {"lock_key": lock_key})


def get_pending_edit_request(
    session: Session, *, tenant_id: str, beat_id: str
) -> BeatEditRequest | None:
    stmt = select(BeatEditRequest).where(
        BeatEditRequest.tenant_id == tenant_id,
        BeatEditRequest.beat_id == beat_id,
        BeatEditRequest.state == "pending_approval",
    )
    return session.execute(stmt).scalar_one_or_none()


def list_pending_edit_beat_ids(
    session: Session, *, tenant_id: str, beat_ids: list[str]
) -> set[str]:
    """Beat ids with a pending edit request, in one query — for the admin beats directory
    report's "Pending Edit Request" column."""

    if not beat_ids:
        return set()
    stmt = select(BeatEditRequest.beat_id).where(
        BeatEditRequest.tenant_id == tenant_id,
        BeatEditRequest.beat_id.in_(beat_ids),
        BeatEditRequest.state == "pending_approval",
    )
    return {row[0] for row in session.execute(stmt).all()}


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def insert_beat_with_draft(
    session: Session,
    *,
    beat_id: str | None,
    tenant_id: str,
    code: str,
    display_name: str,
    owner_employee_id: str,
    created_by_employee_id: str,
    now: datetime,
) -> tuple[Beat, BeatVersion]:
    beat = Beat(
        tenant_id=tenant_id,
        code=code,
        display_name=display_name,
        owner_employee_id=owner_employee_id,
        lifecycle_state="draft",
        activation_state="active",
        created_by_employee_id=created_by_employee_id,
    )
    if beat_id is not None:
        beat.id = beat_id
    session.add(beat)
    session.flush()

    version = BeatVersion(
        tenant_id=tenant_id,
        beat_id=beat.id,
        version_no=1,
        state="draft",
        display_name=display_name,
        code=code,
        geo_scope=build_geo_scope_json(zones=[], states=[], districts=[], cats=[], as_of=now),
        frequency={"frequency": "weekly", "visit_days": [], "week_cycle": []},
        outlet_count=0,
        created_by_employee_id=created_by_employee_id,
    )
    session.add(version)
    session.flush()

    beat.draft_version_id = version.id
    session.flush()
    return beat, version


def insert_version(
    session: Session,
    *,
    tenant_id: str,
    beat_id: str,
    version_no: int,
    state: str,
    display_name: str,
    code: str,
    geo_scope: dict[str, Any],
    frequency: dict[str, Any],
    outlet_count: int,
    created_by_employee_id: str | None,
    approved_at: datetime | None = None,
    approved_by_employee_id: str | None = None,
    approval_request_id: str | None = None,
) -> BeatVersion:
    version = BeatVersion(
        tenant_id=tenant_id,
        beat_id=beat_id,
        version_no=version_no,
        state=state,
        display_name=display_name,
        code=code,
        geo_scope=geo_scope,
        frequency=frequency,
        outlet_count=outlet_count,
        created_by_employee_id=created_by_employee_id,
        approved_at=approved_at,
        approved_by_employee_id=approved_by_employee_id,
        approval_request_id=approval_request_id,
    )
    session.add(version)
    session.flush()
    return version


def update_draft_version(
    session: Session,
    *,
    version: BeatVersion,
    display_name: str | None = None,
    code: str | None = None,
    geo_scope: dict[str, Any] | None = None,
    frequency: dict[str, Any] | None = None,
    outlet_count: int | None = None,
) -> None:
    if display_name is not None:
        version.display_name = display_name
    if code is not None:
        version.code = code
    if geo_scope is not None:
        version.geo_scope = geo_scope
    if frequency is not None:
        version.frequency = frequency
    if outlet_count is not None:
        version.outlet_count = outlet_count
    session.flush()


def replace_outlets(
    session: Session,
    *,
    tenant_id: str,
    version_id: str,
    outlet_ids: list[str],
    created_by_employee_id: str | None,
    now: datetime,
) -> int:
    """Last-write-wins replacement of a version's outlet membership.

    No hard delete exists for beats data: a de-selected outlet is soft-deactivated,
    never removed, and re-selecting it later reactivates the same row rather than colliding with
    `uq_beats_outlets`.
    """

    existing = {
        row.outlet_id: row
        for row in session.execute(
            select(BeatOutlet).where(BeatOutlet.beat_version_id == version_id)
        ).scalars()
    }
    wanted = list(dict.fromkeys(outlet_ids))
    wanted_set = set(wanted)

    for outlet_id, row in existing.items():
        if outlet_id not in wanted_set and row.is_active:
            row.is_active = False
            row.deactivated_at = now

    for sequence, outlet_id in enumerate(wanted, start=1):
        current = existing.get(outlet_id)
        if current is None:
            session.add(
                BeatOutlet(
                    tenant_id=tenant_id,
                    beat_version_id=version_id,
                    outlet_id=outlet_id,
                    sequence_hint=sequence,
                    created_by_employee_id=created_by_employee_id,
                )
            )
        else:
            current.is_active = True
            current.deactivated_at = None
            current.sequence_hint = sequence
    session.flush()
    return len(wanted_set)


def copy_outlets(
    session: Session,
    *,
    tenant_id: str,
    from_version_id: str,
    to_version_id: str,
    created_by_employee_id: str,
) -> int:
    """Copy only ordered membership into a newly created beat version."""

    rows = list_memberships(session, version_id=from_version_id)
    for row in rows:
        session.add(
            BeatOutlet(
                tenant_id=tenant_id,
                beat_version_id=to_version_id,
                outlet_id=row.outlet_id,
                sequence_hint=row.sequence_hint,
                created_by_employee_id=created_by_employee_id,
            )
        )
    session.flush()
    return len(rows)


def insert_edit_request(
    session: Session,
    *,
    tenant_id: str,
    beat_id: str,
    base_version_id: str,
    proposed_version_id: str,
    diff: list[dict[str, Any]],
    submitted_at: datetime,
    submitted_by_employee_id: str,
) -> BeatEditRequest:
    row = BeatEditRequest(
        tenant_id=tenant_id,
        beat_id=beat_id,
        base_version_id=base_version_id,
        proposed_version_id=proposed_version_id,
        state="pending_approval",
        diff=diff,
        submitted_at=submitted_at,
        submitted_by_employee_id=submitted_by_employee_id,
        created_by_employee_id=submitted_by_employee_id,
    )
    session.add(row)
    session.flush()
    return row


def link_edit_request_approval(
    session: Session, *, edit_request: BeatEditRequest, approval_request_id: str
) -> None:
    edit_request.approval_request_id = approval_request_id
    session.flush()


def resolve_edit_request(
    session: Session, *, edit_request: BeatEditRequest, state: str, resolved_at: datetime
) -> None:
    edit_request.state = state
    edit_request.resolved_at = resolved_at
    session.flush()


def update_edit_request_diff(
    session: Session, *, edit_request: BeatEditRequest, diff: list[dict[str, Any]]
) -> None:
    edit_request.diff = diff
    session.flush()


def insert_activation_event(
    session: Session,
    *,
    tenant_id: str,
    beat_id: str,
    action: str,
    actor_employee_id: str,
    reason: str | None,
    occurred_at: datetime,
) -> BeatActivationEvent:
    row = BeatActivationEvent(
        tenant_id=tenant_id,
        beat_id=beat_id,
        action=action,
        actor_employee_id=actor_employee_id,
        reason=reason,
        occurred_at=occurred_at,
        created_by_employee_id=actor_employee_id,
    )
    session.add(row)
    session.flush()
    return row

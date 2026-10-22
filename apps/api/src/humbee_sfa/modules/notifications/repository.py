"""Notification persistence — M06 §5.4.

Every read here is **self-scoped by construction**: each function takes `recipient_id` and pins it
into the predicate. There is no `ScopeContext` variant and there deliberately never will be one —
M06 §9 forbids reading another user's feed for *every* role, so a scope resolver would only create
the possibility of getting it wrong. `tenant_id + recipient_id` is the whole authorisation model.

Reads touch this table alone: no joins, no subject lookups, no Humbee. Every display string was
materialised at write time (R-AP-22), which is what lets the feed render while Humbee is down.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Select, func, select, tuple_, update
from sqlalchemy.orm import Session

from humbee_sfa.modules.notifications.models import Notification


def _own(tenant_id: str, recipient_id: str) -> Select[tuple[Notification]]:
    return select(Notification).where(
        Notification.tenant_id == tenant_id,
        Notification.recipient_id == recipient_id,
        Notification.is_active.is_(True),
    )


def list_feed(
    session: Session,
    *,
    tenant_id: str,
    recipient_id: str,
    cursor: tuple[datetime, str] | None,
    limit: int,
) -> list[Notification]:
    """Keyset page, newest first, served by `ix_notifications_feed`."""

    stmt = _own(tenant_id, recipient_id).order_by(
        Notification.created_at.desc(), Notification.id.desc()
    )
    if cursor is not None:
        stmt = stmt.where(tuple_(Notification.created_at, Notification.id) < cursor)
    return list(session.execute(stmt.limit(limit)).scalars().all())


def count_unread(session: Session, *, tenant_id: str, recipient_id: str) -> int:
    """The bell badge. Served by the partial index `ix_notifications_unread`."""

    stmt = (
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.tenant_id == tenant_id,
            Notification.recipient_id == recipient_id,
            Notification.is_active.is_(True),
            Notification.read_at.is_(None),
        )
    )
    return int(session.execute(stmt).scalar_one())


def get_own(
    session: Session, *, tenant_id: str, recipient_id: str, notification_id: str
) -> Notification | None:
    """Someone else's notification and a non-existent one are indistinguishable here by design;
    the caller turns `None` into `404` rather than `403` (M06 §11.2)."""

    return session.execute(
        _own(tenant_id, recipient_id).where(Notification.id == notification_id)
    ).scalar_one_or_none()


def lock_own(
    session: Session, *, tenant_id: str, recipient_id: str, notification_id: str
) -> Notification | None:
    return session.execute(
        _own(tenant_id, recipient_id).where(Notification.id == notification_id).with_for_update()
    ).scalar_one_or_none()


def mark_all_read(
    session: Session, *, tenant_id: str, recipient_id: str, read_at: datetime
) -> int:
    """One conditional UPDATE, not a read-then-write loop: `read_at IS NULL` in the WHERE clause
    means a concurrent single-row mark cannot be clobbered, and already-read rows keep their
    original timestamp. Returns the number of rows this call actually flipped."""

    result = session.execute(
        update(Notification)
        .where(
            Notification.tenant_id == tenant_id,
            Notification.recipient_id == recipient_id,
            Notification.is_active.is_(True),
            Notification.read_at.is_(None),
        )
        .values(read_at=read_at)
    )
    return int(result.rowcount or 0)


def insert(
    session: Session,
    *,
    tenant_id: str,
    recipient_id: str,
    kind: str,
    title: str,
    subtitle: str | None,
    deep_link_type: str | None,
    deep_link_id: str | None,
    source_request_id: str | None,
    dedupe_key: str,
    actor_employee_id: str | None,
) -> Notification:
    row = Notification(
        tenant_id=tenant_id,
        recipient_id=recipient_id,
        kind=kind,
        title=title[:120],
        subtitle=subtitle[:200] if subtitle else None,
        deep_link_type=deep_link_type,
        deep_link_id=deep_link_id,
        source_request_id=source_request_id,
        read_at=None,
        dedupe_key=dedupe_key[:200],
        created_by_employee_id=actor_employee_id,
    )
    session.add(row)
    session.flush()
    return row

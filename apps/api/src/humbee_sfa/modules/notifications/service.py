"""The in-app notification feed — M06 §5.4, S-NOTIF.

Two halves, and the split matters:

* **`record()`** is the write primitive other modules call. It never commits. A notification is
  written **synchronously, inside the producing module's own transaction** (R-AP-16): the approval
  decision and the notification it causes are one unit, so a committed decision can never be
  missing its notification and a rolled-back decision can never leave a phantom one. Delivery here
  is poll-based and in-app only, with no transport to fail: §12 Q14 closed push, device tokens and
  any `NotificationTransport` abstraction permanently.
* **`NotificationService`** serves the four read/ack endpoints. Every one of them is
  `recipient_id = actor.employee_id`, unconditionally, for every role (M06 §9: "read another
  user's notification feed — ✗ ✗ ✗"). There is no scope resolver here on purpose; see
  `repository.py`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from humbee_sfa.core.clock import Clock, SystemClock
from humbee_sfa.core.db import transaction
from humbee_sfa.core.deps import AccessTokenClaims
from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.modules.notifications import repository, schemas
from humbee_sfa.modules.notifications.models import Notification

# Mirrors `ck_notifications_kind_chk` exactly. Changing one without the other is a bug.
KINDS: frozenset[str] = frozenset(
    {
        "submitted",
        "approved",
        "edited",
        "rejected",
        "auto_approved",
        "escalated",
        "beat",
        "withdrawn",
    }
)

DEEP_LINK_TYPES: frozenset[str] = frozenset(
    {"order", "beat", "leave", "outlet", "approval_request"}
)


# ---------------------------------------------------------------------------
# Write primitive (called from the producing module's transaction)
# ---------------------------------------------------------------------------


def record(
    session: Session,
    *,
    tenant_id: str,
    recipient_id: str,
    kind: str,
    title: str,
    dedupe_key: str,
    subtitle: str | None = None,
    deep_link_type: str | None = None,
    deep_link_id: str | None = None,
    source_request_id: str | None = None,
    actor_employee_id: str | None = None,
) -> str | None:
    """Append one notification inside the caller's transaction. Returns the new id, or `None` when
    `dedupe_key` was already used for this recipient.

    R-AP-24 is enforced by `uq_notifications_dedupe`, not by a pre-check: the insert runs inside a
    SAVEPOINT so a collision — a replayed decision, a retried job — rolls back that statement alone
    and leaves the caller's transaction fully usable, rather than being a race the caller can lose.

    `kind` and the deep-link pair are validated here because this table's CHECK constraints are
    this module's to uphold; a bad value is a programming error in the calling module, not user
    input, so it raises rather than being silently coerced.
    """

    if kind not in KINDS:
        raise ValueError(f"Unknown notification kind {kind!r}; expected one of {sorted(KINDS)}.")
    if (deep_link_type is None) != (deep_link_id is None):
        raise ValueError("deep_link_type and deep_link_id must be set together or both omitted.")
    if deep_link_type is not None and deep_link_type not in DEEP_LINK_TYPES:
        raise ValueError(f"Unknown deep link target type {deep_link_type!r}.")

    try:
        with session.begin_nested():
            row = repository.insert(
                session,
                tenant_id=tenant_id,
                recipient_id=recipient_id,
                kind=kind,
                title=title,
                subtitle=subtitle,
                deep_link_type=deep_link_type,
                deep_link_id=deep_link_id,
                source_request_id=source_request_id,
                dedupe_key=dedupe_key,
                actor_employee_id=actor_employee_id,
            )
    except IntegrityError as exc:
        if "uq_notifications_dedupe" not in str(getattr(exc, "orig", exc)):
            raise
        return None
    return row.id


# ---------------------------------------------------------------------------
# Reads and acknowledgements
# ---------------------------------------------------------------------------


def _item_payload(row: Notification) -> dict[str, Any]:
    return schemas.NotificationItem(
        id=row.id,
        kind=row.kind,
        title=row.title,
        subtitle=row.subtitle,
        deep_link_type=row.deep_link_type,
        deep_link_id=row.deep_link_id,
        source_request_id=row.source_request_id,
        created_at=row.created_at,
        read_at=row.read_at,
        is_unread=row.read_at is None,
    ).model_dump(mode="json")


def _encode_cursor(row: Notification) -> str:
    return f"{row.created_at.isoformat()}|{row.id}"


def _decode_cursor(cursor: str | None) -> tuple[datetime, str] | None:
    if not cursor:
        return None
    created_at, _, notification_id = cursor.partition("|")
    try:
        return datetime.fromisoformat(created_at), notification_id
    except ValueError as exc:
        raise ApiError(422, "invalid_cursor", "The pagination cursor is not valid.") from exc


class NotificationService:
    def __init__(self, session: Session, *, clock: Clock | None = None) -> None:
        self._session = session
        self._clock = clock or SystemClock()

    def list_feed(
        self, *, claims: AccessTokenClaims, cursor: str | None, limit: int
    ) -> dict[str, Any]:
        """S-NOTIF. Opening the feed does **not** mark anything read (R-AP-23) — this is a pure
        read, which is why it does not commit."""

        rows = repository.list_feed(
            self._session,
            tenant_id=claims.tenant_id,
            recipient_id=claims.employee_id,
            cursor=_decode_cursor(cursor),
            limit=limit,
        )
        return schemas.NotificationListResponse(
            items=[schemas.NotificationItem(**_item_payload(row)) for row in rows],
            unread_count=self._unread(claims),
            next_cursor=_encode_cursor(rows[-1]) if len(rows) == limit else None,
        ).model_dump(mode="json")

    def get_unread_count(self, *, claims: AccessTokenClaims) -> dict[str, Any]:
        return schemas.UnreadCountResponse(count=self._unread(claims)).model_dump(mode="json")

    def get_notification(
        self, *, claims: AccessTokenClaims, notification_id: str
    ) -> dict[str, Any]:
        """Resolves a deep-link target. Reading it does not mark it read (R-AP-23)."""

        return _item_payload(self._load_own(claims, notification_id))

    def mark_read(self, *, claims: AccessTokenClaims, notification_id: str) -> dict[str, Any]:
        """One transaction. Re-marking is a no-op `200` that keeps the original `read_at`, so a
        retried fire-and-forget tap from the client cannot rewrite history (M06 §10)."""

        with transaction(self._session):
            row = repository.lock_own(
                self._session,
                tenant_id=claims.tenant_id,
                recipient_id=claims.employee_id,
                notification_id=notification_id,
            )
            if row is None:
                raise ApiError(404, "notification_not_found", "Notification was not found.")
            changed = row.read_at is None
            if changed:
                row.read_at = self._clock.now_utc()
                self._session.flush()
            read_at = row.read_at
            payload = schemas.MarkReadResponse(
                id=row.id,
                read_at=read_at,
                changed=changed,
                unread_count=self._unread(claims),
            ).model_dump(mode="json")
        return payload

    def mark_all_read(self, *, claims: AccessTokenClaims) -> dict[str, Any]:
        with transaction(self._session):
            marked = repository.mark_all_read(
                self._session,
                tenant_id=claims.tenant_id,
                recipient_id=claims.employee_id,
                read_at=self._clock.now_utc(),
            )
            payload = schemas.MarkAllReadResponse(
                marked=marked, unread_count=self._unread(claims)
            ).model_dump(mode="json")
        return payload

    def _unread(self, claims: AccessTokenClaims) -> int:
        return repository.count_unread(
            self._session, tenant_id=claims.tenant_id, recipient_id=claims.employee_id
        )

    def _load_own(self, claims: AccessTokenClaims, notification_id: str) -> Notification:
        row = repository.get_own(
            self._session,
            tenant_id=claims.tenant_id,
            recipient_id=claims.employee_id,
            notification_id=notification_id,
        )
        if row is None:
            # 404, not 403: another recipient's notification must not be distinguishable from a
            # non-existent one (M06 §11.2).
            raise ApiError(404, "notification_not_found", "Notification was not found.")
        return row


__all__ = ["DEEP_LINK_TYPES", "KINDS", "NotificationService", "record"]

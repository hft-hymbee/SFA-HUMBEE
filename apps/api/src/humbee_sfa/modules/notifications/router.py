"""Notification HTTP routes — M06 §10.

There is no create endpoint and never will be: a notification is a side effect of a state
transition somewhere else, written through `notifications.service.record` inside that transition's
transaction. Nothing may post one over HTTP.

Handlers translate HTTP only. Authorisation is not re-implemented here — it is not a route concern
at all in this module, because the service pins `recipient_id` to the caller's own employee id for
every role (M06 §9).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from humbee_sfa.core.db import get_db_session
from humbee_sfa.core.deps import AccessTokenClaims, get_current_claims
from humbee_sfa.modules.notifications import schemas
from humbee_sfa.modules.notifications.service import NotificationService

router = APIRouter(prefix="/api/v1", tags=["Notifications"])

NotificationId = Annotated[str, Path(min_length=1, max_length=26)]


@router.get("/notifications", response_model=schemas.NotificationListResponse)
def list_notifications(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    cursor: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> dict[str, Any]:
    return NotificationService(session).list_feed(claims=claims, cursor=cursor, limit=limit)


# Declared before `/notifications/{notification_id}` so the literal path wins the match.
@router.get("/notifications/unread-count", response_model=schemas.UnreadCountResponse)
def get_unread_count(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return NotificationService(session).get_unread_count(claims=claims)


@router.post("/notifications/read-all", response_model=schemas.MarkAllReadResponse)
def mark_all_read(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    # No `Idempotency-Key`: the operation is naturally idempotent (a conditional UPDATE on
    # `read_at IS NULL`), so a replay marks nothing and returns the same state.
    return NotificationService(session).mark_all_read(claims=claims)


@router.post("/notifications/{notification_id}/read", response_model=schemas.MarkReadResponse)
def mark_read(
    notification_id: NotificationId,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return NotificationService(session).mark_read(
        claims=claims, notification_id=notification_id
    )


@router.get("/notifications/{notification_id}", response_model=schemas.NotificationItem)
def get_notification(
    notification_id: NotificationId,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return NotificationService(session).get_notification(
        claims=claims, notification_id=notification_id
    )

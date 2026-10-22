"""Notification HTTP DTOs — M06 §10.

Rows carry only materialised strings (R-AP-22). Everything the S-NOTIF row renders — the four-tier
IST timestamp label and the `kind` → icon/colour mapping — is the client's job from `created_at` and
`kind`; the server does not send display strings it would then have to keep in sync.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class NotificationItem(BaseModel):
    id: str
    kind: str
    title: str
    subtitle: str | None
    deep_link_type: str | None
    deep_link_id: str | None
    source_request_id: str | None
    created_at: datetime
    read_at: datetime | None
    is_unread: bool


class NotificationListResponse(BaseModel):
    items: list[NotificationItem]
    unread_count: int
    next_cursor: str | None = None


class UnreadCountResponse(BaseModel):
    """`bellCount`. `0` means the client renders no badge at all, not "0" (M06 §8)."""

    count: int


class MarkReadResponse(BaseModel):
    """`changed` is false when the row was already read — re-marking is a no-op `200`, never a
    `409` (M06 §10)."""

    id: str
    read_at: datetime
    changed: bool
    unread_count: int


class MarkAllReadResponse(BaseModel):
    marked: int
    unread_count: int

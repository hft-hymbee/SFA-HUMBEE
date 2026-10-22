"""Approvals HTTP DTOs.

The canonical `ApprovalStatus` crosses this boundary, never the prototype's overloaded `StatusChip`
keys; the display mapping is the frontend's single source. Money is integer paise.
The derived booleans (`is_pending`, `is_granted`, `is_terminal`, `can_decide`) are computed
server-side so the client never re-derives them.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

# The inbox filter chips: `beat_create` and `beat_edit` both live under "beat".
FILTER_TO_SUBJECT_TYPES: dict[str, tuple[str, ...]] = {
    "all": (),
    "order": ("dp_order",),
    "beat": ("beat_create", "beat_edit"),
    "leave": ("leave",),
    "outlet": ("outlet_verification",),
}


class ApprovalListItem(BaseModel):
    id: str
    subject_type: str
    subject_id: str
    subject_version: int
    status: str
    title: str
    subtitle: str
    amount_paise: int | None
    requester_id: str
    assigned_approver_id: str | None
    routing_reason: str
    escalated_from_id: str | None
    escalation_depth: int
    submitted_at: datetime
    submitted_business_date: date
    decided_at: datetime | None
    decided_by_id: str | None
    edit_applied: bool
    is_pending: bool
    is_granted: bool
    is_terminal: bool
    can_decide: bool


class ApprovalListResponse(BaseModel):
    items: list[ApprovalListItem]
    pending_count: int
    next_cursor: str | None = None


class ApprovalSummaryResponse(BaseModel):
    """Single source for every pending count on every surface."""

    pending_total: int
    pending_by_filter: dict[str, int]


class TimelineStep(BaseModel):
    """`state` is one of `done` / `edited` / `current` / `rejected` — the four values the
    design-system component accepts, and not the same enum as `status`."""

    state: str
    action: str
    actor_id: str | None
    actor_role: str | None
    note: str | None
    occurred_at: datetime | None


class DetailBlock(BaseModel):
    kind: str
    label: str
    payload: dict[str, Any]


class Advisory(BaseModel):
    code: str
    severity: str
    message: str


class EditableFieldSchema(BaseModel):
    key: str
    label: str
    kind: str
    current_value: Any = None
    min_value: int | None = None
    max_value: int | None = None


class EditableFieldsResponse(BaseModel):
    items: list[EditableFieldSchema]


class TimelineResponse(BaseModel):
    items: list[TimelineStep]


class ApprovalDetailResponse(BaseModel):
    request: ApprovalListItem
    can_withdraw: bool
    is_editable: bool
    blocks: list[DetailBlock]
    advisories: list[Advisory]
    editable_fields: list[EditableFieldSchema]
    timeline: list[TimelineStep]
    deep_link_type: str | None
    deep_link_id: str | None


class RejectBody(BaseModel):
    # Non-empty after trimming is enforced in policies so the API rule holds whatever
    # the UI does; `min_length` here only rejects the obviously empty case earlier.
    reason: str = Field(min_length=1, max_length=2000)


class ApproveBody(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class EditAndApproveBody(BaseModel):
    patch: dict[str, Any]
    note: str | None = Field(default=None, max_length=2000)


class WithdrawBody(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)

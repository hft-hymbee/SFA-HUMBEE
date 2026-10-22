"""Leave HTTP DTOs.

Only the leave screens' surface is modelled: apply (balances, preview, submit), own history and
team. Display strings the client can compose from these fields — the
`"Casual · 22–23 Jul"` title, the `"Applied 2h ago"` relative label, the status chip — are not sent
(they are client formatters, and the status→label map is a shared client
mapper). Day counts are `float`: the column is `numeric(4,1)`, so a JSON number is lossless and the
client does arithmetic on it.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from humbee_sfa.modules.leave.leave_type import LeaveType

LeaveTypeName = LeaveType

# Own-history tabs and team filter chips. Server-side, not client-side.
MINE_STATUS_FILTERS: dict[str, tuple[str, ...]] = {
    "all": (),
    "pending": ("pending",),
    "history": ("approved", "approved_with_edits", "auto_approved", "rejected", "withdrawn"),
}
TEAM_STATUS_FILTERS: dict[str, tuple[str, ...]] = {
    "all": (),
    "pending": ("pending",),
    # `approved` and `auto_approved` are deliberately distinct buckets.
    "approved": ("approved", "approved_with_edits"),
    "auto_approved": ("auto_approved",),
    "rejected": ("rejected",),
}


class SubmitLeaveBody(BaseModel):
    """Leave submit. `id` is the client-generated ULID that makes a retried submit provably the
    same request; `is_half_day` has no client control in v1 and is not accepted.
    """

    id: str | None = Field(default=None, min_length=26, max_length=26)
    leave_type: LeaveTypeName
    from_date: date
    to_date: date
    reason: str | None = Field(default=None, max_length=500)


class LeaveBalanceItem(BaseModel):
    leave_type: LeaveType
    period_year: int
    entitled_days: float
    consumed_days: float
    pending_days: float
    # Never clamped at 0 — a negative available balance is a legitimate visible state.
    available_days: float


class LeaveBalancesResponse(BaseModel):
    period_year: int
    items: list[LeaveBalanceItem]


class LeavePreviewResponse(BaseModel):
    """The apply-leave info card, server-authoritative. `exceeds_balance` drives the advisory
    banner only — submission is never blocked on it."""

    leave_type: LeaveType
    from_date: date
    to_date: date
    # The leave year this projection is drawn from — `from_date`'s, which is not always the year
    # the balance cards show.
    period_year: int
    day_count: float
    available_days: float
    balance_after: float
    exceeds_balance: bool


class LeaveRequestItem(BaseModel):
    """One own-history row. `approval_request_id` is what the Withdraw action posts to —
    `POST /api/v1/approvals/{id}/withdraw`."""

    id: str
    leave_type: LeaveType
    from_date: date
    to_date: date
    day_count: float
    is_half_day: bool
    reason: str | None
    status: str
    approval_request_id: str
    balance_before: float
    balance_after_projected: float
    applied_at: datetime
    decided_at: datetime | None
    decision_note: str | None


class LeaveRequestListResponse(BaseModel):
    items: list[LeaveRequestItem]


class TeamLeaveItem(BaseModel):
    """One team-leave row. The avatar initials are derived client-side from `employee_name`."""

    id: str
    employee_id: str
    employee_name: str
    leave_type: LeaveType
    from_date: date
    to_date: date
    day_count: float
    status: str
    approval_request_id: str


class TeamLeaveListResponse(BaseModel):
    items: list[TeamLeaveItem]

"""Leave HTTP DTOs — M12 §10.

Only the four screens' worth of surface is modelled: S-LV1 (balances, preview, submit), S-LV2
(own history) and S-LV3 (team). Display strings the client can compose from these fields — the
`"Casual · 22–23 Jul"` title, the `"Applied 2h ago"` relative label, the status chip — are not sent
(M12 §8 lists them as client formatters, and R-LV-18 makes the status→label map a shared client
mapper). Day counts are `float`: the column is `numeric(4,1)`, so a JSON number is lossless and the
client does arithmetic on it.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from humbee_sfa.modules.leave.leave_type import LeaveType

LeaveTypeName = LeaveType

# S-LV2 tabs (M12 §4) and S-LV3 filter chips. Server-side, not client-side (R-LV-17).
MINE_STATUS_FILTERS: dict[str, tuple[str, ...]] = {
    "all": (),
    "pending": ("pending",),
    "history": ("approved", "approved_with_edits", "auto_approved", "rejected", "withdrawn"),
}
TEAM_STATUS_FILTERS: dict[str, tuple[str, ...]] = {
    "all": (),
    "pending": ("pending",),
    # `approved` and `auto_approved` are deliberately distinct buckets (M12 §3.4, §12 Q9).
    "approved": ("approved", "approved_with_edits"),
    "auto_approved": ("auto_approved",),
    "rejected": ("rejected",),
}


class SubmitLeaveBody(BaseModel):
    """S-LV1 submit. `id` is the client-generated ULID that makes a retried submit provably the
    same request (M12 §3.1); `is_half_day` has no S-LV1 control in v1 (§12 Q4) and is not accepted.
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
    # R-LV-21, never clamped at 0 — a negative available balance is a legitimate visible state.
    available_days: float


class LeaveBalancesResponse(BaseModel):
    period_year: int
    items: list[LeaveBalanceItem]


class LeavePreviewResponse(BaseModel):
    """The S-LV1 info card, server-authoritative (M12 §10). `exceeds_balance` drives the advisory
    banner only — submission is never blocked on it (R-LV-11)."""

    leave_type: LeaveType
    from_date: date
    to_date: date
    # The leave year this projection is drawn from — `from_date`'s, which is not always the year
    # the balance cards show (M12 §12 Q14).
    period_year: int
    day_count: float
    available_days: float
    balance_after: float
    exceeds_balance: bool


class LeaveRequestItem(BaseModel):
    """One S-LV2 row. `approval_request_id` is what the Withdraw action posts to —
    `POST /api/v1/approvals/{id}/withdraw` (M12 §4 S-LV2, §10 "Decisions — not here")."""

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
    """One S-LV3 row. The avatar initials are derived client-side from `employee_name` (M12 §8)."""

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

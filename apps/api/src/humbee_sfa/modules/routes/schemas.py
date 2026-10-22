"""Routes/Visits HTTP DTOs — M08 §4, §10.

Field naming mirrors the beats convention (`outlet_ref` in the HTTP layer, `humbee_outlet_id` in
the DB/ORM) so the two modules read the same on the wire.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

NoOrderReason = Literal[
    "shop_closed", "no_requirement", "stock_full", "revisit_later", "credit_issue", "other"
]
VisitType = Literal["physical", "telephonic"]
OverallRating = Literal["good", "average", "needs_work"]


class GpsFix(BaseModel):
    lat: float
    lng: float
    accuracy_m: float | None = Field(default=None, ge=0, le=99999.99)
    provider: str | None = None
    is_mock: bool | None = None


class RouteStopItem(BaseModel):
    outlet_ref: str
    sequence_no: int
    name: str
    locality: str | None
    category: str | None
    distance_from_prev_km: float | None
    beat_id: str | None
    run_origin: str | None
    checkin_gps: GpsFix | None = None
    visit_id: str | None
    visit_state: str | None
    visit_origin: str | None
    visit_type: str | None
    checked_in_at: datetime | None = None
    checked_out_at: datetime | None = None
    outcome: str | None = None
    no_order_reason: str | None = None
    order_count: int | None = None
    combined_visit_scheduled: bool = False
    is_next: bool = False


class RouteOutletGroup(BaseModel):
    beat_id: str | None
    beat_name: str
    run_origin: str | None
    outlets: list[RouteStopItem]


class OfficialWorkBlock(BaseModel):
    id: str
    work_type: str
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int | None


class RoutePlanResponse(BaseModel):
    id: str | None
    business_date: date
    beat_id: str | None
    state: str | None
    planned_stop_count: int
    visited_count: int
    planned_visited_count: int = 0
    unplanned_visit_count: int = 0
    coverage_pct: int | None = None
    started_at: datetime | None
    closed_at: datetime | None
    outlet_groups: list[RouteOutletGroup]
    punched_in_at: datetime | None = None
    punched_out_at: datetime | None = None
    on_duty: bool = False
    official_work: list[OfficialWorkBlock] = Field(default_factory=list)


class SwitchBeatBody(BaseModel):
    """S-ROUTE2b (transition #12)."""

    beat_id: str


class VisitResponse(BaseModel):
    id: str
    route_plan_id: str | None
    route_stop_id: str | None
    outlet_ref: str
    state: str
    origin: str
    visit_type: str | None
    checked_in_at: datetime | None
    checked_out_at: datetime | None
    note: str | None


class VisitOutcomeDetail(BaseModel):
    """Read-back for a visit's close-out (S-VISIT1) — reopening a completed visit shows what was
    recorded, including the orders placed, without growing `RouteStopItem` (read by every stop on
    every route-plan fetch) with per-visit detail only the opened stop needs."""

    visit_id: str
    outcome: str | None
    no_order_reason: str | None
    note: str | None
    order_ids: list[str] = Field(default_factory=list)
    recorded_at: datetime | None


class LastOutletVisit(BaseModel):
    visit_id: str
    business_date: date
    employee_name: str | None
    visit_type: str
    checked_in_at: datetime | None
    checked_out_at: datetime | None
    outcome: str
    no_order_reason: str | None
    note: str | None
    order_count: int


class LastOutletVisitResponse(BaseModel):
    outlet_ref: str
    last_visit: LastOutletVisit | None


class CheckInBody(BaseModel):
    """S-ROUTE4 entry / "Add unplanned visit" (transitions #2/#3)."""

    occurred_at: datetime
    visit_type: VisitType
    outlet_ref: str | None = None  # required only when the visit doesn't already exist
    gps: GpsFix | None = None
    note: str | None = Field(default=None, max_length=2000)


class OutcomeBody(BaseModel):
    """S-VISIT1 (transition #6)."""

    reason: NoOrderReason
    note: str | None = Field(default=None, max_length=2000)
    photo_object_key: str | None = None


class MissedVisitItem(BaseModel):
    id: str
    visit_id: str
    employee_id: str
    outlet_ref: str
    outlet_name: str | None
    outlet_locality: str | None
    business_date: date
    planned_visit_type: str
    swept_at: datetime


class MissedVisitsSummary(BaseModel):
    missed: int
    visited: int
    adherence_pct: int | None


class MissedVisitsResponse(BaseModel):
    items: list[MissedVisitItem]
    summary: MissedVisitsSummary


class LatestFix(BaseModel):
    lat: float
    lng: float
    captured_at: datetime


class CoverageRow(BaseModel):
    employee_id: str
    employee_name: str
    on_duty: bool
    on_leave: bool
    punched_in_at: datetime | None
    latest_fix: LatestFix | None = None
    visited: int
    planned: int
    unplanned_visited: int


class CoverageResponse(BaseModel):
    business_date: date
    on_route: int
    on_route_total: int
    visited: int
    planned: int
    productive: int
    coverage_pct: int | None
    items: list[CoverageRow]


class RouteDaysResponse(BaseModel):
    business_dates: list[date]


class CreateCombinedVisitBody(BaseModel):
    """S-CVIS1 (R-RTE-28/29/30)."""

    id: str | None = Field(default=None, min_length=26, max_length=26)
    sales_person_employee_id: str
    beat_id: str
    outlet_ref: str
    scheduled_business_date: date


class CombinedVisitFeedbackResponse(BaseModel):
    overall_rating: OverallRating
    responses: dict[str, str] = Field(default_factory=dict)
    submitted_at: datetime
    submitted_by_employee_id: str


class CombinedVisitResponse(BaseModel):
    id: str
    manager_employee_id: str
    sales_person_employee_id: str
    beat_id: str
    outlet_ref: str
    scheduled_business_date: date
    state: str
    visit_id: str | None
    feedback: CombinedVisitFeedbackResponse | None = None


class CombinedVisitFeedbackBody(BaseModel):
    """S-CVIS2. `responses` absorbs the still-pending business schema as JSONB (R-RTE-33)."""

    overall_rating: OverallRating
    responses: dict[str, str] = Field(default_factory=dict)


class SweepRunResponse(BaseModel):
    business_date: date
    status: str
    visits_missed: int | None


class UnplannedOutletItem(BaseModel):
    outlet_ref: str
    name: str


class CoordinateCorrectionBody(BaseModel):
    """O-4 — a field pin correction captured during a visit, possibly offline.
    The outlet is the visit's own outlet (from the path), never a client-supplied id."""

    lat: float
    lng: float
    accuracy_m: float = Field(ge=0, le=99999.99)
    provider: str
    captured_at: datetime


class CoordinateCorrectionResponse(BaseModel):
    id: str
    outlet_ref: str
    status: str
    latitude: float | None
    longitude: float | None
    rejection_code: str | None

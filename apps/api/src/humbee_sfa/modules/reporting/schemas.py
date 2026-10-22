"""Reporting KPI HTTP DTOs for dashboard surfaces."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

ReportingKpiSurface = Literal[
    "sp-home",
    "sp-dashboard",
    "sp-targets",
    "manager-dashboard",
    "admin-dashboard",
    "manager-targets",
    "dashboard-drill",
    "coverage-drill",
    "team-day-drill",
    "approvals-drill",
]

KpiAvailability = Literal["available", "unavailable", "no_target"]


class DegradedSourceOut(BaseModel):
    source: str
    reason: str


class KpiCardOut(BaseModel):
    code: str
    title: str
    value: str
    subtitle: str
    icon: str
    tone: str
    trend: list[float] = Field(default_factory=list)
    availability: KpiAvailability = "available"
    status_note: str | None = None


class KpiGroupOut(BaseModel):
    label: str
    items: list[KpiCardOut] = Field(default_factory=list)


class RegionLeaderboardRowOut(BaseModel):
    region: str
    net_value_paise: int
    share_pct: float
    share_label: str


class KpiSurfaceResponse(BaseModel):
    surface: ReportingKpiSurface
    business_date: date
    groups: list[KpiGroupOut] = Field(default_factory=list)
    region_share_label: str | None = None
    region_leaderboard: list[RegionLeaderboardRowOut] = Field(default_factory=list)
    degraded: list[DegradedSourceOut] = Field(default_factory=list)


class CoverageTrendSeriesOut(BaseModel):
    key: str
    label: str
    color: str


class CoverageTrendPointOut(BaseModel):
    business_date: date
    date_label: str
    overall_coverage_pct: int | None
    values: dict[str, int | None] = Field(default_factory=dict)


class AdminCoverageTrendResponse(BaseModel):
    business_date: date
    days: int
    series: list[CoverageTrendSeriesOut] = Field(default_factory=list)
    points: list[CoverageTrendPointOut] = Field(default_factory=list)


DashboardPeriod = Literal["mtd", "today"]


class TargetLineOut(BaseModel):
    manufacturer_id: str
    label: str
    basis: str
    uom_label: str
    target_value: int
    taken_paise: int
    taken_qty: int
    taken_lines: int
    pct: int | None


class CountTargetOut(BaseModel):
    target_type: Literal["outlets", "leads"]
    target_value: int | None
    achieved: int | None
    pct: int | None


class MoneyWindowOut(BaseModel):
    mtd_paise: int
    lmtd_paise: int
    mom_pct: int | None


class LeagueRowOut(BaseModel):
    employee_id: str
    name: str
    net_value_paise: int
    outlets_ordered: int
    pct: int | None = None
    taken_qty: int = 0
    uom_label: str = ""
    has_target: bool = False
    # Target in its own basis unit — paise for "amount", quantity for "volume".
    target_value: int | None = None
    target_basis: str = ""
    designation_code: str = ""


class ScatterPointOut(BaseModel):
    employee_id: str
    name: str
    adherence_pct: int | None
    conversion_pct: int | None


class DistrictRowOut(BaseModel):
    district_id: str
    label: str
    mtd_paise: int
    lmtd_paise: int
    mom_pct: int | None


class ManufacturerMoveOut(BaseModel):
    manufacturer_id: str
    label: str
    mtd_paise: int
    lmtd_paise: int
    mom_pct: int | None


class ApprovalLatencyOut(BaseModel):
    median_hours: float | None
    p90_hours: float | None
    pending_median_hours: float | None
    decided_count: int
    pending_count: int


class TargetsSummaryOut(BaseModel):
    on_track: int
    at_risk: int
    total_amount_lines: int


class SpDashboardMetricsOut(BaseModel):
    utc: int
    visits_total: int
    productive_visits: int
    zo: int
    lpsc: float | None
    orders_submitted: int
    order_value_paise: int | None
    order_volume_units: int | None
    order_volume_uom: str | None
    unplanned_visits: int
    order_lines_count: int
    distance_metres: int
    planned_visits: int = 0
    coverage_pct: int | None = None
    productivity_pct: int = 0
    outlets_ordered: int = 0


class SpDashboardKpisResponse(BaseModel):
    period: DashboardPeriod
    business_date: date
    metrics: SpDashboardMetricsOut
    degraded: list[DegradedSourceOut] = Field(default_factory=list)


class SpTargetsKpisResponse(BaseModel):
    """Manufacturer-scoped target progress only, always MTD.

    Split from `SpDashboardKpisResponse` so the targets screen's manufacturer
    filter doesn't require re-running that endpoint's visit/call metrics.
    """

    business_date: date
    targets: list[TargetLineOut] = Field(default_factory=list)
    count_targets: list[CountTargetOut]
    mom: MoneyWindowOut | None = None
    degraded: list[DegradedSourceOut] = Field(default_factory=list)


class ManagerDashboardMetricsOut(BaseModel):
    visits_total: int
    productive_visits: int
    productivity_pct: int
    punched_in: int | None
    order_value_paise: int | None
    team_size: int | None
    utc: int
    orders_submitted: int
    planned_visits: int = 0
    coverage_pct: int | None = None
    unique_outlets: int = 0
    outlets_ordered: int = 0
    outlets_onboarded_count: int | None = None
    leads_captured_count: int | None = None
    on_duty: int | None = None
    no_punch_in: int | None = None
    on_leave: int | None = None
    pending_approvals: int | None = None


class DesignationScopeOut(BaseModel):
    """Which hierarchy level `targets` is rolled up to, and what else the caller may pick.
    `targets` is always scoped to one designation level, never the whole tree, so a
    manufacturer's target progress means the same thing before and after a filter change.
    Every other field on `ManagerDashboardKpisResponse` (including `mom`) stays whole-tree."""

    active: str
    available: list[str] = Field(default_factory=list)


class ManagerDashboardKpisResponse(BaseModel):
    period: DashboardPeriod
    business_date: date
    team_metrics: ManagerDashboardMetricsOut
    targets: list[TargetLineOut] = Field(default_factory=list)
    designation_scope: DesignationScopeOut | None = None
    league: list[LeagueRowOut] = Field(default_factory=list)
    scatter: list[ScatterPointOut] = Field(default_factory=list)
    districts: list[DistrictRowOut] = Field(default_factory=list)
    mom: MoneyWindowOut | None = None
    degraded: list[DegradedSourceOut] = Field(default_factory=list)


class AdminDashboardMetricsOut(BaseModel):
    visits_total: int
    productive_visits: int
    productivity_pct: int
    order_value_paise: int | None
    active_employees: int | None
    planned_visits: int = 0
    coverage_pct: int | None = None
    unique_outlets: int = 0
    outlets_ordered: int = 0
    outlets_multi_rep: int = 0
    net_new_outlets: int = 0
    on_duty: int | None = None
    no_punch_in: int | None = None
    on_leave: int | None = None
    pending_approvals: int | None = None


class AdminDashboardKpisResponse(BaseModel):
    period: DashboardPeriod
    business_date: date
    org_metrics: AdminDashboardMetricsOut
    targets: list[TargetLineOut] = Field(default_factory=list)
    targets_summary: TargetsSummaryOut | None = None
    manufacturer_movement: list[ManufacturerMoveOut] = Field(default_factory=list)
    approval_latency: ApprovalLatencyOut | None = None
    mom: MoneyWindowOut | None = None
    employee_progress: list[LeagueRowOut] = Field(default_factory=list)
    designation_scope: DesignationScopeOut | None = None
    degraded: list[DegradedSourceOut] = Field(default_factory=list)


AttentionKind = Literal["untouched", "stopped_ordering", "failed_downstream"]
AttentionAction = Literal["View", "Fix"]


class AttentionItemOut(BaseModel):
    kind: AttentionKind
    title: str
    subtitle: str
    action: AttentionAction


class SpAttentionResponse(BaseModel):
    business_date: date
    items: list[AttentionItemOut]


CallsKpiScope = Literal["self", "team", "org"]


class CallsKpiNodeOut(BaseModel):
    employee_id: str
    full_name: str
    role_code: str
    designation_code: str


class CallsKpiViewOut(BaseModel):
    scope: CallsKpiScope
    root: CallsKpiNodeOut | None = None


class CallsKpiRowOut(BaseModel):
    employee_id: str
    full_name: str
    role_code: str
    designation_code: str
    status: str
    direct_reportee_count: int
    tc: int
    pc: int
    sc: int
    utc: int


class CallsKpiTotalsOut(BaseModel):
    tc: int
    pc: int
    sc: int
    utc: int


class CallsKpiWindowOut(BaseModel):
    """One drill level: the view root's own aggregate plus a row per direct reportee.

    `totals` is the root's roll-up over every active sales person beneath it — not the sum of
    `items`, which would count a manager and their own reportees twice over.
    """

    items: list[CallsKpiRowOut] = Field(default_factory=list)
    totals: CallsKpiTotalsOut


class CallsKpiResponse(BaseModel):
    view: CallsKpiViewOut
    business_date: date
    today: CallsKpiWindowOut
    mtd: CallsKpiWindowOut


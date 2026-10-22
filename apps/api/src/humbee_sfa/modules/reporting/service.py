"""Reporting dashboard KPI composition service."""

from __future__ import annotations

from calendar import monthrange
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import cached_property
from typing import Any, Literal

import structlog
from sqlalchemy import ColumnElement, Row, func, select
from sqlalchemy.orm import Session

from humbee_sfa.core.clock import Clock, SystemClock
from humbee_sfa.core.db import end_read_transaction
from humbee_sfa.core.deps import AccessTokenClaims
from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.core.settings import Settings, get_settings
from humbee_sfa.modules.approvals.service import ApprovalService
from humbee_sfa.modules.attendance.service import AttendanceService, current_business_date
from humbee_sfa.modules.beats.service import BeatService
from humbee_sfa.modules.home.service import TodayService
from humbee_sfa.modules.orders.service import OrderService
from humbee_sfa.modules.org import service as org_service
from humbee_sfa.modules.org.geography_service import list_district_labels, list_employee_zone_labels
from humbee_sfa.modules.org.schemas import DESIGNATIONS_BY_ROLE
from humbee_sfa.modules.org.scope import (
    OrgResource,
    Scope,
    ScopeContext,
    ScopeResolver,
    employee_scope_condition,
)
from humbee_sfa.modules.org.service import OrgService
from humbee_sfa.modules.outlets.service import OutletReadService
from humbee_sfa.modules.reporting import repository, schemas
from humbee_sfa.modules.reporting.models import FactEmployeeDay
from humbee_sfa.modules.routes.service import RouteService
from humbee_sfa.modules.targets.service import TargetService

logger = structlog.get_logger("humbee_sfa.reporting")

_REGION_SHARE_LABEL = "share of org sales"
_TREND_COLORS = [
    "var(--color-info)",
    "var(--color-success)",
    "var(--color-warning)",
    "var(--color-primary)",
    "var(--color-error)",
]

# Designation ladder for the calls-KPI roster (P3 plan, 2026-09-20). Admin is NOT on the
# ladder; L1 (national sales head) sits at the top of each hierarchy. A manager-level filter
# shows one row per designated holder aggregating their reps; a sales-person filter shows one
# row per rep with their own values.
_CALLS_LADDER: tuple[tuple[str, ...], ...] = (
    ("national_sales_head",),              # L1 - national sales head
    ("segment_business_head",),            # L2 - segment business head
    ("regional_sales_manager",),           # L3
    ("area_sales_manager",),               # L4
    ("network_officer_salesperson", "territory_development_officer_salesperson"),  # L5 - reps
)
_ROLE_BY_DESIGNATION: dict[str, str] = {
    code: role for role, codes in DESIGNATIONS_BY_ROLE.items() for code in codes
}
_LEVEL_BY_DESIGNATION: dict[str, int] = {
    code: level for level, codes in enumerate(_CALLS_LADDER) for code in codes
}
# Admin's "By employee" card opens on every level at once — admin sits above the whole
# ladder, so there is no "caller level" to default off of the way the manager dashboard does.
_ALL_DESIGNATIONS = "all"


def _flatten_tree_nodes(roots: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Flatten `OrgService.get_tree` roots into `{employee_id: node}` including children."""
    nodes: dict[str, dict[str, Any]] = {}

    def walk(node: dict[str, Any]) -> None:
        node_id = node.get("id")
        if node_id:
            nodes[str(node_id)] = node
        for child in node.get("children", []):
            if isinstance(child, dict):
                walk(child)

    for root in roots:
        if isinstance(root, dict):
            walk(root)
    return nodes


def _subtree_nodes(node: dict[str, Any]) -> list[dict[str, Any]]:
    """All descendant nodes below `node` (excludes `node` itself)."""
    descendants: list[dict[str, Any]] = []

    def walk(current: dict[str, Any]) -> None:
        for child in current.get("children", []):
            if not isinstance(child, dict):
                continue
            descendants.append(child)
            walk(child)

    walk(node)
    return descendants


def _sales_leaf_ids(node: dict[str, Any]) -> list[str]:
    """The active sales persons whose activity rolls up into `node`."""
    if str(node.get("role_code")) == "sales_person":
        return [str(node["id"])] if str(node.get("status")) == "active" else []
    return sorted(
        str(descendant["id"])
        for descendant in _subtree_nodes(node)
        if str(descendant.get("status")) == "active"
        and str(descendant.get("role_code")) == "sales_person"
    )


def _drill_children(node: dict[str, Any] | None, candidates: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """The reportee rows a drill level shows, name-ordered.

    A deactivated manager whose reps are still active keeps a row: their visits count in every
    ancestor's total, so hiding the row would leave a header the caller cannot decompose or
    drill into. Only a node that contributes nothing and leads nowhere is dropped.
    """
    if candidates is None:
        candidates = (node or {}).get("children", [])
    return sorted(
        (
            child
            for child in candidates
            if isinstance(child, dict)
            and child.get("id")
            and (str(child.get("status")) == "active" or _sales_leaf_ids(child))
        ),
        key=lambda child: str(child.get("full_name") or child["id"]).lower(),
    )


@dataclass(frozen=True)
class _CardMeta:
    title: str
    icon: str
    tone: str


@dataclass(frozen=True)
class _SurfaceGroup:
    label: str
    codes: tuple[str, ...]


@dataclass(frozen=True)
class _DashboardContext:
    role_scope: Scope
    business_date: date
    planned: int | None = None
    visited: int | None = None
    productive: int | None = None
    no_order: int | None = None
    pending_approvals: int | None = None
    team_total: int | None = None
    on_duty: int | None = None
    no_punch_in: int | None = None
    coverage_pct: int | None = None
    has_sales_target: bool | None = None
    unique_outlets: int | None = None
    outlets_ordered: int | None = None
    outlets_multi_rep: int | None = None
    net_new_outlets: int | None = None
    assigned_outlets: int | None = None
    beat_adherence_pct: int | None = None
    network_reach_pct: int | None = None
    order_value_paise: int | None = None
    lpsc: float | None = None
    degraded: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class _ManagerSeries:
    key: str
    label: str
    color: str
    sales_person_ids: frozenset[str]


@dataclass(frozen=True)
class _DashboardWindows:
    business_date: date
    month_start: date
    metrics_from: date
    metrics_to: date
    lmtd_from: date
    lmtd_to: date
    prior_month_to: date


_CARD_META: dict[str, _CardMeta] = {
    "ATT": _CardMeta("Punch status and market time", "Schedule", "var(--color-success)"),
    "SC/TC/PC": _CardMeta("Scheduled, total, productive calls", "PhoneInTalk", "var(--color-primary)"),
    "UTC-D": _CardMeta("Unique outlets covered today", "Storefront", "var(--color-info)"),
    "BAD": _CardMeta("Beat adherence", "Checklist", "var(--color-warning)"),
    "PPV": _CardMeta("Visits still pending", "LocationMarker", "var(--color-warning)"),
    "OV": _CardMeta("Order value booked today", "ShoppingCartOutlined", "var(--color-success)"),
    "LPSC": _CardMeta("Lines per sales call", "ViewAgenda", "var(--color-primary)"),
    "IST": _CardMeta("In-store time share", "Timer", "var(--color-info)"),
    "UTC": _CardMeta("Unique outlets visited", "Map", "var(--color-primary)"),
    "RVR": _CardMeta("Revisit ratio", "Autorenew", "var(--color-info)"),
    "COV": _CardMeta("Coverage", "LocationOn", "var(--color-success)"),
    "ECO/UPC": _CardMeta("Outlets ordered", "ReceiptLong", "var(--color-success)"),
    "PROD": _CardMeta("Productivity", "CheckCircle", "var(--color-success)"),
    "UCR": _CardMeta("Unique outlet conversion", "TrendingUp", "var(--color-success)"),
    "ZO": _CardMeta("Zero-order outlets", "DoNotDisturbOn", "var(--color-warning)"),
    "AOV": _CardMeta("Average order value", "PaymentsOutlined", "var(--color-info)"),
    "TLSD": _CardMeta("Unique SKUs sold", "Inventory2Outlined", "var(--color-primary)"),
    "FSC": _CardMeta("Focus SKU compliance", "CenterFocusStrong", "var(--color-primary)"),
    "REP": _CardMeta("Repeat order rate", "Replay", "var(--color-info)"),
    "NEW": _CardMeta("New outlet activation", "AddBusiness", "var(--color-success)"),
    "AGE": _CardMeta("Outlets not visited 30+ days", "AccessTimeFilled", "var(--color-warning)"),
    "UBT": _CardMeta("Unique beats covered", "Route", "var(--color-primary)"),
    "UPD": _CardMeta("Unique outlets per active day", "DateRange", "var(--color-info)"),
    "DAYS": _CardMeta("Attendance and official work", "EventAvailable", "var(--color-success)"),
    "TGT": _CardMeta("Target achievement and run rate", "Flag", "var(--color-primary)"),
    "VOL": _CardMeta("Volume sold", "Scale", "var(--color-info)"),
    "STR": _CardMeta("Team strength split", "Groups", "var(--color-primary)"),
    "PRES": _CardMeta("Present and punch compliance", "FactCheck", "var(--color-success)"),
    "T-CALL": _CardMeta("Team calls and productivity", "SupportAgent", "var(--color-primary)"),
    "T-COV": _CardMeta("Live route coverage", "NearMe", "var(--color-success)"),
    "IDLE": _CardMeta("No activity by 1 PM", "PhoneMissed", "var(--color-warning)"),
    "EXC": _CardMeta("Exception queue", "ReportProblem", "var(--color-warning)"),
    "APP": _CardMeta("Pending approvals and SLA", "Approval", "var(--color-warning)"),
    "T-MTD": _CardMeta("Order value MTD vs LMTD", "ShowChart", "var(--color-success)"),
    "GEO": _CardMeta("Geography-wise sales", "Public", "var(--color-info)"),
    "LEAG": _CardMeta("Rep league table", "Leaderboard", "var(--color-primary)"),
    "T-TGT": _CardMeta("Team target and run rate", "TrackChanges", "var(--color-primary)"),
    "T-UTC": _CardMeta("Team unique outlet reach", "AccountTree", "var(--color-info)"),
    "OVLP": _CardMeta("Outlet overlap", "Hub", "var(--color-warning)"),
    "T-UCR": _CardMeta("Team unique conversion", "TrendingUp", "var(--color-success)"),
    "CHURN": _CardMeta("Outlet churn", "SwapHoriz", "var(--color-warning)"),
    "CVIS": _CardMeta("Combined visit coverage", "Groups2", "var(--color-info)"),
    "GRID": _CardMeta("Daily summary grid and export", "GridView", "var(--color-success)"),
    "SLA": _CardMeta("Approval SLA by manager", "HourglassTop", "var(--color-info)"),
    "UBILL": _CardMeta("Unique outlets ordered & never ordered", "StoreMallDirectory", "var(--color-warning)"),
    "REACH": _CardMeta("Network reach", "WifiTethering", "var(--color-warning)"),
    "REGION": _CardMeta("Region leaderboard", "BarChart", "var(--color-info)"),
    "TGTC": _CardMeta("Target coverage", "TaskAlt", "var(--color-success)"),
}

_SURFACE_GROUPS: dict[schemas.ReportingKpiSurface, tuple[_SurfaceGroup, ...]] = {
    "sp-home": (
        _SurfaceGroup("Route health", ("ATT", "SC/TC/PC", "UTC-D", "BAD")),
        _SurfaceGroup("Execution quality", ("PPV", "OV", "LPSC", "IST")),
    ),
    "sp-dashboard": (
        _SurfaceGroup("Reach and conversion", ("UTC", "RVR", "COV", "ECO/UPC", "UCR", "ZO")),
        _SurfaceGroup("Order quality", ("PROD", "AOV", "TLSD", "FSC", "REP")),
        _SurfaceGroup("Network expansion", ("NEW", "AGE", "UBT", "UPD", "DAYS")),
    ),
    "sp-targets": (_SurfaceGroup("Achievement", ("TGT", "VOL")),),
    "manager-dashboard": (
        _SurfaceGroup("Team pulse", ("STR", "PRES", "T-CALL", "T-COV", "IDLE", "EXC", "APP")),
        _SurfaceGroup("Month momentum", ("T-MTD", "GEO", "LEAG", "T-TGT")),
        _SurfaceGroup("Reach and overlap", ("T-UTC", "OVLP", "T-UCR", "CHURN", "CVIS", "GRID")),
    ),
    "admin-dashboard": (
        _SurfaceGroup("Organization today", ("PRES", "IDLE", "APP", "SC/TC/PC", "T-COV", "REACH")),
        _SurfaceGroup("Reach", ("T-UTC", "ECO/UPC", "REGION")),
    ),
    "manager-targets": (_SurfaceGroup("Target governance", ("T-TGT", "LEAG", "TGTC")),),
    "dashboard-drill": (_SurfaceGroup("Order outcomes", ("OV", "AOV", "ECO/UPC", "ZO", "T-MTD")),),
    "coverage-drill": (_SurfaceGroup("Coverage snapshot", ("COV", "T-COV", "UTC", "T-UTC", "OVLP")),),
    "team-day-drill": (_SurfaceGroup("Day flow", ("UTC-D", "IST", "SC/TC/PC", "OV", "ATT", "BAD")),),
    "approvals-drill": (_SurfaceGroup("Queue and latency", ("APP", "SLA", "EXC")),),
}


def _format_percent(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".") + "%"


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _coverage_pct(visited: int, planned: int) -> int | None:
    if planned <= 0:
        return None
    return round((visited / planned) * 100)


def _mom_pct(mtd_paise: int, lmtd_paise: int) -> int | None:
    if lmtd_paise == 0:
        return None
    return round((mtd_paise - lmtd_paise) / lmtd_paise * 100)


def _lpsc(order_lines_count: int, productive_visits: int) -> float | None:
    if productive_visits == 0:
        return None
    return round(order_lines_count / productive_visits, 1)


def _productivity_pct(productive_visits: int, visits_total: int) -> int:
    if visits_total == 0:
        return 0
    return round(100 * productive_visits / visits_total)


def _money_or_none(paise: int) -> int | None:
    return None if paise == 0 else paise


def _paise_label(paise: int) -> str:
    return f"₹ {round(paise / 100):,}"


def _employee_manufacturer_targets(
    targets_payload: dict[str, Any],
    manufacturer_id: str | None,
) -> dict[str, int]:
    """Each employee's own target line value for `manufacturer_id`. Basis and UOM are not
    carried here — they are fixed per manufacturer, not per employee (`_manufacturer_basis`)."""
    if not manufacturer_id:
        return {}
    found: dict[str, int] = {}
    for target in targets_payload.get("targets") or []:
        employee_id = str(target.get("employee_id") or "")
        if not employee_id:
            continue
        for line in target.get("lines") or []:
            if str(line.get("manufacturer_id") or "") == manufacturer_id:
                found[employee_id] = _to_int(line.get("line_value"))
    return found


def _qty_for_uom(row: dict[str, Any], uom_label: str) -> int:
    """Pick quantity only when the target UOM is the strict volume measure (`Ton`)."""
    by_uom = row.get("qty_by_uom") or {}
    if uom_label != "Ton":
        return 0
    return _to_int(by_uom.get("Ton", 0))


def _league_pct(
    taken_paise: int, taken_qty: int, target_value: int, basis: str, uom_label: str
) -> int | None:
    if target_value <= 0:
        return None
    if basis == "amount" and uom_label == "₹":
        return round(taken_paise / target_value * 100)
    if basis == "volume" and uom_label == "Ton":
        return round(taken_qty / target_value * 100)
    return None


def _section_data(section: dict[str, Any] | None) -> dict[str, Any] | None:
    if not section:
        return None
    if section.get("status") != "available":
        return None
    data = section.get("data")
    return data if isinstance(data, dict) else None


class ReportingService:
    def __init__(
        self, session: Session, *, settings: Settings | None = None, clock: Clock | None = None
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._clock = clock or SystemClock()
        self._degraded: list[dict[str, str]] = []

    def kpi_surface(
        self,
        *,
        claims: AccessTokenClaims,
        surface: schemas.ReportingKpiSurface,
        business_date: date | None,
    ) -> dict[str, Any]:
        as_of_date = business_date or current_business_date(self._clock, settings=self._settings)
        scope = ScopeResolver.resolve_from_claims(claims, OrgResource.ACTIVITY_DATA)
        self._validate_surface_access(scope=scope.scope, surface=surface)

        context = self._load_context(claims=claims, scope=scope, business_date=as_of_date)
        region_rows = (
            self._region_leaderboard(claims=claims, business_date=as_of_date)
            if surface == "admin-dashboard"
            else []
        )
        groups = [
            schemas.KpiGroupOut(
                label=group.label,
                items=[
                    self._build_card(
                        code=code,
                        context=context,
                        region_rows=region_rows,
                    )
                    for code in group.codes
                ],
            )
            for group in _SURFACE_GROUPS[surface]
        ]
        return schemas.KpiSurfaceResponse(
            surface=surface,
            business_date=as_of_date,
            groups=groups,
            region_share_label=_REGION_SHARE_LABEL if region_rows else None,
            region_leaderboard=region_rows,
            degraded=self._degraded_out(),
        ).model_dump(mode="json")

    def admin_coverage_trend(
        self, *, claims: AccessTokenClaims, business_date: date | None, days: int
    ) -> dict[str, Any]:
        as_of_date = business_date or current_business_date(self._clock, settings=self._settings)
        scope = ScopeResolver.resolve_from_claims(claims, OrgResource.ACTIVITY_DATA)
        if scope.scope is not Scope.ORG:
            raise ApiError(403, "forbidden", "Admin-only reporting endpoint.")

        manager_series = self._manager_series(claims)
        route_service = RouteService(self._session, settings=self._settings, clock=self._clock)
        points: list[schemas.CoverageTrendPointOut] = []
        start_date = as_of_date - timedelta(days=max(1, days) - 1)
        window_dates = [start_date + timedelta(days=offset) for offset in range(max(1, days))]

        for day in window_dates:
            coverage_payload = route_service.coverage_team(claims=claims, business_date=day)
            items = coverage_payload.get("items", [])
            values: dict[str, int | None] = {}
            for series in manager_series:
                visited = 0
                planned = 0
                for row in items:
                    employee_id = str(row.get("employee_id", ""))
                    if employee_id not in series.sales_person_ids:
                        continue
                    visited += _to_int(row.get("visited"))
                    planned += _to_int(row.get("planned")) + _to_int(row.get("unplanned_visited"))
                values[series.key] = _coverage_pct(visited, planned)

            points.append(
                schemas.CoverageTrendPointOut(
                    business_date=day,
                    date_label=day.strftime("%d %b"),
                    overall_coverage_pct=coverage_payload.get("coverage_pct"),
                    values=values,
                )
            )

        return schemas.AdminCoverageTrendResponse(
            business_date=as_of_date,
            days=max(1, days),
            series=[
                schemas.CoverageTrendSeriesOut(
                    key=series.key,
                    label=series.label,
                    color=series.color,
                )
                for series in manager_series
            ],
            points=points,
        ).model_dump(mode="json")

    def _validate_surface_access(self, *, scope: Scope, surface: schemas.ReportingKpiSurface) -> None:
        if scope is Scope.SELF and surface in {"manager-dashboard", "admin-dashboard", "manager-targets"}:
            raise ApiError(403, "forbidden", "This KPI surface is not available for this role.")
        if scope is Scope.OWN_TREE and surface in {
            "sp-home",
            "sp-dashboard",
            "sp-targets",
            "admin-dashboard",
        }:
            raise ApiError(403, "forbidden", "This KPI surface is not available for this role.")
        if scope is Scope.ORG and surface in {"sp-home", "sp-dashboard", "sp-targets"}:
            raise ApiError(403, "forbidden", "This KPI surface is not available for this role.")

    def _load_context(
        self, *, claims: AccessTokenClaims, scope: ScopeContext, business_date: date
    ) -> _DashboardContext:
        outlet_facts = self._card_outlet_facts(
            claims=claims, scope=scope, business_date=business_date
        )
        if scope.scope is Scope.SELF:
            today_payload = TodayService(
                self._session, settings=self._settings, clock=self._clock
            ).get_today(claims=claims)
            requests_data = _section_data(today_payload.get("requests"))
            attendance_data = _section_data(today_payload.get("attendance"))
            planned, visited, productive, coverage_pct = self._sp_planned_coverage(
                claims=claims, business_date=business_date
            )
            no_order = (
                max((visited or 0) - (productive or 0), 0)
                if visited is not None and productive is not None
                else None
            )
            pending = _to_int(requests_data.get("pending_count")) if requests_data else None
            if pending is None and isinstance(requests_data, dict):
                pending = len(requests_data.get("items", []))
            has_sales_target = self._has_sales_target(claims=claims, business_date=business_date)
            return _DashboardContext(
                role_scope=scope.scope,
                business_date=business_date,
                planned=planned,
                visited=visited,
                productive=productive,
                no_order=no_order,
                pending_approvals=pending,
                team_total=1 if attendance_data else None,
                on_duty=int(bool(attendance_data.get("on_duty"))) if attendance_data else None,
                no_punch_in=int(not attendance_data.get("on_duty")) if attendance_data else None,
                coverage_pct=coverage_pct,
                has_sales_target=has_sales_target,
                degraded=self._degraded,
                **outlet_facts,
            )

        attendance = AttendanceService(
            self._session, settings=self._settings, clock=self._clock
        ).team(claims=claims, business_date=business_date, page=1, page_size=1)
        approvals = ApprovalService(
            self._session, settings=self._settings, clock=self._clock
        ).get_summary(claims=claims)
        team_total = _to_int(attendance.get("total"))
        on_duty = _to_int(attendance.get("on_duty_count"))
        no_punch = _to_int(attendance.get("no_punch_in_count"))
        planned, visited, productive, coverage_pct = self._team_coverage(
            claims=claims, business_date=business_date
        )
        pending_approvals = approvals.get("pending_total")
        return _DashboardContext(
            role_scope=scope.scope,
            business_date=business_date,
            planned=planned,
            visited=visited,
            productive=productive,
            no_order=max(0, visited - (productive or 0)) if visited else None,
            pending_approvals=pending_approvals,
            team_total=team_total if team_total > 0 else None,
            on_duty=on_duty if team_total > 0 else None,
            no_punch_in=no_punch if team_total > 0 else None,
            coverage_pct=coverage_pct,
            has_sales_target=None,
            degraded=self._degraded,
            **outlet_facts,
        )

    def _build_card(
        self,
        *,
        code: str,
        context: _DashboardContext,
        region_rows: list[schemas.RegionLeaderboardRowOut],
    ) -> schemas.KpiCardOut:
        meta = _CARD_META.get(
            code,
            _CardMeta(code, "InfoFilled", "var(--color-text-secondary)"),
        )
        unavailable = self._unavailable_card(code=code, meta=meta)

        if code in {"COV", "T-COV"} and context.coverage_pct is not None:
            return schemas.KpiCardOut(
                code=code,
                title=meta.title,
                value=f"{context.coverage_pct}%",
                subtitle=self._planned_subtitle(context),
                icon=meta.icon,
                tone=meta.tone,
            )
        if code == "BAD" and context.beat_adherence_pct is not None:
            return schemas.KpiCardOut(
                code=code,
                title=meta.title,
                value=f"{context.beat_adherence_pct}%",
                subtitle="Planned outlets visited / total visits",
                icon=meta.icon,
                tone=meta.tone,
            )
        if code == "REACH" and context.network_reach_pct is not None:
            return schemas.KpiCardOut(
                code=code,
                title=meta.title,
                value=f"{context.network_reach_pct}%",
                subtitle="Unique visited / assigned beat outlets",
                icon=meta.icon,
                tone=meta.tone,
            )
        if code in {"SC/TC/PC", "T-CALL"} and context.planned is not None and context.visited is not None:
            productive = context.productive if context.productive is not None else 0
            return schemas.KpiCardOut(
                code=code,
                title=meta.title,
                value=f"{context.planned} / {context.visited} / {productive}",
                subtitle="Planned / total / productive",
                icon=meta.icon,
                tone=meta.tone,
            )
        if code in {"UTC-D", "UTC", "T-UTC"} and context.unique_outlets is not None:
            return schemas.KpiCardOut(
                code=code,
                title=meta.title,
                value=str(context.unique_outlets),
                subtitle="Distinct outlets in scope",
                icon=meta.icon,
                tone=meta.tone,
            )
        if code == "ECO/UPC" and context.outlets_ordered is not None:
            return schemas.KpiCardOut(
                code=code,
                title=meta.title,
                value=str(context.outlets_ordered),
                subtitle="Distinct outlets with an order",
                icon=meta.icon,
                tone=meta.tone,
            )
        if code == "PROD" and context.productive is not None and context.visited is not None:
            productivity_pct = _coverage_pct(context.productive, context.visited)
            return schemas.KpiCardOut(
                code=code,
                title=meta.title,
                value=f"{productivity_pct}%" if productivity_pct is not None else "—",
                subtitle="Derived from visit outcomes",
                icon=meta.icon,
                tone=meta.tone,
            )
        if code == "PPV" and context.planned is not None and context.visited is not None:
            return schemas.KpiCardOut(
                code=code,
                title=meta.title,
                value=str(max(0, context.planned - context.visited)),
                subtitle="Planned outlets pending",
                icon=meta.icon,
                tone=meta.tone,
            )
        if code == "ZO" and context.unique_outlets is not None and context.outlets_ordered is not None:
            return schemas.KpiCardOut(
                code=code,
                title=meta.title,
                value=str(max(0, context.unique_outlets - context.outlets_ordered)),
                subtitle="Visited outlets with no order",
                icon=meta.icon,
                tone=meta.tone,
            )
        if code == "OV" and context.order_value_paise is not None:
            return schemas.KpiCardOut(
                code=code,
                title=meta.title,
                value=_paise_label(context.order_value_paise),
                subtitle="Net order value today",
                icon=meta.icon,
                tone=meta.tone,
            )
        if code == "LPSC" and context.lpsc is not None:
            return schemas.KpiCardOut(
                code=code,
                title=meta.title,
                value=str(context.lpsc),
                subtitle="Lines per productive visit",
                icon=meta.icon,
                tone=meta.tone,
            )
        if (
            code in {"UCR", "T-UCR"}
            and context.unique_outlets is not None
            and context.outlets_ordered is not None
        ):
            conversion_pct = _coverage_pct(context.outlets_ordered, context.unique_outlets)
            if conversion_pct is not None:
                return schemas.KpiCardOut(
                    code=code,
                    title=meta.title,
                    value=f"{conversion_pct}%",
                    subtitle="Ordered / unique outlets",
                    icon=meta.icon,
                    tone=meta.tone,
                )
        if code == "OVLP" and context.outlets_multi_rep is not None:
            return schemas.KpiCardOut(
                code=code,
                title=meta.title,
                value=str(context.outlets_multi_rep),
                subtitle="Outlets visited by 2+ reps",
                icon=meta.icon,
                tone=meta.tone,
            )
        if code == "NEW" and context.net_new_outlets is not None:
            return schemas.KpiCardOut(
                code=code,
                title=meta.title,
                value=str(context.net_new_outlets),
                subtitle="Outlets first visited this month",
                icon=meta.icon,
                tone=meta.tone,
            )
        if code == "APP" and context.pending_approvals is not None:
            return schemas.KpiCardOut(
                code=code,
                title=meta.title,
                value=str(context.pending_approvals),
                subtitle="Pending approval queue",
                icon=meta.icon,
                tone=meta.tone,
            )
        if code == "STR" and context.team_total is not None:
            return schemas.KpiCardOut(
                code=code,
                title=meta.title,
                value=str(context.team_total),
                subtitle="Active people in scope",
                icon=meta.icon,
                tone=meta.tone,
            )
        if code == "PRES" and context.team_total is not None and context.on_duty is not None:
            pct = _coverage_pct(context.on_duty, context.team_total)
            return schemas.KpiCardOut(
                code=code,
                title=meta.title,
                value=f"{context.on_duty}/{context.team_total}",
                subtitle=f"{pct}%" if pct is not None else "—",
                icon=meta.icon,
                tone=meta.tone,
            )
        if code == "IDLE" and context.no_punch_in is not None:
            return schemas.KpiCardOut(
                code=code,
                title=meta.title,
                value=f"{context.no_punch_in} reps",
                subtitle="No punch-in yet",
                icon=meta.icon,
                tone=meta.tone,
            )
        if code == "EXC":
            parts = [context.pending_approvals, context.no_punch_in]
            total = sum(part for part in parts if isinstance(part, int))
            if total > 0:
                return schemas.KpiCardOut(
                    code=code,
                    title=meta.title,
                    value=str(total),
                    subtitle="Approvals + no-punch exceptions",
                    icon=meta.icon,
                    tone=meta.tone,
                )
        if code in {"TGT", "T-TGT", "TGTC"}:
            if context.has_sales_target is False:
                return schemas.KpiCardOut(
                    code=code,
                    title=meta.title,
                    value="No target",
                    subtitle="No target set for current month",
                    icon=meta.icon,
                    tone=meta.tone,
                    availability="no_target",
                    status_note="Target is optional",
                )
            if context.has_sales_target is True:
                return schemas.KpiCardOut(
                    code=code,
                    title=meta.title,
                    value="—",
                    subtitle="Target set; achievement feed unavailable",
                    icon=meta.icon,
                    tone=meta.tone,
                    availability="unavailable",
                    status_note="Awaiting Humbee achievement capability",
                )
            return schemas.KpiCardOut(
                code=code,
                title=meta.title,
                value="—",
                subtitle="Target status unavailable",
                icon=meta.icon,
                tone=meta.tone,
                availability="unavailable",
                status_note="Target lookup failed",
            )
        if code == "REGION":
            if region_rows:
                top = region_rows[0]
                return schemas.KpiCardOut(
                    code=code,
                    title=meta.title,
                    value=f"{top.region} {top.share_label}",
                    subtitle="Share of org sales",
                    icon=meta.icon,
                    tone=meta.tone,
                )
            return schemas.KpiCardOut(
                code=code,
                title=meta.title,
                value="—",
                subtitle="No regional sales data available",
                icon=meta.icon,
                tone=meta.tone,
                availability="unavailable",
                status_note="Region leaderboard requires non-zero net order value",
            )
        return unavailable

    def _planned_subtitle(self, context: _DashboardContext) -> str:
        if context.visited is None or context.planned is None:
            return "Coverage data unavailable"
        return f"{context.visited}/{context.planned} visits completed"

    def _unavailable_card(self, *, code: str, meta: _CardMeta) -> schemas.KpiCardOut:
        return schemas.KpiCardOut(
            code=code,
            title=meta.title,
            value="—",
            subtitle="Live KPI source not released",
            icon=meta.icon,
            tone=meta.tone,
            availability="unavailable",
            status_note="Awaiting source capability",
        )

    def _region_leaderboard(
        self, *, claims: AccessTokenClaims, business_date: date
    ) -> list[schemas.RegionLeaderboardRowOut]:
        scope = ScopeResolver.resolve_from_claims(claims, OrgResource.ACTIVITY_DATA)
        if scope.scope is not Scope.ORG:
            raise ApiError(403, "forbidden", "Admin-only reporting endpoint.")
        month_start = business_date.replace(day=1)
        employee_rows = repository.list_employee_net_values(
            self._session,
            tenant_id=claims.tenant_id,
            from_date=month_start,
            to_date=business_date,
        )
        zone_labels = list_employee_zone_labels(self._session, tenant_id=claims.tenant_id)
        grouped: dict[str, int] = {}
        for employee_id, region_name, net_value_paise in employee_rows:
            if net_value_paise <= 0:
                continue
            label = region_name or zone_labels.get(employee_id) or "Unassigned"
            grouped[label] = grouped.get(label, 0) + net_value_paise
        org_total = sum(grouped.values())
        ranked = sorted(grouped.items(), key=lambda item: item[1], reverse=True)
        if org_total <= 0:
            return []
        return [
            schemas.RegionLeaderboardRowOut(
                region=region,
                net_value_paise=net_value_paise,
                share_pct=(net_value_paise / org_total) * 100,
                share_label=_format_percent((net_value_paise / org_total) * 100),
            )
            for region, net_value_paise in ranked
        ]

    def _has_sales_target(self, *, claims: AccessTokenClaims, business_date: date) -> bool:
        payload = TargetService(self._session, settings=self._settings, clock=self._clock).list_targets(
            claims=claims,
            employee_id=claims.employee_id,
            period_month=business_date.replace(day=1),
            target_type="sales",
        )
        return bool(payload["targets"])

    def _manager_series(self, claims: AccessTokenClaims) -> list[_ManagerSeries]:
        tree_payload = OrgService(
            self._session, settings=self._settings, clock=self._clock
        ).get_tree(claims=claims)
        roots = tree_payload.get("roots", [])
        managers: list[_ManagerSeries] = []

        def walk(node: dict[str, Any]) -> None:
            if str(node.get("role_code", "")).lower() == "manager":
                # Direct SPs only — nested managers share the same subtree and would
                # otherwise draw identical coverage lines on top of Overall.
                team_ids = {
                    str(child.get("id", ""))
                    for child in node.get("children", [])
                    if str(child.get("role_code", "")).lower() == "sales_person" and child.get("id")
                }
                manager_id = str(node.get("id", ""))
                if manager_id and team_ids:
                    managers.append(
                        _ManagerSeries(
                            key=f"managerCoveragePct_{manager_id}",
                            label=str(node.get("full_name", manager_id)),
                            color=_TREND_COLORS[len(managers) % len(_TREND_COLORS)],
                            sales_person_ids=frozenset(team_ids),
                        )
                    )
            for child in node.get("children", []):
                walk(child)

        for root in roots:
            if isinstance(root, dict):
                walk(root)

        return sorted(managers, key=lambda series: series.label.lower())

    @cached_property
    def _manufacturer_roster(self) -> list[dict[str, Any]] | None:
        end_read_transaction(self._session)
        try:
            roster: list[dict[str, Any]] = TargetService(
                self._session, settings=self._settings, clock=self._clock
            ).list_manufacturers()["manufacturers"]
        except ApiError as exc:
            logger.warning(
                "reporting_dashboard_source_unavailable",
                source="target_manufacturers",
                error=exc.code,
            )
            self._degraded.append({"source": "target_manufacturers", "reason": exc.code})
            return None
        return roster

    # --- Phase 1 fact table KPI calculations ---

    def _dashboard_windows(self, period: schemas.DashboardPeriod) -> _DashboardWindows:
        business_date = current_business_date(self._clock, settings=self._settings)
        month_start = business_date.replace(day=1)
        prior_month_to = month_start - timedelta(days=1)
        lmtd_from = prior_month_to.replace(day=1)
        lmtd_to = min(lmtd_from + timedelta(days=business_date.day - 1), prior_month_to)
        if period == "mtd":
            metrics_from, metrics_to = month_start, business_date
        else:
            metrics_from, metrics_to = business_date, business_date
        return _DashboardWindows(
            business_date=business_date,
            month_start=month_start,
            metrics_from=metrics_from,
            metrics_to=metrics_to,
            lmtd_from=lmtd_from,
            lmtd_to=lmtd_to,
            prior_month_to=prior_month_to,
        )

    def _employee_day_facts(
        self,
        *,
        tenant_id: str,
        window_start: date,
        window_end: date,
        extra: tuple[ColumnElement[bool], ...] = (),
    ) -> Sequence[Row[Any]]:
        return self._session.execute(
            select(
                FactEmployeeDay.employee_id,
                FactEmployeeDay.visits_total,
                FactEmployeeDay.productive_visits,
                FactEmployeeDay.order_net_value_paise,
                FactEmployeeDay.orders_submitted_count,
                FactEmployeeDay.order_lines_count,
                FactEmployeeDay.unplanned_visits,
                FactEmployeeDay.distance_metres,
                FactEmployeeDay.punched_in,
            ).where(
                FactEmployeeDay.tenant_id == tenant_id,
                FactEmployeeDay.business_date >= window_start,
                FactEmployeeDay.business_date <= window_end,
                *extra,
            )
        ).all()

    def get_sp_attention(self, *, claims: AccessTokenClaims) -> dict[str, Any]:
        scope = ScopeResolver.resolve_from_claims(claims, OrgResource.ACTIVITY_DATA)
        self._validate_surface_access(scope=scope.scope, surface="sp-home")
        business_date = current_business_date(self._clock, settings=self._settings)
        items: list[schemas.AttentionItemOut] = []

        assigned = BeatService(
            self._session, settings=self._settings, clock=self._clock
        ).list_assigned_outlets(claims=claims)
        if assigned:
            last_visits = repository.last_visit_dates(
                self._session,
                tenant_id=claims.tenant_id,
                employee_id=claims.employee_id,
            )
            stale: list[tuple[int | None, str]] = []
            for outlet in assigned:
                if not isinstance(outlet, dict):
                    continue
                outlet_id = str(outlet.get("humbee_outlet_id") or "")
                name = str(outlet.get("name") or "").strip()
                if not outlet_id or not name:
                    continue
                last_visit = last_visits.get(outlet_id)
                days = (business_date - last_visit).days if last_visit is not None else None
                if days is None or days > 30:
                    stale.append((days, name))
            if stale:
                never_visited = [name for days, name in stale if days is None]
                oldest = max((item for item in stale if item[0] is not None), default=None)
                if never_visited:
                    subtitle = f"Never visited · {never_visited[0]}"
                elif oldest is not None:
                    subtitle = f"Oldest {oldest[0]} days · {oldest[1]}"
                else:
                    subtitle = "No visit in the last 30 days"
                count = len(stale)
                plural = "" if count == 1 else "s"
                # A never-visited outlet may simply be a fresh assignment (no assignment date is
                # available from list_assigned_outlets to tell "new" from "overdue" apart), so the
                # title only claims a concrete "30+ days" age when every item in the bucket has one.
                title = (
                    f"{count} outlet{plural} need a visit"
                    if never_visited
                    else f"{count} outlet{plural} untouched 30+ days"
                )
                items.append(
                    schemas.AttentionItemOut(
                        kind="untouched",
                        title=title,
                        subtitle=subtitle,
                        action="View",
                    )
                )

        signals = OrderService(
            self._session, settings=self._settings, clock=self._clock
        ).attention_signals(claims=claims, business_date=business_date)
        dropoff = signals.get("dropoff")
        if isinstance(dropoff, dict):
            count = _to_int(dropoff.get("outlet_count"))
            manufacturer = str(dropoff.get("manufacturer_name") or "").strip()
            previous_month = str(dropoff.get("previous_month_label") or "").strip()
            current_month = str(dropoff.get("current_month_label") or "").strip()
            if count > 0 and manufacturer:
                items.append(
                    schemas.AttentionItemOut(
                        kind="stopped_ordering",
                        title=f"{count} outlet{'' if count == 1 else 's'} stopped ordering {manufacturer}",
                        subtitle=(
                            f"Ordered in {previous_month}, none in {current_month}"
                            if previous_month and current_month
                            else "No order this month after ordering last month"
                        ),
                        action="View",
                    )
                )
        failed_count = _to_int(signals.get("failed_count"))
        if failed_count > 0:
            items.append(
                schemas.AttentionItemOut(
                    kind="failed_downstream",
                    title=f"{failed_count} order{'' if failed_count == 1 else 's'} failed downstream",
                    subtitle="Approved, rejected by Humbee",
                    action="Fix",
                )
            )

        return schemas.SpAttentionResponse(
            business_date=business_date,
            items=items,
        ).model_dump(mode="json")

    def _period_visit_totals(
        self,
        *,
        tenant_id: str,
        window_start: date,
        window_end: date,
        extra: tuple[ColumnElement[bool], ...] = (),
    ) -> tuple[int, int, int, int, int, int]:
        day_rows = self._employee_day_facts(
            tenant_id=tenant_id,
            window_start=window_start,
            window_end=window_end,
            extra=extra,
        )
        return (
            sum(_to_int(row.visits_total) for row in day_rows),
            sum(_to_int(row.productive_visits) for row in day_rows),
            sum(_to_int(row.orders_submitted_count) for row in day_rows),
            sum(_to_int(row.order_lines_count) for row in day_rows),
            sum(_to_int(row.unplanned_visits) for row in day_rows),
            sum(_to_int(row.distance_metres) for row in day_rows),
        )

    def _with_live_today(
        self,
        *,
        tenant_id: str,
        period: schemas.DashboardPeriod,
        windows: _DashboardWindows,
        extra: tuple[ColumnElement[bool], ...],
        visits_total: int,
        productive_visits: int,
        coverage: tuple[int, int | None, int | None, int | None],
    ) -> tuple[int, int, int, int | None]:
        planned_visits, live_visited, live_productive, coverage_pct = coverage
        today_visits, today_productive, *_ = self._period_visit_totals(
            tenant_id=tenant_id,
            window_start=windows.business_date,
            window_end=windows.business_date,
            extra=extra,
        )
        visits_total += max(live_visited or 0, today_visits) - today_visits
        productive_visits += max(live_productive or 0, today_productive) - today_productive
        if period != "today":
            planned_visits, coverage_pct = 0, None
        return visits_total, productive_visits, planned_visits, coverage_pct

    def _manufacturer_basis(self, manufacturer_id: str | None) -> tuple[str, str]:
        if not manufacturer_id or self._manufacturer_roster is None:
            return "", ""
        for item in self._manufacturer_roster:
            if item["manufacturer_id"] == manufacturer_id:
                return item["basis"], item["uom_label"]
        return "", ""

    def _sum_money(
        self,
        scope: ScopeContext,
        from_date: date,
        to_date: date,
        manufacturer_id: str | None,
    ) -> int:
        return repository.sum_money_by_window(
            self._session,
            scope=scope,
            from_date=from_date,
            to_date=to_date,
            manufacturer_id=manufacturer_id,
        )

    def _mom_out(
        self,
        scope: ScopeContext,
        windows: _DashboardWindows,
        manufacturer_id: str | None,
    ) -> schemas.MoneyWindowOut:
        mtd_paise = self._sum_money(
            scope, windows.month_start, windows.business_date, manufacturer_id
        )
        lmtd_paise = self._sum_money(scope, windows.lmtd_from, windows.lmtd_to, manufacturer_id)
        return schemas.MoneyWindowOut(
            mtd_paise=mtd_paise,
            lmtd_paise=lmtd_paise,
            mom_pct=_mom_pct(mtd_paise, lmtd_paise),
        )

    def _degraded_out(self) -> list[schemas.DegradedSourceOut]:
        return [
            schemas.DegradedSourceOut(source=item["source"], reason=item["reason"])
            for item in self._degraded
        ]

    def _manufacturer_totals_by_id(
        self,
        scope: ScopeContext,
        from_date: date,
        to_date: date,
        manufacturer_id: str | None,
        employee_ids: list[str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        if employee_ids is not None and not employee_ids:
            return {}
        rows = repository.list_manufacturer_totals(
            self._session,
            scope=scope,
            from_date=from_date,
            to_date=to_date,
            manufacturer_id=manufacturer_id,
            employee_ids=employee_ids,
        )
        return {str(row["manufacturer_id"]): row for row in rows}

    def _sp_order_measures(
        self, manufacturer_totals: dict[str, dict[str, Any]]
    ) -> tuple[int | None, int | None, str | None]:
        manufacturers = self._manufacturer_roster
        if manufacturers is None:
            return None, None, None

        amount_ids = {
            str(item.get("manufacturer_id"))
            for item in manufacturers
            if item.get("basis") == "amount"
        }
        volume_uom_by_id = {
            str(item.get("manufacturer_id")): str(item.get("uom_label"))
            for item in manufacturers
            if item.get("basis") == "volume"
        }
        classified_ids = amount_ids | set(volume_uom_by_id)
        if set(manufacturer_totals) - classified_ids:
            self._degraded.append(
                {"source": "order_measures", "reason": "UnclassifiedManufacturer"}
            )
            return None, None, None

        order_value_paise = sum(
            _to_int(manufacturer_totals.get(manufacturer_id, {}).get("net_value_paise"))
            for manufacturer_id in amount_ids
        )
        volume_uoms = set(volume_uom_by_id.values())
        if not volume_uoms:
            return order_value_paise, None, None
        if len(volume_uoms) > 1:
            self._degraded.append(
                {"source": "order_volume", "reason": "IncompatibleUnits"}
            )
            return order_value_paise, None, None

        order_volume_uom = next(iter(volume_uoms))
        order_volume_units = 0
        for manufacturer_id in volume_uom_by_id:
            quantities = manufacturer_totals.get(manufacturer_id, {}).get("qty_by_uom", {})
            if any(
                label != order_volume_uom and _to_int(qty) > 0
                for label, qty in quantities.items()
            ):
                self._degraded.append(
                    {"source": "order_volume", "reason": "IncompatibleUnits"}
                )
                return order_value_paise, None, None
            order_volume_units += _to_int(quantities.get(order_volume_uom))
        return order_value_paise, order_volume_units, order_volume_uom

    def _map_target_lines(
        self,
        targets_payload: dict[str, Any],
        *,
        femd_by_id: dict[str, dict[str, Any]],
        manufacturer_id: str | None,
    ) -> list[schemas.TargetLineOut]:
        buckets: dict[tuple[str, str], dict[str, Any]] = {}
        for target in targets_payload.get("targets") or []:
            for line in target.get("lines") or []:
                mid = str(line.get("manufacturer_id") or "")
                if not mid or (manufacturer_id and mid != manufacturer_id):
                    continue
                basis = str(line.get("line_basis") or "")
                key = (mid, basis)
                bucket = buckets.setdefault(
                    key,
                    {
                        "manufacturer_id": mid,
                        "label": str(line.get("manufacturer_label") or mid),
                        "basis": basis,
                        "uom_label": str(line.get("uom_label") or ""),
                        "target_value": 0,
                    },
                )
                bucket["target_value"] += _to_int(line.get("line_value"))
        rows: list[schemas.TargetLineOut] = []
        for (mid, basis), bucket in buckets.items():
            taken = femd_by_id.get(mid) or {}
            taken_paise = _to_int(taken.get("net_value_paise"))
            taken_qty = _qty_for_uom(taken, bucket["uom_label"])
            taken_lines = _to_int(taken.get("lines_count"))
            pct = _league_pct(
                taken_paise,
                taken_qty,
                bucket["target_value"],
                basis,
                bucket["uom_label"],
            )
            rows.append(
                schemas.TargetLineOut(
                    manufacturer_id=mid,
                    label=bucket["label"],
                    basis=basis,
                    uom_label=bucket["uom_label"],
                    target_value=bucket["target_value"],
                    taken_paise=taken_paise,
                    taken_qty=taken_qty,
                    taken_lines=taken_lines,
                    pct=pct,
                )
            )
        return rows

    def _targets_summary_out(
        self,
        targets_payload: dict[str, Any],
        *,
        scope: ScopeContext,
        windows: _DashboardWindows,
        manufacturer_id: str | None,
    ) -> schemas.TargetsSummaryOut:
        amount_lines: list[tuple[str, str, int]] = []
        for target in targets_payload.get("targets") or []:
            employee_id = str(target.get("employee_id") or "")
            for line in target.get("lines") or []:
                if str(line.get("line_basis") or "") != "amount":
                    continue
                mid = str(line.get("manufacturer_id") or "")
                if not employee_id or not mid:
                    continue
                if manufacturer_id and mid != manufacturer_id:
                    continue
                amount_lines.append((employee_id, mid, _to_int(line.get("line_value"))))
        total = len(amount_lines)
        if total == 0:
            return schemas.TargetsSummaryOut(on_track=0, at_risk=0, total_amount_lines=0)
        days_in_month = monthrange(windows.business_date.year, windows.business_date.month)[1]
        pace = windows.business_date.day / days_in_month
        taken_by = repository.list_employee_manufacturer_money(
            self._session,
            scope=scope,
            from_date=windows.month_start,
            to_date=windows.business_date,
            manufacturer_ids={mid for _employee_id, mid, _value in amount_lines},
        )
        on_track = 0
        for employee_id, mid, target_value in amount_lines:
            taken = taken_by.get((employee_id, mid), 0)
            if target_value > 0 and (taken / target_value) >= pace:
                on_track += 1
        return schemas.TargetsSummaryOut(
            on_track=on_track,
            at_risk=total - on_track,
            total_amount_lines=total,
        )

    def _scatter(
        self, scope: ScopeContext, windows: _DashboardWindows
    ) -> list[schemas.ScatterPointOut]:
        totals = repository.list_employee_totals(
            self._session,
            scope=scope,
            from_date=windows.month_start,
            to_date=windows.business_date,
        )
        ranked = sorted(totals, key=lambda row: row["net_value_paise"], reverse=True)
        return [
            schemas.ScatterPointOut(
                employee_id=row["employee_id"],
                name=row["name"],
                adherence_pct=_coverage_pct(row["productive_visits"], row["visits_total"]),
                conversion_pct=_coverage_pct(row["outlets_converted"], row["outlets_visited"]),
            )
            for row in ranked
        ]

    def _designation_progress(
        self,
        *,
        scope: ScopeContext,
        windows: _DashboardWindows,
        manufacturer_id: str | None,
        targets_payload: dict[str, Any],
        designation_by_id: dict[str, str],
    ) -> list[schemas.LeagueRowOut]:
        """One row per employee in `designation_by_id`, rolled up across that employee's
        own subtree (self plus every descendant down to the L5 salesperson leaves), and
        ordered by hierarchy level then name.

        Only the leaf sales person does field activity — a manager's own
        `FactEmployeeDay`/`FactEmployeeManufacturerDay` rows are typically empty, so
        this sums every descendant's totals onto the manager's row instead of
        reading the manager's own (usually zero) fact data.
        """
        manager_ids = sorted(designation_by_id)
        if not manager_ids:
            return []

        subtree_by_manager = org_service.list_subtree_ids_by_manager(
            self._session, scope=scope, manager_ids=manager_ids
        )
        member_ids = sorted({
            member_id for members in subtree_by_manager.values() for member_id in members
        })
        totals_by_member = {
            str(row["employee_id"]): row
            for row in repository.list_employee_totals(
                self._session,
                scope=scope,
                from_date=windows.month_start,
                to_date=windows.business_date,
                manufacturer_id=manufacturer_id,
                employee_ids=member_ids,
            )
        }
        names = repository.list_display_names(
            self._session, tenant_id=scope.tenant_id, employee_ids=set(manager_ids)
        )
        targets = _employee_manufacturer_targets(targets_payload, manufacturer_id)
        basis, uom_label = self._manufacturer_basis(manufacturer_id)
        team_target_holders = {
            holder_id
            for holder_id, members in org_service.list_subtree_ids_by_manager(
                self._session, scope=scope, manager_ids=sorted(set(targets) & set(member_ids))
            ).items()
            if any(member_id != holder_id and member_id in targets for member_id in members)
        }

        built: list[schemas.LeagueRowOut] = []
        for manager_id in manager_ids:
            taken_paise = 0
            outlets_ordered = 0
            all_qty_by_uom: dict[str, int] = {}
            # A manager's team target is the sum of the targets beneath them; their own line
            # counts only when nobody below them holds one.
            target_value = 0
            for member_id in subtree_by_manager.get(manager_id, [manager_id]):
                member_row = totals_by_member.get(member_id)
                if member_row is not None:
                    taken_paise += _to_int(member_row.get("net_value_paise"))
                    outlets_ordered += _to_int(member_row.get("outlets_ordered"))
                    for label, qty in (member_row.get("qty_by_uom") or {}).items():
                        all_qty_by_uom[label] = all_qty_by_uom.get(label, 0) + _to_int(qty)
                if member_id not in team_target_holders:
                    target_value += targets.get(member_id, 0)

            has_target = target_value > 0
            taken_qty = _qty_for_uom({"qty_by_uom": all_qty_by_uom}, uom_label)
            pct = (
                _league_pct(taken_paise, taken_qty, target_value, basis, uom_label)
                if has_target
                else None
            )

            built.append(
                schemas.LeagueRowOut(
                    employee_id=manager_id,
                    name=names.get(manager_id, manager_id),
                    net_value_paise=taken_paise,
                    outlets_ordered=outlets_ordered,
                    pct=pct,
                    taken_qty=taken_qty,
                    uom_label=uom_label,
                    has_target=has_target,
                    target_value=target_value if has_target else None,
                    target_basis=basis,
                    designation_code=designation_by_id[manager_id],
                )
            )
        built.sort(
            key=lambda row: (
                _LEVEL_BY_DESIGNATION.get(row.designation_code, len(_CALLS_LADDER)),
                row.designation_code,
                row.name.lower(),
            )
        )
        return built

    def _district_rows(
        self,
        scope: ScopeContext,
        windows: _DashboardWindows,
        manufacturer_id: str | None,
        claims: AccessTokenClaims,
    ) -> list[schemas.DistrictRowOut]:
        # FEOD has no manufacturer grain — manufacturer_id is accepted and ignored.
        mtd_rows = repository.list_district_totals(
            self._session,
            scope=scope,
            from_date=windows.month_start,
            to_date=windows.business_date,
            manufacturer_id=manufacturer_id,
        )
        lmtd_rows = repository.list_district_totals(
            self._session,
            scope=scope,
            from_date=windows.lmtd_from,
            to_date=windows.lmtd_to,
            manufacturer_id=manufacturer_id,
        )
        labels = list_district_labels(self._session, tenant_id=claims.tenant_id)
        mtd_by_id = {row["district_id"]: row for row in mtd_rows}
        lmtd_by_id = {row["district_id"]: row for row in lmtd_rows}
        rows: list[schemas.DistrictRowOut] = []
        for district_key in set(mtd_by_id) | set(lmtd_by_id):
            district_id = "" if district_key is None else str(district_key)
            label = (
                "Unassigned"
                if not district_id
                else str(labels.get(district_id) or district_id)
            )
            mtd_paise = _to_int((mtd_by_id.get(district_key) or {}).get("net_value_paise"))
            lmtd_paise = _to_int((lmtd_by_id.get(district_key) or {}).get("net_value_paise"))
            rows.append(
                schemas.DistrictRowOut(
                    district_id=district_id,
                    label=label,
                    mtd_paise=mtd_paise,
                    lmtd_paise=lmtd_paise,
                    mom_pct=_mom_pct(mtd_paise, lmtd_paise),
                )
            )
        rows.sort(key=lambda row: row.mtd_paise, reverse=True)
        return rows

    def _manufacturer_movement(
        self,
        scope: ScopeContext,
        windows: _DashboardWindows,
        manufacturer_id: str | None,
    ) -> list[schemas.ManufacturerMoveOut]:
        mtd_by_id = self._manufacturer_totals_by_id(
            scope, windows.month_start, windows.business_date, manufacturer_id
        )
        lmtd_by_id = self._manufacturer_totals_by_id(
            scope, windows.lmtd_from, windows.lmtd_to, manufacturer_id
        )
        rows: list[schemas.ManufacturerMoveOut] = []
        for mid in set(mtd_by_id) | set(lmtd_by_id):
            mtd = mtd_by_id.get(mid) or {}
            lmtd = lmtd_by_id.get(mid) or {}
            mtd_paise = _to_int(mtd.get("net_value_paise"))
            lmtd_paise = _to_int(lmtd.get("net_value_paise"))
            rows.append(
                schemas.ManufacturerMoveOut(
                    manufacturer_id=mid,
                    label=str(mtd.get("label") or lmtd.get("label") or mid),
                    mtd_paise=mtd_paise,
                    lmtd_paise=lmtd_paise,
                    mom_pct=_mom_pct(mtd_paise, lmtd_paise),
                )
            )
        rows.sort(key=lambda row: row.mtd_paise, reverse=True)
        return rows

    def _sp_planned_coverage(
        self, *, claims: AccessTokenClaims, business_date: date
    ) -> tuple[int, int | None, int | None, int | None]:
        total = RouteService(
            self._session, settings=self._settings, clock=self._clock
        ).day_totals(
            tenant_id=claims.tenant_id,
            employee_ids=[claims.employee_id],
            business_date=business_date,
        )[claims.employee_id]
        return (
            _to_int(total.planned),
            _to_int(total.visited),
            _to_int(total.productive),
            total.coverage_pct,
        )

    def _team_coverage(
        self, *, claims: AccessTokenClaims, business_date: date
    ) -> tuple[int, int | None, int | None, int | None]:
        payload = RouteService(
            self._session, settings=self._settings, clock=self._clock
        ).coverage_team(claims=claims, business_date=business_date)
        return (
            _to_int(payload.get("planned")),
            _to_int(payload.get("visited")),
            _to_int(payload.get("productive")),
            payload.get("coverage_pct"),
        )

    def _team_attendance(
        self, *, claims: AccessTokenClaims, business_date: date
    ) -> dict[str, int]:
        payload = AttendanceService(
            self._session, settings=self._settings, clock=self._clock
        ).team(claims=claims, business_date=business_date, page=1, page_size=1)
        return {
            "total": payload["total"],
            "punched_in": payload["total"] - payload["no_punch_in_count"] - payload["on_leave_count"],
            "on_duty": payload["on_duty_count"],
            "no_punch_in": payload["no_punch_in_count"],
            "on_leave": payload["on_leave_count"],
        }

    def _pending_approvals(self, *, claims: AccessTokenClaims) -> int:
        payload = ApprovalService(
            self._session, settings=self._settings, clock=self._clock
        ).get_summary(claims=claims)
        return _to_int(payload.get("pending_total"))

    def _approval_latency_out(
        self, *, claims: AccessTokenClaims, windows: _DashboardWindows
    ) -> schemas.ApprovalLatencyOut:
        summary = ApprovalService(
            self._session, settings=self._settings, clock=self._clock
        ).latency_summary(claims, from_date=windows.month_start, to_date=windows.business_date)
        return schemas.ApprovalLatencyOut(
            median_hours=summary.median_hours,
            p90_hours=summary.p90_hours,
            pending_median_hours=summary.pending_median_hours,
            decided_count=summary.decided_count,
            pending_count=summary.pending_count,
        )

    def _outlet_counts(
        self, scope: ScopeContext, from_date: date, to_date: date
    ) -> tuple[int, int, int]:
        unique = repository.count_distinct_outlets(
            self._session, scope=scope, from_date=from_date, to_date=to_date
        )
        ordered = repository.count_distinct_outlets_ordered(
            self._session, scope=scope, from_date=from_date, to_date=to_date
        )
        multi = repository.count_outlets_multi_employee(
            self._session, scope=scope, from_date=from_date, to_date=to_date
        )
        return unique, ordered, multi

    def _assigned_outlet_count(self, *, claims: AccessTokenClaims) -> int:
        return len(
            BeatService(
                self._session, settings=self._settings, clock=self._clock
            ).list_assigned_outlets(claims=claims)
        )

    def _card_outlet_facts(
        self,
        *,
        claims: AccessTokenClaims,
        scope: ScopeContext,
        business_date: date,
    ) -> dict[str, Any]:
        unique, ordered, multi = self._outlet_counts(scope, business_date, business_date)
        totals = self._session.execute(
            select(
                func.coalesce(func.sum(FactEmployeeDay.visited_planned_outlets), 0),
                func.coalesce(func.sum(FactEmployeeDay.planned_outlets), 0),
                func.coalesce(func.sum(FactEmployeeDay.order_net_value_paise), 0),
                func.coalesce(func.sum(FactEmployeeDay.order_lines_count), 0),
                func.coalesce(func.sum(FactEmployeeDay.productive_visits), 0),
            ).where(
                FactEmployeeDay.tenant_id == claims.tenant_id,
                FactEmployeeDay.business_date == business_date,
                employee_scope_condition(scope, FactEmployeeDay.employee_id),
            )
        ).one()
        visited_planned = _to_int(totals[0])
        planned = _to_int(totals[1])
        assigned = self._assigned_outlet_count(claims=claims)
        month_start = business_date.replace(day=1)
        prior_to = month_start - timedelta(days=1)
        prior_from = prior_to.replace(day=1)
        return {
            "unique_outlets": unique,
            "outlets_ordered": ordered,
            "outlets_multi_rep": multi,
            "net_new_outlets": repository.count_new_outlets(
                self._session,
                scope=scope,
                from_date=month_start,
                to_date=business_date,
                prior_from=prior_from,
                prior_to=prior_to,
            ),
            "assigned_outlets": assigned,
            "beat_adherence_pct": _coverage_pct(visited_planned, planned),
            "network_reach_pct": (
                _coverage_pct(unique, assigned) if assigned else None
            ),
            "order_value_paise": _money_or_none(_to_int(totals[2])),
            "lpsc": _lpsc(_to_int(totals[3]), _to_int(totals[4])),
        }

    def get_sp_dashboard_kpis(
        self,
        *,
        claims: AccessTokenClaims,
        period: schemas.DashboardPeriod = "mtd",
    ) -> dict[str, Any]:
        """Calculate S-DASH-SP visit/call KPIs from fact tables and live routes.

        Manufacturer-scoped target progress lives on `get_sp_targets_kpis` —
        keeping it off this method means switching the targets screen's
        manufacturer filter doesn't re-run these visit-metric queries.
        """
        scope = ScopeResolver.resolve_from_claims(claims, OrgResource.ACTIVITY_DATA)
        self._validate_surface_access(scope=scope.scope, surface="sp-home")
        windows = self._dashboard_windows(period)
        fact_scope = (FactEmployeeDay.employee_id == claims.employee_id,)

        (
            visits_total,
            productive_visits,
            orders_submitted,
            order_lines_count,
            unplanned_visits,
            distance_metres,
        ) = self._period_visit_totals(
            tenant_id=claims.tenant_id,
            window_start=windows.metrics_from,
            window_end=windows.metrics_to,
            extra=fact_scope,
        )
        utc = repository.count_distinct_outlets(
            self._session,
            scope=scope,
            from_date=windows.metrics_from,
            to_date=windows.metrics_to,
        )
        outlets_ordered = repository.count_distinct_outlets_ordered(
            self._session,
            scope=scope,
            from_date=windows.metrics_from,
            to_date=windows.metrics_to,
        )
        zero_order_outlets = repository.count_zero_order_outlets(
            self._session,
            scope=scope,
            from_date=windows.metrics_from,
            to_date=windows.metrics_to,
        )
        # Today's visited / productive come from the live route: fact rows lag the projector, so
        # a busy day otherwise renders as 0 of N planned in any period that contains today.
        visits_total, productive_visits, planned_visits, coverage_pct = self._with_live_today(
            tenant_id=claims.tenant_id,
            period=period,
            windows=windows,
            extra=fact_scope,
            visits_total=visits_total,
            productive_visits=productive_visits,
            coverage=self._sp_planned_coverage(claims=claims, business_date=windows.business_date),
        )
        order_value_paise, order_volume_units, order_volume_uom = self._sp_order_measures(
            self._manufacturer_totals_by_id(
                scope, windows.metrics_from, windows.metrics_to, None
            ),
        )

        return schemas.SpDashboardKpisResponse(
            period=period,
            business_date=windows.business_date,
            metrics=schemas.SpDashboardMetricsOut(
                utc=utc,
                visits_total=visits_total,
                productive_visits=productive_visits,
                zo=zero_order_outlets,
                lpsc=_lpsc(order_lines_count, productive_visits),
                orders_submitted=orders_submitted,
                order_value_paise=order_value_paise,
                order_volume_units=order_volume_units,
                order_volume_uom=order_volume_uom,
                unplanned_visits=unplanned_visits,
                order_lines_count=order_lines_count,
                distance_metres=distance_metres,
                planned_visits=planned_visits,
                coverage_pct=coverage_pct if planned_visits > 0 else None,
                productivity_pct=_productivity_pct(productive_visits, visits_total),
                outlets_ordered=outlets_ordered,
            ),
            degraded=self._degraded_out(),
        ).model_dump(mode="json")

    def get_sp_targets_kpis(
        self,
        *,
        claims: AccessTokenClaims,
        manufacturer_id: str | None = None,
    ) -> dict[str, Any]:
        """Manufacturer-scoped target progress (always MTD) — no visit/call metrics.

        Split out of `get_sp_dashboard_kpis`: the targets screen only needs this
        slice and previously paid for that endpoint's full visit-metric queries
        on every manufacturer switch.
        """
        scope = ScopeResolver.resolve_from_claims(claims, OrgResource.ACTIVITY_DATA)
        self._validate_surface_access(scope=scope.scope, surface="sp-home")
        manufacturer_id = manufacturer_id or None
        windows = self._dashboard_windows("mtd")

        employee_targets = TargetService(
            self._session, settings=self._settings, clock=self._clock
        ).list_targets(
            claims=claims,
            employee_id=claims.employee_id,
            period_month=windows.month_start,
            target_type=None,
        )["targets"]
        femd_by_id = self._manufacturer_totals_by_id(
            scope, windows.month_start, windows.business_date, manufacturer_id
        )

        return schemas.SpTargetsKpisResponse(
            business_date=windows.business_date,
            targets=self._map_target_lines(
                {"targets": [row for row in employee_targets if row["target_type"] == "sales"]},
                femd_by_id=femd_by_id,
                manufacturer_id=manufacturer_id,
            ),
            count_targets=self._count_targets(
                claims=claims, windows=windows, targets=employee_targets
            ),
            mom=self._mom_out(scope, windows, manufacturer_id),
            degraded=self._degraded_out(),
        ).model_dump(mode="json")

    def _count_targets(
        self,
        *,
        claims: AccessTokenClaims,
        windows: _DashboardWindows,
        targets: list[dict[str, Any]],
    ) -> list[schemas.CountTargetOut]:
        achieved_by_type: dict[Literal["outlets", "leads"], int] = {
            "outlets": OutletReadService(
                self._session, settings=self._settings, clock=self._clock
            ).count_onboarded_in_scope(
                claims=claims, from_date=windows.month_start, to_date=windows.business_date
            ),
            "leads": TargetService(
                self._session, settings=self._settings, clock=self._clock
            ).count_leads_in_scope(
                claims=claims, from_date=windows.month_start, to_date=windows.business_date
            ),
        }
        rows: list[schemas.CountTargetOut] = []
        for target_type, achieved in achieved_by_type.items():
            target_value = next(
                (
                    row["target_value"]
                    for row in targets
                    if row["target_type"] == target_type and row["target_value"]
                ),
                None,
            )
            rows.append(
                schemas.CountTargetOut(
                    target_type=target_type,
                    target_value=target_value,
                    achieved=achieved,
                    pct=(
                        round(achieved * 100 / target_value)
                        if target_value and achieved is not None
                        else None
                    ),
                )
            )
        return rows

    def get_manager_dashboard_kpis(
        self,
        *,
        claims: AccessTokenClaims,
        period: schemas.DashboardPeriod = "mtd",
        manufacturer_id: str | None = None,
        designation_code: str | None = None,
    ) -> dict[str, Any]:
        """Calculate S-DASH-MGR KPIs from team's fact tables.

        `targets` is scoped to one hierarchy level below the caller by default (or to
        `designation_code` when given), never the whole tree — see `_resolve_target_designations`.
        Every other field, including `mom`, stays whole-tree.
        """
        scope = ScopeResolver.resolve_from_claims(claims, OrgResource.ACTIVITY_DATA)
        self._validate_surface_access(scope=scope.scope, surface="manager-dashboard")
        manufacturer_id = manufacturer_id or None
        windows = self._dashboard_windows(period)
        fact_scope = (employee_scope_condition(scope, FactEmployeeDay.employee_id),)

        (
            visits_total,
            productive_visits,
            orders_submitted,
            _lines,
            _unplanned,
            _distance,
        ) = self._period_visit_totals(
            tenant_id=claims.tenant_id,
            window_start=windows.metrics_from,
            window_end=windows.metrics_to,
            extra=fact_scope,
        )
        # Not `_outlet_counts`: that also runs `count_outlets_multi_employee`, which nothing
        # here uses since the "Visited by 2+ reps" tile was dropped.
        unique_outlets = repository.count_distinct_outlets(
            self._session, scope=scope, from_date=windows.metrics_from, to_date=windows.metrics_to
        )
        outlets_ordered = repository.count_distinct_outlets_ordered(
            self._session, scope=scope, from_date=windows.metrics_from, to_date=windows.metrics_to
        )
        outlets_onboarded_count = OutletReadService(
            self._session, settings=self._settings, clock=self._clock
        ).count_onboarded_in_scope(
            claims=claims, from_date=windows.month_start, to_date=windows.business_date
        )
        leads_captured_count = TargetService(
            self._session, settings=self._settings, clock=self._clock
        ).count_leads_in_scope(
            claims=claims, from_date=windows.month_start, to_date=windows.business_date
        )
        # There is no month-wide planned-stop count, so an MTD window reports no planned
        # denominator; today's live visits still overlay the lagging fact rows.
        visits_total, productive_visits, planned_visits, coverage_pct = self._with_live_today(
            tenant_id=claims.tenant_id,
            period=period,
            windows=windows,
            extra=fact_scope,
            visits_total=visits_total,
            productive_visits=productive_visits,
            coverage=self._team_coverage(claims=claims, business_date=windows.business_date),
        )
        attendance = self._team_attendance(claims=claims, business_date=windows.business_date)

        caller_designation_code = org_service.get_employee_in_scope(
            self._session, scope=scope, employee_id=claims.employee_id
        ).designation_code
        target_designations = self._resolve_target_designations(
            scope=scope,
            caller_designation_code=caller_designation_code,
            designation_code=designation_code,
        )
        designation_by_id = (
            org_service.list_designations_by_employee_id(
                self._session, scope=scope, designation_codes=target_designations
            )
            if target_designations
            else {}
        )
        target_employee_ids = list(designation_by_id)
        targets_payload = TargetService(
            self._session, settings=self._settings, clock=self._clock
        ).list_targets_in_scope(claims, period_month=windows.month_start, target_type="sales")
        target_id_set = set(target_employee_ids)
        designation_targets_payload = {
            "targets": [
                target
                for target in targets_payload.get("targets") or []
                if str(target.get("employee_id") or "") in target_id_set
            ]
        }
        femd_by_id = self._manufacturer_totals_by_id(
            scope,
            windows.month_start,
            windows.business_date,
            manufacturer_id,
            employee_ids=target_employee_ids,
        )
        league = self._designation_progress(
            scope=scope,
            windows=windows,
            manufacturer_id=manufacturer_id,
            targets_payload=targets_payload,
            designation_by_id=designation_by_id,
        )

        return schemas.ManagerDashboardKpisResponse(
            period=period,
            business_date=windows.business_date,
            team_metrics=schemas.ManagerDashboardMetricsOut(
                visits_total=visits_total,
                productive_visits=productive_visits,
                productivity_pct=_productivity_pct(productive_visits, visits_total),
                punched_in=attendance["punched_in"],
                order_value_paise=self._sum_money(
                    scope, windows.metrics_from, windows.metrics_to, manufacturer_id
                ),
                team_size=attendance["total"],
                utc=unique_outlets,
                orders_submitted=orders_submitted,
                planned_visits=planned_visits,
                coverage_pct=coverage_pct if planned_visits > 0 else None,
                unique_outlets=unique_outlets,
                outlets_ordered=outlets_ordered,
                outlets_onboarded_count=outlets_onboarded_count,
                leads_captured_count=leads_captured_count,
                on_duty=attendance["on_duty"],
                no_punch_in=attendance["no_punch_in"],
                on_leave=attendance["on_leave"],
                pending_approvals=self._pending_approvals(claims=claims),
            ),
            targets=self._map_target_lines(
                designation_targets_payload, femd_by_id=femd_by_id, manufacturer_id=manufacturer_id
            ),
            designation_scope=schemas.DesignationScopeOut(
                active=target_designations[0] if len(target_designations) == 1 else "",
                available=list(
                    self._designations_below(
                        scope=scope, caller_designation_code=caller_designation_code
                    )
                ),
            ),
            league=league,
            scatter=self._scatter(scope, windows),
            districts=self._district_rows(scope, windows, manufacturer_id, claims),
            mom=self._mom_out(scope, windows, manufacturer_id),
            degraded=self._degraded_out(),
        ).model_dump(mode="json")

    def get_admin_dashboard_kpis(
        self,
        *,
        claims: AccessTokenClaims,
        period: schemas.DashboardPeriod = "mtd",
        manufacturer_id: str | None = None,
        designation_code: str | None = None,
    ) -> dict[str, Any]:
        """Calculate S-DASH-ADM org-wide KPIs.

        `employee_progress` is one row per active holder of `designation_code`, or of
        every ladder level when it is `all` (the default), ordered by level then name.
        Every other field stays org-wide.
        """
        scope = ScopeResolver.resolve_from_claims(claims, OrgResource.ACTIVITY_DATA)
        if scope.scope is not Scope.ORG:
            raise ApiError(403, "forbidden", "Admin-only reporting endpoint.")
        self._validate_surface_access(scope=scope.scope, surface="admin-dashboard")
        manufacturer_id = manufacturer_id or None
        windows = self._dashboard_windows(period)
        fact_scope = (employee_scope_condition(scope, FactEmployeeDay.employee_id),)

        (
            visits_total,
            productive_visits,
            _orders,
            _lines,
            _unplanned,
            _distance,
        ) = self._period_visit_totals(
            tenant_id=claims.tenant_id,
            window_start=windows.metrics_from,
            window_end=windows.metrics_to,
            extra=fact_scope,
        )
        unique_outlets, outlets_ordered, outlets_multi_rep = self._outlet_counts(
            scope, windows.metrics_from, windows.metrics_to
        )
        net_new_outlets = repository.count_new_outlets(
            self._session,
            scope=scope,
            from_date=windows.month_start,
            to_date=windows.business_date,
            prior_from=windows.lmtd_from,
            prior_to=windows.prior_month_to,
        )
        # There is no month-wide planned-stop count, so an MTD window reports no planned
        # denominator; today's live visits still overlay the lagging fact rows.
        visits_total, productive_visits, planned_visits, coverage_pct = self._with_live_today(
            tenant_id=claims.tenant_id,
            period=period,
            windows=windows,
            extra=fact_scope,
            visits_total=visits_total,
            productive_visits=productive_visits,
            coverage=self._team_coverage(claims=claims, business_date=windows.business_date),
        )
        attendance = self._team_attendance(claims=claims, business_date=windows.business_date)
        targets_payload = TargetService(
            self._session, settings=self._settings, clock=self._clock
        ).list_targets_in_scope(claims, period_month=windows.month_start, target_type="sales")
        femd_by_id = self._manufacturer_totals_by_id(
            scope, windows.month_start, windows.business_date, manufacturer_id
        )

        all_designations = self._designations_below(scope=scope, caller_designation_code=None)
        showing_all = designation_code in (None, "", _ALL_DESIGNATIONS)
        target_designations = (
            all_designations
            if showing_all
            else self._resolve_target_designations(
                scope=scope, caller_designation_code=None, designation_code=designation_code,
            )
        )
        designation_by_id = (
            org_service.list_designations_by_employee_id(
                self._session, scope=scope, designation_codes=target_designations
            )
            if target_designations
            else {}
        )
        employee_progress = self._designation_progress(
            scope=scope,
            windows=windows,
            manufacturer_id=manufacturer_id,
            # Whole-org payload, not one filtered to `target_designations`: a manager's
            # target is the sum of their subtree's targets, exactly as their sales are.
            targets_payload=targets_payload,
            designation_by_id=designation_by_id,
        )

        return schemas.AdminDashboardKpisResponse(
            period=period,
            business_date=windows.business_date,
            org_metrics=schemas.AdminDashboardMetricsOut(
                visits_total=visits_total,
                productive_visits=productive_visits,
                productivity_pct=_productivity_pct(productive_visits, visits_total),
                order_value_paise=self._sum_money(
                    scope, windows.metrics_from, windows.metrics_to, manufacturer_id
                ),
                active_employees=attendance["total"],
                planned_visits=planned_visits,
                coverage_pct=coverage_pct if planned_visits > 0 else None,
                unique_outlets=unique_outlets,
                outlets_ordered=outlets_ordered,
                outlets_multi_rep=outlets_multi_rep,
                net_new_outlets=net_new_outlets,
                on_duty=attendance["on_duty"],
                no_punch_in=attendance["no_punch_in"],
                on_leave=attendance["on_leave"],
                pending_approvals=self._pending_approvals(claims=claims),
            ),
            targets=self._map_target_lines(
                targets_payload, femd_by_id=femd_by_id, manufacturer_id=manufacturer_id
            ),
            targets_summary=self._targets_summary_out(
                targets_payload, scope=scope, windows=windows, manufacturer_id=None
            ),
            manufacturer_movement=self._manufacturer_movement(scope, windows, None),
            approval_latency=self._approval_latency_out(claims=claims, windows=windows),
            mom=self._mom_out(scope, windows, manufacturer_id),
            employee_progress=employee_progress,
            designation_scope=schemas.DesignationScopeOut(
                active=_ALL_DESIGNATIONS if showing_all else target_designations[0],
                available=[_ALL_DESIGNATIONS, *all_designations],
            ),
            degraded=self._degraded_out(),
        ).model_dump(mode="json")

    # --- Calls-KPI roster (P3) ------------------------------------------------

    def kpis_calls(
        self,
        *,
        claims: AccessTokenClaims,
        scope_path: schemas.CallsKpiScope,
        for_employee_id: str | None = None,
        business_date: date | None = None,
    ) -> dict[str, Any]:
        """One calls-KPI drill level: TC/PC/SC/UTC for the view root and each direct reportee.

        `for_employee_id` roots the level at that employee; omitted, it roots at the caller —
        an admin holds no tree position, so it roots at the forest and rows are the top-level
        managers. Every value aggregates the active sales persons beneath the row: managers are
        reporting nodes, not field-execution nodes, so their own field activity is excluded.
        UTC unions outlet sets rather than summing distinct counts, which keeps a parent's
        number equal to the roll-up of the children the caller is about to drill into.
        The live activity timeline stays on the coverage endpoints.
        """
        scope = ScopeResolver.resolve_from_claims(claims, OrgResource.ACTIVITY_DATA)
        expected_path = {Scope.SELF: "self", Scope.OWN_TREE: "team", Scope.ORG: "org"}.get(
            scope.scope
        )
        if expected_path != scope_path:
            raise ApiError(403, "forbidden", "This calls-KPI view is not available for this role.")
        as_of_date = business_date or current_business_date(self._clock, settings=self._settings)
        month_start = as_of_date.replace(day=1)

        tree_payload = OrgService(
            self._session, settings=self._settings, clock=self._clock
        ).get_tree(claims=claims)
        nodes = _flatten_tree_nodes(tree_payload.get("roots", []))

        root_node, children = self._calls_drill_level(
            claims=claims,
            scope=scope,
            nodes=nodes,
            tree_roots=tree_payload.get("roots", []),
            for_employee_id=for_employee_id,
        )
        leaf_sets = {str(child["id"]): _sales_leaf_ids(child) for child in children}
        # An admin holds no tree position, so the root total is the union over the rows rather
        # than one node's subtree. Sibling subtrees are disjoint, so the union never double-counts.
        root_leaves = (
            sorted({leaf for leaves in leaf_sets.values() for leaf in leaves})
            if root_node is None
            else _sales_leaf_ids(root_node)
        )
        all_leaf_ids = sorted({*root_leaves, *(leaf for leaves in leaf_sets.values() for leaf in leaves)})

        def facts(from_date: date) -> tuple[dict[str, dict[str, int]], dict[str, set[str]]]:
            if not all_leaf_ids:
                return {}, {}
            return (
                repository.calls_totals_by_employee(
                    self._session, tenant_id=scope.tenant_id, employee_ids=all_leaf_ids,
                    from_date=from_date, to_date=as_of_date,
                ),
                repository.calls_outlets_by_employee(
                    self._session, tenant_id=scope.tenant_id, employee_ids=all_leaf_ids,
                    from_date=from_date, to_date=as_of_date,
                ),
            )

        today_facts, today_outlets = facts(as_of_date)
        mtd_facts, mtd_outlets = facts(month_start)

        live: dict[str, tuple[int | None, int | None, int | None]] = {}
        if scope.scope is Scope.SELF and all_leaf_ids:
            planned, visited, productive, _pct = self._sp_planned_coverage(
                claims=claims, business_date=as_of_date
            )
            live[claims.employee_id] = (planned, visited, productive)
        elif all_leaf_ids:
            coverage = RouteService(
                self._session, settings=self._settings, clock=self._clock
            ).coverage_team(claims=claims, business_date=as_of_date, only_sales_person=True)
            for item in coverage.get("items", []):
                # coverage_team carries no live productive-visit count (CoverageRow has no such
                # field) — pc falls back to the fact_employee_day rollup for this branch.
                live[str(item.get("employee_id"))] = (
                    _to_int(item.get("planned")),
                    _to_int(item.get("visited")),
                    None,
                )

        view = schemas.CallsKpiViewOut(
            scope=scope_path,
            root=(
                schemas.CallsKpiNodeOut(
                    employee_id=str(root_node["id"]),
                    full_name=str(root_node.get("full_name") or ""),
                    role_code=str(root_node.get("role_code") or ""),
                    designation_code=str(root_node.get("designation_code") or ""),
                )
                if root_node is not None
                else None
            ),
        )
        return schemas.CallsKpiResponse(
            view=view,
            business_date=as_of_date,
            today=self._build_calls_window(
                children, leaf_sets, root_leaves, today_facts, today_outlets, live,
            ),
            mtd=self._build_calls_window(
                children, leaf_sets, root_leaves, mtd_facts, mtd_outlets, {},
            ),
        ).model_dump(mode="json")

    def _resolve_target_designations(
        self,
        *,
        scope: ScopeContext,
        caller_designation_code: str | None,
        designation_code: str | None,
    ) -> tuple[str, ...]:
        """Designations a hierarchy-level-scoped rollup shows (calls-KPI roster, manager
        target progress). Explicit code wins; otherwise one level below the caller's own
        designation (admin → L1 sales heads)."""
        if designation_code is not None:
            if _ROLE_BY_DESIGNATION.get(designation_code) in (None, "admin"):
                raise ApiError(422, "invalid_designation", "Unknown designation_code.")
            return (designation_code,)
        if scope.scope is Scope.ORG:
            return _CALLS_LADDER[0]
        level = _LEVEL_BY_DESIGNATION.get(caller_designation_code) if caller_designation_code else None
        if level is None:
            level = 0
        if scope.scope is Scope.SELF or level + 1 >= len(_CALLS_LADDER):
            return (caller_designation_code,) if caller_designation_code else ()
        return _CALLS_LADDER[level + 1]

    def _designations_below(
        self, *, scope: ScopeContext, caller_designation_code: str | None
    ) -> tuple[str, ...]:
        """Every designation code strictly below the caller's level — the pickable set for a
        hierarchy-level filter, one level's default plus every level further down."""
        if scope.scope is Scope.ORG:
            start = 0
        else:
            level = _LEVEL_BY_DESIGNATION.get(caller_designation_code) if caller_designation_code else None
            start = (level + 1) if level is not None else 0
        return tuple(code for codes in _CALLS_LADDER[start:] for code in codes)

    def _calls_drill_level(
        self,
        *,
        claims: AccessTokenClaims,
        scope: ScopeContext,
        nodes: dict[str, dict[str, Any]],
        tree_roots: list[dict[str, Any]],
        for_employee_id: str | None,
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        """The root a drill level hangs off, and that root's active direct reportees.

        Rows follow the tree's real parent-child edges, not the designation ladder, so a
        hierarchy that skips a level still drills. A rep roots at themself with no rows.
        """
        if scope.scope is Scope.SELF:
            if for_employee_id is not None and for_employee_id != claims.employee_id:
                raise ApiError(403, "forbidden", "You may only view your own values.")
            return nodes.get(claims.employee_id), []
        if for_employee_id is not None:
            root = nodes.get(for_employee_id)
            if root is None:
                if scope.scope is Scope.ORG:
                    raise ApiError(404, "not_found", "Employee was not found.")
                raise ApiError(403, "forbidden", "That employee is not within your scope.")
            return root, _drill_children(root)
        if scope.scope is Scope.ORG:
            return None, _drill_children(None, tree_roots)
        caller_node = nodes.get(claims.employee_id)
        return caller_node, _drill_children(caller_node) if caller_node else []

    def _build_calls_window(
        self,
        children: list[dict[str, Any]],
        leaf_sets: dict[str, list[str]],
        root_leaves: list[str],
        facts: dict[str, dict[str, int]],
        outlets: dict[str, set[str]],
        live: dict[str, tuple[int | None, int | None, int | None]],
    ) -> schemas.CallsKpiWindowOut:
        def aggregate(leaf_ids: list[str]) -> schemas.CallsKpiTotalsOut:
            tc = pc = sc = 0
            covered: set[str] = set()
            for leaf_id in leaf_ids:
                fact = facts.get(leaf_id) or {"tc": 0, "pc": 0, "sc": 0}
                planned, visited, productive = live.get(leaf_id, (None, None, None))
                tc += visited if visited is not None else fact["tc"]
                pc += productive if productive is not None else fact["pc"]
                sc += planned if planned is not None else fact["sc"]
                covered |= outlets.get(leaf_id) or set()
            return schemas.CallsKpiTotalsOut(tc=tc, pc=pc, sc=sc, utc=len(covered))

        items = []
        for child in children:
            child_id = str(child["id"])
            values = aggregate(leaf_sets[child_id])
            items.append(
                schemas.CallsKpiRowOut(
                    employee_id=child_id,
                    full_name=str(child.get("full_name") or child_id),
                    role_code=str(child.get("role_code") or ""),
                    designation_code=str(child.get("designation_code") or ""),
                    status=str(child.get("status") or ""),
                    direct_reportee_count=len(_drill_children(child)),
                    tc=values.tc,
                    pc=values.pc,
                    sc=values.sc,
                    utc=values.utc,
                )
            )
        return schemas.CallsKpiWindowOut(items=items, totals=aggregate(root_leaves))


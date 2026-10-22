"""Admin Excel report downloads — synchronous, in-request generation.

Each report composes other modules only through their public service classes/functions,
never their repositories or models directly (see CLAUDE.md). Admin-only, gated the same way
`ReportingService.admin_coverage_trend` gates its endpoint.
"""

from __future__ import annotations

import calendar
import io
from datetime import date
from typing import Any

from fastapi import Response
from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy.orm import Session

from humbee_sfa.core.business_date import IST_ZONE
from humbee_sfa.core.clock import Clock, SystemClock
from humbee_sfa.core.deps import AccessTokenClaims
from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.core.settings import Settings, get_settings
from humbee_sfa.modules.attendance.service import AttendanceService
from humbee_sfa.modules.beats.service import BeatService
from humbee_sfa.modules.org.geography_service import (
    GeographyService,
    district_geography_labels,
    list_district_labels,
    list_employee_assignment_details,
    list_employee_geography_labels,
)
from humbee_sfa.modules.org.scope import OrgResource, Scope, ScopeResolver
from humbee_sfa.modules.org.service import OrgService
from humbee_sfa.modules.outlets.service import OutletReadService
from humbee_sfa.modules.reporting import repository
from humbee_sfa.modules.reporting.service import _LEVEL_BY_DESIGNATION

_MAX_ATTENDANCE_RANGE_MONTHS = 4
_XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _add_months(value: date, months: int) -> date:
    year, month_index = divmod(value.year * 12 + value.month - 1 + months, 12)
    month = month_index + 1
    return value.replace(
        year=year, month=month, day=min(value.day, calendar.monthrange(year, month)[1])
    )


def _designation_level_label(designation_code: str) -> str:
    """"L1".."L5" from the single canonical ladder in `reporting.service`. Admin carries no
    level — it sits above the ladder, not on it (M03 designation_role_chk)."""

    level = _LEVEL_BY_DESIGNATION.get(designation_code)
    return f"L{level + 1}" if level is not None else "Admin"


def _workbook_response(
    *, sheets: list[tuple[str, list[str], list[list[Any]]]], filename: str
) -> Response:
    """One workbook, one or more named sheets. `sheets` is `(name, headers, rows)` triples."""

    workbook = Workbook()
    workbook.remove(workbook.active)
    for sheet_name, headers, rows in sheets:
        sheet = workbook.create_sheet(sheet_name)
        sheet.append(headers)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for row in rows:
            sheet.append(row)
        for column in sheet.columns:
            longest = max((len(str(cell.value)) for cell in column if cell.value is not None), default=10)
            sheet.column_dimensions[column[0].column_letter].width = min(60, max(12, longest + 2))

    buffer = io.BytesIO()
    workbook.save(buffer)
    return Response(
        content=buffer.getvalue(),
        media_type=_XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _single_sheet_response(
    *, sheet_name: str, headers: list[str], rows: list[list[Any]], filename: str
) -> Response:
    return _workbook_response(sheets=[(sheet_name, headers, rows)], filename=filename)


def _status_label(value: str) -> str:
    return value.replace("_", " ").title()


def _yes_no(value: bool) -> str:
    return "Yes" if value else "No"


def _ist_time(value: Any) -> str:
    if value is None:
        return ""
    return value.astimezone(IST_ZONE).strftime("%H:%M")


def _date_label(value: date | None) -> str:
    return value.isoformat() if value else ""


class AdminReportsService:
    def __init__(
        self, session: Session, *, settings: Settings | None = None, clock: Clock | None = None
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._clock = clock or SystemClock()

    def _require_admin(self, claims: AccessTokenClaims) -> None:
        scope = ScopeResolver.resolve_from_claims(claims, OrgResource.ACTIVITY_DATA)
        if scope.scope is not Scope.ORG:
            raise ApiError(403, "forbidden", "Admin-only report.")

    def _directory(self, claims: AccessTokenClaims) -> dict[str, dict[str, Any]]:
        """Full roster (code, name, phone, designation, manager, hierarchy span), keyed by
        employee id — the shared identity source for every report below."""

        rows = OrgService(
            self._session, settings=self._settings, clock=self._clock
        ).list_employees_for_report(claims=claims)
        return {row["employee_id"]: row for row in rows}

    # -- 1. Geography Mapping ------------------------------------------------

    def geography_mapping_report(self, *, claims: AccessTokenClaims) -> Response:
        self._require_admin(claims)
        directory = self._directory(claims)
        labels_by_employee = list_employee_geography_labels(self._session, tenant_id=claims.tenant_id)
        assignment_by_employee = list_employee_assignment_details(
            self._session, tenant_id=claims.tenant_id
        )
        # `GeographyScopeAssignment` is not role-restricted, so a name outside `directory`
        # (hierarchy roles only) still needs to resolve — never fall back to a raw employee id.
        fallback_names = repository.list_display_names(
            self._session,
            tenant_id=claims.tenant_id,
            employee_ids=set(labels_by_employee) - set(directory),
        )
        local_outlets = OutletReadService(
            self._session, settings=self._settings, clock=self._clock
        ).list_local_outlets(tenant_id=claims.tenant_id)
        outlet_count_by_district: dict[str, int] = {}
        for outlet in local_outlets:
            if outlet.district_id:
                outlet_count_by_district[outlet.district_id] = (
                    outlet_count_by_district.get(outlet.district_id, 0) + 1
                )

        def _display_name(employee_id: str) -> str:
            return directory.get(employee_id, {}).get("full_name") or fallback_names.get(
                employee_id, employee_id
            )

        # District → employee names sharing it, for the overlap column.
        employees_by_district: dict[str, list[str]] = {}
        for employee_id, assignment in assignment_by_employee.items():
            name = _display_name(employee_id)
            for district_id in assignment["district_ids"]:
                employees_by_district.setdefault(district_id, []).append(name)

        rows = []
        for employee_id, labels in sorted(
            labels_by_employee.items(), key=lambda item: _display_name(item[0])
        ):
            person = directory.get(employee_id, {})
            assignment = assignment_by_employee.get(employee_id, {"district_ids": [], "assigned_at": None})
            district_ids = assignment["district_ids"]
            outlets_in_scope = sum(outlet_count_by_district.get(d, 0) for d in district_ids)
            self_name = _display_name(employee_id)
            overlap_names = sorted(
                {
                    name
                    for district_id in district_ids
                    for name in employees_by_district.get(district_id, [])
                    if name != self_name
                }
            )
            rows.append(
                [
                    person.get("employee_code", ""),
                    self_name,
                    person.get("phone_e164", ""),
                    person.get("designation_code", ""),
                    person.get("manager_name", ""),
                    ", ".join(labels["zones"]),
                    ", ".join(labels["states"]),
                    ", ".join(labels["districts"]),
                    len(district_ids),
                    outlets_in_scope,
                    ", ".join(overlap_names),
                    assignment["assigned_at"].isoformat() if assignment["assigned_at"] else "",
                ]
            )
        return _single_sheet_response(
            sheet_name="Geography Mapping",
            headers=[
                "Employee Code", "Name", "Phone", "Designation", "Manager", "Zones", "States",
                "Districts", "No. of Districts", "Outlets in Scope", "Overlap With", "Assigned On",
            ],
            rows=rows,
            filename="geography-mapping-report.xlsx",
        )

    # -- 2. Employee Hierarchy ------------------------------------------------

    def employee_hierarchy_report(self, *, claims: AccessTokenClaims) -> Response:
        self._require_admin(claims)
        directory = self._directory(claims)
        labels_by_employee = list_employee_geography_labels(self._session, tenant_id=claims.tenant_id)
        rows = [
            [
                person["employee_code"],
                person["full_name"],
                person["phone_e164"],
                person["role_code"],
                person["designation_code"],
                person["status"],
                _date_label(person["joined_on"]),
                directory.get(person["manager_employee_id"], {}).get("employee_code", ""),
                person["manager_name"],
                _designation_level_label(person["designation_code"]),
                person["direct_reports"],
                person["team_size"],
                ", ".join(labels_by_employee.get(person["employee_id"], {}).get("districts", [])),
            ]
            for person in sorted(directory.values(), key=lambda item: item["full_name"])
        ]
        return _single_sheet_response(
            sheet_name="Employee Hierarchy",
            headers=[
                "Employee Code", "Name", "Phone", "Role", "Designation", "Status", "Joined On",
                "Manager Code", "Manager Name", "Level", "Direct Reports", "Total Team Size",
                "Territory (Districts)",
            ],
            rows=rows,
            filename="employee-hierarchy-report.xlsx",
        )

    # -- 3. Beats --------------------------------------------------------------

    def beats_report(self, *, claims: AccessTokenClaims) -> Response:
        self._require_admin(claims)
        directory = self._directory(claims)
        beats = BeatService(
            self._session, settings=self._settings, clock=self._clock
        ).list_beats_for_directory_report(claims=claims)
        district_labels = list_district_labels(self._session, tenant_id=claims.tenant_id)
        outlet_activity = repository.outlet_activity_summary(self._session, tenant_id=claims.tenant_id)

        all_local_outlet_ids = sorted({outlet_id for beat in beats for outlet_id in beat["outlet_ids"]})
        projected = OutletReadService(
            self._session, settings=self._settings, clock=self._clock
        ).get_projected_outlets(tenant_id=claims.tenant_id, outlet_ids=all_local_outlet_ids, ids_are_local=True)
        external_id_by_local_id = {outlet.local_id: outlet.record.external_id for outlet in projected}

        rows = []
        for beat in sorted(beats, key=lambda beat: beat["display_name"]):
            owner = directory.get(beat["owner_employee_id"], {})
            visit_dates = [
                outlet_activity[external_id]["last_visit_date"]
                for local_id in beat["outlet_ids"]
                if (external_id := external_id_by_local_id.get(local_id)) in outlet_activity
                and outlet_activity[external_id]["last_visit_date"]
            ]
            rows.append(
                [
                    beat["code"],
                    beat["display_name"],
                    owner.get("full_name", beat["owner_employee_id"]),
                    owner.get("phone_e164", ""),
                    owner.get("manager_name", ""),
                    ", ".join(district_labels.get(d, d) for d in beat["district_ids"]),
                    beat["frequency_label"],
                    beat["outlet_count"],
                    _status_label(beat["display_status"]),
                    _date_label(beat["approved_at"].astimezone(IST_ZONE).date()) if beat["approved_at"] else "",
                    _yes_no(beat["pending_edit_request"]),
                    _date_label(max(visit_dates)) if visit_dates else "",
                ]
            )
        return _single_sheet_response(
            sheet_name="Beats",
            headers=[
                "Beat Code", "Beat Name", "Sales Person", "Phone", "Manager", "Districts",
                "Frequency", "Outlet Count", "Status", "Approved On", "Pending Edit Request",
                "Last Visit Date",
            ],
            rows=rows,
            filename="beat-report.xlsx",
        )

    # -- 4. Beat Outlets ---------------------------------------------------------

    def beat_outlets_report(self, *, claims: AccessTokenClaims) -> Response:
        self._require_admin(claims)
        directory = self._directory(claims)
        beats = BeatService(
            self._session, settings=self._settings, clock=self._clock
        ).list_beats_for_report(claims=claims)
        district_labels = list_district_labels(self._session, tenant_id=claims.tenant_id)
        outlet_activity = repository.outlet_activity_summary(self._session, tenant_id=claims.tenant_id)

        all_local_outlet_ids = sorted({outlet_id for beat in beats for outlet_id, _ in beat["outlets"]})
        projected = OutletReadService(
            self._session, settings=self._settings, clock=self._clock
        ).get_projected_outlets(tenant_id=claims.tenant_id, outlet_ids=all_local_outlet_ids, ids_are_local=True)
        projected_by_local_id = {outlet.local_id: outlet.record for outlet in projected}

        beat_count_by_outlet: dict[str, int] = {}
        for beat in beats:
            for outlet_id, _ in beat["outlets"]:
                beat_count_by_outlet[outlet_id] = beat_count_by_outlet.get(outlet_id, 0) + 1

        rows = []
        for beat in sorted(beats, key=lambda beat: beat["display_name"]):
            owner = directory.get(beat["owner_employee_id"], {})
            for sequence_no, (outlet_id, _) in enumerate(beat["outlets"], start=1):
                record = projected_by_local_id.get(outlet_id)
                activity = outlet_activity.get(record.external_id, {}) if record else {}
                rows.append(
                    [
                        beat["code"],
                        beat["display_name"],
                        owner.get("full_name", beat["owner_employee_id"]),
                        sequence_no,
                        record.external_id if record else outlet_id,
                        record.name if record else outlet_id,
                        record.category if record and record.category else "",
                        district_labels.get(record.district_external_id, record.district_external_id)
                        if record and record.district_external_id
                        else "",
                        record.gstin if record else "",
                        record.pan if record else "",
                        _date_label(activity.get("last_visit_date")),
                        _date_label(activity.get("last_order_date")),
                        _yes_no(beat_count_by_outlet.get(outlet_id, 0) > 1),
                    ]
                )
        return _single_sheet_response(
            sheet_name="Beat Outlets",
            headers=[
                "Beat Code", "Beat Name", "Sales Person", "Sequence No", "Outlet ID", "Outlet Name",
                "Shop Category", "District", "GSTIN", "PAN", "Last Visit Date", "Last Order Date",
                "Mapped to Multiple Beats",
            ],
            rows=rows,
            filename="beat-wise-outlet-report.xlsx",
        )

    # -- 5. Unassigned Outlets -----------------------------------------------

    def unassigned_outlets_report(self, *, claims: AccessTokenClaims) -> Response:
        """Every outlet Humbee has, across every district the tenant actually operates in
        (the union of every employee's assigned territory), that SFA has not assigned to any
        beat — a straight Humbee-vs-SFA diff, not a local-projection count.

        Deliberately scoped to the tenant's own geography, not Humbee's global district master:
        that master is nationwide and unscoped (India-wide, ~750 districts) — walking all of it
        and searching outlets across every one of them is what made the first version of this
        report effectively never finish.
        """

        self._require_admin(claims)
        district_geo = district_geography_labels(self._session, tenant_id=claims.tenant_id)
        if not district_geo:
            return _single_sheet_response(
                sheet_name="Unassigned Outlets",
                headers=[
                    "Outlet ID", "Outlet Name", "Shop Category", "Zone", "State", "District",
                    "GSTIN", "PAN",
                ],
                rows=[],
                filename="unassigned-outlets-report.xlsx",
            )

        # Zone/state are a small, bounded lookup (a few dozen states) — unlike districts, safe
        # to fetch from Humbee's whole master and index once.
        geography = GeographyService(self._session, settings=self._settings, clock=self._clock)
        zones = geography.list_zones(claims=claims)["zones"]
        states = geography.list_states(claims=claims, zone_ids=[z["id"] for z in zones])["states"]
        zone_name_by_id = {z["id"]: z["name"] for z in zones}
        zone_name_by_state_id = {s["id"]: zone_name_by_id.get(s["zone_id"], "") for s in states}

        humbee_outlets = OutletReadService(
            self._session, settings=self._settings, clock=self._clock
        ).search_humbee_outlets(
            tenant_id=claims.tenant_id, district_ids=sorted(district_geo)
        )

        beats = BeatService(
            self._session, settings=self._settings, clock=self._clock
        ).list_beats_for_report(claims=claims)
        assigned_local_outlet_ids = {outlet_id for beat in beats for outlet_id, _ in beat["outlets"]}
        projected = OutletReadService(
            self._session, settings=self._settings, clock=self._clock
        ).get_projected_outlets(
            tenant_id=claims.tenant_id, outlet_ids=list(assigned_local_outlet_ids), ids_are_local=True
        )
        assigned_external_ids = {outlet.record.external_id for outlet in projected}

        seen: set[str] = set()
        rows = []
        for outlet in humbee_outlets:
            if outlet.external_id in assigned_external_ids or outlet.external_id in seen:
                continue
            seen.add(outlet.external_id)
            geo = district_geo.get(outlet.district_external_id, {})
            rows.append(
                [
                    outlet.external_id,
                    outlet.name,
                    outlet.category or "",
                    zone_name_by_state_id.get(geo.get("state_id"), ""),
                    geo.get("state_name", ""),
                    geo.get("name") or outlet.district_name,
                    outlet.gstin or "",
                    outlet.pan or "",
                ]
            )
        rows.sort(key=lambda row: row[1])

        return _single_sheet_response(
            sheet_name="Unassigned Outlets",
            headers=[
                "Outlet ID", "Outlet Name", "Shop Category", "Zone", "State", "District",
                "GSTIN", "PAN",
            ],
            rows=rows,
            filename="unassigned-outlets-report.xlsx",
        )

    # -- 6. Attendance -----------------------------------------------------------

    def attendance_report(self, *, claims: AccessTokenClaims, from_date: date, to_date: date) -> Response:
        self._require_admin(claims)
        if to_date < from_date:
            raise ApiError(400, "invalid_range", "'to_date' must not be before 'from_date'.")
        if to_date >= _add_months(from_date, _MAX_ATTENDANCE_RANGE_MONTHS):
            raise ApiError(
                400, "range_too_large", f"Date range must not exceed {_MAX_ATTENDANCE_RANGE_MONTHS} months."
            )
        directory = self._directory(claims)
        records = AttendanceService(
            self._session, settings=self._settings, clock=self._clock
        ).list_attendance_for_report(claims=claims, from_date=from_date, to_date=to_date)
        fact_days = repository.fact_employee_days_map(
            self._session,
            tenant_id=claims.tenant_id,
            employee_ids=list(directory),
            from_date=from_date,
            to_date=to_date,
        )

        rows = []
        for record in records:
            person = directory.get(record["employee_id"], {})
            fact = fact_days.get((record["employee_id"], record["business_date"]))
            punched_in_at = record["punched_in_at"]
            punched_out_at = record["punched_out_at"]
            if punched_in_at and punched_out_at:
                minutes = int((punched_out_at - punched_in_at).total_seconds() // 60)
                working_hours = f"{minutes // 60}:{minutes % 60:02d}"
            else:
                working_hours = ""
            mock_gps = bool(record["punch_in_is_mock"]) or bool(record["punch_out_is_mock"])
            rows.append(
                [
                    person.get("employee_code", record["employee_id"]),
                    record["employee_name"],
                    person.get("phone_e164", ""),
                    person.get("designation_code", ""),
                    person.get("manager_name", ""),
                    record["business_date"].isoformat(),
                    record["business_date"].strftime("%A"),
                    _status_label(record["status"]),
                    _status_label(record["leave_type"]) if record["leave_type"] else "",
                    _ist_time(punched_in_at),
                    record["punch_in_address"] or "",
                    _ist_time(punched_out_at),
                    record["punch_out_address"] or "",
                    _yes_no(record["is_late"]),
                    record["late_by_minutes"] if record["late_by_minutes"] is not None else "",
                    working_hours,
                    round(fact.distance_metres / 1000, 2) if fact else "",
                    fact.visits_total if fact else "",
                    fact.orders_submitted_count if fact else "",
                    _yes_no(mock_gps) if (record["punch_in_is_mock"] is not None or record["punch_out_is_mock"] is not None) else "",
                ]
            )
        return _single_sheet_response(
            sheet_name="Attendance",
            headers=[
                "Employee Code", "Name", "Phone", "Designation", "Manager", "Date", "Day", "Status",
                "Leave Type", "Punch In", "Punch In Location", "Punch Out", "Punch Out Location",
                "Late", "Late By (Mins)", "Working Hours", "Distance (km)", "Visits", "Orders",
                "Mock GPS",
            ],
            rows=rows,
            filename=f"attendance-report-{from_date.isoformat()}-to-{to_date.isoformat()}.xlsx",
        )

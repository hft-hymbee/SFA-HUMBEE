"""Attendance/Official-Work persistence. Thin, scoped, no business decisions.

Every read that can return more than one employee's row takes a resolved `ScopeContext` from
`org.scope` (attendance is `OrgResource.ACTIVITY_DATA`: SELF for a Sales Person, OWN_TREE for a
Manager, ORG for an Admin). Punch/official-work *writes* are always for the
acting employee (the id never comes from the request body), so writers take a plain
`tenant_id`/`employee_id` pair instead of a scope object.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from humbee_sfa.modules.attendance.models.attendance_day import AttendanceDay, AttendanceStatus
from humbee_sfa.modules.attendance.models.export_job import ExportJob
from humbee_sfa.modules.attendance.models.gps_fix import GpsFix
from humbee_sfa.modules.attendance.models.official_work_session import OfficialWorkSession
from humbee_sfa.modules.attendance.models.punch_event import PunchEvent
from humbee_sfa.modules.org.scope import ScopeContext, apply_scope
from humbee_sfa.platform.models.form_definition import FormDefinition

# ---------------------------------------------------------------------------
# Attendance days
# ---------------------------------------------------------------------------


def get_attendance_day(
    session: Session, *, tenant_id: str, employee_id: str, business_date: date
) -> AttendanceDay | None:
    stmt = select(AttendanceDay).where(
        AttendanceDay.tenant_id == tenant_id,
        AttendanceDay.employee_id == employee_id,
        AttendanceDay.business_date == business_date,
    )
    return session.execute(stmt).scalar_one_or_none()


def get_attendance_day_for_update(
    session: Session, *, tenant_id: str, employee_id: str, business_date: date
) -> AttendanceDay | None:
    """Row-locked read used by `punch()` so two concurrent punches for the same employee/day
    cannot both observe "not on duty" and both insert an `IN`."""

    stmt = (
        select(AttendanceDay)
        .where(
            AttendanceDay.tenant_id == tenant_id,
            AttendanceDay.employee_id == employee_id,
            AttendanceDay.business_date == business_date,
        )
        .with_for_update()
    )
    return session.execute(stmt).scalar_one_or_none()


def create_attendance_day(
    session: Session, *, tenant_id: str, employee_id: str, business_date: date
) -> AttendanceDay:
    """First punch of the business date creates the row on demand."""

    row = AttendanceDay(
        tenant_id=tenant_id,
        employee_id=employee_id,
        business_date=business_date,
        status=AttendanceStatus.NO_RECORD,
        on_duty=False,
        is_late=False,
        created_by_employee_id=employee_id,
    )
    session.add(row)
    session.flush()
    return row


def list_attendance_days_in_range(
    session: Session,
    *,
    scope: ScopeContext,
    employee_id: str,
    from_date: date,
    to_date: date,
) -> list[AttendanceDay]:
    """Monthly attendance calendar — `SELF` only in practice, scoped anyway for defence in depth."""

    stmt = (
        apply_scope(
            select(AttendanceDay),
            scope,
            tenant_column=AttendanceDay.tenant_id,
            employee_id_column=AttendanceDay.employee_id,
        )
        .where(
            AttendanceDay.employee_id == employee_id,
            AttendanceDay.business_date >= from_date,
            AttendanceDay.business_date <= to_date,
        )
        .order_by(AttendanceDay.business_date)
    )
    return list(session.execute(stmt).scalars().all())


def list_attendance_days_for_employees(
    session: Session, *, tenant_id: str, employee_ids: list[str], business_date: date
) -> dict[str, AttendanceDay]:
    """Team and org attendance row list — keyed by employee id so the caller can left-join against the org
    roster (employees with no row that day render "no punch-in", not an error)."""

    if not employee_ids:
        return {}
    stmt = select(AttendanceDay).where(
        AttendanceDay.tenant_id == tenant_id,
        AttendanceDay.employee_id.in_(employee_ids),
        AttendanceDay.business_date == business_date,
    )
    return {row.employee_id: row for row in session.execute(stmt).scalars().all()}


def list_attendance_days_for_employees_in_range(
    session: Session, *, tenant_id: str, employee_ids: list[str], from_date: date, to_date: date
) -> list[AttendanceDay]:
    """Every attendance row for the given employees within a date range, for the admin
    employee-wise attendance report."""

    if not employee_ids:
        return []
    stmt = select(AttendanceDay).where(
        AttendanceDay.tenant_id == tenant_id,
        AttendanceDay.employee_id.in_(employee_ids),
        AttendanceDay.business_date >= from_date,
        AttendanceDay.business_date <= to_date,
    )
    return list(session.execute(stmt).scalars().all())


def gps_fixes_for_punch_events(
    session: Session, *, tenant_id: str, punch_event_ids: list[str]
) -> dict[str, GpsFix]:
    """`GpsFix` keyed by punch event id, for the admin attendance report's punch-in/out
    location, GPS accuracy and mock-location columns. `attendance_days.first_punch_in_id` /
    `last_punch_out_id` are punch event ids, not GPS fix ids."""

    if not punch_event_ids:
        return {}
    stmt = (
        select(PunchEvent.id, GpsFix)
        .join(GpsFix, GpsFix.id == PunchEvent.gps_fix_id)
        .where(PunchEvent.tenant_id == tenant_id, PunchEvent.id.in_(punch_event_ids))
    )
    return {punch_id: fix for punch_id, fix in session.execute(stmt).all()}


# ---------------------------------------------------------------------------
# GPS fixes and punch events (append-only)
# ---------------------------------------------------------------------------


def insert_gps_fix(
    session: Session,
    *,
    tenant_id: str,
    employee_id: str,
    latitude: float,
    longitude: float,
    accuracy_m: float,
    altitude_m: float | None,
    provider: str,
    is_mock_location: bool,
    captured_at: datetime,
    resolved_address: str | None,
) -> GpsFix:
    point = cast(
        func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326),
        Geography(geometry_type="POINT", srid=4326),
    )
    row = GpsFix(
        tenant_id=tenant_id,
        latitude=latitude,
        longitude=longitude,
        point=point,
        accuracy_m=accuracy_m,
        altitude_m=altitude_m,
        provider=provider,
        is_mock_location=is_mock_location,
        captured_at=captured_at,
        resolved_address=resolved_address,
        geocode_status="ok" if resolved_address else "pending",
        created_by_employee_id=employee_id,
    )
    session.add(row)
    session.flush()
    return row


def latest_gps_fixes_for_employees(
    session: Session,
    *,
    tenant_id: str,
    employee_ids: list[str],
    start_utc: datetime,
    end_utc: datetime,
) -> dict[str, GpsFix]:
    """The single most recent `GpsFix` per employee within `[start_utc, end_utc)` — the coverage drill-down's
    "latest fix" map preview, owned here since GPS fixes are attendance's append-only
    raw evidence table."""

    if not employee_ids:
        return {}
    stmt = (
        select(GpsFix)
        .distinct(GpsFix.created_by_employee_id)
        .where(
            GpsFix.tenant_id == tenant_id,
            GpsFix.created_by_employee_id.in_(employee_ids),
            GpsFix.captured_at >= start_utc,
            GpsFix.captured_at < end_utc,
        )
        .order_by(GpsFix.created_by_employee_id, GpsFix.captured_at.desc())
    )
    rows = session.execute(stmt).scalars().all()
    return {row.created_by_employee_id: row for row in rows if row.created_by_employee_id is not None}


def insert_punch_event(
    session: Session,
    *,
    punch_id: str | None,
    tenant_id: str,
    employee_id: str,
    attendance_day_id: str,
    direction: str,
    occurred_at: datetime,
    received_at: datetime,
    business_date: date,
    gps_fix_id: str,
    idempotency_key: str,
) -> PunchEvent:
    row = PunchEvent(
        tenant_id=tenant_id,
        employee_id=employee_id,
        attendance_day_id=attendance_day_id,
        direction=direction,
        occurred_at=occurred_at,
        received_at=received_at,
        business_date=business_date,
        gps_fix_id=gps_fix_id,
        idempotency_key=idempotency_key,
        created_by_employee_id=employee_id,
    )
    if punch_id is not None:
        row.id = punch_id
    session.add(row)
    session.flush()
    return row


# ---------------------------------------------------------------------------
# Official work sessions
# ---------------------------------------------------------------------------


def get_running_official_work(
    session: Session, *, tenant_id: str, employee_id: str
) -> OfficialWorkSession | None:
    stmt = select(OfficialWorkSession).where(
        OfficialWorkSession.tenant_id == tenant_id,
        OfficialWorkSession.employee_id == employee_id,
        OfficialWorkSession.status == "running",
    )
    return session.execute(stmt).scalar_one_or_none()


def get_official_work_session(
    session: Session, *, tenant_id: str, employee_id: str, session_id: str
) -> OfficialWorkSession | None:
    stmt = select(OfficialWorkSession).where(
        OfficialWorkSession.tenant_id == tenant_id,
        OfficialWorkSession.employee_id == employee_id,
        OfficialWorkSession.id == session_id,
    )
    return session.execute(stmt).scalar_one_or_none()


def insert_official_work_session(
    session: Session,
    *,
    session_id: str | None,
    tenant_id: str,
    employee_id: str,
    business_date: date,
    work_type: str,
    form_definition_id: str,
    form_response: dict[str, Any],
    started_at: datetime,
    received_at: datetime,
    idempotency_key: str,
) -> OfficialWorkSession:
    row = OfficialWorkSession(
        tenant_id=tenant_id,
        employee_id=employee_id,
        business_date=business_date,
        work_type=work_type,
        form_definition_id=form_definition_id,
        form_response=form_response,
        started_at=started_at,
        # `FieldEventTimingMixin` columns: the "event" this row records is the start.
        occurred_at=started_at,
        received_at=received_at,
        status="running",
        idempotency_key=idempotency_key,
        created_by_employee_id=employee_id,
    )
    if session_id is not None:
        row.id = session_id
    session.add(row)
    session.flush()
    return row


def complete_official_work_session(
    session: Session, *, row: OfficialWorkSession, ended_at: datetime, duration_seconds: int
) -> OfficialWorkSession:
    row.ended_at = ended_at
    row.duration_seconds = duration_seconds
    row.status = "completed"
    session.flush()
    return row


def list_official_work_sessions_in_range(
    session: Session, *, tenant_id: str, employee_id: str, from_date: date, to_date: date
) -> list[OfficialWorkSession]:
    """Official-work history — `SELF`-scoped, completed sessions only (running sessions have no end to show)."""

    stmt = (
        select(OfficialWorkSession)
        .where(
            OfficialWorkSession.tenant_id == tenant_id,
            OfficialWorkSession.employee_id == employee_id,
            OfficialWorkSession.business_date >= from_date,
            OfficialWorkSession.business_date <= to_date,
            OfficialWorkSession.status == "completed",
        )
        .order_by(OfficialWorkSession.started_at.desc())
    )
    return list(session.execute(stmt).scalars().all())


def get_or_create_form_definition(
    session: Session, *, tenant_id: str, form_key: str, schema_payload: dict[str, Any]
) -> FormDefinition:
    """Lazily provisions the one `platform_form_definitions` row `OfficialWorkSession` needs to
    satisfy its `NOT NULL` FK. The field taxonomy is still pending business input,
    so no admin surface manages this yet — a fixed v1 definition is created on first use."""

    stmt = (
        select(FormDefinition)
        .where(FormDefinition.tenant_id == tenant_id, FormDefinition.form_key == form_key)
        .order_by(FormDefinition.version.desc())
        .limit(1)
    )
    existing = session.execute(stmt).scalar_one_or_none()
    if existing is not None:
        return existing
    row = FormDefinition(
        tenant_id=tenant_id,
        form_key=form_key,
        version=1,
        schema_payload=schema_payload,
        is_published=True,
    )
    session.add(row)
    session.flush()
    return row


# ---------------------------------------------------------------------------
# Attendance export jobs (Admin-only)
# ---------------------------------------------------------------------------


def insert_export_job(
    session: Session,
    *,
    tenant_id: str,
    requested_by: str,
    date_from: date,
    date_to: date,
    export_format: str,
    requested_at: datetime,
) -> ExportJob:
    row = ExportJob(
        tenant_id=tenant_id,
        requested_by=requested_by,
        scope="org",
        date_from=date_from,
        date_to=date_to,
        format=export_format,
        status="queued",
        requested_at=requested_at,
        created_by_employee_id=requested_by,
    )
    session.add(row)
    session.flush()
    return row


def get_export_job(
    session: Session, *, tenant_id: str, requested_by: str, job_id: str
) -> ExportJob | None:
    """An export is retrievable only by the Admin who requested it."""

    stmt = select(ExportJob).where(
        ExportJob.tenant_id == tenant_id,
        ExportJob.id == job_id,
        ExportJob.requested_by == requested_by,
    )
    return session.execute(stmt).scalar_one_or_none()

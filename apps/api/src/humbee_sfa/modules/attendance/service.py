"""Attendance / Official-Work business logic.

Transaction ownership lives here, not in the router (a service owns one transaction
per state transition together with its audit and domain-event writes), mirroring
`leave.service` / `beats.service`. Punch and official-work writes are always for the acting
employee — the employee id comes from `claims`, never from the request body.

`get_duty_state()` is a plain module function, not a method: the Today composition calls
it directly, in-process, alongside `AttendanceService`'s own HTTP-facing use of it for
`GET /attendance/today`.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, time, timedelta
from typing import Any

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from humbee_sfa.core.business_date import IST_ZONE, business_date_bounds_utc, to_business_date
from humbee_sfa.core.clock import Clock, SystemClock
from humbee_sfa.core.db import transaction
from humbee_sfa.core.deps import AccessTokenClaims
from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.core.settings import Settings, get_settings
from humbee_sfa.modules.attendance import events, repository, schemas
from humbee_sfa.modules.attendance.models.attendance_day import AttendanceDay, AttendanceStatus
from humbee_sfa.modules.attendance.models.official_work_session import OfficialWorkSession
from humbee_sfa.modules.leave.service import employees_on_leave, leave_types_by_ids
from humbee_sfa.modules.org.scope import OrgResource, Scope, ScopeContext, ScopeResolver
from humbee_sfa.modules.org.service import OrgService
from humbee_sfa.platform.audit import AuditLogService
from humbee_sfa.platform.domain_events import DomainEventPublisher
from humbee_sfa.platform.idempotency import IdempotencyService

logger = structlog.get_logger("humbee_sfa.attendance")

AUDIT_ENTITY_ATTENDANCE_DAY = "attendance_day"
AUDIT_ENTITY_OFFICIAL_WORK = "official_work_session"
AUDIT_ENTITY_EXPORT_JOB = "attendance_export_job"

OFFICIAL_WORK_FORM_KEY = "official_work"
# The field taxonomy is still pending business input; this is the fixed v1 shape.
_OFFICIAL_WORK_FORM_SCHEMA: dict[str, Any] = {"fields": ["purpose", "notes"]}


def _fingerprint(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _require_aware(value: datetime, *, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ApiError(422, "invalid_timestamp", f"{field} must be a timezone-aware timestamp.")
    return value


def current_business_date(clock: Clock, *, settings: Settings) -> date:
    return to_business_date(clock.now_utc(), settings.day_boundary_hour_ist)


def _check_idempotency(
    idempotency: IdempotencyService,
    *,
    endpoint: str,
    idempotency_key: str,
    raw_body: bytes,
    tenant_id: str,
) -> tuple[int, dict[str, Any]] | None:
    existing = idempotency.get(tenant_id=tenant_id, endpoint=endpoint, key=idempotency_key)
    if existing is None:
        return None
    if not idempotency.is_exact_replay(existing, _fingerprint(raw_body)):
        raise ApiError(
            409,
            "idempotency_conflict",
            "Idempotency key was already used with a different payload.",
        )
    return existing.status_code, existing.response_payload


def _store_idempotency(
    idempotency: IdempotencyService,
    *,
    endpoint: str,
    idempotency_key: str,
    raw_body: bytes,
    status_code: int,
    payload: dict[str, Any],
    tenant_id: str,
    actor_employee_id: str,
) -> None:
    idempotency.save(
        tenant_id=tenant_id,
        endpoint=endpoint,
        key=idempotency_key,
        request_fingerprint=_fingerprint(raw_body),
        response_fingerprint=_fingerprint(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ),
        status_code=status_code,
        response_payload=payload,
        actor_employee_id=actor_employee_id,
    )


# ---------------------------------------------------------------------------
# Duty state — the punch-in gate
# ---------------------------------------------------------------------------


def _today_payload(*, business_date: date, day: AttendanceDay | None) -> dict[str, Any]:
    return schemas.AttendanceTodayResponse(
        business_date=business_date,
        on_duty=day.on_duty if day else False,
        punched_in_at=day.punched_in_at if day else None,
        punched_out_at=day.punched_out_at if day else None,
        punch_in_address=day.punch_in_address if day else None,
    ).model_dump(mode="json")


def get_duty_state(
    session: Session,
    *,
    tenant_id: str,
    employee_id: str,
    clock: Clock | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """The canonical duty-state read — one query key app-wide. The Today
    composition and `GET /attendance/today` both call this, so the punch-in gate can never drift
    between the two surfaces."""

    active_clock = clock or SystemClock()
    active_settings = settings or get_settings()
    business_date = current_business_date(active_clock, settings=active_settings)
    day = repository.get_attendance_day(
        session, tenant_id=tenant_id, employee_id=employee_id, business_date=business_date
    )
    return _today_payload(business_date=business_date, day=day)


def latest_positions(
    session: Session,
    *,
    tenant_id: str,
    employee_ids: list[str],
    business_date: date,
    settings: Settings,
) -> dict[str, dict[str, Any]]:
    """`{employee_id: {"lat", "lng", "captured_at"}}` for the given business date — the coverage drill-down's
    map preview. Cross-module callers (routes.service) pass their own already-scoped
    `employee_ids`, so this takes no claims/scope of its own, matching `get_duty_state`."""

    start_utc, end_utc = business_date_bounds_utc(business_date, settings.day_boundary_hour_ist)
    fixes = repository.latest_gps_fixes_for_employees(
        session, tenant_id=tenant_id, employee_ids=employee_ids, start_utc=start_utc, end_utc=end_utc,
    )
    return {
        employee_id: {"lat": fix.latitude, "lng": fix.longitude, "captured_at": fix.captured_at}
        for employee_id, fix in fixes.items()
    }


def day_summary(
    session: Session, *, tenant_id: str, employee_id: str, business_date: date,
) -> dict[str, Any]:
    """Punch in/out + completed official-work blocks for one employee/day — the attendance half of
    a manager's day-drill-down timeline. Plain params like `get_duty_state`,
    since `routes.service` calls this for a report it has already scope-authorized itself."""

    day = repository.get_attendance_day(
        session, tenant_id=tenant_id, employee_id=employee_id, business_date=business_date
    )
    sessions = repository.list_official_work_sessions_in_range(
        session, tenant_id=tenant_id, employee_id=employee_id,
        from_date=business_date, to_date=business_date,
    )
    return {
        "punched_in_at": day.punched_in_at if day else None,
        "punched_out_at": day.punched_out_at if day else None,
        "on_duty": bool(day and day.on_duty),
        "official_work": [
            {
                "id": row.id, "work_type": row.work_type, "started_at": row.started_at,
                "ended_at": row.ended_at, "duration_seconds": row.duration_seconds,
            }
            for row in sessions
        ],
    }


def _official_work_item(row: OfficialWorkSession) -> schemas.OfficialWorkSessionItem:
    return schemas.OfficialWorkSessionItem(
        id=row.id,
        work_type=row.work_type,
        purpose=row.form_response.get("purpose"),
        notes=row.form_response.get("notes"),
        started_at=row.started_at,
        ended_at=row.ended_at,
        duration_seconds=row.duration_seconds,
        status=row.status,
    )


def _official_work_payload(row: OfficialWorkSession) -> dict[str, Any]:
    return _official_work_item(row).model_dump(mode="json")


# ---------------------------------------------------------------------------
# Attendance — punches, history, oversight, export
# ---------------------------------------------------------------------------


class AttendanceService:
    def __init__(
        self, session: Session, *, settings: Settings | None = None, clock: Clock | None = None
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._clock = clock or SystemClock()
        self._audit = AuditLogService(session)
        self._events = DomainEventPublisher(session, self._clock)
        self._idempotency = IdempotencyService(session)

    def _scope(self, claims: AccessTokenClaims) -> ScopeContext:
        return ScopeResolver.resolve_from_claims(claims, OrgResource.ACTIVITY_DATA)

    # -- reads ---------------------------------------------------------

    def today(self, *, claims: AccessTokenClaims) -> dict[str, Any]:
        return get_duty_state(
            self._session,
            tenant_id=claims.tenant_id,
            employee_id=claims.employee_id,
            clock=self._clock,
            settings=self._settings,
        )

    def history(self, *, claims: AccessTokenClaims, month: str) -> dict[str, Any]:
        """`SELF` only; blank days (no row) are simply absent from `days`,
        never fabricated as `ABSENT`."""

        year_str, month_str = month.split("-", 1)
        year, month_num = int(year_str), int(month_str)
        from_date = date(year, month_num, 1)
        next_month = date(year + 1, 1, 1) if month_num == 12 else date(year, month_num + 1, 1)
        to_date = next_month - timedelta(days=1)

        scope = self._scope(claims)
        rows = repository.list_attendance_days_in_range(
            self._session,
            scope=scope,
            employee_id=claims.employee_id,
            from_date=from_date,
            to_date=to_date,
        )
        summary = schemas.AttendanceHistorySummary(
            present=sum(1 for row in rows if row.status == AttendanceStatus.PRESENT),
            late=sum(1 for row in rows if row.status == AttendanceStatus.LATE),
            absent=sum(1 for row in rows if row.status == AttendanceStatus.ABSENT),
            leave=sum(1 for row in rows if row.status == AttendanceStatus.LEAVE),
        )
        return schemas.AttendanceHistoryResponse(
            month=month,
            days=[
                schemas.AttendanceHistoryDay(
                    business_date=row.business_date,
                    status=row.status,
                    punched_in_at=row.punched_in_at,
                    punched_out_at=row.punched_out_at,
                    on_duty=row.on_duty,
                )
                for row in rows
            ],
            summary=summary,
        ).model_dump(mode="json")

    def team(
        self, *, claims: AccessTokenClaims, business_date: date, page: int, page_size: int | None
    ) -> dict[str, Any]:
        """One endpoint, scope resolved from the actor. Summary counts
        cover the full scope, not the visible page."""

        scope = self._scope(claims)
        if scope.scope is Scope.SELF:
            raise ApiError(403, "forbidden", "Team attendance is available to managers and admins.")

        everyone = OrgService(
            self._session, settings=self._settings, clock=self._clock
        ).list_all_employees(claims=claims, status="active")
        if page_size is None:
            page, page_size = 1, max(len(everyone), 1)
        page_items = everyone[(page - 1) * page_size : page * page_size]
        days_by_employee = repository.list_attendance_days_for_employees(
            self._session,
            tenant_id=scope.tenant_id,
            employee_ids=[item["id"] for item in everyone],
            business_date=business_date,
        )
        on_leave_ids = employees_on_leave(
            self._session, tenant_id=scope.tenant_id, on_date=business_date
        )
        punched_ids = {
            employee_id
            for employee_id, day in days_by_employee.items()
            if day.punched_in_at is not None
        }
        roster_ids = {item["id"] for item in everyone}
        items = []
        for item in page_items:
            day = days_by_employee.get(item["id"])
            items.append(
                schemas.TeamAttendanceRow(
                    employee_id=item["id"],
                    employee_name=item["full_name"],
                    punched_in_at=day.punched_in_at if day else None,
                    punch_in_address=day.punch_in_address if day else None,
                    on_duty=bool(day and day.on_duty),
                    is_late=bool(day and day.is_late),
                    on_leave=item["id"] in on_leave_ids,
                )
            )
        return schemas.TeamAttendanceResponse(
            business_date=business_date,
            on_duty_count=sum(1 for day in days_by_employee.values() if day.on_duty),
            after_9am_count=sum(1 for day in days_by_employee.values() if day.is_late),
            no_punch_in_count=len(roster_ids - punched_ids - on_leave_ids),
            on_leave_count=len(roster_ids & on_leave_ids),
            items=items,
            total=len(everyone),
            page=page,
            page_size=page_size,
        ).model_dump(mode="json")

    def list_attendance_for_report(
        self, *, claims: AccessTokenClaims, from_date: date, to_date: date
    ) -> list[dict[str, Any]]:
        """Admin-only bulk export: one row per active employee per business date in range,
        for the admin employee-wise attendance report. A date with no attendance row renders
        `no_record` rather than being dropped, so gaps are visible."""

        scope = self._scope(claims)
        if scope.scope is Scope.SELF:
            raise ApiError(403, "forbidden", "Team attendance is available to managers and admins.")

        roster = OrgService(self._session, settings=self._settings, clock=self._clock).list_all_employees(
            claims=claims, status="active"
        )
        employee_ids = [item["id"] for item in roster]
        names_by_id = {item["id"]: item["full_name"] for item in roster}
        days = repository.list_attendance_days_for_employees_in_range(
            self._session,
            tenant_id=scope.tenant_id,
            employee_ids=employee_ids,
            from_date=from_date,
            to_date=to_date,
        )
        days_by_key = {(day.employee_id, day.business_date): day for day in days}

        punch_event_ids = list(
            {day.first_punch_in_id for day in days if day.first_punch_in_id}
            | {day.last_punch_out_id for day in days if day.last_punch_out_id}
        )
        gps_by_punch_event = repository.gps_fixes_for_punch_events(
            self._session, tenant_id=scope.tenant_id, punch_event_ids=punch_event_ids
        )
        leave_request_ids = [day.leave_request_id for day in days if day.leave_request_id]
        leave_type_by_request_id = leave_types_by_ids(
            self._session, tenant_id=scope.tenant_id, leave_request_ids=leave_request_ids
        )
        threshold_hour = self._settings.attendance_late_threshold_hour_ist

        def _gps_columns(prefix: str, punch_event_id: str | None, *, address: str | None = None) -> dict[str, Any]:
            fix = gps_by_punch_event.get(punch_event_id) if punch_event_id else None
            return {
                f"{prefix}_address": address if address is not None else (fix.resolved_address if fix else None),
                f"{prefix}_latitude": float(fix.latitude) if fix else None,
                f"{prefix}_longitude": float(fix.longitude) if fix else None,
                f"{prefix}_accuracy_m": float(fix.accuracy_m) if fix else None,
                f"{prefix}_is_mock": bool(fix.is_mock_location) if fix else None,
            }

        def _late_by_minutes(day: AttendanceDay | None) -> int | None:
            if day is None or not day.is_late or day.punched_in_at is None:
                return None
            local_in = day.punched_in_at.astimezone(IST_ZONE)
            threshold_dt = local_in.replace(hour=threshold_hour, minute=0, second=0, microsecond=0)
            return max(0, round((local_in - threshold_dt).total_seconds() / 60))

        rows: list[dict[str, Any]] = []
        current = from_date
        while current <= to_date:
            for employee_id in employee_ids:
                day = days_by_key.get((employee_id, current))
                row: dict[str, Any] = {
                    "employee_id": employee_id,
                    "employee_name": names_by_id.get(employee_id, employee_id),
                    "business_date": current,
                    "status": day.status if day else AttendanceStatus.NO_RECORD.value,
                    "leave_type": leave_type_by_request_id.get(day.leave_request_id)
                    if day and day.leave_request_id
                    else None,
                    "punched_in_at": day.punched_in_at if day else None,
                    "punched_out_at": day.punched_out_at if day else None,
                    "is_late": bool(day.is_late) if day else False,
                    "late_by_minutes": _late_by_minutes(day),
                }
                row.update(
                    _gps_columns(
                        "punch_in",
                        day.first_punch_in_id if day else None,
                        address=day.punch_in_address if day else None,
                    )
                )
                row.update(_gps_columns("punch_out", day.last_punch_out_id if day else None))
                rows.append(row)
            current += timedelta(days=1)
        return rows

    # -- punch -----------------------------------------------------------

    def punch(
        self,
        *,
        claims: AccessTokenClaims,
        body: schemas.PunchBody,
        idempotency_key: str,
        raw_body: bytes,
    ) -> tuple[int, dict[str, Any]]:
        """Punch confirm. One transaction: GPS fix, the
        append-only punch event, the `AttendanceDay` upsert, audit and the domain event."""

        tenant_id, employee_id = claims.tenant_id, claims.employee_id
        endpoint = "/api/v1/attendance/punches"
        try:
            with transaction(self._session):
                replay = _check_idempotency(
                    self._idempotency, endpoint=endpoint, idempotency_key=idempotency_key,
                    raw_body=raw_body, tenant_id=tenant_id,
                )
                if replay is not None:
                    return replay

                fix = body.gps_fix

                occurred_at = _require_aware(body.occurred_at, field="occurred_at")
                business_date = to_business_date(occurred_at, self._settings.day_boundary_hour_ist)

                # Row lock: two concurrent punches for the same employee/day must not both observe
                # "not on duty".
                day = repository.get_attendance_day_for_update(
                    self._session, tenant_id=tenant_id, employee_id=employee_id, business_date=business_date
                )

                if body.direction == "in":
                    if day is not None and day.on_duty:
                        raise ApiError(409, "already_punched_in", "You are already punched in.")
                    if day is not None and day.last_punch_out_id is not None:
                        # Exactly one IN -> OUT cycle is allowed per employee/business date.
                        raise ApiError(
                            409, "punch_sequence_conflict", "Only one punch-in/out cycle is allowed per day."
                        )
                else:
                    if day is None or not day.on_duty:
                        raise ApiError(409, "already_punched_out", "You are not currently punched in.")
                    if repository.get_running_official_work(
                        self._session, tenant_id=tenant_id, employee_id=employee_id
                    ) is not None:
                        # Official work must end before punch-out is accepted.
                        raise ApiError(409, "official_work_running", "End official work before punching out.")
                    from humbee_sfa.modules.routes.service import RouteService

                    if RouteService(
                        self._session, settings=self._settings, clock=self._clock
                    ).get_active_visit_id(claims=claims) is not None:
                        raise ApiError(409, "visit_in_progress", "End your visit before punching out.")

                received_at = self._clock.now_utc()
                gps_row = repository.insert_gps_fix(
                    self._session,
                    tenant_id=tenant_id,
                    employee_id=employee_id,
                    latitude=fix.latitude,
                    longitude=fix.longitude,
                    accuracy_m=fix.accuracy_m,
                    altitude_m=fix.altitude_m,
                    provider=fix.provider,
                    is_mock_location=fix.is_mock_location,
                    captured_at=fix.captured_at,
                    resolved_address=body.resolved_address,
                )

                if day is None:
                    day = repository.create_attendance_day(
                        self._session, tenant_id=tenant_id, employee_id=employee_id, business_date=business_date
                    )

                punch_row = repository.insert_punch_event(
                    self._session,
                    punch_id=body.id,
                    tenant_id=tenant_id,
                    employee_id=employee_id,
                    attendance_day_id=day.id,
                    direction=body.direction,
                    occurred_at=occurred_at,
                    received_at=received_at,
                    business_date=business_date,
                    gps_fix_id=gps_row.id,
                    idempotency_key=idempotency_key,
                )

                if body.direction == "in":
                    threshold = time(self._settings.attendance_late_threshold_hour_ist, 0)
                    is_late = occurred_at.astimezone(IST_ZONE).time() > threshold
                    day.first_punch_in_id = punch_row.id
                    day.punched_in_at = occurred_at
                    day.punch_in_address = body.resolved_address
                    day.on_duty = True
                    day.is_late = is_late
                    day.status = AttendanceStatus.LATE if is_late else AttendanceStatus.PRESENT
                    event_type = events.PUNCHED_IN
                else:
                    day.last_punch_out_id = punch_row.id
                    day.punched_out_at = occurred_at
                    day.on_duty = False
                    event_type = events.PUNCHED_OUT
                self._session.flush()

                self._audit.record_transition(
                    tenant_id=tenant_id,
                    entity_type=AUDIT_ENTITY_ATTENDANCE_DAY,
                    entity_id=day.id,
                    from_state=None,
                    to_state=body.direction,
                    actor_employee_id=employee_id,
                    change_payload={"punch_event_id": punch_row.id},
                )
                events.publish_attendance_event(
                    self._events,
                    tenant_id=tenant_id,
                    event_type=event_type,
                    aggregate_type=events.AGGREGATE_ATTENDANCE_DAY,
                    aggregate_id=day.id,
                    payload={
                        "employee_id": employee_id,
                        "business_date": business_date.isoformat(),
                        "is_late": day.is_late,
                    },
                    actor_employee_id=employee_id,
                    occurred_at=occurred_at,
                )

                payload = _today_payload(business_date=business_date, day=day)
                _store_idempotency(
                    self._idempotency, endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body,
                    status_code=201, payload=payload, tenant_id=tenant_id, actor_employee_id=employee_id,
                )
        except IntegrityError as exc:
            if "uq_attendance_punch_idem" in str(getattr(exc, "orig", exc)):
                raise ApiError(409, "idempotency_conflict", "Idempotency key was already used.") from exc
            raise

        logger.info(
            "attendance_punch_recorded",
            employee_id=employee_id,
            direction=body.direction,
            business_date=str(business_date),
        )
        return 201, payload

    # -- export (Admin-only) ------------------------------------

    def request_export(
        self,
        *,
        claims: AccessTokenClaims,
        body: schemas.ExportRequestBody,
        idempotency_key: str,
        raw_body: bytes,
    ) -> tuple[int, dict[str, Any]]:
        """Enqueues the `attendance_export_jobs` bookkeeping row (never a synchronous
        file response). **No worker exists to process the queue** — object
        storage has not landed — so a job stays `queued` until that lands."""

        scope = self._scope(claims)
        if scope.scope is not Scope.ORG:
            raise ApiError(403, "export_admin_only", "Attendance export is Admin-only.")
        endpoint = "/api/v1/attendance/exports"
        with transaction(self._session):
            replay = _check_idempotency(
                self._idempotency, endpoint=endpoint, idempotency_key=idempotency_key,
                raw_body=raw_body, tenant_id=scope.tenant_id,
            )
            if replay is not None:
                return replay
            if body.date_to < body.date_from:
                raise ApiError(422, "invalid_date_range", "date_to cannot be before date_from.")

            row = repository.insert_export_job(
                self._session,
                tenant_id=scope.tenant_id,
                requested_by=claims.employee_id,
                date_from=body.date_from,
                date_to=body.date_to,
                export_format=body.format,
                requested_at=self._clock.now_utc(),
            )
            self._audit.record_transition(
                tenant_id=scope.tenant_id,
                entity_type=AUDIT_ENTITY_EXPORT_JOB,
                entity_id=row.id,
                from_state=None,
                to_state="queued",
                actor_employee_id=claims.employee_id,
                change_payload={
                    "date_from": body.date_from.isoformat(),
                    "date_to": body.date_to.isoformat(),
                    "format": body.format,
                },
            )
            payload = schemas.ExportJobResponse(
                id=row.id, status=row.status, artifact_url=row.artifact_url,
                requested_at=row.requested_at, completed_at=row.completed_at,
            ).model_dump(mode="json")
            _store_idempotency(
                self._idempotency, endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body,
                status_code=202, payload=payload, tenant_id=scope.tenant_id, actor_employee_id=claims.employee_id,
            )

        logger.info("attendance_export_requested", job_id=row.id, format=body.format)
        return 202, payload

    def get_export(self, *, claims: AccessTokenClaims, job_id: str) -> dict[str, Any]:
        scope = self._scope(claims)
        if scope.scope is not Scope.ORG:
            raise ApiError(403, "export_admin_only", "Attendance export is Admin-only.")
        row = repository.get_export_job(
            self._session, tenant_id=scope.tenant_id, requested_by=claims.employee_id, job_id=job_id
        )
        if row is None:
            raise ApiError(404, "export_job_not_found", "Export job was not found.")
        return schemas.ExportJobResponse(
            id=row.id, status=row.status, artifact_url=row.artifact_url,
            requested_at=row.requested_at, completed_at=row.completed_at,
        ).model_dump(mode="json")


# ---------------------------------------------------------------------------
# Official work — timer, lifecycle, history
# ---------------------------------------------------------------------------


class OfficialWorkService:
    def __init__(
        self, session: Session, *, settings: Settings | None = None, clock: Clock | None = None
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._clock = clock or SystemClock()
        self._audit = AuditLogService(session)
        self._events = DomainEventPublisher(session, self._clock)
        self._idempotency = IdempotencyService(session)

    def current(self, *, claims: AccessTokenClaims) -> dict[str, Any] | None:
        row = repository.get_running_official_work(
            self._session, tenant_id=claims.tenant_id, employee_id=claims.employee_id
        )
        return _official_work_payload(row) if row is not None else None

    def start(
        self,
        *,
        claims: AccessTokenClaims,
        body: schemas.OfficialWorkStartBody,
        idempotency_key: str,
        raw_body: bytes,
    ) -> tuple[int, dict[str, Any]]:
        """Official-work start. Requires an active punch-in for the business date
        the session starts in."""

        tenant_id, employee_id = claims.tenant_id, claims.employee_id
        endpoint = "/api/v1/official-work/sessions"
        try:
            with transaction(self._session):
                replay = _check_idempotency(
                    self._idempotency, endpoint=endpoint, idempotency_key=idempotency_key,
                    raw_body=raw_body, tenant_id=tenant_id,
                )
                if replay is not None:
                    return replay

                occurred_at = _require_aware(body.occurred_at, field="occurred_at")
                business_date = to_business_date(occurred_at, self._settings.day_boundary_hour_ist)

                duty_day = repository.get_attendance_day(
                    self._session, tenant_id=tenant_id, employee_id=employee_id, business_date=business_date
                )
                if duty_day is None or not duty_day.on_duty:
                    raise ApiError(403, "not_on_duty", "Punch in before starting official work.")
                from humbee_sfa.modules.routes.service import RouteService

                if RouteService(
                    self._session, settings=self._settings, clock=self._clock
                ).get_active_visit_id(claims=claims) is not None:
                    raise ApiError(
                        409, "visit_in_progress", "End your current visit before starting official work."
                    )
                if repository.get_running_official_work(
                    self._session, tenant_id=tenant_id, employee_id=employee_id
                ) is not None:
                    raise ApiError(409, "official_work_already_running", "A session is already running.")

                form_definition = repository.get_or_create_form_definition(
                    self._session, tenant_id=tenant_id, form_key=OFFICIAL_WORK_FORM_KEY,
                    schema_payload=_OFFICIAL_WORK_FORM_SCHEMA,
                )
                row = repository.insert_official_work_session(
                    self._session,
                    session_id=body.id,
                    tenant_id=tenant_id,
                    employee_id=employee_id,
                    business_date=business_date,
                    work_type=body.work_type,
                    form_definition_id=form_definition.id,
                    form_response={"purpose": body.purpose, "notes": body.notes},
                    started_at=occurred_at,
                    received_at=self._clock.now_utc(),
                    idempotency_key=idempotency_key,
                )
                self._audit.record_transition(
                    tenant_id=tenant_id, entity_type=AUDIT_ENTITY_OFFICIAL_WORK, entity_id=row.id,
                    from_state=None, to_state="running", actor_employee_id=employee_id,
                )
                events.publish_attendance_event(
                    self._events,
                    tenant_id=tenant_id,
                    event_type=events.OFFICIAL_WORK_STARTED,
                    aggregate_type=events.AGGREGATE_OFFICIAL_WORK_SESSION,
                    aggregate_id=row.id,
                    payload={
                        "employee_id": employee_id,
                        "work_type": row.work_type,
                        "business_date": business_date.isoformat(),
                    },
                    actor_employee_id=employee_id,
                    occurred_at=occurred_at,
                )

                payload = _official_work_payload(row)
                _store_idempotency(
                    self._idempotency, endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body,
                    status_code=201, payload=payload, tenant_id=tenant_id, actor_employee_id=employee_id,
                )
        except IntegrityError as exc:
            marker = str(getattr(exc, "orig", exc))
            if "uq_attendance_official_running" in marker:
                raise ApiError(409, "official_work_already_running", "A session is already running.") from exc
            if "uq_attendance_official_idem" in marker:
                raise ApiError(409, "idempotency_conflict", "Idempotency key was already used.") from exc
            raise

        logger.info("official_work_started", session_id=row.id, work_type=row.work_type)
        return 201, payload

    def end(
        self,
        *,
        claims: AccessTokenClaims,
        session_id: str,
        body: schemas.OfficialWorkEndBody,
        idempotency_key: str,
        raw_body: bytes,
    ) -> tuple[int, dict[str, Any]]:
        """Official-work end: duration is computed server-side from the two
        server-held timestamps, never trusted from the client's tick counter."""

        tenant_id, employee_id = claims.tenant_id, claims.employee_id
        endpoint = f"/api/v1/official-work/sessions/{session_id}/end"
        with transaction(self._session):
            replay = _check_idempotency(
                self._idempotency, endpoint=endpoint, idempotency_key=idempotency_key,
                raw_body=raw_body, tenant_id=tenant_id,
            )
            if replay is not None:
                return replay

            row = repository.get_official_work_session(
                self._session, tenant_id=tenant_id, employee_id=employee_id, session_id=session_id
            )
            if row is None:
                raise ApiError(404, "official_work_not_found", "Session was not found.")
            if row.status != "running":
                raise ApiError(409, "official_work_not_running", "Session has already ended.")

            ended_at = _require_aware(body.occurred_at, field="occurred_at")
            if ended_at < row.started_at:
                raise ApiError(422, "invalid_end_time", "End time cannot be before the start time.")
            duration_seconds = int((ended_at - row.started_at).total_seconds())

            repository.complete_official_work_session(
                self._session, row=row, ended_at=ended_at, duration_seconds=duration_seconds
            )
            self._audit.record_transition(
                tenant_id=tenant_id, entity_type=AUDIT_ENTITY_OFFICIAL_WORK, entity_id=row.id,
                from_state="running", to_state="completed", actor_employee_id=employee_id,
            )
            events.publish_attendance_event(
                self._events,
                tenant_id=tenant_id,
                event_type=events.OFFICIAL_WORK_LOGGED,
                aggregate_type=events.AGGREGATE_OFFICIAL_WORK_SESSION,
                aggregate_id=row.id,
                payload={
                    "employee_id": employee_id,
                    "work_type": row.work_type,
                    "duration_seconds": duration_seconds,
                    "business_date": row.business_date.isoformat(),
                },
                actor_employee_id=employee_id,
                occurred_at=ended_at,
            )

            payload = _official_work_payload(row)
            _store_idempotency(
                self._idempotency, endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body,
                status_code=200, payload=payload, tenant_id=tenant_id, actor_employee_id=employee_id,
            )

        logger.info("official_work_logged", session_id=row.id, duration_seconds=duration_seconds)
        return 200, payload

    def history(
        self, *, claims: AccessTokenClaims, from_date: date, to_date: date
    ) -> dict[str, Any]:
        rows = repository.list_official_work_sessions_in_range(
            self._session, tenant_id=claims.tenant_id, employee_id=claims.employee_id,
            from_date=from_date, to_date=to_date,
        )
        total_seconds = sum(row.duration_seconds or 0 for row in rows)
        return schemas.OfficialWorkHistoryResponse(
            items=[_official_work_item(row) for row in rows],
            summary=schemas.OfficialWorkHistorySummary(total_seconds=total_seconds, count=len(rows)),
        ).model_dump(mode="json")

"""Attendance / Official-Work HTTP DTOs — M09 §10.

Only the S-ATT1–4 and S-OFF1–2 surface is modelled. Client-composed display strings (the
`"In 9:12 AM · MG Road"` row subtitle, the `"1.2 km"` distance copy, the `HH:MM:SS` timer) are not
sent — M09 §8 lists every one of them as a client formatter over these raw fields.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

PunchDirection = Literal["in", "out"]
GpsProvider = Literal["gps", "network", "fused"]
WorkType = Literal["meeting", "training", "collection", "other"]
ExportFormat = Literal["csv", "xlsx", "pdf"]


class GpsFixBody(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: float = Field(ge=0, le=99999.99)
    altitude_m: float | None = None
    provider: GpsProvider
    is_mock_location: bool = False
    captured_at: datetime


class PunchBody(BaseModel):
    """`id` is the client-generated ULID for the `PunchEvent` (M09 §3.2, R-ATT-18)."""

    id: str | None = Field(default=None, min_length=26, max_length=26)
    direction: PunchDirection
    occurred_at: datetime
    gps_fix: GpsFixBody
    resolved_address: str | None = Field(default=None, max_length=500)


class AttendanceTodayResponse(BaseModel):
    """The single canonical duty-state payload — S-ATT1 mount, the punch-in gate, and the body of
    every successful `POST /attendance/punches` (M09 §5.1, §5.2)."""

    business_date: date
    on_duty: bool
    punched_in_at: datetime | None
    punched_out_at: datetime | None
    punch_in_address: str | None


class AttendanceHistoryDay(BaseModel):
    business_date: date
    status: str
    punched_in_at: datetime | None
    punched_out_at: datetime | None
    on_duty: bool


class AttendanceHistorySummary(BaseModel):
    present: int
    late: int
    absent: int
    leave: int


class AttendanceHistoryResponse(BaseModel):
    month: str
    days: list[AttendanceHistoryDay]
    summary: AttendanceHistorySummary


class TeamAttendanceRow(BaseModel):
    employee_id: str
    employee_name: str
    punched_in_at: datetime | None
    punch_in_address: str | None
    on_duty: bool
    is_late: bool
    on_leave: bool


class TeamAttendanceResponse(BaseModel):
    """S-ATT3/S-ATT4 — one endpoint, scope resolved from the actor (R-ATT-17). Summary counts are
    computed over the full scope, never the visible page (R-ATT-12)."""

    business_date: date
    on_duty_count: int
    after_9am_count: int
    no_punch_in_count: int
    on_leave_count: int
    items: list[TeamAttendanceRow]
    total: int
    page: int
    page_size: int


class ExportRequestBody(BaseModel):
    date_from: date
    date_to: date
    format: ExportFormat


class ExportJobResponse(BaseModel):
    id: str
    status: str
    artifact_url: str | None
    requested_at: datetime
    completed_at: datetime | None


class OfficialWorkStartBody(BaseModel):
    id: str | None = Field(default=None, min_length=26, max_length=26)
    work_type: WorkType
    occurred_at: datetime
    purpose: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)


class OfficialWorkEndBody(BaseModel):
    occurred_at: datetime


class OfficialWorkSessionItem(BaseModel):
    id: str
    work_type: str
    purpose: str | None
    notes: str | None
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int | None
    status: str


class OfficialWorkHistorySummary(BaseModel):
    total_seconds: int
    count: int


class OfficialWorkHistoryResponse(BaseModel):
    items: list[OfficialWorkSessionItem]
    summary: OfficialWorkHistorySummary

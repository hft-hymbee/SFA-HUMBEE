"""`attendance` models — database-design.md §9. Read this file for the index; open a specific
module for column detail.

- `gps_fix.py`                 `attendance_gps_fixes` — append-only, raw GPS evidence.
- `attendance_day.py`          `attendance_days` — one row per employee per business date.
- `punch_event.py`             `attendance_punch_events` — append-only punch log.
- `official_work_session.py`   `attendance_official_work_sessions` — meeting/training/collection time.
- `export_job.py`              `attendance_export_jobs` — async org-wide export requests.
"""

from __future__ import annotations

from humbee_sfa.modules.attendance.models.attendance_day import AttendanceDay, AttendanceStatus
from humbee_sfa.modules.attendance.models.export_job import ExportJob
from humbee_sfa.modules.attendance.models.gps_fix import GpsFix
from humbee_sfa.modules.attendance.models.official_work_session import OfficialWorkSession
from humbee_sfa.modules.attendance.models.punch_event import PunchEvent

__all__ = [
    "AttendanceDay",
    "AttendanceStatus",
    "ExportJob",
    "GpsFix",
    "OfficialWorkSession",
    "PunchEvent",
]

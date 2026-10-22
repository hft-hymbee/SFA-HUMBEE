from __future__ import annotations

from enum import StrEnum


class LeaveType(StrEnum):
    PRIVILEGED = "privileged"
    CASUAL = "casual"
    SICK = "sick"


LEAVE_TYPE_VALUES_SQL = "', '".join(leave_type.value for leave_type in LeaveType)


__all__ = ["LEAVE_TYPE_VALUES_SQL", "LeaveType"]

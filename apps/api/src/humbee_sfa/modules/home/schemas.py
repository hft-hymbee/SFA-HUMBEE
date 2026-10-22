"""Today composition HTTP DTOs.

Each section is `{status: "available", data}` or `{status: "unavailable", reason, retryable,
as_of}`. `identity` is typed precisely
since it is small and wholly owned by this module; the other sections carry whatever their owning
module's own public service already returns, so this module never duplicates attendance/routes/
approvals/notifications DTOs.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel


class SectionUnavailable(BaseModel):
    status: Literal["unavailable"] = "unavailable"
    reason: str
    retryable: bool
    as_of: datetime | None = None


class SectionAvailable(BaseModel):
    status: Literal["available"] = "available"
    data: dict[str, Any]


class TodayIdentity(BaseModel):
    greeting_name: str
    role: str


class IdentitySectionAvailable(BaseModel):
    status: Literal["available"] = "available"
    data: TodayIdentity


class TodayResponse(BaseModel):
    business_date: date
    identity: IdentitySectionAvailable | SectionUnavailable
    attendance: SectionAvailable | SectionUnavailable
    route: SectionAvailable | SectionUnavailable
    requests: SectionAvailable | SectionUnavailable
    notifications: SectionAvailable | SectionUnavailable
    targets: SectionAvailable | SectionUnavailable

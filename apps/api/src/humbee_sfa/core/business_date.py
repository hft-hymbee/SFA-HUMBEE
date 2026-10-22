"""Business-date helpers using IST as canonical business calendar."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

IST_ZONE = ZoneInfo("Asia/Kolkata")


def to_business_date(timestamp_utc: datetime, day_boundary_hour: int = 0) -> date:
    """Convert a UTC timestamp to the configured IST business date."""

    if timestamp_utc.tzinfo is None or timestamp_utc.utcoffset() is None:
        raise ValueError("timestamp_utc must be timezone-aware")
    local_time = timestamp_utc.astimezone(IST_ZONE)
    if local_time.hour < day_boundary_hour:
        local_time = local_time - timedelta(days=1)
    return local_time.date()


def business_date_bounds_utc(
    business_date: date, day_boundary_hour: int = 0
) -> tuple[datetime, datetime]:
    """UTC `[start, end)` instants covering `business_date` in IST — the inverse of
    `to_business_date`. Used to bound a query by business date when the underlying row has no
    stored `business_date` column of its own (e.g. `GpsFix`, which is append-only raw evidence)."""

    start_local = datetime(
        business_date.year, business_date.month, business_date.day,
        hour=day_boundary_hour, tzinfo=IST_ZONE,
    )
    start_utc = start_local.astimezone(UTC)
    return start_utc, start_utc + timedelta(days=1)

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from humbee_sfa.core.business_date import to_business_date


@pytest.mark.parametrize(
    ("timestamp_utc", "expected_business_date"),
    [
        (datetime(2026, 8, 22, 18, 29, 59, tzinfo=UTC), date(2026, 8, 22)),
        (datetime(2026, 8, 22, 18, 30, 0, tzinfo=UTC), date(2026, 8, 23)),
        (datetime(2026, 8, 22, 18, 30, 1, tzinfo=UTC), date(2026, 8, 23)),
    ],
)
def test_default_midnight_boundary(timestamp_utc: datetime, expected_business_date: date) -> None:
    assert to_business_date(timestamp_utc) == expected_business_date


@pytest.mark.parametrize(
    ("timestamp_utc", "expected_business_date"),
    [
        (datetime(2026, 8, 21, 23, 29, 59, tzinfo=UTC), date(2026, 8, 21)),
        (datetime(2026, 8, 21, 23, 30, 0, tzinfo=UTC), date(2026, 8, 22)),
    ],
)
def test_custom_day_boundary_hour(timestamp_utc: datetime, expected_business_date: date) -> None:
    assert to_business_date(timestamp_utc, day_boundary_hour=5) == expected_business_date


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        to_business_date(datetime.fromisoformat("2026-08-22T12:00:00"))

"""Pin `core.business_date.to_business_date` at the IST midnight boundary (M10 business-date
convention). A journey test pins one clock value; this checks the instant the date actually
rolls over, which a single frozen-clock journey never reaches.

Pure function, no DB dependency, no fixture needed. IST is UTC+5:30 with no DST, so the boundary
instant for the default (midnight) cutoff is always UTC 18:30:00 on the previous day.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from humbee_sfa.core.business_date import to_business_date


@pytest.mark.parametrize(
    ("timestamp_utc", "expected_business_date"),
    [
        # One second before IST midnight (2026-08-23 00:00:00 IST) still belongs to 2026-08-22.
        (datetime(2026, 8, 22, 18, 29, 59, tzinfo=UTC), date(2026, 8, 22)),
        # The exact boundary instant rolls over to the new business date.
        (datetime(2026, 8, 22, 18, 30, 0, tzinfo=UTC), date(2026, 8, 23)),
        # One second after the boundary stays on the new business date.
        (datetime(2026, 8, 22, 18, 30, 1, tzinfo=UTC), date(2026, 8, 23)),
    ],
)
def test_default_midnight_boundary(timestamp_utc: datetime, expected_business_date: date) -> None:
    assert to_business_date(timestamp_utc) == expected_business_date


@pytest.mark.parametrize(
    ("timestamp_utc", "expected_business_date"),
    [
        # IST 04:59:59 with a 5am cutoff still rolls back to the previous business date.
        (datetime(2026, 8, 21, 23, 29, 59, tzinfo=UTC), date(2026, 8, 21)),
        # IST 05:00:00 exactly meets the configured cutoff hour.
        (datetime(2026, 8, 21, 23, 30, 0, tzinfo=UTC), date(2026, 8, 22)),
    ],
)
def test_custom_day_boundary_hour(timestamp_utc: datetime, expected_business_date: date) -> None:
    assert to_business_date(timestamp_utc, day_boundary_hour=5) == expected_business_date


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        to_business_date(datetime(2026, 8, 22, 12, 0, 0))

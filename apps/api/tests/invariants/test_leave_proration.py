from __future__ import annotations

from decimal import Decimal

import pytest

from humbee_sfa.modules.leave.service import _prorated_entitlement


@pytest.mark.parametrize(
    ("join_month", "privileged", "casual", "sick"),
    [
        (1, 21, 2, 2),
        (7, 11, 1, 1),
        (10, 6, 1, 1),
        (11, 4, 1, 1),
        (12, 2, 1, 1),
    ],
)
def test_join_month_proration_rounds_up(join_month: int, privileged: int, casual: int, sick: int) -> None:
    remaining = 12 - join_month + 1
    assert [
        _prorated_entitlement(annual_days=Decimal(annual), remaining_months_inclusive=remaining)
        for annual in (21, 2, 2)
    ] == [Decimal(privileged), Decimal(casual), Decimal(sick)]


def test_zero_annual_entitlement_stays_zero() -> None:
    assert _prorated_entitlement(annual_days=Decimal(0), remaining_months_inclusive=5) == Decimal(0)

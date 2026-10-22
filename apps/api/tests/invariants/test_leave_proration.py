from __future__ import annotations

from decimal import Decimal

import pytest

from humbee_sfa.modules.leave.service import _prorated_entitlement


@pytest.mark.parametrize(
    ("join_month", "privileged", "casual", "sick"),
    [
        (1, 12, 6, 6),
        (7, 6, 3, 3),
        (10, 3, 2, 2),
        (12, 1, 1, 1),
    ],
)
def test_join_month_proration_rounds_half_up(join_month: int, privileged: int, casual: int, sick: int) -> None:
    remaining = 12 - join_month + 1
    assert [
        _prorated_entitlement(annual_days=Decimal(annual), remaining_months_inclusive=remaining)
        for annual in (12, 6, 6)
    ] == [Decimal(privileged), Decimal(casual), Decimal(sick)]

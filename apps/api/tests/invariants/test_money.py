from __future__ import annotations

from decimal import Decimal

import pytest

from humbee_sfa.modules.orders.service import (
    _apportion,
    _basis_point_amount,
    _line_product_discount_paise,
    _round_half_up,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("2.5", 3), ("2.4999", 2), ("0.5", 1), ("5062.5", 5063), ("-2.5", -3), ("-2.4", -2)],
)
def test_round_half_up_rounds_halves_away_from_zero(value: str, expected: int) -> None:
    assert _round_half_up(Decimal(value)) == expected


@pytest.mark.parametrize(
    ("amount", "rate_bp", "expected"),
    [
        (10_000, 0, 0),
        (10_000, -5, 0),
        (10_000, 1, 1),
        (5_000, 1, 1),
        (4_999, 1, 0),
        (28_125, 1_800, 5_063),
        (49_475, 500, 2_474),
    ],
)
def test_basis_point_amount(amount: int, rate_bp: int, expected: int) -> None:
    assert _basis_point_amount(amount, rate_bp) == expected


@pytest.mark.parametrize(
    ("unit_price", "rate_bp", "qty", "expected"),
    [(None, 500, 3, 0), (10_000, 500, 3, 1_500), (10, 500, 3, 3), (10_000, 0, 2, 0)],
)
def test_line_product_discount_rounds_per_unit_then_multiplies(
    unit_price: int | None, rate_bp: int, qty: int, expected: int
) -> None:
    assert _line_product_discount_paise(unit_price, rate_bp, qty) == expected


@pytest.mark.parametrize(
    ("total", "weights", "expected"),
    [
        (1_000, [30_000, 50_100], [375, 625]),
        (1_000, [30_000, 25_050], [545, 455]),
        (10, [1, 1, 1], [4, 3, 3]),
        (1, [1, 1], [1, 0]),
        (5, [0, 3], [0, 5]),
        (0, [1, 2], [0, 0]),
        (5, [0, 0], [0, 0]),
        (-3, [1, 1], [0, 0]),
    ],
)
def test_apportion_preserves_the_total_by_largest_remainder(
    total: int, weights: list[int], expected: list[int]
) -> None:
    assert _apportion(total, weights) == expected

from decimal import Decimal
from controllers.arbitrage.common import kelly_fraction_edge_variance, position_size_by_kelly

def test_kelly_bounds_and_truncation():
    f = kelly_fraction_edge_variance(Decimal("5"), Decimal("100"), Decimal("0.0"), Decimal("0.2"))
    # 5/100 = 0.05 within caps
    assert f == Decimal("0.05")

    f2 = kelly_fraction_edge_variance(Decimal("-5"), Decimal("100"), Decimal("0.0"), Decimal("0.2"))
    # negative edge -> 0 then clamp to min 0
    assert f2 == Decimal("0")

    f3 = kelly_fraction_edge_variance(Decimal("50"), Decimal("100"), Decimal("0.0"), Decimal("0.2"))
    # 0.5 -> capped at 0.2
    assert f3 == Decimal("0.2")

def test_position_size():
    pos = position_size_by_kelly(Decimal("10000"), Decimal("5"), Decimal("50"), Decimal("0.0"), Decimal("0.2"))
    # f ≈ 5/2500 = 0.002 => size ~ 20
    assert pos == Decimal("20.00000000")
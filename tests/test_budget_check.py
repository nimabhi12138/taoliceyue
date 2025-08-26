from decimal import Decimal
from controllers.arbitrage.common import ExchangeFilters, apply_filters

def test_apply_filters_and_min_notional():
    filters = ExchangeFilters(
        lot_step_size=Decimal("0.001"),
        min_notional=Decimal("10"),
        price_tick_size=Decimal("0.01"),
    )
    amt, px = apply_filters(Decimal("0.12345"), Decimal("80.1234"), filters)
    # truncated price; amount rejected due to min notional
    assert px == Decimal("80.12")
    assert amt == 0  # 0.123 * 80.12 = 9.855 < 10 -> reject to 0

def test_below_min_notional_returns_zero():
    filters = ExchangeFilters(
        lot_step_size=Decimal("0.1"),
        min_notional=Decimal("100"),
        price_tick_size=Decimal("0.01"),
    )
    amt, px = apply_filters(Decimal("0.5"), Decimal("50"), filters)
    assert amt == 0  # 0.5 * 50 = 25 < 100, thus rejected
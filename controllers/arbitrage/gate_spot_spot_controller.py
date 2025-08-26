from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Tuple

from .common import (BaseArbController, ExecutorAction, FeeOverrides, ExchangeFilters,
                     apply_filters)

@dataclass
class SpotSpotSymbols:
    buy_connector: str
    buy_pair: str
    sell_connector: str
    sell_pair: str

class GateSpotSpotController(BaseArbController):
    """
    Cross-market spot arbitrage (intra-exchange or cross-venue via connector abstraction).
    Prefer maker where possible; fallback to taker if edge allows.
    """
    def __init__(self, config: Dict[str, Any], fee_overrides: FeeOverrides):
        super().__init__(config, fee_overrides)
        s = config.get("symbols", {})
        self.syms = SpotSpotSymbols(
            buy_connector=s.get("buy_connector", "gate_io"),
            buy_pair=s.get("buy_pair", "ETH-USDT"),
            sell_connector=s.get("sell_connector", "gate_io"),
            sell_pair=s.get("sell_pair", "ETH-USDT"),
        )
        th = config.get("thresholds", {})
        self.entry_bps = Decimal(str(th.get("entry_bps", 6)))
        self.slippage_bps = Decimal(str(th.get("slippage_buffer_bps", 2)))
        self.safety_bps = Decimal(str(th.get("safety_margin_bps", 1)))

        rm = config.get("risk", {})
        self.per_trade_notional_cap = Decimal(str(rm.get("per_trade_notional_cap", 2000)))
        self.portfolio_notional = Decimal(str(rm.get("portfolio_notional", 20000)))

        f = config.get("filters", {})
        self.filters_buy = ExchangeFilters(
            lot_step_size=Decimal(str(f.get("buy_lot_step_size", "0.001"))),
            min_notional=Decimal(str(f.get("buy_min_notional", "10"))),
            price_tick_size=Decimal(str(f.get("buy_price_tick_size", "0.01"))),
        )
        self.filters_sell = ExchangeFilters(
            lot_step_size=Decimal(str(f.get("sell_lot_step_size", "0.001"))),
            min_notional=Decimal(str(f.get("sell_min_notional", "10"))),
            price_tick_size=Decimal(str(f.get("sell_price_tick_size", "0.01"))),
        )
        self.cooldown_seconds = int(config.get("cooldown_seconds", 3))
        self._cooldown_left = 0

    @classmethod
    def from_yaml(cls, path: str) -> "GateSpotSpotController":
        base = super().from_yaml(path)  # type: ignore
        return base

    def fetch_quotes(self) -> Tuple[Decimal, Decimal]:
        """
        Replace with HB orderbook mid/best quotes. Here placeholders for demo/testing.
        Returns (buy_market_best_ask, sell_market_best_bid)
        """
        best_ask = Decimal(str(self.config.get("debug_buy_best_ask", "3500.0")))
        best_bid = Decimal(str(self.config.get("debug_sell_best_bid", "3510.0")))
        return best_ask, best_bid

    def on_tick(self) -> List[ExecutorAction]:
        if self._cooldown_left > 0:
            self._cooldown_left -= 1
            return []
        actions: List[ExecutorAction] = []

        ask_buy, bid_sell = self.fetch_quotes()
        spread_bps = (bid_sell - ask_buy) / ask_buy * Decimal("10000")

        taker_buy = self.fee_overrides.eff_taker_bps(self.syms.buy_connector, "spot")
        taker_sell = self.fee_overrides.eff_taker_bps(self.syms.sell_connector, "spot")
        total_fees = taker_buy + taker_sell
        total_overheads = total_fees + self.slippage_bps + self.safety_bps

        if spread_bps > self.entry_bps + total_overheads:
            notional = min(self.portfolio_notional * Decimal("0.2"), self.per_trade_notional_cap)
            qty = (notional / ask_buy).quantize(Decimal("0.00000001"))
            qty_buy, px_buy = apply_filters(qty, ask_buy, self.filters_buy)
            qty_sell, px_sell = apply_filters(qty, bid_sell, self.filters_sell)
            if qty_buy > 0 and qty_sell > 0:
                actions.append(ExecutorAction(
                    connector_name=self.syms.buy_connector,
                    trading_pair=self.syms.buy_pair,
                    side="BUY",
                    order_type="LIMIT",
                    amount=qty_buy,
                    price=px_buy,
                    time_in_force="IOC",
                    post_only=False,
                    tag="spot_spot_buy_leg",
                ))
                actions.append(ExecutorAction(
                    connector_name=self.syms.sell_connector,
                    trading_pair=self.syms.sell_pair,
                    side="SELL",
                    order_type="LIMIT",
                    amount=qty_sell,
                    price=px_sell,
                    time_in_force="IOC",
                    post_only=False,
                    tag="spot_spot_sell_leg",
                ))
                self.last_status = f"Spot-spot arb triggered: spread {spread_bps} bps"
                self._cooldown_left = self.cooldown_seconds

        return actions
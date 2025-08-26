from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Tuple

from .common import (BaseArbController, ExecutorAction, FeeOverrides, ExchangeFilters,
                     apply_filters, bps_to_ratio)

@dataclass
class SpotPerpSymbols:
    spot_connector: str
    spot_pair: str
    perp_connector: str
    perp_pair: str
    leverage: int

class GateSpotPerpController(BaseArbController):
    """
    Cash-and-carry on Gate: exploit basis between spot and perpetual.
    Emits hedge actions for official executors. No raw orders are placed here.
    """
    def __init__(self, config: Dict[str, Any], fee_overrides: FeeOverrides):
        super().__init__(config, fee_overrides)
        s = config.get("symbols", {})
        self.syms = SpotPerpSymbols(
            spot_connector=s.get("spot_connector", "gate_io"),
            spot_pair=s.get("spot_pair", "BTC-USDT"),
            perp_connector=s.get("perp_connector", "gate_io_perpetual"),
            perp_pair=s.get("perp_pair", "BTC-USDT"),
            leverage=int(s.get("leverage", 5)),
        )
        th = config.get("thresholds", {})
        self.entry_bps = Decimal(str(th.get("basis_entry_bps", 10)))
        self.exit_bps = Decimal(str(th.get("basis_exit_bps", 2)))
        self.slippage_bps = Decimal(str(th.get("slippage_buffer_bps", 2)))
        self.safety_bps = Decimal(str(th.get("safety_margin_bps", 1)))

        rm = config.get("risk", {})
        self.kelly_min = Decimal(str(rm.get("kelly_min", 0)))
        self.kelly_max = Decimal(str(rm.get("kelly_max", 0.15)))
        self.per_trade_notional_cap = Decimal(str(rm.get("per_trade_notional_cap", 1000)))
        self.portfolio_notional = Decimal(str(rm.get("portfolio_notional", 10000)))
        self.volatility_bps = Decimal(str(rm.get("volatility_bps", 50)))

        self.filters_spot = ExchangeFilters(
            lot_step_size=Decimal(str(config.get("filters", {}).get("spot_lot_step_size", "0.0001"))),
            min_notional=Decimal(str(config.get("filters", {}).get("spot_min_notional", "10"))),
            price_tick_size=Decimal(str(config.get("filters", {}).get("spot_price_tick_size", "0.01"))),
        )
        self.filters_perp = ExchangeFilters(
            lot_step_size=Decimal(str(config.get("filters", {}).get("perp_lot_step_size", "0.001"))),
            min_notional=Decimal(str(config.get("filters", {}).get("perp_min_notional", "10"))),
            price_tick_size=Decimal(str(config.get("filters", {}).get("perp_price_tick_size", "0.1"))),
        )

        self.cooldown_seconds = int(config.get("cooldown_seconds", 5))
        self._cooldown_left = 0

    @classmethod
    def from_yaml(cls, path: str) -> "GateSpotPerpController":
        base = super().from_yaml(path)  # type: ignore
        return base  # already constructed with FeeOverrides

    def fetch_spot_perp_prices(self) -> Tuple[Decimal, Decimal]:
        """
        In production, use Hummingbot data providers (mid/mark prices).
        Here we place placeholders that must be replaced by HB 2.x runtime.
        """
        # Replace with HB-provided market data in live runs
        spot_price = Decimal(str(self.config.get("debug_spot_price", "68000")))
        perp_mark = Decimal(str(self.config.get("debug_perp_mark", "68100")))
        return spot_price, perp_mark

    def compute_basis_bps(self, spot_price: Decimal, perp_mark: Decimal) -> Decimal:
        basis = (perp_mark - spot_price) / spot_price
        return (basis * Decimal("10000")).quantize(Decimal("0.0001"))

    def on_tick(self) -> List[ExecutorAction]:
        if self._cooldown_left > 0:
            self._cooldown_left -= 1
            return []

        actions: List[ExecutorAction] = []
        spot_price, perp_mark = self.fetch_spot_perp_prices()
        basis_bps = self.compute_basis_bps(spot_price, perp_mark)

        maker_spot = self.fee_overrides.eff_maker_bps(self.syms.spot_connector, "spot")
        taker_spot = self.fee_overrides.eff_taker_bps(self.syms.spot_connector, "spot")
        maker_perp = self.fee_overrides.eff_maker_bps(self.syms.perp_connector, "perpetual")
        taker_perp = self.fee_overrides.eff_taker_bps(self.syms.perp_connector, "perpetual")

        # Assume taker on entry (conservative), maker on exit (optional)
        entry_fee_sum = taker_spot + taker_perp
        exit_fee_sum = maker_spot + maker_perp
        total_overheads_bps = entry_fee_sum + self.slippage_bps + self.safety_bps

        if basis_bps > (self.entry_bps + total_overheads_bps):
            # Enter cash-and-carry: Buy spot, Short perp
            notional = min(self.portfolio_notional * Decimal("0.5"), self.per_trade_notional_cap)
            qty_spot = (notional / spot_price).quantize(Decimal("0.00000001"))
            qty_perp = qty_spot  # delta-neutral

            qty_spot, px_spot = apply_filters(qty_spot, spot_price, self.filters_spot)
            qty_perp, px_perp = apply_filters(qty_perp, perp_mark, self.filters_perp)
            if qty_spot > 0 and qty_perp > 0:
                actions.append(ExecutorAction(
                    connector_name=self.syms.spot_connector,
                    trading_pair=self.syms.spot_pair,
                    side="BUY",
                    order_type="LIMIT",
                    amount=qty_spot,
                    price=px_spot,
                    time_in_force="IOC",
                    post_only=False,
                    tag="spot_perp_entry_spot_long",
                ))
                actions.append(ExecutorAction(
                    connector_name=self.syms.perp_connector,
                    trading_pair=self.syms.perp_pair,
                    side="SELL",
                    order_type="LIMIT",
                    amount=qty_perp,
                    price=px_perp,
                    time_in_force="IOC",
                    reduce_only=False,
                    post_only=False,
                    tag="spot_perp_entry_perp_short",
                ))
                self.last_status = f"Enter basis: {basis_bps} bps"
                self._cooldown_left = self.cooldown_seconds

        elif basis_bps < self.exit_bps:
            # Exit condition example: flatten positions (BUY perp to close, SELL spot)
            # Real implementation would query current position sizes from HB.
            est_qty = Decimal(str(self.config.get("debug_est_position_qty", "0.001")))
            if est_qty > 0:
                qty_spot, px_spot = apply_filters(est_qty, spot_price, self.filters_spot)
                qty_perp, px_perp = apply_filters(est_qty, perp_mark, self.filters_perp)
                if qty_spot > 0 and qty_perp > 0:
                    actions.append(ExecutorAction(
                        connector_name=self.syms.perp_connector,
                        trading_pair=self.syms.perp_pair,
                        side="BUY",
                        order_type="LIMIT",
                        amount=qty_perp,
                        price=px_perp,
                        time_in_force="IOC",
                        reduce_only=True,
                        tag="spot_perp_exit_perp_cover",
                    ))
                    actions.append(ExecutorAction(
                        connector_name=self.syms.spot_connector,
                        trading_pair=self.syms.spot_pair,
                        side="SELL",
                        order_type="LIMIT",
                        amount=qty_spot,
                        price=px_spot,
                        time_in_force="IOC",
                        post_only=False,
                        tag="spot_perp_exit_spot_sell",
                    ))
                    self.last_status = f"Exit basis: {basis_bps} bps"
                    self._cooldown_left = self.cooldown_seconds

        return actions
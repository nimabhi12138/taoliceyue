from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List

from .common import (BaseArbController, ExecutorAction, FeeOverrides, ExchangeFilters,
                     apply_filters)

@dataclass
class PairSymbols:
    connector: str
    pair_x: str
    pair_y: str

class GateStatArbController(BaseArbController):
    """
    Simple statistical pairs controller:
    - Monitor spread Z-score between two coin pairs (co-integration assumed)
    - Enter mean-reversion positions when |Z| > entry_z, exit when |Z| < exit_z
    Notes: In real deployment, use HB data providers for price history and cointegration tests.
    """
    def __init__(self, config: Dict[str, Any], fee_overrides: FeeOverrides):
        super().__init__(config, fee_overrides)
        s = config.get("symbols", {})
        self.syms = PairSymbols(
            connector=s.get("connector", "gate_io"),
            pair_x=s.get("pair_x", "ETH-USDT"),
            pair_y=s.get("pair_y", "BTC-USDT"),
        )
        th = config.get("thresholds", {})
        self.entry_z = Decimal(str(th.get("entry_z", 2.0)))
        self.exit_z = Decimal(str(th.get("exit_z", 0.5)))
        self.slippage_bps = Decimal(str(th.get("slippage_buffer_bps", 3)))
        self.safety_bps = Decimal(str(th.get("safety_margin_bps", 2)))

        rm = config.get("risk", {})
        self.per_trade_notional_cap = Decimal(str(rm.get("per_trade_notional_cap", 1000)))
        self.portfolio_notional = Decimal(str(rm.get("portfolio_notional", 10000)))

        f = config.get("filters", {})
        self.filters = ExchangeFilters(
            lot_step_size=Decimal(str(f.get("lot_step_size", "0.001"))),
            min_notional=Decimal(str(f.get("min_notional", "10"))),
            price_tick_size=Decimal(str(f.get("price_tick_size", "0.01"))),
        )
        self.cooldown_seconds = int(config.get("cooldown_seconds", 3))
        self._cooldown_left = 0

    @classmethod
    def from_yaml(cls, path: str) -> "GateStatArbController":
        base = super().from_yaml(path)  # type: ignore
        return base

    def fetch_last_zscore(self) -> Decimal:
        """
        Replace with HB timeseries of spread; compute Z via rolling window.
        Here: placeholder value.
        """
        return Decimal(str(self.config.get("debug_zscore", "0.0")))

    def on_tick(self) -> List[ExecutorAction]:
        if self._cooldown_left > 0:
            self._cooldown_left -= 1
            return []
        actions: List[ExecutorAction] = []

        z = self.fetch_last_zscore()
        taker = self.fee_overrides.eff_taker_bps(self.syms.connector, "spot")
        overheads = taker * Decimal("2") + self.slippage_bps + self.safety_bps

        if abs(z) > self.entry_z:
            # Enter mean-reversion: if z > 0, short X, long Y; else long X, short Y
            notional = min(self.portfolio_notional * Decimal("0.1"), self.per_trade_notional_cap)
            # demo prices:
            px_x = Decimal(str(self.config.get("debug_px_x", "3500")))
            px_y = Decimal(str(self.config.get("debug_px_y", "68000")))
            qty_x = (notional / px_x).quantize(Decimal("0.00000001"))
            qty_y = (notional / px_y).quantize(Decimal("0.00000001"))
            qty_x, px_x = apply_filters(qty_x, px_x, self.filters)
            qty_y, px_y = apply_filters(qty_y, px_y, self.filters)
            if qty_x > 0 and qty_y > 0:
                if z > 0:
                    actions.append(ExecutorAction(self.syms.connector, self.syms.pair_x, "SELL", "LIMIT", qty_x, px_x, "IOC", False, False, "stat_arb_enter_short_x"))
                    actions.append(ExecutorAction(self.syms.connector, self.syms.pair_y, "BUY", "LIMIT", qty_y, px_y, "IOC", False, False, "stat_arb_enter_long_y"))
                else:
                    actions.append(ExecutorAction(self.syms.connector, self.syms.pair_x, "BUY", "LIMIT", qty_x, px_x, "IOC", False, False, "stat_arb_enter_long_x"))
                    actions.append(ExecutorAction(self.syms.connector, self.syms.pair_y, "SELL", "LIMIT", qty_y, px_y, "IOC", False, False, "stat_arb_enter_short_y"))
                self.last_status = f"Stat-arb enter: z={z}"
                self._cooldown_left = self.cooldown_seconds

        elif abs(z) < self.exit_z:
            # Exit positions — demonstration. Real positions must be queried from HB.
            self.last_status = f"Stat-arb near exit: z={z}"

        return actions
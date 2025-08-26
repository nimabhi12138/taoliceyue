from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Tuple

from .common import (BaseArbController, ExecutorAction, FeeOverrides, ExchangeFilters,
                     apply_filters, triangular_cycle_edge_bps)

@dataclass
class TriSymbols:
    a_b_pair: str  # A/B
    b_c_pair: str  # B/C
    c_a_pair: str  # C/A
    connector: str # assume same connector for simplicity

class GateTriangularController(BaseArbController):
    def __init__(self, config: Dict[str, Any], fee_overrides: FeeOverrides):
        super().__init__(config, fee_overrides)
        s = config.get("symbols", {})
        self.syms = TriSymbols(
            a_b_pair=s.get("a_b_pair", "ETH-BTC"),
            b_c_pair=s.get("b_c_pair", "BTC-USDT"),
            c_a_pair=s.get("c_a_pair", "USDT-ETH"),
            connector=s.get("connector", "gate_io"),
        )
        th = config.get("thresholds", {})
        self.entry_bps = Decimal(str(th.get("entry_bps", 8)))
        self.slippage_bps = Decimal(str(th.get("slippage_buffer_bps", 3)))
        self.safety_bps = Decimal(str(th.get("safety_margin_bps", 2)))

        rm = config.get("risk", {})
        self.per_trade_notional_cap = Decimal(str(rm.get("per_trade_notional_cap", 1500)))
        self.portfolio_notional = Decimal(str(rm.get("portfolio_notional", 15000)))

        f = config.get("filters", {})
        self.filters = ExchangeFilters(
            lot_step_size=Decimal(str(f.get("lot_step_size", "0.0001"))),
            min_notional=Decimal(str(f.get("min_notional", "10"))),
            price_tick_size=Decimal(str(f.get("price_tick_size", "0.0001"))),
        )
        self.cooldown_seconds = int(config.get("cooldown_seconds", 2))
        self._cooldown_left = 0

    @classmethod
    def from_yaml(cls, path: str) -> "GateTriangularController":
        base = super().from_yaml(path)  # type: ignore
        return base

    def fetch_conversion_prices(self) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Return multiplicative conversions: A->B, B->C, C->A.
        In real use, compute from best quotes per leg considering taker/maker.
        """
        a_to_b = Decimal(str(self.config.get("debug_a_to_b", "0.06")))   # e.g., ETH->BTC
        b_to_c = Decimal(str(self.config.get("debug_b_to_c", "68000"))) # BTC->USDT
        c_to_a = Decimal(str(self.config.get("debug_c_to_a", "0.0002857"))) # USDT->ETH
        return a_to_b, b_to_c, c_to_a

    def on_tick(self) -> List[ExecutorAction]:
        if self._cooldown_left > 0:
            self._cooldown_left -= 1
            return []

        a_to_b, b_to_c, c_to_a = self.fetch_conversion_prices()
        maker = self.fee_overrides.eff_maker_bps(self.syms.connector, "spot")
        taker = self.fee_overrides.eff_taker_bps(self.syms.connector, "spot")
        # Assume worst-case taker on all legs; can optimize to mix maker/taker where post-only possible
        fees = [taker, taker, taker]
        edge_bps = triangular_cycle_edge_bps(a_to_b, b_to_c, c_to_a, fees, self.slippage_bps, self.safety_bps)
        actions: List[ExecutorAction] = []

        if edge_bps > self.entry_bps:
            # Execute cycle. We choose a notional in currency A terms via portfolio notionals.
            notional = min(self.portfolio_notional * Decimal("0.15"), self.per_trade_notional_cap)
            # For demo, assume first leg prices can convert notional to amount:
            # amount_a = notional in A terms (requires an A price in stable; here we just scale simplistically)
            amount_a = (notional / Decimal("1000")).quantize(Decimal("0.00000001"))
            amt_a, _ = apply_filters(amount_a, Decimal("1"), self.filters)
            if amt_a > 0:
                actions.append(ExecutorAction(
                    connector_name=self.syms.connector,
                    trading_pair=self.syms.a_b_pair,
                    side="SELL",  # A->B
                    order_type="MARKET",
                    amount=amt_a,
                    tag="tri_leg1_a_to_b",
                ))
                actions.append(ExecutorAction(
                    connector_name=self.syms.connector,
                    trading_pair=self.syms.b_c_pair,
                    side="SELL",  # B->C
                    order_type="MARKET",
                    amount=amt_a,  # simplified
                    tag="tri_leg2_b_to_c",
                ))
                actions.append(ExecutorAction(
                    connector_name=self.syms.connector,
                    trading_pair=self.syms.c_a_pair,
                    side="SELL",  # C->A
                    order_type="MARKET",
                    amount=amt_a,  # simplified
                    tag="tri_leg3_c_to_a",
                ))
                self.last_status = f"Triangular edge: {edge_bps} bps"
                self._cooldown_left = self.cooldown_seconds

        return actions
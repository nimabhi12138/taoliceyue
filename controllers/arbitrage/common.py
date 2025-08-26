from __future__ import annotations

import json
import math
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, getcontext
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# Ensure high precision for financial calcs
getcontext().prec = 40

# ---------- Shims for Hummingbot types (used if HB not importable) ----------
try:
    from hummingbot.core.controller_base import ControllerBase  # type: ignore
except Exception:
    class ControllerBase:
        def initialize(self) -> None:
            pass
        def on_tick(self) -> List[Any]:
            return []
        def shutdown(self) -> None:
            pass
        def format_status(self) -> str:
            return "OK"

try:
    from hummingbot.core.executor_action import ExecutorAction  # type: ignore
except Exception:
    @dataclass
    class ExecutorAction:
        connector_name: str
        trading_pair: str
        side: str  # "BUY" or "SELL"
        order_type: str  # "LIMIT", "MARKET"
        amount: Decimal
        price: Optional[Decimal] = None
        time_in_force: Optional[str] = None  # "GTC","IOC","FOK"
        post_only: bool = False
        reduce_only: bool = False
        tag: str = "arb"

# ---------- Fee Model and Overrides ----------

@dataclass
class ConnectorFee:
    maker_bps: Decimal
    taker_bps: Decimal
    # If provided, these are already post-rebate (raw * (1 - rebate_ratio))
    maker_bps_post_rebate: Optional[Decimal] = None
    taker_bps_post_rebate: Optional[Decimal] = None

@dataclass
class FeeOverrides:
    connectors: Dict[str, Dict[str, ConnectorFee]]
    rebate_ratio: Decimal

    @staticmethod
    def from_yaml(path: str | Path) -> "FeeOverrides":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        rebate_ratio = Decimal(str(data.get("rebate_ratio", "0.75")))
        connectors: Dict[str, Dict[str, ConnectorFee]] = {}
        for conn, types in (data.get("connectors") or {}).items():
            connectors[conn] = {}
            for market_type, cfg in (types or {}).items():
                def dget(k: str) -> Optional[Decimal]:
                    v = cfg.get(k)
                    return None if v is None else Decimal(str(v))
                connectors[conn][market_type] = ConnectorFee(
                    maker_bps=dget("maker_bps") or Decimal("0"),
                    taker_bps=dget("taker_bps") or Decimal("0"),
                    maker_bps_post_rebate=dget("maker_bps_post_rebate"),
                    taker_bps_post_rebate=dget("taker_bps_post_rebate"),
                )
        return FeeOverrides(connectors=connectors, rebate_ratio=rebate_ratio)

    def eff_maker_bps(self, connector: str, market_type: str) -> Decimal:
        cfg = self.connectors.get(connector, {}).get(market_type)
        if cfg is None:
            return Decimal("0")
        if cfg.maker_bps_post_rebate is not None:
            return cfg.maker_bps_post_rebate
        return (cfg.maker_bps * (Decimal("1") - self.rebate_ratio)).quantize(Decimal("0.0001"))

    def eff_taker_bps(self, connector: str, market_type: str) -> Decimal:
        cfg = self.connectors.get(connector, {}).get(market_type)
        if cfg is None:
            return Decimal("0")
        if cfg.taker_bps_post_rebate is not None:
            return cfg.taker_bps_post_rebate
        return (cfg.taker_bps * (Decimal("1") - self.rebate_ratio)).quantize(Decimal("0.0001"))

# ---------- Numeric Helpers ----------

def bps_to_ratio(bps: Decimal | float | str) -> Decimal:
    b = Decimal(str(bps))
    return b / Decimal("10000")

def ratio_to_bps(r: Decimal | float | str) -> Decimal:
    rr = Decimal(str(r))
    return rr * Decimal("10000")

def clamp(value: Decimal, lo: Decimal, hi: Decimal) -> Decimal:
    return max(lo, min(hi, value))  # type: ignore[arg-type]

def decimal_truncate(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        return value
    return (value // step) * step

# ---------- Risk Sizing (Truncated Kelly) ----------

def kelly_fraction_edge_variance(edge_bps: Decimal, variance_bps2: Decimal,
                                 cap_min: Decimal, cap_max: Decimal) -> Decimal:
    """
    Approx Kelly with edge and variance (both in bps units).
    f* ≈ edge/variance. Truncated to [cap_min, cap_max], min at 0 if edge <= 0.
    """
    if variance_bps2 <= 0:
        return Decimal("0")
    f = Decimal(edge_bps) / Decimal(variance_bps2)
    f = clamp(f, Decimal("0"), Decimal("1"))
    return clamp(f, cap_min, cap_max)

def position_size_by_kelly(portfolio_notional: Decimal,
                           edge_bps: Decimal,
                           volatility_bps: Decimal,
                           cap_min: Decimal,
                           cap_max: Decimal) -> Decimal:
    """
    volatility_bps: proxy of std-dev in bps for trade horizon.
    """
    variance_bps2 = volatility_bps * volatility_bps
    f = kelly_fraction_edge_variance(edge_bps, variance_bps2, cap_min, cap_max)
    return (portfolio_notional * f).quantize(Decimal("0.00000001"))

# ---------- Budget & Filters ----------

@dataclass
class ExchangeFilters:
    lot_step_size: Decimal
    min_notional: Decimal
    price_tick_size: Decimal

def apply_filters(amount: Decimal,
                  price: Decimal,
                  filters: ExchangeFilters) -> Tuple[Decimal, Decimal]:
    """
    Truncate amount to lot_step_size and price to price_tick_size, ensuring min_notional.
    Returns (amount, price). If notional < min_notional after truncation, returns (0, price).
    """
    price_adj = decimal_truncate(price, filters.price_tick_size)
    amt_adj = decimal_truncate(amount, filters.lot_step_size)
    notional = (amt_adj * price_adj).quantize(Decimal("0.00000001"))
    if notional < filters.min_notional:
        return Decimal("0"), price_adj
    return amt_adj, price_adj

# ---------- Triangular Arbitrage Math ----------

def triangular_cycle_edge_bps(a_to_b: Decimal,
                              b_to_c: Decimal,
                              c_to_a: Decimal,
                              fees_bps: List[Decimal],
                              slippage_bps: Decimal,
                              safety_bps: Decimal) -> Decimal:
    """
    Prices are multiplicative conversions A->B, B->C, C->A for a consistent direction.
    Gross cycle return R = a_to_b * b_to_c * c_to_a
    Edge_bps = (R - 1) * 10000 - sum(fees) - slippage_bps - safety_bps
    """
    gross = a_to_b * b_to_c * c_to_a
    gross_bps = (gross - Decimal("1")) * Decimal("10000")
    total_fee_bps = sum(fees_bps)
    net_bps = gross_bps - Decimal(total_fee_bps) - slippage_bps - safety_bps
    return net_bps.quantize(Decimal("0.0001"))

# ---------- Logging/Status ----------

def json_log(event: str, payload: Dict[str, Any]) -> str:
    return json.dumps({"event": event, **payload, "ts": float(0)})

# ---------- Base Controller ----------

class BaseArbController(ControllerBase):
    def __init__(self, config: Dict[str, Any], fee_overrides: FeeOverrides):
        super().__init__()
        self.config = config
        self.fee_overrides = fee_overrides
        self.last_status: str = "initialized"
        self.session_realized_pnl: Decimal = Decimal("0")
        self.session_unrealized_pnl: Decimal = Decimal("0")
        self.error_counter: int = 0

    @classmethod
    def from_yaml(cls, path: str | Path) -> "BaseArbController":
        with open(path, "r", encoding="utf-8") as f:
            conf = yaml.safe_load(f) or {}
        fee_path = conf.get("global_fee_overrides_path", "conf/examples/conf_fee_overrides.yml")
        fee_overrides = FeeOverrides.from_yaml(fee_path)
        return cls(conf, fee_overrides)

    def initialize(self) -> None:
        self.last_status = "ready"

    def on_tick(self) -> List[ExecutorAction]:
        # Derived classes should implement
        return []

    def shutdown(self) -> None:
        self.last_status = "stopped"

    def format_status(self) -> str:
        return (f"status={self.last_status} realized={self.session_realized_pnl} "
                f"unrealized={self.session_unrealized_pnl}")
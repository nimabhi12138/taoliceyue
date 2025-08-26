#!/usr/bin/env python3
"""
Fee Model for Gate.io Arbitrage
Handles fee calculations with rebate support
"""

import logging
import yaml
from decimal import Decimal
from pathlib import Path
from typing import Dict, Optional, Tuple

from hummingbot.core.data_type.common import TradeType


class FeeModel:
    """
    Fee model that calculates effective fees after rebates
    Supports Gate.io 75% trading fee rebate
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.fee_overrides = {}
        self.default_fees = {
            "gate_io": {
                "maker": Decimal("0.002"),  # 0.2%
                "taker": Decimal("0.002")   # 0.2%
            },
            "gate_io_perpetual": {
                "maker": Decimal("0.0002"), # 0.02%
                "taker": Decimal("0.0006")  # 0.06%
            }
        }
        self.default_rebate_ratio = Decimal("0.75")  # 75% rebate
        
        if config_path:
            self.load_fee_overrides(config_path)
            
    def load_fee_overrides(self, config_path: str):
        """Load fee overrides from YAML configuration"""
        try:
            path = Path(config_path)
            if path.exists():
                with open(path, 'r') as f:
                    config = yaml.safe_load(f)
                    self.fee_overrides = config.get('fee_overrides', {})
                    self.logger.info(f"Loaded fee overrides from {config_path}")
            else:
                self.logger.warning(f"Fee override file not found: {config_path}")
        except Exception as e:
            self.logger.error(f"Error loading fee overrides: {e}")
            
    def get_effective_fee_rate(
        self, 
        connector: str, 
        trade_type: TradeType,
        rebate_ratio: Optional[Decimal] = None
    ) -> Decimal:
        """
        Calculate effective fee rate after rebate
        
        Args:
            connector: Exchange connector name (gate_io, gate_io_perpetual)
            trade_type: MAKER or TAKER
            rebate_ratio: Override rebate ratio (default 75%)
            
        Returns:
            Effective fee rate as decimal (e.g., 0.0005 for 0.05%)
        """
        if rebate_ratio is None:
            rebate_ratio = self.default_rebate_ratio
            
        # Get base fee rate
        trade_type_str = "maker" if trade_type == TradeType.BUY else "taker"
        
        # Check overrides first
        if connector in self.fee_overrides:
            connector_fees = self.fee_overrides[connector]
            if trade_type_str in connector_fees:
                base_fee = Decimal(str(connector_fees[trade_type_str]))
            else:
                base_fee = self.default_fees.get(connector, {}).get(trade_type_str, Decimal("0.002"))
        else:
            base_fee = self.default_fees.get(connector, {}).get(trade_type_str, Decimal("0.002"))
            
        # Apply rebate
        effective_fee = base_fee * (Decimal("1") - rebate_ratio)
        
        self.logger.debug(
            f"Fee calculation - Connector: {connector}, Type: {trade_type_str}, "
            f"Base: {base_fee:.4f}, Rebate: {rebate_ratio:.2f}, Effective: {effective_fee:.6f}"
        )
        
        return effective_fee
        
    def calculate_trading_cost(
        self,
        connector: str,
        trade_type: TradeType,
        amount: Decimal,
        price: Decimal,
        rebate_ratio: Optional[Decimal] = None
    ) -> Decimal:
        """
        Calculate total trading cost including fees
        
        Args:
            connector: Exchange connector name
            trade_type: MAKER or TAKER
            amount: Trade amount in base currency
            price: Trade price
            rebate_ratio: Override rebate ratio
            
        Returns:
            Total fee cost in quote currency
        """
        effective_rate = self.get_effective_fee_rate(connector, trade_type, rebate_ratio)
        notional = amount * price
        return notional * effective_rate
        
    def calculate_net_profit(
        self,
        buy_connector: str,
        sell_connector: str,
        buy_trade_type: TradeType,
        sell_trade_type: TradeType,
        amount: Decimal,
        buy_price: Decimal,
        sell_price: Decimal,
        funding_cost: Decimal = Decimal("0"),
        rebate_ratio: Optional[Decimal] = None
    ) -> Tuple[Decimal, Dict[str, Decimal]]:
        """
        Calculate net profit after all costs
        
        Args:
            buy_connector: Connector for buy side
            sell_connector: Connector for sell side
            buy_trade_type: MAKER or TAKER for buy
            sell_trade_type: MAKER or TAKER for sell
            amount: Trade amount
            buy_price: Buy price
            sell_price: Sell price
            funding_cost: Additional funding cost (for perps)
            rebate_ratio: Override rebate ratio
            
        Returns:
            Tuple of (net_profit, cost_breakdown)
        """
        # Calculate gross profit
        gross_profit = (sell_price - buy_price) * amount
        
        # Calculate fees
        buy_fee = self.calculate_trading_cost(
            buy_connector, buy_trade_type, amount, buy_price, rebate_ratio
        )
        sell_fee = self.calculate_trading_cost(
            sell_connector, sell_trade_type, amount, sell_price, rebate_ratio
        )
        
        total_fees = buy_fee + sell_fee
        net_profit = gross_profit - total_fees - funding_cost
        
        cost_breakdown = {
            "gross_profit": gross_profit,
            "buy_fee": buy_fee,
            "sell_fee": sell_fee,
            "total_fees": total_fees,
            "funding_cost": funding_cost,
            "net_profit": net_profit
        }
        
        return net_profit, cost_breakdown
        
    def is_profitable(
        self,
        buy_connector: str,
        sell_connector: str,
        buy_trade_type: TradeType,
        sell_trade_type: TradeType,
        amount: Decimal,
        buy_price: Decimal,
        sell_price: Decimal,
        min_profit_bps: Decimal = Decimal("5"),  # 0.05% minimum
        funding_cost: Decimal = Decimal("0"),
        slippage_buffer_bps: Decimal = Decimal("2"),  # 0.02% slippage buffer
        rebate_ratio: Optional[Decimal] = None
    ) -> Tuple[bool, Dict[str, Decimal]]:
        """
        Check if trade is profitable after all costs
        
        Args:
            buy_connector: Connector for buy side
            sell_connector: Connector for sell side
            buy_trade_type: MAKER or TAKER for buy
            sell_trade_type: MAKER or TAKER for sell
            amount: Trade amount
            buy_price: Buy price
            sell_price: Sell price
            min_profit_bps: Minimum profit in basis points
            funding_cost: Additional funding cost
            slippage_buffer_bps: Slippage buffer in basis points
            rebate_ratio: Override rebate ratio
            
        Returns:
            Tuple of (is_profitable, analysis)
        """
        net_profit, cost_breakdown = self.calculate_net_profit(
            buy_connector, sell_connector, buy_trade_type, sell_trade_type,
            amount, buy_price, sell_price, funding_cost, rebate_ratio
        )
        
        # Calculate profit in basis points
        notional = amount * buy_price
        profit_bps = (net_profit / notional) * Decimal("10000") if notional > 0 else Decimal("0")
        
        # Account for slippage buffer
        effective_profit_bps = profit_bps - slippage_buffer_bps
        
        is_profitable = effective_profit_bps >= min_profit_bps
        
        analysis = {
            **cost_breakdown,
            "profit_bps": profit_bps,
            "slippage_buffer_bps": slippage_buffer_bps,
            "effective_profit_bps": effective_profit_bps,
            "min_profit_bps": min_profit_bps,
            "is_profitable": is_profitable
        }
        
        return is_profitable, analysis
        
    def get_fee_summary(self) -> Dict[str, Dict[str, Decimal]]:
        """Get summary of current fee configuration"""
        summary = {}
        
        for connector in ["gate_io", "gate_io_perpetual"]:
            summary[connector] = {}
            for trade_type in [TradeType.BUY, TradeType.SELL]:  # MAKER, TAKER
                effective_rate = self.get_effective_fee_rate(connector, trade_type)
                trade_type_str = "maker" if trade_type == TradeType.BUY else "taker"
                summary[connector][trade_type_str] = effective_rate
                
        return summary
#!/usr/bin/env python3
"""
Gate.io Arbitrage Example Script for Hummingbot
Compatible with Hummingbot 2.x framework

This script demonstrates how to use the Gate.io arbitrage controllers
in a standard Hummingbot script strategy format.
"""

from decimal import Decimal
from typing import Dict
import logging

from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import TradeType


class GateArbExample(ScriptStrategyBase):
    """
    Example Gate.io arbitrage script using the arbitrage controllers
    """
    
    # Required: Define markets that this script will use
    markets = {
        "gate_io": ["BTC-USDT", "ETH-USDT"],
        "gate_io_perpetual": ["BTC-USDT", "ETH-USDT"]
    }
    
    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        
        # Configuration
        self.min_profitability = Decimal("0.0008")  # 0.08% minimum profit
        self.max_position_size = Decimal("0.1")
        self.check_interval = 5.0  # Check every 5 seconds
        
        # Initialize logging
        self.logger = logging.getLogger(type(self).__name__)
        
        # State tracking
        self.last_check_time = 0
        self.active_arbitrages = {}
        
        self.logger.info("Gate.io Arbitrage Example Script initialized")
    
    def on_tick(self):
        """
        Main strategy logic - called every tick
        """
        if not self.ready_to_trade:
            return
            
        current_time = self.current_timestamp
        
        # Check for arbitrage opportunities every check_interval seconds
        if current_time - self.last_check_time < self.check_interval:
            return
            
        self.last_check_time = current_time
        
        # Simple spot-perp arbitrage check
        self.check_spot_perp_arbitrage()
    
    def check_spot_perp_arbitrage(self):
        """
        Check for spot-perpetual arbitrage opportunities
        """
        spot_connector = self.connectors.get("gate_io")
        perp_connector = self.connectors.get("gate_io_perpetual")
        
        if not spot_connector or not perp_connector:
            return
            
        for trading_pair in ["BTC-USDT", "ETH-USDT"]:
            try:
                # Get order books
                spot_book = spot_connector.get_order_book(trading_pair)
                perp_book = perp_connector.get_order_book(trading_pair)
                
                if not spot_book or not perp_book:
                    continue
                    
                # Simple profitability check
                spot_mid = (spot_book.best_bid_price + spot_book.best_ask_price) / 2
                perp_mid = (perp_book.best_bid_price + perp_book.best_ask_price) / 2
                
                # Calculate potential profit
                if spot_mid > 0 and perp_mid > 0:
                    price_diff = abs(spot_mid - perp_mid) / min(spot_mid, perp_mid)
                    
                    if price_diff > self.min_profitability:
                        self.logger.info(
                            f"Arbitrage opportunity found for {trading_pair}: "
                            f"Spot: {spot_mid:.2f}, Perp: {perp_mid:.2f}, "
                            f"Diff: {price_diff:.4%}"
                        )
                        
                        # In a real implementation, you would:
                        # 1. Check available balances
                        # 2. Calculate optimal position size
                        # 3. Execute trades using the arbitrage controllers
                        # 4. Monitor and manage positions
                        
            except Exception as e:
                self.logger.error(f"Error checking arbitrage for {trading_pair}: {e}")
    
    def did_fill_order(self, event):
        """
        Called when an order is filled
        """
        self.logger.info(f"Order filled: {event}")
    
    def did_fail_order(self, event):
        """
        Called when an order fails
        """
        self.logger.warning(f"Order failed: {event}")
    
    def did_cancel_order(self, event):
        """
        Called when an order is cancelled
        """
        self.logger.info(f"Order cancelled: {event}")
    
    def format_status(self) -> str:
        """
        Return formatted status string
        """
        lines = [
            "=== Gate.io Arbitrage Example Status ===",
            f"Ready to trade: {self.ready_to_trade}",
            f"Active arbitrages: {len(self.active_arbitrages)}",
            f"Min profitability: {self.min_profitability:.4%}",
            f"Max position size: {self.max_position_size}",
        ]
        
        # Add connector status
        for name, connector in self.connectors.items():
            if connector:
                balance = connector.get_available_balance("USDT")
                lines.append(f"{name} USDT balance: {balance:.2f}")
        
        return "\n".join(lines)


# This function is required for Hummingbot to recognize the script
def start(connectors: Dict[str, ConnectorBase]):
    return GateArbExample(connectors)
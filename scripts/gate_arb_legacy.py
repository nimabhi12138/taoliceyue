#!/usr/bin/env python3
"""
Gate.io Arbitrage Legacy Script
ScriptStrategyBase demo for backward compatibility
Simple spot-perp arbitrage example
"""

import asyncio
import logging
from decimal import Decimal
from typing import Dict, Optional

from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate


class GateArbLegacy(ScriptStrategyBase):
    """
    Legacy Gate.io arbitrage script for demonstration
    Implements simple spot-perp basis arbitrage
    """
    
    # Required: Define markets that this script will use
    markets = {
        "gate_io": ["BTC-USDT", "ETH-USDT"],
        "gate_io_perpetual": ["BTC-USDT", "ETH-USDT"]
    }
    
    # Default configuration
    spot_connector = "gate_io"
    perp_connector = "gate_io_perpetual"
    trading_pair = "BTC-USDT"
    min_profitability = Decimal("0.001")  # 0.1% minimum profit
    order_amount = Decimal("0.001")  # BTC
    
    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        self.spot_connector_name = self.spot_connector
        self.perp_connector_name = self.perp_connector
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging"""
        self.logger = logging.getLogger(self.__class__.__name__)
        
    @property
    def spot_connector_instance(self) -> Optional[ConnectorBase]:
        """Get spot connector instance"""
        return self.connectors.get(self.spot_connector_name)
        
    @property
    def perp_connector_instance(self) -> Optional[ConnectorBase]:
        """Get perpetual connector instance"""
        return self.connectors.get(self.perp_connector_name)
        
    def on_tick(self):
        """Main strategy logic"""
        if not self.ready_to_trade:
            return
            
        try:
            self.check_arbitrage_opportunity()
        except Exception as e:
            self.logger.error(f"Error in arbitrage check: {e}")
            
    def check_arbitrage_opportunity(self):
        """Check for spot-perp arbitrage opportunities"""
        spot_connector = self.spot_connector_instance
        perp_connector = self.perp_connector_instance
        
        if not spot_connector or not perp_connector:
            return
            
        # Get current prices
        spot_price = self.get_mid_price(spot_connector, self.trading_pair)
        perp_price = self.get_mid_price(perp_connector, self.trading_pair)
        
        if not spot_price or not perp_price:
            return
            
        # Calculate basis and profitability
        basis = (perp_price - spot_price) / spot_price
        
        self.logger.info(f"Spot: {spot_price}, Perp: {perp_price}, Basis: {basis:.4f}")
        
        # Check if profitable after fees
        if abs(basis) > self.min_profitability:
            if basis > 0:
                # Perp is premium - short perp, long spot
                self.execute_arbitrage("short_perp_long_spot", basis)
            else:
                # Spot is premium - long perp, short spot  
                self.execute_arbitrage("long_perp_short_spot", abs(basis))
                
    def execute_arbitrage(self, direction: str, profitability: Decimal):
        """Execute arbitrage trade"""
        self.logger.info(f"Executing {direction} arbitrage, profit: {profitability:.4f}")
        
        # This is a simplified example - in production use proper risk management
        if direction == "short_perp_long_spot":
            # Buy spot, sell perp
            self.buy(
                connector_name=self.spot_connector_name,
                trading_pair=self.trading_pair,
                amount=self.order_amount,
                order_type=OrderType.MARKET
            )
            self.sell(
                connector_name=self.perp_connector_name,
                trading_pair=self.trading_pair,
                amount=self.order_amount,
                order_type=OrderType.MARKET
            )
        elif direction == "long_perp_short_spot":
            # Sell spot, buy perp
            self.sell(
                connector_name=self.spot_connector_name,
                trading_pair=self.trading_pair,
                amount=self.order_amount,
                order_type=OrderType.MARKET
            )
            self.buy(
                connector_name=self.perp_connector_name,
                trading_pair=self.trading_pair,
                amount=self.order_amount,
                order_type=OrderType.MARKET
            )
            
    def get_mid_price(self, connector: ConnectorBase, trading_pair: str) -> Optional[Decimal]:
        """Get mid price for a trading pair"""
        try:
            order_book = connector.get_order_book(trading_pair)
            if order_book and order_book.best_bid_price and order_book.best_ask_price:
                return (order_book.best_bid_price + order_book.best_ask_price) / 2
        except Exception as e:
            self.logger.error(f"Error getting mid price: {e}")
        return None
        
    def format_status(self) -> str:
        """Return strategy status"""
        spot_connector = self.spot_connector_instance
        perp_connector = self.perp_connector_instance
        
        if not spot_connector or not perp_connector:
            return "Connectors not ready"
            
        spot_price = self.get_mid_price(spot_connector, self.trading_pair)
        perp_price = self.get_mid_price(perp_connector, self.trading_pair)
        
        if spot_price and perp_price:
            basis = (perp_price - spot_price) / spot_price
            return f"Spot: {spot_price:.2f}, Perp: {perp_price:.2f}, Basis: {basis:.4f}"
        
        return "Waiting for price data..."
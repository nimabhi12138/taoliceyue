#!/usr/bin/env python3
"""
Gate.io Spot-Spot Arbitrage Controller
Cross-market spot arbitrage with maker preference optimization
"""

import asyncio
import logging
import time
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.strategy.strategy_v2_base import StrategyV2Base
from hummingbot.strategy.executors.arbitrage_executor import ArbitrageExecutor

from .fee_model import FeeModel
from .risk_manager import RiskManager


@dataclass
class SpotArbitrageOpportunity:
    """Spot-spot arbitrage opportunity"""
    symbol: str
    buy_exchange: str
    sell_exchange: str
    buy_price: Decimal
    sell_price: Decimal
    spread_bps: Decimal
    expected_profit_bps: Decimal
    size: Decimal
    confidence: Decimal


class GateSpotSpotController(StrategyV2Base):
    """
    Gate.io Spot-Spot Arbitrage Controller
    
    Implements cross-market and cross-venue spot arbitrage with maker preference
    for optimal fee utilization with Gate.io's rebate structure.
    """
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Configuration
        self.primary_connector = config.get("primary_connector", "gate_io")
        self.secondary_connectors = config.get("secondary_connectors", [])
        self.trading_pairs = config.get("trading_pairs", ["BTC-USDT", "ETH-USDT"])
        self.min_profitability_bps = Decimal(str(config.get("min_profitability_bps", "8")))
        self.max_position_size = Decimal(str(config.get("max_position_size", "1.0")))
        self.slippage_buffer_bps = Decimal(str(config.get("slippage_buffer_bps", "3")))
        self.prefer_maker_orders = config.get("prefer_maker_orders", True)
        self.min_spread_bps = Decimal(str(config.get("min_spread_bps", "5")))
        self.max_price_age_seconds = config.get("max_price_age_seconds", 2)
        
        # Intra-exchange arbitrage (different order books on same exchange)
        self.enable_intra_exchange = config.get("enable_intra_exchange", True)
        self.alternative_books = config.get("alternative_books", [])  # Different market segments
        
        # Components
        self.fee_model = FeeModel(config.get("fee_override_path"))
        self.risk_manager = RiskManager(config.get("risk_config", {}))
        
        # State
        self.active_arbitrages: Dict[str, Dict] = {}
        self.price_cache: Dict[str, Dict] = {}
        self.last_scan_time = 0
        self.executors: List[ArbitrageExecutor] = []
        
        self.is_active = True
        self.name = "GateSpotSpotController"
        
    async def process_tick(self):
        """Main processing loop"""
        try:
            # Update price cache
            await self.update_price_cache()
            
            # Scan for cross-exchange opportunities
            if self.secondary_connectors:
                await self.scan_cross_exchange_opportunities()
            
            # Scan for intra-exchange opportunities  
            if self.enable_intra_exchange:
                await self.scan_intra_exchange_opportunities()
                
            # Manage existing arbitrages
            await self.manage_active_arbitrages()
            
        except Exception as e:
            self.logger.error(f"Error in process_tick: {e}")
            
    async def update_price_cache(self):
        """Update price cache for all connectors and trading pairs"""
        if time.time() - self.last_scan_time < 0.5:  # Update every 500ms
            return
            
        current_time = time.time()
        
        # Update primary connector prices
        await self._update_connector_prices(self.primary_connector, current_time)
        
        # Update secondary connector prices
        for connector_name in self.secondary_connectors:
            await self._update_connector_prices(connector_name, current_time)
            
        self.last_scan_time = current_time
        
    async def _update_connector_prices(self, connector_name: str, timestamp: float):
        """Update prices for a specific connector"""
        connector = self.connectors.get(connector_name)
        if not connector:
            return
            
        if connector_name not in self.price_cache:
            self.price_cache[connector_name] = {}
            
        for trading_pair in self.trading_pairs:
            try:
                order_book = connector.get_order_book(trading_pair)
                if order_book and order_book.best_bid_price and order_book.best_ask_price:
                    self.price_cache[connector_name][trading_pair] = {
                        "bid": order_book.best_bid_price,
                        "ask": order_book.best_ask_price,
                        "bid_size": order_book.best_bid_entries[0].amount if order_book.best_bid_entries else Decimal("0"),
                        "ask_size": order_book.best_ask_entries[0].amount if order_book.best_ask_entries else Decimal("0"),
                        "timestamp": timestamp,
                        "mid": (order_book.best_bid_price + order_book.best_ask_price) / 2
                    }
            except Exception as e:
                self.logger.debug(f"Error updating price for {connector_name} {trading_pair}: {e}")
                
    async def scan_cross_exchange_opportunities(self):
        """Scan for arbitrage opportunities across different exchanges"""
        current_time = time.time()
        
        for trading_pair in self.trading_pairs:
            try:
                opportunity = await self.find_best_cross_exchange_opportunity(trading_pair, current_time)
                if opportunity:
                    await self.execute_spot_arbitrage(opportunity)
            except Exception as e:
                self.logger.debug(f"Error scanning cross-exchange for {trading_pair}: {e}")
                
    async def find_best_cross_exchange_opportunity(
        self, 
        trading_pair: str, 
        current_time: float
    ) -> Optional[SpotArbitrageOpportunity]:
        """Find the best cross-exchange arbitrage opportunity for a trading pair"""
        
        exchanges = [self.primary_connector] + self.secondary_connectors
        valid_prices = {}
        
        # Collect valid price data
        for exchange in exchanges:
            price_data = self.price_cache.get(exchange, {}).get(trading_pair)
            if price_data and (current_time - price_data["timestamp"]) <= self.max_price_age_seconds:
                valid_prices[exchange] = price_data
                
        if len(valid_prices) < 2:
            return None
            
        # Find best buy and sell opportunities
        best_opportunity = None
        max_profit = Decimal("0")
        
        for buy_exchange, buy_data in valid_prices.items():
            for sell_exchange, sell_data in valid_prices.items():
                if buy_exchange == sell_exchange:
                    continue
                    
                # Calculate potential profit
                buy_price = buy_data["ask"]  # We buy at ask
                sell_price = sell_data["bid"]  # We sell at bid
                
                if sell_price <= buy_price:
                    continue
                    
                # Calculate spread
                spread_bps = ((sell_price - buy_price) / buy_price) * Decimal("10000")
                
                if spread_bps < self.min_spread_bps:
                    continue
                    
                # Calculate available size
                max_buy_size = buy_data["ask_size"]
                max_sell_size = sell_data["bid_size"]
                available_size = min(max_buy_size, max_sell_size, self.max_position_size)
                
                if available_size <= 0:
                    continue
                    
                # Check profitability after fees
                is_profitable, analysis = self.fee_model.is_profitable(
                    buy_exchange,
                    sell_exchange,
                    TradeType.BUY,   # Buy = taker unless maker preference works
                    TradeType.SELL,  # Sell = maker preference
                    available_size,
                    buy_price,
                    sell_price,
                    min_profit_bps=self.min_profitability_bps,
                    slippage_buffer_bps=self.slippage_buffer_bps
                )
                
                if is_profitable and analysis["effective_profit_bps"] > max_profit:
                    max_profit = analysis["effective_profit_bps"]
                    
                    # Calculate position size with risk management
                    available_capital = self.get_available_capital(buy_exchange)
                    position_size = self.risk_manager.get_position_size(
                        symbol=trading_pair,
                        expected_return=analysis["effective_profit_bps"] / Decimal("10000"),
                        available_capital=available_capital,
                        confidence=Decimal("0.7")  # Moderate confidence for cross-exchange
                    )
                    
                    position_size = min(position_size, available_size)
                    
                    if position_size > 0:
                        best_opportunity = SpotArbitrageOpportunity(
                            symbol=trading_pair,
                            buy_exchange=buy_exchange,
                            sell_exchange=sell_exchange,
                            buy_price=buy_price,
                            sell_price=sell_price,
                            spread_bps=spread_bps,
                            expected_profit_bps=analysis["effective_profit_bps"],
                            size=position_size,
                            confidence=Decimal("0.7")
                        )
                        
        return best_opportunity
        
    async def scan_intra_exchange_opportunities(self):
        """Scan for arbitrage opportunities within the same exchange"""
        # This could include different market segments, trading modes, etc.
        # For Gate.io, this might be different order book depths or market types
        
        for trading_pair in self.trading_pairs:
            try:
                # Look for price inefficiencies in different order book levels
                opportunity = await self.find_intra_exchange_opportunity(trading_pair)
                if opportunity:
                    await self.execute_spot_arbitrage(opportunity)
            except Exception as e:
                self.logger.debug(f"Error scanning intra-exchange for {trading_pair}: {e}")
                
    async def find_intra_exchange_opportunity(self, trading_pair: str) -> Optional[SpotArbitrageOpportunity]:
        """Find intra-exchange arbitrage opportunities"""
        primary_connector = self.connectors.get(self.primary_connector)
        if not primary_connector:
            return None
            
        try:
            order_book = primary_connector.get_order_book(trading_pair)
            if not order_book:
                return None
                
            # Look for opportunities in order book depth
            # This is a simplified example - could be much more sophisticated
            bid_entries = order_book.bid_entries[:5]  # Top 5 bid levels
            ask_entries = order_book.ask_entries[:5]  # Top 5 ask levels
            
            # Look for large spread between deeper levels
            if len(bid_entries) >= 2 and len(ask_entries) >= 2:
                deep_bid = bid_entries[1].price  # Second best bid
                shallow_ask = ask_entries[0].price  # Best ask
                
                if deep_bid > shallow_ask:
                    spread_bps = ((deep_bid - shallow_ask) / shallow_ask) * Decimal("10000")
                    
                    if spread_bps >= self.min_profitability_bps:
                        size = min(bid_entries[1].amount, ask_entries[0].amount, self.max_position_size)
                        
                        # This would require more sophisticated execution logic
                        # For now, return None as this needs careful implementation
                        pass
                        
        except Exception as e:
            self.logger.debug(f"Error in intra-exchange analysis: {e}")
            
        return None
        
    async def execute_spot_arbitrage(self, opportunity: SpotArbitrageOpportunity):
        """Execute a spot arbitrage opportunity"""
        
        # Check risk limits
        can_trade, violations = self.risk_manager.check_risk_limits()
        if not can_trade:
            self.logger.warning(f"Risk limits violated: {violations}")
            return
            
        arbitrage_id = f"spot_{int(time.time() * 1000)}"
        
        self.logger.info(
            f"Executing spot arbitrage {arbitrage_id}: "
            f"Buy {opportunity.symbol} on {opportunity.buy_exchange} at {opportunity.buy_price:.6f}, "
            f"Sell on {opportunity.sell_exchange} at {opportunity.sell_price:.6f}, "
            f"Expected profit: {opportunity.expected_profit_bps:.2f}bps, "
            f"Size: {opportunity.size:.6f}"
        )
        
        try:
            # Create arbitrage executor
            executor_config = {
                "trading_pair": opportunity.symbol,
                "min_profitability": float(self.min_profitability_bps / Decimal("10000")),
                "order_amount": float(opportunity.size),
                "max_retries": 3,
                "timeout": 30
            }
            
            executor = ArbitrageExecutor(
                strategy=self,
                config=executor_config,
                buy_connector_name=opportunity.buy_exchange,
                sell_connector_name=opportunity.sell_exchange
            )
            
            self.executors.append(executor)
            
            # Track the arbitrage
            self.active_arbitrages[arbitrage_id] = {
                "opportunity": opportunity,
                "executor": executor,
                "start_time": time.time(),
                "status": "executing"
            }
            
            # Start execution
            executor.start()
            
        except Exception as e:
            self.logger.error(f"Error executing spot arbitrage: {e}")
            
    async def manage_active_arbitrages(self):
        """Manage active arbitrage executions"""
        current_time = time.time()
        
        for arbitrage_id, arbitrage in list(self.active_arbitrages.items()):
            try:
                executor = arbitrage["executor"]
                
                # Check if executor completed
                if not executor.is_active:
                    await self._complete_arbitrage(arbitrage_id, arbitrage)
                    continue
                    
                # Check for timeout
                elapsed = current_time - arbitrage["start_time"]
                if elapsed > 60:  # 1 minute timeout
                    self.logger.warning(f"Arbitrage {arbitrage_id} timed out")
                    executor.stop()
                    await self._complete_arbitrage(arbitrage_id, arbitrage)
                    
            except Exception as e:
                self.logger.error(f"Error managing arbitrage {arbitrage_id}: {e}")
                
    async def _complete_arbitrage(self, arbitrage_id: str, arbitrage: Dict):
        """Complete an arbitrage execution"""
        try:
            opportunity = arbitrage["opportunity"]
            executor = arbitrage["executor"]
            
            # Calculate actual PnL (simplified)
            estimated_pnl = opportunity.size * opportunity.expected_profit_bps / Decimal("10000")
            
            # Record trade result
            self.risk_manager.record_trade(
                symbol=opportunity.symbol,
                pnl=estimated_pnl,
                size=opportunity.size,
                success=True
            )
            
            # Clean up
            del self.active_arbitrages[arbitrage_id]
            
            execution_time = time.time() - arbitrage["start_time"]
            self.logger.info(
                f"Completed arbitrage {arbitrage_id} in {execution_time:.1f}s, "
                f"estimated PnL: {estimated_pnl:.6f}"
            )
            
        except Exception as e:
            self.logger.error(f"Error completing arbitrage {arbitrage_id}: {e}")
            
    def get_available_capital(self, exchange: str) -> Decimal:
        """Get available capital for trading on specific exchange"""
        # Simplified implementation - should check actual balances
        return Decimal("5.0")  # Placeholder
        
    def handle_order_fill(self, event):
        """Handle order fill events"""
        # Track fills for risk management
        pass
        
    def get_status(self) -> str:
        """Get controller status"""
        status_lines = [
            f"Active arbitrages: {len(self.active_arbitrages)}",
            f"Active executors: {len([e for e in self.executors if e.is_active])}",
            f"Monitored exchanges: {[self.primary_connector] + self.secondary_connectors}",
        ]
        
        # Risk status
        risk_status = self.risk_manager.get_risk_status()
        status_lines.append(f"Can trade: {risk_status['can_trade']}")
        status_lines.append(f"Total PnL: {risk_status['metrics']['total_pnl']:.4f}")
        status_lines.append(f"Win rate: {risk_status['metrics']['win_rate']:.2%}")
        
        # Active arbitrages
        for arbitrage_id, arbitrage in self.active_arbitrages.items():
            opportunity = arbitrage["opportunity"]
            elapsed = time.time() - arbitrage["start_time"]
            status_lines.append(
                f"{arbitrage_id}: {opportunity.buy_exchange} -> {opportunity.sell_exchange}, "
                f"profit={opportunity.expected_profit_bps:.2f}bps, elapsed={elapsed:.1f}s"
            )
            
        return "\n".join(status_lines)
        
    def stop(self):
        """Stop the controller"""
        self.is_active = False
        
        # Stop all executors
        for executor in self.executors:
            if executor.is_active:
                executor.stop()
                
        self.logger.info("Gate Spot-Spot Controller stopped")
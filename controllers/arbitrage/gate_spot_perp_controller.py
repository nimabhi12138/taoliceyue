#!/usr/bin/env python3
"""
Gate.io Spot-Perp Arbitrage Controller
Cash-and-carry and basis arbitrage between spot and perpetual markets
"""

import asyncio
import logging
import time
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.connector.connector_base import ConnectorBase

try:
    from hummingbot.strategy.strategy_v2_base import StrategyV2Base
except ImportError:
    # Fallback for older versions
    from hummingbot.strategy.strategy_base import StrategyBase as StrategyV2Base
    
try:
    from hummingbot.strategy.executors.arbitrage_executor import ArbitrageExecutor
except ImportError:
    # Create a placeholder if not available
    class ArbitrageExecutor:
        def __init__(self, *args, **kwargs):
            self.is_active = False
        def start(self):
            pass
        def stop(self):
            pass

from .fee_model import FeeModel
from .risk_manager import RiskManager


@dataclass
class ArbitrageOpportunity:
    """Arbitrage opportunity data"""
    symbol: str
    spot_price: Decimal
    perp_price: Decimal
    basis_bps: Decimal
    funding_rate: Decimal
    expected_profit_bps: Decimal
    size: Decimal
    direction: str  # "long_spot_short_perp" or "short_spot_long_perp"
    confidence: Decimal


class GateSpotPerpController(StrategyV2Base):
    """
    Gate.io Spot-Perpetual Arbitrage Controller
    
    Implements cash-and-carry arbitrage between Gate.io spot and perpetual markets.
    Focuses on basis trading with funding rate considerations.
    """
    
    def __init__(self, config: Dict):
        # Initialize with config, connectors will be set separately
        super().__init__(config)
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Get connectors from config if provided
        self.connectors = config.get("connectors", {})
        
        # Configuration
        self.spot_connector = config.get("spot_connector", "gate_io")
        self.perp_connector = config.get("perp_connector", "gate_io_perpetual")
        self.trading_pairs = config.get("trading_pairs", ["BTC-USDT", "ETH-USDT"])
        self.min_profitability_bps = Decimal(str(config.get("min_profitability_bps", "5")))
        self.max_position_size = Decimal(str(config.get("max_position_size", "1.0")))
        self.funding_threshold_bps = Decimal(str(config.get("funding_threshold_bps", "2")))
        self.max_funding_periods = config.get("max_funding_periods", 24)  # Max hours to hold
        self.rebalance_threshold_bps = Decimal(str(config.get("rebalance_threshold_bps", "20")))
        self.slippage_buffer_bps = Decimal(str(config.get("slippage_buffer_bps", "2")))
        
        # Components
        self.fee_model = FeeModel(config.get("fee_override_path"))
        self.risk_manager = RiskManager(config.get("risk_config", {}))
        
        # State
        self.active_positions: Dict[str, Dict] = {}
        self.funding_rates: Dict[str, Decimal] = {}
        self.last_funding_update = 0
        self.executors: List[ArbitrageExecutor] = []
        
        self.is_active = True
        self.name = "GateSpotPerpController"
        
    async def process_tick(self):
        """Main processing loop"""
        try:
            # Update funding rates
            await self.update_funding_rates()
            
            # Check existing positions for rebalancing/closing
            await self.manage_existing_positions()
            
            # Look for new opportunities
            await self.scan_opportunities()
            
        except Exception as e:
            self.logger.error(f"Error in process_tick: {e}")
            
    async def update_funding_rates(self):
        """Update funding rates from perpetual exchange"""
        if time.time() - self.last_funding_update < 60:  # Update every minute
            return
            
        try:
            perp_connector = self.connectors.get(self.perp_connector)
            if not perp_connector:
                return
                
            for trading_pair in self.trading_pairs:
                if hasattr(perp_connector, 'get_funding_info'):
                    funding_info = await perp_connector.get_funding_info(trading_pair)
                    if funding_info:
                        self.funding_rates[trading_pair] = Decimal(str(funding_info.rate))
                        
            self.last_funding_update = time.time()
            
        except Exception as e:
            self.logger.error(f"Error updating funding rates: {e}")
            
    async def scan_opportunities(self):
        """Scan for arbitrage opportunities"""
        spot_connector = self.connectors.get(self.spot_connector)
        perp_connector = self.connectors.get(self.perp_connector)
        
        if not spot_connector or not perp_connector:
            return
            
        for trading_pair in self.trading_pairs:
            try:
                opportunity = await self.analyze_pair(
                    trading_pair, spot_connector, perp_connector
                )
                
                if opportunity and opportunity.expected_profit_bps >= self.min_profitability_bps:
                    await self.execute_opportunity(opportunity)
                    
            except Exception as e:
                self.logger.error(f"Error analyzing pair {trading_pair}: {e}")
                
    async def analyze_pair(
        self, 
        trading_pair: str, 
        spot_connector: ConnectorBase, 
        perp_connector: ConnectorBase
    ) -> Optional[ArbitrageOpportunity]:
        """Analyze a trading pair for arbitrage opportunities"""
        
        # Get order books
        spot_book = spot_connector.get_order_book(trading_pair)
        perp_book = perp_connector.get_order_book(trading_pair)
        
        if not spot_book or not perp_book:
            return None
            
        # Get best prices
        spot_bid = spot_book.best_bid_price
        spot_ask = spot_book.best_ask_price
        perp_bid = perp_book.best_bid_price
        perp_ask = perp_book.best_ask_price
        
        if not all([spot_bid, spot_ask, perp_bid, perp_ask]):
            return None
            
        # Calculate mid prices
        spot_mid = (spot_bid + spot_ask) / 2
        perp_mid = (perp_bid + perp_ask) / 2
        
        # Calculate basis (perp premium/discount)
        basis_bps = ((perp_mid - spot_mid) / spot_mid) * Decimal("10000")
        
        # Get funding rate
        funding_rate = self.funding_rates.get(trading_pair, Decimal("0"))
        funding_bps = funding_rate * Decimal("10000")
        
        # Determine direction and calculate expected profit
        if basis_bps > 0:
            # Perp is premium - sell perp, buy spot
            direction = "short_perp_long_spot"
            entry_spot_price = spot_ask  # Buy spot at ask
            entry_perp_price = perp_bid  # Sell perp at bid
            
            # Calculate expected profit
            is_profitable, analysis = self.fee_model.is_profitable(
                buy_connector=self.spot_connector,
                sell_connector=self.perp_connector,
                buy_trade_type=TradeType.BUY,  # Taker on spot
                sell_trade_type=TradeType.SELL,  # Maker on perp (if possible)
                amount=self.max_position_size,
                buy_price=entry_spot_price,
                sell_price=entry_perp_price,
                funding_cost=funding_bps * self.max_funding_periods / Decimal("10000"),
                min_profit_bps=self.min_profitability_bps,
                slippage_buffer_bps=self.slippage_buffer_bps
            )
            
        else:
            # Spot is premium - buy perp, sell spot  
            direction = "long_perp_short_spot"
            entry_perp_price = perp_ask  # Buy perp at ask
            entry_spot_price = spot_bid  # Sell spot at bid
            
            # Calculate expected profit
            is_profitable, analysis = self.fee_model.is_profitable(
                buy_connector=self.perp_connector,
                sell_connector=self.spot_connector,
                buy_trade_type=TradeType.BUY,  # Taker on perp
                sell_trade_type=TradeType.SELL,  # Maker on spot (if possible)
                amount=self.max_position_size,
                buy_price=entry_perp_price,
                sell_price=entry_spot_price,
                funding_cost=-funding_bps * self.max_funding_periods / Decimal("10000"),  # Receive funding
                min_profit_bps=self.min_profitability_bps,
                slippage_buffer_bps=self.slippage_buffer_bps
            )
            
        if not is_profitable:
            return None
            
        # Calculate position size based on risk management
        available_capital = self.get_available_capital()
        position_size = self.risk_manager.get_position_size(
            symbol=trading_pair,
            expected_return=analysis["effective_profit_bps"] / Decimal("10000"),
            available_capital=available_capital,
            confidence=Decimal("0.8")  # Conservative confidence for basis arb
        )
        
        if position_size <= 0:
            return None
            
        return ArbitrageOpportunity(
            symbol=trading_pair,
            spot_price=spot_mid,
            perp_price=perp_mid,
            basis_bps=basis_bps,
            funding_rate=funding_rate,
            expected_profit_bps=analysis["effective_profit_bps"],
            size=position_size,
            direction=direction,
            confidence=Decimal("0.8")
        )
        
    async def execute_opportunity(self, opportunity: ArbitrageOpportunity):
        """Execute an arbitrage opportunity"""
        
        # Check risk limits
        can_trade, violations = self.risk_manager.check_risk_limits()
        if not can_trade:
            self.logger.warning(f"Risk limits violated: {violations}")
            return
            
        self.logger.info(
            f"Executing {opportunity.direction} on {opportunity.symbol}: "
            f"basis={opportunity.basis_bps:.2f}bps, "
            f"expected_profit={opportunity.expected_profit_bps:.2f}bps, "
            f"size={opportunity.size:.6f}"
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
            
            if opportunity.direction == "short_perp_long_spot":
                # Buy spot, sell perp
                buy_connector_name = self.spot_connector
                sell_connector_name = self.perp_connector
            else:
                # Buy perp, sell spot
                buy_connector_name = self.perp_connector
                sell_connector_name = self.spot_connector
                
            executor = ArbitrageExecutor(
                strategy=self,
                config=executor_config,
                buy_connector_name=buy_connector_name,
                sell_connector_name=sell_connector_name
            )
            
            self.executors.append(executor)
            
            # Track the position
            self.active_positions[opportunity.symbol] = {
                "direction": opportunity.direction,
                "size": opportunity.size,
                "entry_time": time.time(),
                "entry_basis": opportunity.basis_bps,
                "funding_rate": opportunity.funding_rate,
                "executor": executor
            }
            
            # Start the executor
            executor.start()
            
        except Exception as e:
            self.logger.error(f"Error executing opportunity: {e}")
            
    async def manage_existing_positions(self):
        """Manage existing positions for rebalancing or closing"""
        for symbol, position in list(self.active_positions.items()):
            try:
                await self.check_position_exit(symbol, position)
            except Exception as e:
                self.logger.error(f"Error managing position {symbol}: {e}")
                
    async def check_position_exit(self, symbol: str, position: Dict):
        """Check if a position should be closed"""
        
        # Check if executor is still active
        executor = position.get("executor")
        if executor and not executor.is_active:
            # Position was closed by executor
            del self.active_positions[symbol]
            return
            
        # Check time-based exit
        position_age = time.time() - position["entry_time"]
        max_age = self.max_funding_periods * 3600  # Convert hours to seconds
        
        if position_age > max_age:
            self.logger.info(f"Closing {symbol} position due to time limit")
            await self.close_position(symbol, position, "time_limit")
            return
            
        # Check profitability-based exit
        current_opportunity = await self.analyze_pair(
            symbol,
            self.connectors.get(self.spot_connector),
            self.connectors.get(self.perp_connector)
        )
        
        if current_opportunity:
            current_basis = current_opportunity.basis_bps
            entry_basis = position["entry_basis"]
            basis_change = abs(current_basis - entry_basis)
            
            # Close if basis has moved significantly against us
            if basis_change > self.rebalance_threshold_bps:
                self.logger.info(
                    f"Closing {symbol} position due to basis change: "
                    f"{entry_basis:.2f} -> {current_basis:.2f} bps"
                )
                await self.close_position(symbol, position, "basis_change")
                
    async def close_position(self, symbol: str, position: Dict, reason: str):
        """Close a position"""
        try:
            executor = position.get("executor")
            if executor and executor.is_active:
                executor.stop()
                
            # Record trade result
            current_time = time.time()
            holding_period = current_time - position["entry_time"]
            
            # Calculate approximate PnL (actual PnL will be calculated by executor)
            estimated_pnl = position["size"] * Decimal("0.001")  # Placeholder
            
            self.risk_manager.record_trade(
                symbol=symbol,
                pnl=estimated_pnl,
                size=position["size"],
                success=True
            )
            
            del self.active_positions[symbol]
            
            self.logger.info(
                f"Closed {symbol} position after {holding_period:.0f}s, reason: {reason}"
            )
            
        except Exception as e:
            self.logger.error(f"Error closing position {symbol}: {e}")
            
    def get_available_capital(self) -> Decimal:
        """Get available capital for trading"""
        # This is a simplified implementation
        # In practice, you'd calculate based on actual balances
        return Decimal("10.0")  # Placeholder
        
    def handle_order_fill(self, event):
        """Handle order fill events from executors"""
        # Track fills for risk management
        pass
        
    def get_status(self) -> str:
        """Get controller status"""
        status_lines = [
            f"Active positions: {len(self.active_positions)}",
            f"Active executors: {len([e for e in self.executors if e.is_active])}",
        ]
        
        # Risk status
        risk_status = self.risk_manager.get_risk_status()
        status_lines.append(f"Can trade: {risk_status['can_trade']}")
        status_lines.append(f"Total PnL: {risk_status['metrics']['total_pnl']:.4f}")
        status_lines.append(f"Win rate: {risk_status['metrics']['win_rate']:.2%}")
        
        # Position details
        for symbol, position in self.active_positions.items():
            age = time.time() - position["entry_time"]
            status_lines.append(
                f"{symbol}: {position['direction']}, "
                f"size={position['size']:.6f}, age={age:.0f}s"
            )
            
        return "\n".join(status_lines)
        
    def stop(self):
        """Stop the controller and all executors"""
        self.is_active = False
        for executor in self.executors:
            if executor.is_active:
                executor.stop()
        self.logger.info("Gate Spot-Perp Controller stopped")
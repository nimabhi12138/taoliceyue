from typing import List
from typing import Optional
"""
Gate.io Statistical Arbitrage Controller
Implements mean-reversion pairs trading with cointegration analysis
"""

import asyncio
import logging
import numpy as np
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import deque

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.smart_components.models.executor_actions import ExecutorAction, CreateExecutorAction, StopExecutorAction

from hummingbot.smart_components.controllers.controller_base import ControllerBase, ControllerConfigBase
from hummingbot.smart_components.executors.position_executor import PositionExecutor
from pydantic import Field, validator

logger = logging.getLogger(__name__)


class GateStatArbControllerConfig(ControllerConfigBase):
    """Configuration for Statistical Arbitrage Controller"""
    
    controller_name: str = "gate_stat_arb_controller"
    controller_type: str = "directional"
    connector: str = Field(default="gate_io")
    
    # Trading pairs
    pairs: List[Dict[str, str]] = Field(
        default=[
            {"asset1": "BTC-USDT", "asset2": "ETH-USDT", "hedge_ratio": 15.0},
            {"asset1": "BNB-USDT", "asset2": "SOL-USDT", "hedge_ratio": 5.0},
        ],
        description="Cointegrated pairs to trade"
    )
    
    # Statistical parameters
    lookback_period: int = Field(default=100, description="Candles for mean/std calculation")
    entry_z_score: Decimal = Field(default=Decimal("2.0"), description="Z-score for entry")
    exit_z_score: Decimal = Field(default=Decimal("0.5"), description="Z-score for exit")
    stop_z_score: Decimal = Field(default=Decimal("3.5"), description="Z-score for stop loss")
    
    # Position sizing
    position_size_pct: Decimal = Field(default=Decimal("0.05"))
    max_position_usd: Decimal = Field(default=Decimal("3000"))
    
    # Risk management
    max_open_pairs: int = Field(default=3)
    min_half_life: int = Field(default=10, description="Min half-life in candles")
    max_half_life: int = Field(default=100, description="Max half-life in candles")
    
    # Fee configuration
    maker_fee_bps: Decimal = Field(default=Decimal("2.5"))
    taker_fee_bps: Decimal = Field(default=Decimal("5.0"))


@dataclass
class PairStats:
    """Statistics for a trading pair"""
    spread_mean: float
    spread_std: float
    current_spread: float
    z_score: float
    half_life: float
    hedge_ratio: float
    cointegration_pvalue: float
    last_updated: datetime


class GateStatArbController(ControllerBase):
    """
    Statistical Arbitrage Controller
    Implements mean-reversion pairs trading with dynamic hedge ratios
    """
    
    def __init__(self, config: GateStatArbControllerConfig):
        super().__init__(config)
        self.config = config
        
        # Tracking
        self._pair_stats: Dict[str, PairStats] = {}
        self._price_history: Dict[str, deque] = {}
        self._active_positions: Dict[str, List[PositionExecutor]] = {}
        
        # Performance
        self._total_pnl = Decimal("0")
        self._total_trades = 0
        self._winning_trades = 0
        
    async def start(self) -> None:
        """Initialize the controller"""
        await super().start()
        self.logger.info(f"Starting {self.config.controller_name}")
        
        await self._load_fee_overrides()
        await self._initialize_price_history()
        
        asyncio.create_task(self._update_statistics())
        asyncio.create_task(self._monitor_signals())
        asyncio.create_task(self._monitor_positions())
        
    async def stop(self) -> None:
        """Cleanup on stop"""
        self.logger.info(f"Stopping {self.config.controller_name}")
        
        # Close all positions
        for executors in self._active_positions.values():
            for executor in executors:
                if executor.is_active:
                    await executor.early_stop()
                    
        await super().stop()
        
    async def _load_fee_overrides(self) -> None:
        """Load fee overrides"""
        try:
            import yaml
            with open("conf/conf_fee_overrides.yml", "r") as f:
                overrides = yaml.safe_load(f)
                
            if self.config.connector in overrides:
                fees = overrides[self.config.connector]
                self.config.maker_fee_bps = Decimal(str(fees.get("maker_fee", 0.025))) * 100
                self.config.taker_fee_bps = Decimal(str(fees.get("taker_fee", 0.05))) * 100
                
        except Exception as e:
            self.logger.warning(f"Could not load fee overrides: {e}")
            
    async def _initialize_price_history(self) -> None:
        """Initialize price history for all pairs"""
        for pair_config in self.config.pairs:
            asset1 = pair_config["asset1"]
            asset2 = pair_config["asset2"]
            
            self._price_history[asset1] = deque(maxlen=self.config.lookback_period)
            self._price_history[asset2] = deque(maxlen=self.config.lookback_period)
            
            # Load historical data if available
            await self._load_historical_prices(asset1)
            await self._load_historical_prices(asset2)
            
    async def _load_historical_prices(self, symbol: str) -> None:
        """Load historical prices for a symbol"""
        try:
            connector = self.connectors[self.config.connector]
            # Simplified - would use actual historical data API
            current_price = connector.get_mid_price(symbol)
            if current_price:
                # Initialize with current price
                for _ in range(min(20, self.config.lookback_period)):
                    self._price_history[symbol].append(float(current_price))
        except Exception as e:
            self.logger.error(f"Error loading historical prices for {symbol}: {e}")
            
    async def _update_statistics(self) -> None:
        """Update pair statistics periodically"""
        while self.is_active:
            try:
                connector = self.connectors[self.config.connector]
                
                # Update price history
                for symbol in self._price_history.keys():
                    price = connector.get_mid_price(symbol)
                    if price:
                        self._price_history[symbol].append(float(price))
                        
                # Calculate statistics for each pair
                for pair_config in self.config.pairs:
                    asset1 = pair_config["asset1"]
                    asset2 = pair_config["asset2"]
                    pair_id = f"{asset1}_{asset2}"
                    
                    if len(self._price_history[asset1]) >= 20 and len(self._price_history[asset2]) >= 20:
                        stats = self._calculate_pair_stats(
                            self._price_history[asset1],
                            self._price_history[asset2],
                            float(pair_config.get("hedge_ratio", 1.0))
                        )
                        self._pair_stats[pair_id] = stats
                        
                await asyncio.sleep(60)  # Update every minute
                
            except Exception as e:
                self.logger.error(f"Error updating statistics: {e}")
                await asyncio.sleep(60)
                
    def _calculate_pair_stats(self, prices1: deque, prices2: deque, hedge_ratio: float) -> PairStats:
        """Calculate statistical properties of a pair"""
        try:
            # Convert to numpy arrays
            p1 = np.array(prices1)
            p2 = np.array(prices2)
            
            # Calculate spread
            spread = p1 - hedge_ratio * p2
            
            # Calculate statistics
            spread_mean = np.mean(spread)
            spread_std = np.std(spread)
            current_spread = spread[-1]
            z_score = (current_spread - spread_mean) / spread_std if spread_std > 0 else 0
            
            # Calculate half-life (simplified)
            half_life = self._calculate_half_life(spread)
            
            # Cointegration test (simplified - would use proper statistical test)
            cointegration_pvalue = 0.01  # Placeholder
            
            return PairStats(
                spread_mean=spread_mean,
                spread_std=spread_std,
                current_spread=current_spread,
                z_score=z_score,
                half_life=half_life,
                hedge_ratio=hedge_ratio,
                cointegration_pvalue=cointegration_pvalue,
                last_updated=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Error calculating pair stats: {e}")
            return PairStats(0, 1, 0, 0, 50, hedge_ratio, 1.0, datetime.now())
            
    def _calculate_half_life(self, spread: np.ndarray) -> float:
        """Calculate mean reversion half-life"""
        try:
            # Simple AR(1) model
            spread_lag = spread[:-1]
            spread_diff = spread[1:] - spread[:-1]
            
            if len(spread_lag) > 0:
                # OLS regression
                theta = np.sum(spread_lag * spread_diff) / np.sum(spread_lag ** 2)
                half_life = -np.log(2) / theta if theta < 0 else 100
                return min(max(half_life, 1), 100)
                
        except Exception:
            pass
            
        return 50  # Default half-life
        
    async def _monitor_signals(self) -> None:
        """Monitor for trading signals"""
        while self.is_active:
            try:
                for pair_config in self.config.pairs:
                    asset1 = pair_config["asset1"]
                    asset2 = pair_config["asset2"]
                    pair_id = f"{asset1}_{asset2}"
                    
                    if pair_id not in self._pair_stats:
                        continue
                        
                    stats = self._pair_stats[pair_id]
                    
                    # Check if we have an active position
                    has_position = pair_id in self._active_positions and len(self._active_positions[pair_id]) > 0
                    
                    if not has_position:
                        # Check entry signals
                        if abs(stats.z_score) > float(self.config.entry_z_score):
                            if stats.half_life >= self.config.min_half_life and \
                               stats.half_life <= self.config.max_half_life:
                                await self._enter_position(pair_id, asset1, asset2, stats)
                    else:
                        # Check exit signals
                        if abs(stats.z_score) < float(self.config.exit_z_score):
                            await self._exit_position(pair_id)
                        elif abs(stats.z_score) > float(self.config.stop_z_score):
                            await self._exit_position(pair_id)
                            
                await asyncio.sleep(5)
                
            except Exception as e:
                self.logger.error(f"Error monitoring signals: {e}")
                await asyncio.sleep(10)
                
    async def _enter_position(self, pair_id: str, asset1: str, asset2: str, stats: PairStats) -> None:
        """Enter a statistical arbitrage position"""
        try:
            if len(self._active_positions) >= self.config.max_open_pairs:
                return
                
            connector = self.connectors[self.config.connector]
            
            # Calculate position sizes
            balance = connector.get_available_balance("USDT")
            position_value = min(
                balance * self.config.position_size_pct,
                self.config.max_position_usd
            )
            
            # Allocate between assets based on hedge ratio
            asset1_value = position_value / (1 + stats.hedge_ratio)
            asset2_value = position_value - asset1_value
            
            asset1_price = connector.get_mid_price(asset1)
            asset2_price = connector.get_mid_price(asset2)
            
            if not asset1_price or not asset2_price:
                return
                
            asset1_amount = asset1_value / float(asset1_price)
            asset2_amount = asset2_value / float(asset2_price)
            
            executors = []
            
            # Determine direction based on z-score
            if stats.z_score > 0:
                # Spread is high - sell asset1, buy asset2
                side1 = TradeType.SELL
                side2 = TradeType.BUY
            else:
                # Spread is low - buy asset1, sell asset2
                side1 = TradeType.BUY
                side2 = TradeType.SELL
                
            # Create executors
            executor1 = PositionExecutor(
                strategy=self,
                config={
                    "controller_id": self.config.controller_name,
                    "trading_pair": asset1,
                    "connector_name": self.config.connector,
                    "side": side1,
                    "amount": Decimal(str(asset1_amount)),
                    "order_type": OrderType.LIMIT
                }
            )
            
            executor2 = PositionExecutor(
                strategy=self,
                config={
                    "controller_id": self.config.controller_name,
                    "trading_pair": asset2,
                    "connector_name": self.config.connector,
                    "side": side2,
                    "amount": Decimal(str(asset2_amount)),
                    "order_type": OrderType.LIMIT
                }
            )
            
            await executor1.start()
            await executor2.start()
            
            executors = [executor1, executor2]
            self._active_positions[pair_id] = executors
            self._total_trades += 1
            
            self.logger.info(f"Entered stat arb position: {pair_id} z-score={stats.z_score:.2f} "
                           f"half-life={stats.half_life:.1f}")
            
        except Exception as e:
            self.logger.error(f"Error entering position: {e}")
            
    async def _exit_position(self, pair_id: str) -> None:
        """Exit a statistical arbitrage position"""
        try:
            if pair_id not in self._active_positions:
                return
                
            executors = self._active_positions[pair_id]
            total_pnl = Decimal("0")
            
            for executor in executors:
                if executor.is_active:
                    await executor.early_stop()
                pnl = executor.get_net_pnl_quote()
                total_pnl += pnl
                
            self._total_pnl += total_pnl
            if total_pnl > 0:
                self._winning_trades += 1
                
            del self._active_positions[pair_id]
            
            self.logger.info(f"Exited stat arb position: {pair_id} PnL=${total_pnl:.2f}")
            
        except Exception as e:
            self.logger.error(f"Error exiting position: {e}")
            
    async def _monitor_positions(self) -> None:
        """Monitor active positions"""
        while self.is_active:
            try:
                for pair_id, executors in list(self._active_positions.items()):
                    # Check if all executors are inactive
                    all_inactive = all(not e.is_active for e in executors)
                    if all_inactive:
                        total_pnl = sum(e.get_net_pnl_quote() for e in executors)
                        self._total_pnl += total_pnl
                        if total_pnl > 0:
                            self._winning_trades += 1
                        del self._active_positions[pair_id]
                        
                await asyncio.sleep(5)
                
            except Exception as e:
                self.logger.error(f"Error monitoring positions: {e}")
                await asyncio.sleep(10)
                
    def format_status(self) -> str:
        """Format controller status"""
        lines = []
        lines.append(f"\n{'=' * 50}")
    async def update_processed_data(self) -> None:
        """
        V2 Framework: Update processed data periodically
        """
        # Update any cached data here
        pass
        lines.append(f"{'=' * 50}")
    async def determine_executor_actions(self) -> List[ExecutorAction]:
        """
        V2 Framework: Determine what executors to create/stop
        """
        actions = []
        # Add logic to create executor actions
        return actions
        
        lines.append(f"Active Positions: {len(self._active_positions)}")
    def to_format_status(self) -> List[str]:
        """
        V2 Framework: Format status for display
        """
        lines = []
        lines.append(f"Controller: {self.config.controller_name}")
        lines.append(f"Status: {'Active' if self.is_active else 'Inactive'}")
        return lines
        
        for pair_id, executors in self._active_positions.items():
            pnl = sum(e.get_net_pnl_quote() for e in executors)
            lines.append(f"  {pair_id}: PnL=${pnl:.2f}")
            
        # Performance
        win_rate = (self._winning_trades / max(self._total_trades, 1)) * 100
        lines.append(f"\nPerformance:")
        lines.append(f"  Total PnL: ${self._total_pnl:.2f}")
        lines.append(f"  Total Trades: {self._total_trades}")
        lines.append(f"  Win Rate: {win_rate:.1f}%")
        
        # Pair statistics
        if self._pair_stats:
            lines.append(f"\nPair Statistics:")
            for pair_id, stats in self._pair_stats.items():
                lines.append(f"  {pair_id}:")
                lines.append(f"    Z-Score: {stats.z_score:.2f}")
                lines.append(f"    Half-Life: {stats.half_life:.1f} candles")
                
        return "\n".join(lines)
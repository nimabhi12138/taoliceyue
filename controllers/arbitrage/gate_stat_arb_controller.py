#!/usr/bin/env python3
"""
Gate.io Statistical Arbitrage Controller
Mean-reversion and co-integration pairs trading with net-fee edge optimization
"""

import asyncio
import logging
import time
import numpy as np
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import deque

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.strategy.strategy_v2_base import StrategyV2Base
from hummingbot.strategy.executors.arbitrage_executor import ArbitrageExecutor

from .fee_model import FeeModel
from .risk_manager import RiskManager


@dataclass
class TradingPair:
    """Statistical arbitrage trading pair"""
    symbol_a: str
    symbol_b: str
    hedge_ratio: Decimal
    correlation: Decimal
    half_life: float  # Mean reversion half-life in seconds
    
    
@dataclass
class StatArbSignal:
    """Statistical arbitrage signal"""
    pair: TradingPair
    z_score: Decimal
    spread: Decimal
    signal_strength: Decimal
    direction: str  # "long_spread", "short_spread", "close"
    size_a: Decimal
    size_b: Decimal
    expected_profit_bps: Decimal


class GateStatArbController(StrategyV2Base):
    """
    Gate.io Statistical Arbitrage Controller
    
    Implements pairs trading using mean reversion and co-integration models.
    Optimized for Gate.io's fee structure with soft-edge validation.
    """
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Configuration
        self.connector_name = config.get("connector", "gate_io")
        self.trading_pairs = self._parse_trading_pairs(config.get("trading_pairs", {}))
        self.lookback_period = config.get("lookback_period", 200)  # Price history length
        self.z_score_entry = Decimal(str(config.get("z_score_entry", "2.0")))
        self.z_score_exit = Decimal(str(config.get("z_score_exit", "0.5")))
        self.z_score_stop = Decimal(str(config.get("z_score_stop", "3.5")))
        self.min_half_life = config.get("min_half_life", 300)  # 5 minutes minimum
        self.max_half_life = config.get("max_half_life", 7200)  # 2 hours maximum
        self.min_correlation = Decimal(str(config.get("min_correlation", "0.7")))
        self.max_position_size = Decimal(str(config.get("max_position_size", "1.0")))
        self.rebalance_frequency = config.get("rebalance_frequency", 3600)  # 1 hour
        
        # Components
        self.fee_model = FeeModel(config.get("fee_override_path"))
        self.risk_manager = RiskManager(config.get("risk_config", {}))
        
        # State
        self.price_history: Dict[str, deque] = {}
        self.spread_history: Dict[str, deque] = {}
        self.active_positions: Dict[str, Dict] = {}
        self.last_rebalance: Dict[str, float] = {}
        self.executors: List[ArbitrageExecutor] = []
        
        # Initialize price history
        for pair in self.trading_pairs:
            self.price_history[pair.symbol_a] = deque(maxlen=self.lookback_period)
            self.price_history[pair.symbol_b] = deque(maxlen=self.lookback_period)
            pair_id = f"{pair.symbol_a}_{pair.symbol_b}"
            self.spread_history[pair_id] = deque(maxlen=self.lookback_period)
            self.last_rebalance[pair_id] = 0
            
        self.is_active = True
        self.name = "GateStatArbController"
        
    def _parse_trading_pairs(self, pairs_config: Dict) -> List[TradingPair]:
        """Parse trading pairs configuration"""
        pairs = []
        for pair_name, config in pairs_config.items():
            symbols = pair_name.split("_")
            if len(symbols) == 2:
                pairs.append(TradingPair(
                    symbol_a=symbols[0],
                    symbol_b=symbols[1],
                    hedge_ratio=Decimal(str(config.get("hedge_ratio", "1.0"))),
                    correlation=Decimal(str(config.get("correlation", "0.0"))),
                    half_life=config.get("half_life", 1800.0)  # 30 minutes default
                ))
        return pairs
        
    async def process_tick(self):
        """Main processing loop"""
        try:
            # Update price history
            await self.update_price_history()
            
            # Rebalance pairs statistics if needed
            await self.rebalance_pairs()
            
            # Generate signals
            await self.generate_signals()
            
            # Manage existing positions
            await self.manage_positions()
            
        except Exception as e:
            self.logger.error(f"Error in process_tick: {e}")
            
    async def update_price_history(self):
        """Update price history for all symbols"""
        connector = self.connectors.get(self.connector_name)
        if not connector:
            return
            
        current_time = time.time()
        
        # Collect unique symbols
        symbols = set()
        for pair in self.trading_pairs:
            symbols.add(pair.symbol_a)
            symbols.add(pair.symbol_b)
            
        # Update prices
        for symbol in symbols:
            try:
                order_book = connector.get_order_book(symbol)
                if order_book and order_book.best_bid_price and order_book.best_ask_price:
                    mid_price = (order_book.best_bid_price + order_book.best_ask_price) / 2
                    self.price_history[symbol].append({
                        "price": mid_price,
                        "timestamp": current_time
                    })
            except Exception as e:
                self.logger.debug(f"Error updating price for {symbol}: {e}")
                
    async def rebalance_pairs(self):
        """Rebalance pairs statistics periodically"""
        current_time = time.time()
        
        for pair in self.trading_pairs:
            pair_id = f"{pair.symbol_a}_{pair.symbol_b}"
            
            if current_time - self.last_rebalance[pair_id] > self.rebalance_frequency:
                await self._calculate_pair_statistics(pair)
                self.last_rebalance[pair_id] = current_time
                
    async def _calculate_pair_statistics(self, pair: TradingPair):
        """Calculate co-integration and mean reversion statistics for a pair"""
        try:
            # Get price series
            prices_a = [p["price"] for p in self.price_history[pair.symbol_a]]
            prices_b = [p["price"] for p in self.price_history[pair.symbol_b]]
            
            if len(prices_a) < 50 or len(prices_b) < 50:  # Need minimum history
                return
                
            # Calculate correlation
            correlation = self._calculate_correlation(prices_a, prices_b)
            pair.correlation = Decimal(str(correlation))
            
            if correlation < float(self.min_correlation):
                self.logger.debug(f"Low correlation for {pair.symbol_a}_{pair.symbol_b}: {correlation:.3f}")
                return
                
            # Calculate hedge ratio using linear regression
            hedge_ratio = self._calculate_hedge_ratio(prices_a, prices_b)
            pair.hedge_ratio = Decimal(str(hedge_ratio))
            
            # Calculate mean reversion half-life
            spreads = [float(prices_a[i]) - float(hedge_ratio) * float(prices_b[i]) 
                      for i in range(len(prices_a))]
            half_life = self._calculate_half_life(spreads)
            
            if self.min_half_life <= half_life <= self.max_half_life:
                pair.half_life = half_life
                
                # Update spread history
                pair_id = f"{pair.symbol_a}_{pair.symbol_b}"
                for i, spread in enumerate(spreads[-len(self.spread_history[pair_id]):]):
                    if i < len(self.price_history[pair.symbol_a]):
                        timestamp = self.price_history[pair.symbol_a][-(len(spreads) - i)]["timestamp"]
                        self.spread_history[pair_id].append({
                            "spread": Decimal(str(spread)),
                            "timestamp": timestamp
                        })
                        
                self.logger.info(
                    f"Updated {pair.symbol_a}_{pair.symbol_b}: "
                    f"correlation={correlation:.3f}, hedge_ratio={hedge_ratio:.4f}, "
                    f"half_life={half_life:.0f}s"
                )
            else:
                self.logger.debug(
                    f"Invalid half-life for {pair.symbol_a}_{pair.symbol_b}: {half_life:.0f}s"
                )
                
        except Exception as e:
            self.logger.error(f"Error calculating statistics for {pair.symbol_a}_{pair.symbol_b}: {e}")
            
    def _calculate_correlation(self, prices_a: List, prices_b: List) -> float:
        """Calculate Pearson correlation coefficient"""
        try:
            return float(np.corrcoef(prices_a, prices_b)[0, 1])
        except:
            return 0.0
            
    def _calculate_hedge_ratio(self, prices_a: List, prices_b: List) -> float:
        """Calculate hedge ratio using linear regression"""
        try:
            # Simple linear regression: prices_a = alpha + beta * prices_b
            prices_a_np = np.array(prices_a)
            prices_b_np = np.array(prices_b)
            
            # Add constant term for regression
            X = np.vstack([prices_b_np, np.ones(len(prices_b_np))]).T
            beta, alpha = np.linalg.lstsq(X, prices_a_np, rcond=None)[0]
            
            return float(beta)
        except:
            return 1.0
            
    def _calculate_half_life(self, spreads: List[float]) -> float:
        """Calculate mean reversion half-life using Ornstein-Uhlenbeck process"""
        try:
            spreads_np = np.array(spreads)
            spreads_lag = spreads_np[:-1]
            spreads_diff = np.diff(spreads_np)
            
            # Regression: Δspread(t) = α + β * spread(t-1) + ε(t)
            X = np.vstack([spreads_lag, np.ones(len(spreads_lag))]).T
            beta, alpha = np.linalg.lstsq(X, spreads_diff, rcond=None)[0]
            
            # Half-life = ln(2) / (-β)
            if beta < 0:
                half_life = np.log(2) / (-beta)
                return float(half_life)
            else:
                return float('inf')  # No mean reversion
        except:
            return float('inf')
            
    async def generate_signals(self):
        """Generate statistical arbitrage signals"""
        for pair in self.trading_pairs:
            try:
                signal = await self._analyze_pair_signal(pair)
                if signal:
                    await self._execute_stat_arb_signal(signal)
            except Exception as e:
                self.logger.debug(f"Error generating signal for {pair.symbol_a}_{pair.symbol_b}: {e}")
                
    async def _analyze_pair_signal(self, pair: TradingPair) -> Optional[StatArbSignal]:
        """Analyze a pair for statistical arbitrage signals"""
        pair_id = f"{pair.symbol_a}_{pair.symbol_b}"
        
        # Need sufficient correlation and valid half-life
        if pair.correlation < self.min_correlation:
            return None
            
        if not (self.min_half_life <= pair.half_life <= self.max_half_life):
            return None
            
        # Get recent spread data
        spreads = [s["spread"] for s in self.spread_history[pair_id]]
        if len(spreads) < 20:  # Need minimum history
            return None
            
        # Calculate z-score
        mean_spread = sum(spreads) / len(spreads)
        std_spread = self._calculate_std(spreads, mean_spread)
        
        if std_spread == 0:
            return None
            
        current_spread = spreads[-1]
        z_score = (current_spread - mean_spread) / std_spread
        
        # Generate signal
        signal_direction = None
        if abs(z_score) >= self.z_score_entry:
            if z_score > 0:
                signal_direction = "short_spread"  # Spread too high, expect reversion
            else:
                signal_direction = "long_spread"   # Spread too low, expect reversion
        elif abs(z_score) <= self.z_score_exit:
            if pair_id in self.active_positions:
                signal_direction = "close"
                
        if not signal_direction:
            return None
            
        # Calculate position sizes
        connector = self.connectors.get(self.connector_name)
        if not connector:
            return None
            
        # Get current prices
        book_a = connector.get_order_book(pair.symbol_a)
        book_b = connector.get_order_book(pair.symbol_b)
        
        if not book_a or not book_b:
            return None
            
        mid_a = (book_a.best_bid_price + book_a.best_ask_price) / 2
        mid_b = (book_b.best_bid_price + book_b.best_ask_price) / 2
        
        # Position sizing based on risk management
        base_size = min(
            self.max_position_size,
            self.risk_manager.get_position_size(
                pair_id, 
                abs(z_score) / Decimal("10"), 
                Decimal("10.0"),  # Available capital
                abs(z_score) / Decimal("5")  # Confidence based on z-score
            )
        )
        
        if signal_direction == "short_spread":
            # Short A, Long B (hedge_ratio * B)
            size_a = base_size
            size_b = base_size * pair.hedge_ratio
        elif signal_direction == "long_spread":
            # Long A, Short B
            size_a = base_size
            size_b = base_size * pair.hedge_ratio
        else:  # close
            # Close existing positions
            if pair_id in self.active_positions:
                position = self.active_positions[pair_id]
                size_a = position.get("size_a", Decimal("0"))
                size_b = position.get("size_b", Decimal("0"))
            else:
                return None
                
        # Calculate expected profit (simplified)
        expected_reversion = std_spread * (abs(z_score) - self.z_score_exit) / 2
        notional_a = size_a * mid_a
        expected_profit_bps = (expected_reversion / notional_a) * Decimal("10000")
        
        # Check if profitable after fees
        total_notional = notional_a + size_b * mid_b
        estimated_fees = total_notional * self.fee_model.get_effective_fee_rate(
            self.connector_name, TradeType.BUY
        ) * 2  # Round trip
        
        if expected_profit_bps * total_notional / Decimal("10000") <= estimated_fees:
            return None
            
        return StatArbSignal(
            pair=pair,
            z_score=z_score,
            spread=current_spread,
            signal_strength=abs(z_score),
            direction=signal_direction,
            size_a=size_a,
            size_b=size_b,
            expected_profit_bps=expected_profit_bps
        )
        
    def _calculate_std(self, values: List[Decimal], mean: Decimal) -> Decimal:
        """Calculate standard deviation"""
        if len(values) <= 1:
            return Decimal("0")
            
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return variance ** Decimal("0.5")
        
    async def _execute_stat_arb_signal(self, signal: StatArbSignal):
        """Execute a statistical arbitrage signal"""
        
        # Check risk limits
        can_trade, violations = self.risk_manager.check_risk_limits()
        if not can_trade:
            self.logger.warning(f"Risk limits violated: {violations}")
            return
            
        pair_id = f"{signal.pair.symbol_a}_{signal.pair.symbol_b}"
        
        self.logger.info(
            f"Executing stat arb signal for {pair_id}: "
            f"direction={signal.direction}, z_score={signal.z_score:.2f}, "
            f"expected_profit={signal.expected_profit_bps:.2f}bps"
        )
        
        try:
            if signal.direction == "close":
                await self._close_stat_arb_position(pair_id)
            else:
                await self._open_stat_arb_position(signal)
                
        except Exception as e:
            self.logger.error(f"Error executing stat arb signal: {e}")
            
    async def _open_stat_arb_position(self, signal: StatArbSignal):
        """Open a new statistical arbitrage position"""
        pair_id = f"{signal.pair.symbol_a}_{signal.pair.symbol_b}"
        
        # Track the position
        self.active_positions[pair_id] = {
            "signal": signal,
            "entry_time": time.time(),
            "entry_z_score": signal.z_score,
            "size_a": signal.size_a,
            "size_b": signal.size_b,
            "direction": signal.direction
        }
        
        # This would create actual orders through executors
        # For now, just log the intended trades
        self.logger.info(f"Opened stat arb position {pair_id}")
        
    async def _close_stat_arb_position(self, pair_id: str):
        """Close an existing statistical arbitrage position"""
        if pair_id not in self.active_positions:
            return
            
        position = self.active_positions[pair_id]
        
        # Calculate PnL (simplified)
        holding_time = time.time() - position["entry_time"]
        estimated_pnl = position["size_a"] * Decimal("0.001")  # Placeholder
        
        # Record trade
        self.risk_manager.record_trade(
            symbol=pair_id,
            pnl=estimated_pnl,
            size=position["size_a"],
            success=True
        )
        
        del self.active_positions[pair_id]
        
        self.logger.info(
            f"Closed stat arb position {pair_id} after {holding_time:.0f}s, "
            f"estimated PnL: {estimated_pnl:.6f}"
        )
        
    async def manage_positions(self):
        """Manage existing statistical arbitrage positions"""
        current_time = time.time()
        
        for pair_id, position in list(self.active_positions.items()):
            try:
                # Check for stop loss
                signal = position["signal"]
                
                # Get current z-score
                pair = signal.pair
                spreads = [s["spread"] for s in self.spread_history[pair_id]]
                if len(spreads) < 2:
                    continue
                    
                mean_spread = sum(spreads) / len(spreads)
                std_spread = self._calculate_std(spreads, mean_spread)
                current_z_score = (spreads[-1] - mean_spread) / std_spread if std_spread > 0 else Decimal("0")
                
                # Check stop loss
                if abs(current_z_score) >= self.z_score_stop:
                    self.logger.warning(f"Stop loss triggered for {pair_id}, z-score: {current_z_score:.2f}")
                    await self._close_stat_arb_position(pair_id)
                    continue
                    
                # Check time-based exit (positions shouldn't be held too long)
                max_holding_time = signal.pair.half_life * 3  # 3x half-life
                if current_time - position["entry_time"] > max_holding_time:
                    self.logger.info(f"Time-based exit for {pair_id}")
                    await self._close_stat_arb_position(pair_id)
                    
            except Exception as e:
                self.logger.error(f"Error managing position {pair_id}: {e}")
                
    def get_status(self) -> str:
        """Get controller status"""
        status_lines = [
            f"Trading pairs: {len(self.trading_pairs)}",
            f"Active positions: {len(self.active_positions)}",
        ]
        
        # Risk status
        risk_status = self.risk_manager.get_risk_status()
        status_lines.append(f"Can trade: {risk_status['can_trade']}")
        status_lines.append(f"Total PnL: {risk_status['metrics']['total_pnl']:.4f}")
        status_lines.append(f"Win rate: {risk_status['metrics']['win_rate']:.2%}")
        
        # Pair statistics
        for pair in self.trading_pairs:
            pair_id = f"{pair.symbol_a}_{pair.symbol_b}"
            history_len = len(self.spread_history[pair_id])
            status_lines.append(
                f"{pair_id}: corr={pair.correlation:.3f}, "
                f"hedge={pair.hedge_ratio:.4f}, half_life={pair.half_life:.0f}s, "
                f"history={history_len}"
            )
            
        return "\n".join(status_lines)
        
    def stop(self):
        """Stop the controller"""
        self.is_active = False
        
        # Close all positions
        for pair_id in list(self.active_positions.keys()):
            asyncio.create_task(self._close_stat_arb_position(pair_id))
            
        self.logger.info("Gate Statistical Arbitrage Controller stopped")
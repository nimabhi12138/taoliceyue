from typing import List
from typing import Optional
"""
Gate.io Spot-Perpetual Basis Arbitrage Controller
Implements cash-and-carry arbitrage between spot and perpetual markets
"""

import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from hummingbot.core.data_type.common import OrderType, PositionAction, PositionSide, TradeType
from hummingbot.smart_components.models.executor_actions import ExecutorAction, CreateExecutorAction, StopExecutorAction

from hummingbot.smart_components.controllers.controller_base import ControllerBase, ControllerConfigBase
from hummingbot.smart_components.executors.arbitrage_executor import ArbitrageExecutor
from hummingbot.smart_components.models.executors import CloseType
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.connector.connector_base import ConnectorBase
from pydantic import Field, validator

logger = logging.getLogger(__name__)


class GateSpotPerpControllerConfig(ControllerConfigBase):
    """Configuration for Spot-Perp Arbitrage Controller"""
    
    controller_name: str = "gate_spot_perp_controller"
    controller_type: str = "directional"
    spot_connector: str = Field(default="gate_io", description="Spot connector name")
    perp_connector: str = Field(default="gate_io_perpetual", description="Perpetual connector name")
    
    # Trading pairs
    symbols: List[str] = Field(
        default=["BTC-USDT", "ETH-USDT"],
        description="List of trading symbols"
    )
    
    # Arbitrage parameters
    min_basis_bps: Decimal = Field(
        default=Decimal("30"),
        description="Minimum basis in bps to trigger arbitrage (after fees)"
    )
    slippage_buffer_bps: Decimal = Field(
        default=Decimal("5"),
        description="Slippage buffer in basis points"
    )
    safety_margin_bps: Decimal = Field(
        default=Decimal("10"),
        description="Additional safety margin in bps"
    )
    
    # Position sizing
    position_size_pct: Decimal = Field(
        default=Decimal("0.1"),
        description="Position size as percentage of available balance"
    )
    max_position_usd: Decimal = Field(
        default=Decimal("10000"),
        description="Maximum position size in USD"
    )
    kelly_fraction: Decimal = Field(
        default=Decimal("0.25"),
        description="Kelly criterion fraction for sizing"
    )
    
    # Rebalancing
    rebalance_threshold: Decimal = Field(
        default=Decimal("0.02"),
        description="Delta drift threshold for rebalancing"
    )
    auto_rebalance: bool = Field(
        default=True,
        description="Enable automatic rebalancing"
    )
    
    # Funding rate
    funding_lookback_hours: int = Field(
        default=8,
        description="Hours to look back for funding rate calculation"
    )
    max_funding_rate_8h: Decimal = Field(
        default=Decimal("0.001"),
        description="Maximum acceptable 8h funding rate"
    )
    
    # Risk management
    max_open_positions: int = Field(default=3)
    stop_loss_pct: Decimal = Field(default=Decimal("0.02"))
    take_profit_pct: Decimal = Field(default=Decimal("0.01"))
    
    # Execution
    use_maker_orders: bool = Field(default=True)
    order_refresh_time: int = Field(default=30)
    max_retries: int = Field(default=3)
    
    # Fee configuration (will be overridden by conf_fee_overrides.yml)
    spot_maker_fee_bps: Decimal = Field(default=Decimal("2.5"))  # 0.025% with 75% rebate
    spot_taker_fee_bps: Decimal = Field(default=Decimal("5.0"))  # 0.05% with 75% rebate
    perp_maker_fee_bps: Decimal = Field(default=Decimal("0.5"))  # 0.005% with 75% rebate
    perp_taker_fee_bps: Decimal = Field(default=Decimal("1.5"))  # 0.015% with 75% rebate
    
    @validator("min_basis_bps")
    def validate_min_basis(cls, v) -> bool:
        if v <= 0:
            raise ValueError("min_basis_bps must be positive")
        return v


@dataclass
class ArbitrageOpportunity:
    """Represents an arbitrage opportunity"""
    symbol: str
    spot_price: Decimal
    perp_price: Decimal
    basis_bps: Decimal
    net_edge_bps: Decimal
    funding_rate: Decimal
    size: Decimal
    direction: str  # "long_spot_short_perp" or "short_spot_long_perp"
    timestamp: datetime = field(default_factory=datetime.now)


class GateSpotPerpController(ControllerBase):
    """
    Spot-Perpetual Basis Arbitrage Controller for Gate.io
    Implements cash-and-carry and reverse cash-and-carry strategies
    """
    
    def __init__(self, config: GateSpotPerpControllerConfig):
        super().__init__(config)
        self.config = config
        
        # Tracking
        self._active_executors: Dict[str, ArbitrageExecutor] = {}
        self._opportunities: List[ArbitrageOpportunity] = []
        self._last_funding_check = datetime.now()
        self._funding_rates: Dict[str, Decimal] = {}
        self._circuit_breaker_triggered = False
        self._session_pnl = Decimal("0")
        self._max_drawdown = Decimal("0")
        
        # Performance metrics
        self._total_trades = 0
        self._winning_trades = 0
        self._total_pnl_bps = Decimal("0")
        self._avg_slippage_bps = Decimal("0")
        
    async def start(self) -> None:
        """Initialize the controller"""
        await super().start()
        self.logger.info(f"Starting {self.config.controller_name}")
        
        # Load fee overrides if available
        await self._load_fee_overrides()
        
        # Start monitoring tasks
        asyncio.create_task(self._monitor_opportunities())
        asyncio.create_task(self._monitor_positions())
        asyncio.create_task(self._update_funding_rates())
        
    async def stop(self) -> None:
        """Cleanup on stop"""
        self.logger.info(f"Stopping {self.config.controller_name}")
        
        # Close all positions
        for executor in self._active_executors.values():
            if executor.is_active:
                await executor.close_position(CloseType.STOP_LOSS)
                
        await super().stop()
        
    async def _load_fee_overrides(self) -> None:
        """Load fee overrides from conf_fee_overrides.yml"""
        try:
            import yaml
            with open("conf/conf_fee_overrides.yml", "r") as f:
                overrides = yaml.safe_load(f)
                
            if "gate_io" in overrides:
                self.config.spot_maker_fee_bps = Decimal(str(overrides["gate_io"].get("maker_fee", 0.025))) * 100
                self.config.spot_taker_fee_bps = Decimal(str(overrides["gate_io"].get("taker_fee", 0.05))) * 100
                
            if "gate_io_perpetual" in overrides:
                self.config.perp_maker_fee_bps = Decimal(str(overrides["gate_io_perpetual"].get("maker_fee", 0.005))) * 100
                self.config.perp_taker_fee_bps = Decimal(str(overrides["gate_io_perpetual"].get("taker_fee", 0.015))) * 100
                
            self.logger.info(f"Loaded fee overrides: Spot maker={self.config.spot_maker_fee_bps}bps, "
                           f"Spot taker={self.config.spot_taker_fee_bps}bps, "
                           f"Perp maker={self.config.perp_maker_fee_bps}bps, "
                           f"Perp taker={self.config.perp_taker_fee_bps}bps")
        except Exception as e:
            self.logger.warning(f"Could not load fee overrides: {e}")
            
    async def _monitor_opportunities(self) -> None:
        """Monitor for arbitrage opportunities"""
        while self.is_active:
            try:
                for symbol in self.config.symbols:
                    opportunity = await self._check_opportunity(symbol)
                    if opportunity:
                        self._opportunities.append(opportunity)
                        await self._execute_opportunity(opportunity)
                        
                await asyncio.sleep(1)  # Check every second
                
            except Exception as e:
                self.logger.error(f"Error monitoring opportunities: {e}")
                await asyncio.sleep(5)
                
    async def _check_opportunity(self, symbol: str) -> Optional[ArbitrageOpportunity]:
        """Check if arbitrage opportunity exists for a symbol"""
        try:
            # Get orderbook data
            spot_connector = self.connectors[self.config.spot_connector]
            perp_connector = self.connectors[self.config.perp_connector]
            
            spot_ob = spot_connector.get_order_book(symbol)
            perp_ob = perp_connector.get_order_book(symbol)
            
            if not spot_ob or not perp_ob:
                return None
                
            # Get mid prices
            spot_mid = (spot_ob.get_price(True) + spot_ob.get_price(False)) / 2
            perp_mid = (perp_ob.get_price(True) + perp_ob.get_price(False)) / 2
            
            # Calculate basis
            basis = perp_mid - spot_mid
            basis_bps = (basis / spot_mid) * 10000
            
            # Get funding rate
            funding_rate = self._funding_rates.get(symbol, Decimal("0"))
            
            # Calculate net edge after fees
            if basis_bps > 0:  # Long spot, short perp
                direction = "long_spot_short_perp"
                if self.config.use_maker_orders:
                    total_fee_bps = self.config.spot_maker_fee_bps + self.config.perp_maker_fee_bps
                else:
                    total_fee_bps = self.config.spot_taker_fee_bps + self.config.perp_taker_fee_bps
            else:  # Short spot, long perp
                direction = "short_spot_long_perp"
                if self.config.use_maker_orders:
                    total_fee_bps = self.config.spot_maker_fee_bps + self.config.perp_maker_fee_bps
                else:
                    total_fee_bps = self.config.spot_taker_fee_bps + self.config.perp_taker_fee_bps
                    
            # Include funding in calculation
            funding_bps = funding_rate * 10000 * (self.config.funding_lookback_hours / 8)
            
            net_edge_bps = abs(basis_bps) - total_fee_bps - self.config.slippage_buffer_bps - \
                          self.config.safety_margin_bps - abs(funding_bps)
            
            # Check if opportunity is profitable
            if net_edge_bps > self.config.min_basis_bps:
                # Calculate position size
                size = await self._calculate_position_size(symbol, net_edge_bps)
                
                if size > 0:
                    return ArbitrageOpportunity(
                        symbol=symbol,
                        spot_price=spot_mid,
                        perp_price=perp_mid,
                        basis_bps=basis_bps,
                        net_edge_bps=net_edge_bps,
                        funding_rate=funding_rate,
                        size=size,
                        direction=direction
                    )
                    
        except Exception as e:
            self.logger.error(f"Error checking opportunity for {symbol}: {e}")
            
        return None
        
    async def _calculate_position_size(self, symbol: str, edge_bps: Decimal) -> Decimal:
        """Calculate position size using Kelly criterion with safety caps"""
        try:
            # Get available balance
            spot_connector = self.connectors[self.config.spot_connector]
            quote_balance = spot_connector.get_available_balance("USDT")
            
            # Kelly sizing
            win_prob = Decimal("0.65")  # Conservative estimate
            kelly_size = (win_prob * edge_bps / 10000) / (1 - win_prob)
            kelly_size = min(kelly_size, self.config.kelly_fraction)
            
            # Calculate position size
            position_size = quote_balance * self.config.position_size_pct * kelly_size
            
            # Apply caps
            position_size = min(position_size, self.config.max_position_usd)
            
            # Check minimum order size
            trading_rules = spot_connector.trading_rules.get(symbol)
            if trading_rules:
                min_notional = trading_rules.min_notional_size
                if position_size < min_notional:
                    return Decimal("0")
                    
                # Round to lot size
                lot_size = trading_rules.min_order_size
                position_size = (position_size // lot_size) * lot_size
                
            return position_size
            
        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return Decimal("0")
            
    async def _execute_opportunity(self, opportunity: ArbitrageOpportunity) -> None:
        """Execute an arbitrage opportunity"""
        try:
            # Check circuit breaker
            if self._circuit_breaker_triggered:
                self.logger.warning("Circuit breaker triggered, skipping execution")
                return
                
            # Check position limits
            if len(self._active_executors) >= self.config.max_open_positions:
                self.logger.info("Max positions reached, skipping")
                return
                
            # Create executor
            executor_id = f"{opportunity.symbol}_{datetime.now().timestamp()}"
            
            if opportunity.direction == "long_spot_short_perp":
                # Buy spot, sell perp
                executor = ArbitrageExecutor(
                    arbitrage_config={
                        "id": executor_id,
                        "buying_market": self.config.spot_connector,
                        "selling_market": self.config.perp_connector,
                        "trading_pair": opportunity.symbol,
                        "amount": opportunity.size,
                        "min_profitability": float(opportunity.net_edge_bps / 10000),
                        "use_oracle": False,
                        "take_profit": float(self.config.take_profit_pct),
                        "stop_loss": float(self.config.stop_loss_pct),
                        "time_limit": self.config.order_refresh_time,
                        "mode": "MARKET" if not self.config.use_maker_orders else "LIMIT"
                    }
                )
            else:
                # Sell spot, buy perp
                executor = ArbitrageExecutor(
                    arbitrage_config={
                        "id": executor_id,
                        "buying_market": self.config.perp_connector,
                        "selling_market": self.config.spot_connector,
                        "trading_pair": opportunity.symbol,
                        "amount": opportunity.size,
                        "min_profitability": float(opportunity.net_edge_bps / 10000),
                        "use_oracle": False,
                        "take_profit": float(self.config.take_profit_pct),
                        "stop_loss": float(self.config.stop_loss_pct),
                        "time_limit": self.config.order_refresh_time,
                        "mode": "MARKET" if not self.config.use_maker_orders else "LIMIT"
                    }
                )
                
            # Start executor
            await executor.start()
            self._active_executors[executor_id] = executor
            
            self.logger.info(f"Executed arbitrage: {opportunity.symbol} "
                           f"basis={opportunity.basis_bps:.2f}bps "
                           f"net_edge={opportunity.net_edge_bps:.2f}bps "
                           f"size=${opportunity.size:.2f}")
            
        except Exception as e:
            self.logger.error(f"Error executing opportunity: {e}")
            
    async def _monitor_positions(self) -> None:
        """Monitor and rebalance active positions"""
        while self.is_active:
            try:
                for executor_id, executor in list(self._active_executors.items()):
                    if not executor.is_active:
                        # Remove completed executors
                        self._update_metrics(executor)
                        del self._active_executors[executor_id]
                    elif self.config.auto_rebalance:
                        # Check for rebalancing needs
                        await self._check_rebalance(executor)
                        
                # Check circuit breakers
                await self._check_circuit_breakers()
                
                await asyncio.sleep(5)
                
            except Exception as e:
                self.logger.error(f"Error monitoring positions: {e}")
                await asyncio.sleep(10)
                
    async def _check_rebalance(self, executor: ArbitrageExecutor) -> None:
        """Check if position needs rebalancing"""
        try:
            # Get current positions
            spot_position = executor.get_net_pnl_quote()  # Simplified, would need actual position tracking
            perp_position = executor.get_net_pnl_quote()
            
            # Calculate delta
            delta = abs(spot_position + perp_position) / (abs(spot_position) + abs(perp_position))
            
            if delta > self.config.rebalance_threshold:
                self.logger.info(f"Rebalancing position, delta={delta:.4f}")
                # Implement rebalancing logic
                # This would involve adjusting positions to maintain delta neutrality
                
        except Exception as e:
            self.logger.error(f"Error checking rebalance: {e}")
            
    async def _update_funding_rates(self) -> None:
        """Update funding rates periodically"""
        while self.is_active:
            try:
                perp_connector = self.connectors.get(self.config.perp_connector)
                if perp_connector:
                    for symbol in self.config.symbols:
                        # Get funding rate from perpetual connector
                        # This is a simplified version - actual implementation would use connector API
                        funding_info = await perp_connector.get_funding_info(symbol)
                        if funding_info:
                            self._funding_rates[symbol] = Decimal(str(funding_info.get("rate", 0)))
                            
                await asyncio.sleep(3600)  # Update hourly
                
            except Exception as e:
                self.logger.error(f"Error updating funding rates: {e}")
                await asyncio.sleep(300)
                
    def _update_metrics(self, executor: ArbitrageExecutor) -> None:
        """Update performance metrics"""
        try:
            pnl = executor.get_net_pnl_quote()
            self._session_pnl += pnl
            self._total_trades += 1
            
            if pnl > 0:
                self._winning_trades += 1
                
            # Update average slippage
            # Simplified - would need actual slippage calculation
            
        except Exception as e:
            self.logger.error(f"Error updating metrics: {e}")
            
    async def _check_circuit_breakers(self) -> None:
        """Check if circuit breakers should be triggered"""
        try:
            # Session loss limit
            if self._session_pnl < -self.config.max_position_usd * Decimal("0.1"):
                self._circuit_breaker_triggered = True
                self.logger.warning("Circuit breaker triggered: Session loss limit reached")
                
            # Drawdown check
            if self._session_pnl < self._max_drawdown - self.config.max_position_usd * Decimal("0.05"):
                self._circuit_breaker_triggered = True
                self.logger.warning("Circuit breaker triggered: Drawdown limit reached")
                
            self._max_drawdown = min(self._max_drawdown, self._session_pnl)
            
        except Exception as e:
            self.logger.error(f"Error checking circuit breakers: {e}")
            
    def format_status(self) -> str:
        """Format controller status for display"""
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
        
        # Active positions
        lines.append(f"Active Positions: {len(self._active_executors)}")
    def to_format_status(self) -> List[str]:
        """
        V2 Framework: Format status for display
        """
        lines = []
        lines.append(f"Controller: {self.config.controller_name}")
        lines.append(f"Status: {'Active' if self.is_active else 'Inactive'}")
        return lines
        
        for executor_id, executor in self._active_executors.items():
            symbol = executor.config.trading_pair
            pnl = executor.get_net_pnl_quote()
            lines.append(f"  {symbol}: PnL=${pnl:.2f}")
            
        # Performance metrics
        win_rate = (self._winning_trades / max(self._total_trades, 1)) * 100
        lines.append(f"\nPerformance:")
        lines.append(f"  Session PnL: ${self._session_pnl:.2f}")
        lines.append(f"  Total Trades: {self._total_trades}")
        lines.append(f"  Win Rate: {win_rate:.1f}%")
        lines.append(f"  Max Drawdown: ${self._max_drawdown:.2f}")
        
        # Circuit breaker status
        lines.append(f"\nCircuit Breaker: {'TRIGGERED' if self._circuit_breaker_triggered else 'Active'}")
        
        # Recent opportunities
        if self._opportunities:
            lines.append(f"\nRecent Opportunities:")
            for opp in self._opportunities[-3:]:
                lines.append(f"  {opp.symbol}: basis={opp.basis_bps:.2f}bps edge={opp.net_edge_bps:.2f}bps")
                
        # Funding rates
        if self._funding_rates:
            lines.append(f"\nFunding Rates (8h):")
            for symbol, rate in self._funding_rates.items():
                lines.append(f"  {symbol}: {rate*100:.4f}%")
                
        return "\n".join(lines)
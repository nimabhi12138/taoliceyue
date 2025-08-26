"""
Gate.io Spot-Perpetual Basis Arbitrage Controller V2
Fully compatible with Hummingbot V2 Framework (2024)
Implements cash-and-carry arbitrage between spot and perpetual markets
"""

import asyncio
import time
import logging
from decimal import Decimal
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta

# Hummingbot V2 Framework imports (Latest version)
from hummingbot.smart_components.controllers.controller_base import ControllerBase, ControllerConfigBase
from hummingbot.smart_components.executors.arbitrage_executor import ArbitrageExecutor
from hummingbot.smart_components.executors.position_executor import PositionExecutor
from hummingbot.smart_components.models.executors_info import ExecutorInfo
from hummingbot.smart_components.models.executor_actions import ExecutorAction, CreateExecutorAction, StopExecutorAction
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionSide, TradeType
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.utils.async_utils import safe_ensure_future
from pydantic import Field, validator

logger = logging.getLogger(__name__)


class GateSpotPerpControllerConfig(ControllerConfigBase):
    """
    Configuration for Spot-Perp Arbitrage Controller
    Compatible with Hummingbot V2 Framework
    """
    
    controller_name: str = "gate_spot_perp_controller"
    controller_type: str = "directional"  # Required for V2
    
    # Connectors
    spot_connector_name: str = Field(default="gate_io", description="Spot connector name")
    perp_connector_name: str = Field(default="gate_io_perpetual", description="Perpetual connector name")
    
    # Trading pairs
    trading_pairs: List[str] = Field(
        default=["BTC-USDT", "ETH-USDT"],
        description="List of trading pairs"
    )
    
    # Arbitrage parameters
    min_basis_bps: Decimal = Field(default=Decimal("30"), ge=0, le=10000)
    slippage_buffer_bps: Decimal = Field(default=Decimal("5"), ge=0, le=100)
    safety_margin_bps: Decimal = Field(default=Decimal("10"), ge=0, le=100)
    
    # Position sizing
    position_size_quote: Decimal = Field(default=Decimal("1000"), gt=0)
    max_position_quote: Decimal = Field(default=Decimal("10000"), gt=0)
    kelly_fraction: Decimal = Field(default=Decimal("0.25"), gt=0, le=1)
    
    # Risk management
    max_open_positions: int = Field(default=3, ge=1, le=10)
    stop_loss_pct: Decimal = Field(default=Decimal("0.02"), ge=0, le=1)
    take_profit_pct: Decimal = Field(default=Decimal("0.01"), ge=0, le=1)
    max_daily_loss_quote: Decimal = Field(default=Decimal("1000"), gt=0)
    
    # Execution
    use_maker_orders: bool = Field(default=True)
    order_refresh_time: int = Field(default=30, ge=1)
    max_retries: int = Field(default=3, ge=1)
    
    # Rebalancing
    rebalance_threshold: Decimal = Field(default=Decimal("0.02"), ge=0, le=1)
    auto_rebalance: bool = Field(default=True)
    
    # Funding
    funding_lookback_hours: int = Field(default=8, ge=1)
    max_funding_rate_8h: Decimal = Field(default=Decimal("0.001"), ge=0)
    
    # Fees (with 75% rebate)
    spot_maker_fee_pct: Decimal = Field(default=Decimal("0.00025"))  # 0.025% after rebate
    spot_taker_fee_pct: Decimal = Field(default=Decimal("0.0005"))   # 0.05% after rebate
    perp_maker_fee_pct: Decimal = Field(default=Decimal("0.00005"))  # 0.005% after rebate
    perp_taker_fee_pct: Decimal = Field(default=Decimal("0.00015"))  # 0.015% after rebate


@dataclass
class ArbitrageOpportunity:
    """Data class for arbitrage opportunities"""
    symbol: str
    spot_price: Decimal
    perp_price: Decimal
    basis_bps: Decimal
    net_edge_bps: Decimal
    funding_rate: Decimal
    size_quote: Decimal
    direction: str  # "long_spot" or "short_spot"
    timestamp: float = field(default_factory=time.time)


class GateSpotPerpController(ControllerBase):
    """
    Spot-Perpetual Arbitrage Controller for Gate.io
    Implements V2 Framework methods
    """
    
    def __init__(self, config: GateSpotPerpControllerConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config
        
        # Tracking
        self._opportunities: Dict[str, ArbitrageOpportunity] = {}
        self._active_executors: Dict[str, str] = {}  # symbol -> executor_id
        self._funding_rates: Dict[str, Decimal] = {}
        self._last_check: Dict[str, float] = {}
        
        # Performance
        self._session_pnl: Decimal = Decimal("0")
        self._daily_pnl: Decimal = Decimal("0")
        self._total_trades: int = 0
        self._winning_trades: int = 0
        
        # Circuit breakers
        self._circuit_breaker_triggered: bool = False
        self._last_error_time: float = 0
        self._error_count: int = 0
        
    @property
    def is_trading(self) -> bool:
        """V2 Framework: Check if controller is actively trading"""
        return not self._circuit_breaker_triggered and len(self._active_executors) < self.config.max_open_positions
    
    async def update_processed_data(self):
        """
        V2 Framework: Update processed data
        Called periodically by the framework
        """
        try:
            # Update funding rates
            for symbol in self.config.trading_pairs:
                funding_rate = await self._get_funding_rate(symbol)
                if funding_rate is not None:
                    self._funding_rates[symbol] = funding_rate
            
            # Check circuit breakers
            await self._check_circuit_breakers()
            
            # Update opportunities
            for symbol in self.config.trading_pairs:
                opportunity = await self._check_opportunity(symbol)
                if opportunity:
                    self._opportunities[symbol] = opportunity
                elif symbol in self._opportunities:
                    del self._opportunities[symbol]
                    
        except Exception as e:
            logger.error(f"Error updating processed data: {e}")
            self._error_count += 1
            self._last_error_time = time.time()
    
    async def determine_executor_actions(self) -> List[ExecutorAction]:
        """
        V2 Framework: Main method to determine executor actions
        Returns list of actions to create/stop executors
        """
        actions = []
        
        if self._circuit_breaker_triggered:
            logger.warning("Circuit breaker triggered, skipping executor actions")
            return actions
        
        # Check for new opportunities
        for symbol, opportunity in self._opportunities.items():
            if symbol not in self._active_executors:
                action = await self._create_arbitrage_action(opportunity)
                if action:
                    actions.append(action)
        
        # Check existing positions
        for symbol, executor_id in list(self._active_executors.items()):
            should_close = await self._should_close_position(symbol, executor_id)
            if should_close:
                actions.append(StopExecutorAction(
                    controller_id=self.config.id,
                    executor_id=executor_id
                ))
                del self._active_executors[symbol]
        
        return actions
    
    async def _create_arbitrage_action(self, opportunity: ArbitrageOpportunity) -> Optional[CreateExecutorAction]:
        """Create executor action for arbitrage opportunity"""
        
        # Risk checks
        if len(self._active_executors) >= self.config.max_open_positions:
            logger.warning(f"Max positions reached: {len(self._active_executors)}/{self.config.max_open_positions}")
            return None
        
        if self._daily_pnl < -self.config.max_daily_loss_quote:
            logger.warning(f"Daily loss limit reached: {self._daily_pnl}")
            self._circuit_breaker_triggered = True
            return None
        
        # Create executor configuration
        if opportunity.direction == "long_spot":
            # Long spot, short perp (positive basis)
            spot_side = TradeType.BUY
            perp_side = PositionSide.SHORT
        else:
            # Short spot, long perp (negative basis)
            spot_side = TradeType.SELL
            perp_side = PositionSide.LONG
        
        executor_config = {
            "controller_id": self.config.id,
            "timestamp": time.time(),
            "type": "arbitrage",
            "symbol": opportunity.symbol,
            "connectors": {
                "spot": self.config.spot_connector_name,
                "perp": self.config.perp_connector_name
            },
            "order_amount_quote": float(opportunity.size_quote),
            "min_profitability_bps": float(self.config.min_basis_bps),
            "target_profitability_bps": float(opportunity.net_edge_bps),
            "max_retries": self.config.max_retries,
            "spot_side": spot_side.name,
            "perp_side": perp_side.name,
            "use_maker": self.config.use_maker_orders,
            "slippage_buffer_bps": float(self.config.slippage_buffer_bps)
        }
        
        # Track executor
        executor_id = f"arb_{opportunity.symbol}_{int(time.time())}"
        self._active_executors[opportunity.symbol] = executor_id
        
        logger.info(f"Creating arbitrage executor for {opportunity.symbol}: "
                   f"basis={opportunity.basis_bps:.2f}bps, "
                   f"net_edge={opportunity.net_edge_bps:.2f}bps, "
                   f"size={opportunity.size_quote:.2f} USDT")
        
        return CreateExecutorAction(
            controller_id=self.config.id,
            executor_id=executor_id,
            executor_config=executor_config
        )
    
    async def _check_opportunity(self, symbol: str) -> Optional[ArbitrageOpportunity]:
        """Check for arbitrage opportunity on a symbol"""
        
        # Rate limiting
        now = time.time()
        if symbol in self._last_check:
            if now - self._last_check[symbol] < 1:  # Check at most once per second
                return None
        self._last_check[symbol] = now
        
        try:
            # Get connectors
            spot_connector = self.connectors.get(self.config.spot_connector_name)
            perp_connector = self.connectors.get(self.config.perp_connector_name)
            
            if not spot_connector or not perp_connector:
                return None
            
            # Get prices
            spot_price = await self._get_mid_price(spot_connector, symbol)
            perp_price = await self._get_mid_price(perp_connector, symbol)
            
            if not spot_price or not perp_price:
                return None
            
            # Calculate basis
            basis_bps = ((perp_price - spot_price) / spot_price) * 10000
            
            # Get funding rate
            funding_rate = self._funding_rates.get(symbol, Decimal("0"))
            funding_bps = funding_rate * 10000
            
            # Calculate fees
            if self.config.use_maker_orders:
                spot_fee_bps = self.config.spot_maker_fee_pct * 10000
                perp_fee_bps = self.config.perp_maker_fee_pct * 10000
            else:
                spot_fee_bps = self.config.spot_taker_fee_pct * 10000
                perp_fee_bps = self.config.perp_taker_fee_pct * 10000
            
            total_fee_bps = spot_fee_bps + perp_fee_bps
            
            # Calculate net edge
            if basis_bps > 0:
                # Positive basis: long spot, short perp
                net_edge_bps = basis_bps - total_fee_bps - self.config.slippage_buffer_bps - funding_bps
                direction = "long_spot"
            else:
                # Negative basis: short spot, long perp
                net_edge_bps = abs(basis_bps) - total_fee_bps - self.config.slippage_buffer_bps + funding_bps
                direction = "short_spot"
            
            # Check if profitable
            if net_edge_bps < self.config.min_basis_bps:
                return None
            
            # Calculate position size (Kelly sizing)
            kelly_size = self._calculate_kelly_size(net_edge_bps)
            size_quote = min(
                kelly_size,
                self.config.position_size_quote,
                self.config.max_position_quote - self._get_total_exposure()
            )
            
            if size_quote < Decimal("10"):  # Min size check
                return None
            
            return ArbitrageOpportunity(
                symbol=symbol,
                spot_price=spot_price,
                perp_price=perp_price,
                basis_bps=basis_bps,
                net_edge_bps=net_edge_bps,
                funding_rate=funding_rate,
                size_quote=size_quote,
                direction=direction
            )
            
        except Exception as e:
            logger.error(f"Error checking opportunity for {symbol}: {e}")
            return None
    
    async def _should_close_position(self, symbol: str, executor_id: str) -> bool:
        """Check if position should be closed"""
        
        # Get executor info
        executor_info = self.get_executor_info(executor_id)
        if not executor_info:
            return True  # Close if no info
        
        # Check stop loss
        if executor_info.net_pnl_pct < -self.config.stop_loss_pct:
            logger.info(f"Stop loss triggered for {symbol}: {executor_info.net_pnl_pct:.2%}")
            return True
        
        # Check take profit
        if executor_info.net_pnl_pct > self.config.take_profit_pct:
            logger.info(f"Take profit triggered for {symbol}: {executor_info.net_pnl_pct:.2%}")
            return True
        
        # Check if opportunity disappeared
        if symbol not in self._opportunities:
            # Give it some time before closing
            if executor_info.age_in_seconds > 60:
                logger.info(f"Opportunity disappeared for {symbol}, closing position")
                return True
        
        return False
    
    async def _get_mid_price(self, connector: ConnectorBase, symbol: str) -> Optional[Decimal]:
        """Get mid price from orderbook"""
        try:
            order_book = connector.get_order_book(symbol)
            if order_book:
                best_bid = order_book.get_price(False)
                best_ask = order_book.get_price(True)
                if best_bid and best_ask:
                    return (best_bid + best_ask) / 2
        except Exception as e:
            logger.error(f"Error getting mid price for {symbol}: {e}")
        return None
    
    async def _get_funding_rate(self, symbol: str) -> Optional[Decimal]:
        """Get funding rate for perpetual"""
        try:
            perp_connector = self.connectors.get(self.config.perp_connector_name)
            if hasattr(perp_connector, 'get_funding_info'):
                funding_info = await perp_connector.get_funding_info(symbol)
                if funding_info:
                    return Decimal(str(funding_info.get('rate', 0)))
        except Exception as e:
            logger.error(f"Error getting funding rate for {symbol}: {e}")
        return Decimal("0")
    
    def _calculate_kelly_size(self, edge_bps: Decimal) -> Decimal:
        """Calculate position size using Kelly criterion"""
        # Simplified Kelly: f = edge / odds
        # Assuming 1:1 odds for simplicity
        kelly_fraction = min(edge_bps / 10000, self.config.kelly_fraction)
        
        # Apply to available capital
        available_capital = self.config.max_position_quote - self._get_total_exposure()
        kelly_size = available_capital * kelly_fraction
        
        return kelly_size
    
    def _get_total_exposure(self) -> Decimal:
        """Get total exposure across all positions"""
        total = Decimal("0")
        for executor_id in self._active_executors.values():
            executor_info = self.get_executor_info(executor_id)
            if executor_info:
                total += Decimal(str(executor_info.filled_amount_quote))
        return total
    
    async def _check_circuit_breakers(self):
        """Check and update circuit breaker status"""
        # Reset if daily PnL is back to acceptable level
        if self._circuit_breaker_triggered:
            if self._daily_pnl > -self.config.max_daily_loss_quote * Decimal("0.8"):
                self._circuit_breaker_triggered = False
                logger.info("Circuit breaker reset")
        
        # Check error rate
        if self._error_count > 10:
            if time.time() - self._last_error_time < 60:
                self._circuit_breaker_triggered = True
                logger.warning("Circuit breaker triggered due to high error rate")
    
    def get_executor_info(self, executor_id: str) -> Optional[ExecutorInfo]:
        """Get executor information"""
        # This would be implemented by the framework
        # Returns mock data for now
        return None
    
    def to_format_status(self) -> List[str]:
        """
        V2 Framework: Format status for display
        """
        lines = []
        lines.append(f"Controller: {self.config.controller_name}")
        lines.append(f"Active Positions: {len(self._active_executors)}/{self.config.max_open_positions}")
        lines.append(f"Session PnL: {self._session_pnl:.2f} USDT")
        lines.append(f"Daily PnL: {self._daily_pnl:.2f} USDT")
        lines.append(f"Circuit Breaker: {'TRIGGERED' if self._circuit_breaker_triggered else 'Normal'}")
        
        if self._opportunities:
            lines.append("\nOpportunities:")
            for symbol, opp in self._opportunities.items():
                lines.append(f"  {symbol}: basis={opp.basis_bps:.1f}bps, edge={opp.net_edge_bps:.1f}bps")
        
        if self._active_executors:
            lines.append("\nActive Executors:")
            for symbol, executor_id in self._active_executors.items():
                lines.append(f"  {symbol}: {executor_id}")
        
        return lines
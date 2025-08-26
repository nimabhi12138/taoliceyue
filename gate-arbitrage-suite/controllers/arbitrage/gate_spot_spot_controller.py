from typing import List
from typing import Optional
"""
Gate.io Spot-Spot Cross-Market Arbitrage Controller
Captures price inefficiencies across different spot markets
"""

import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.smart_components.models.executor_actions import ExecutorAction, CreateExecutorAction, StopExecutorAction

from hummingbot.smart_components.controllers.controller_base import ControllerBase, ControllerConfigBase
from hummingbot.smart_components.executors.arbitrage_executor import ArbitrageExecutor
from pydantic import Field, validator

logger = logging.getLogger(__name__)


class GateSpotSpotControllerConfig(ControllerConfigBase):
    """Configuration for Spot-Spot Arbitrage Controller"""
    
    controller_name: str = "gate_spot_spot_controller"
    controller_type: str = "directional"
    connector: str = Field(default="gate_io", description="Primary connector")
    secondary_connector: str = Field(default="gate_io", description="Secondary connector (can be same)")
    
    # Trading pairs
    symbol_pairs: List[Dict[str, str]] = Field(
        default=[
            {"primary": "BTC-USDT", "secondary": "BTC-USDC"},
            {"primary": "ETH-USDT", "secondary": "ETH-USDC"},
        ],
        description="Symbol pairs to arbitrage"
    )
    
    # Arbitrage parameters
    min_spread_bps: Decimal = Field(default=Decimal("15"))
    slippage_buffer_bps: Decimal = Field(default=Decimal("5"))
    
    # Position sizing
    position_size_pct: Decimal = Field(default=Decimal("0.1"))
    max_position_usd: Decimal = Field(default=Decimal("5000"))
    
    # Execution
    use_maker_orders: bool = Field(default=True)
    order_refresh_time: int = Field(default=30)
    
    # Risk management
    max_open_positions: int = Field(default=5)
    
    # Fee configuration
    maker_fee_bps: Decimal = Field(default=Decimal("2.5"))
    taker_fee_bps: Decimal = Field(default=Decimal("5.0"))


@dataclass
class SpotArbitrageOpportunity:
    """Represents a spot-spot arbitrage opportunity"""
    primary_symbol: str
    secondary_symbol: str
    spread_bps: Decimal
    net_edge_bps: Decimal
    size: Decimal
    direction: str  # "buy_primary_sell_secondary" or vice versa
    timestamp: datetime


class GateSpotSpotController(ControllerBase):
    """
    Spot-Spot Cross-Market Arbitrage Controller
    Exploits price differences between correlated spot markets
    """
    
    def __init__(self, config: GateSpotSpotControllerConfig):
        super().__init__(config)
        self.config = config
        self._active_executors: Dict[str, ArbitrageExecutor] = {}
        self._opportunities: List[SpotArbitrageOpportunity] = []
        self._total_pnl = Decimal("0")
        self._total_trades = 0
        
    async def start(self) -> None:
        """Initialize the controller"""
        await super().start()
        self.logger.info(f"Starting {self.config.controller_name}")
        await self._load_fee_overrides()
        asyncio.create_task(self._monitor_opportunities())
        asyncio.create_task(self._monitor_positions())
        
    async def stop(self) -> None:
        """Cleanup on stop"""
        self.logger.info(f"Stopping {self.config.controller_name}")
        for executor in self._active_executors.values():
            if executor.is_active:
                await executor.early_stop()
        await super().stop()
        
    async def _load_fee_overrides(self) -> None:
        """Load fee overrides from conf_fee_overrides.yml"""
        try:
            import yaml
            with open("conf/conf_fee_overrides.yml", "r") as f:
                overrides = yaml.safe_load(f)
            
            if self.config.connector in overrides:
                fees = overrides[self.config.connector]
                self.config.maker_fee_bps = Decimal(str(fees.get("maker_fee", 0.025))) * 100
                self.config.taker_fee_bps = Decimal(str(fees.get("taker_fee", 0.05))) * 100
                
            self.logger.info(f"Loaded fees: maker={self.config.maker_fee_bps}bps, "
                           f"taker={self.config.taker_fee_bps}bps")
        except Exception as e:
            self.logger.warning(f"Could not load fee overrides: {e}")
            
    async def _monitor_opportunities(self) -> None:
        """Monitor for arbitrage opportunities"""
        while self.is_active:
            try:
                for pair_config in self.config.symbol_pairs:
                    opportunity = await self._check_opportunity(
                        pair_config["primary"],
                        pair_config["secondary"]
                    )
                    if opportunity and opportunity.net_edge_bps > self.config.min_spread_bps:
                        self._opportunities.append(opportunity)
                        await self._execute_opportunity(opportunity)
                        
                await asyncio.sleep(1)
            except Exception as e:
                self.logger.error(f"Error monitoring opportunities: {e}")
                await asyncio.sleep(5)
                
    async def _check_opportunity(self, primary_symbol: str, secondary_symbol: str) -> Optional[SpotArbitrageOpportunity]:
        """Check if arbitrage opportunity exists between two symbols"""
        try:
            primary_conn = self.connectors[self.config.connector]
            secondary_conn = self.connectors[self.config.secondary_connector]
            
            # Get orderbooks
            primary_ob = primary_conn.get_order_book(primary_symbol)
            secondary_ob = secondary_conn.get_order_book(secondary_symbol)
            
            if not primary_ob or not secondary_ob:
                return None
                
            # Get mid prices
            primary_mid = (primary_ob.get_price(True) + primary_ob.get_price(False)) / 2
            secondary_mid = (secondary_ob.get_price(True) + secondary_ob.get_price(False)) / 2
            
            # Calculate spread
            spread = abs(primary_mid - secondary_mid)
            spread_bps = (spread / min(primary_mid, secondary_mid)) * 10000
            
            # Calculate net edge after fees
            fee_bps = self.config.taker_fee_bps * 2 if not self.config.use_maker_orders else self.config.maker_fee_bps * 2
            net_edge_bps = spread_bps - fee_bps - self.config.slippage_buffer_bps
            
            if net_edge_bps > 0:
                # Determine direction
                if primary_mid > secondary_mid:
                    direction = "sell_primary_buy_secondary"
                else:
                    direction = "buy_primary_sell_secondary"
                    
                # Calculate position size
                size = await self._calculate_position_size(primary_symbol, net_edge_bps)
                
                if size > 0:
                    return SpotArbitrageOpportunity(
                        primary_symbol=primary_symbol,
                        secondary_symbol=secondary_symbol,
                        spread_bps=spread_bps,
                        net_edge_bps=net_edge_bps,
                        size=size,
                        direction=direction,
                        timestamp=datetime.now()
                    )
                    
        except Exception as e:
            self.logger.error(f"Error checking opportunity: {e}")
            
        return None
        
    async def _calculate_position_size(self, symbol: str, edge_bps: Decimal) -> Decimal:
        """Calculate position size"""
        try:
            connector = self.connectors[self.config.connector]
            balance = connector.get_available_balance("USDT")
            
            # Basic sizing with caps
            position_size = balance * self.config.position_size_pct
            position_size = min(position_size, self.config.max_position_usd)
            
            # Check minimum order size
            trading_rules = connector.trading_rules.get(symbol)
            if trading_rules:
                if position_size < trading_rules.min_notional_size:
                    return Decimal("0")
                    
            return position_size
            
        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return Decimal("0")
            
    async def _execute_opportunity(self, opportunity: SpotArbitrageOpportunity) -> None:
        """Execute arbitrage opportunity"""
        try:
            if len(self._active_executors) >= self.config.max_open_positions:
                return
                
            executor_id = f"{opportunity.primary_symbol}_{datetime.now().timestamp()}"
            
            if opportunity.direction == "buy_primary_sell_secondary":
                buying_market = self.config.connector
                buying_symbol = opportunity.primary_symbol
                selling_market = self.config.secondary_connector
                selling_symbol = opportunity.secondary_symbol
            else:
                buying_market = self.config.secondary_connector
                buying_symbol = opportunity.secondary_symbol
                selling_market = self.config.connector
                selling_symbol = opportunity.primary_symbol
                
            executor = ArbitrageExecutor(
                arbitrage_config={
                    "id": executor_id,
                    "buying_market": buying_market,
                    "selling_market": selling_market,
                    "buying_pair": buying_symbol,
                    "selling_pair": selling_symbol,
                    "amount": opportunity.size,
                    "min_profitability": float(opportunity.net_edge_bps / 10000),
                    "use_oracle": False,
                    "time_limit": self.config.order_refresh_time,
                    "mode": "LIMIT" if self.config.use_maker_orders else "MARKET"
                }
            )
            
            await executor.start()
            self._active_executors[executor_id] = executor
            self._total_trades += 1
            
            self.logger.info(f"Executed spot-spot arbitrage: {opportunity.primary_symbol} <-> "
                           f"{opportunity.secondary_symbol} spread={opportunity.spread_bps:.2f}bps")
            
        except Exception as e:
            self.logger.error(f"Error executing opportunity: {e}")
            
    async def _monitor_positions(self) -> None:
        """Monitor active positions"""
        while self.is_active:
            try:
                for executor_id, executor in list(self._active_executors.items()):
                    if not executor.is_active:
                        pnl = executor.get_net_pnl_quote()
                        self._total_pnl += pnl
                        del self._active_executors[executor_id]
                        
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
        lines.append(f"Active Positions: {len(self._active_executors)}")
    def to_format_status(self) -> List[str]:
        """
        V2 Framework: Format status for display
        """
        lines = []
        lines.append(f"Controller: {self.config.controller_name}")
        lines.append(f"Status: {'Active' if self.is_active else 'Inactive'}")
        return lines
        lines.append(f"Total PnL: ${self._total_pnl:.2f}")
        lines.append(f"Total Trades: {self._total_trades}")
        
        if self._opportunities:
            lines.append(f"\nRecent Opportunities:")
            for opp in self._opportunities[-3:]:
                lines.append(f"  {opp.primary_symbol}<->{opp.secondary_symbol}: "
                           f"spread={opp.spread_bps:.2f}bps edge={opp.net_edge_bps:.2f}bps")
                
        return "\n".join(lines)
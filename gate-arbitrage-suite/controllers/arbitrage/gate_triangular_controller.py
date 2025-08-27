from typing import List
from typing import Optional
"""
Gate.io Triangular Arbitrage Controller
Implements triangular arbitrage with net-fee edge calculation
"""

import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple, NamedTuple
from dataclasses import dataclass, field
from datetime import datetime
import networkx as nx

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.smart_components.models.executor_actions import ExecutorAction, CreateExecutorAction, StopExecutorAction

from hummingbot.smart_components.controllers.controller_base import ControllerBase, ControllerConfigBase
from hummingbot.smart_components.executors.position_executor import PositionExecutor
from hummingbot.core.event.events import OrderFilledEvent, OrderCancelledEvent
from hummingbot.connector.connector_base import ConnectorBase
from pydantic import Field, validator

logger = logging.getLogger(__name__)


class TriangularPath(NamedTuple):
    """Represents a triangular arbitrage path"""
    path: List[str]  # e.g., ["USDT", "BTC", "ETH", "USDT"]
    pairs: List[str]  # e.g., ["BTC-USDT", "ETH-BTC", "ETH-USDT"]
    sides: List[str]  # e.g., ["buy", "sell", "sell"]
    prices: List[Decimal]
    sizes: List[Decimal]
    net_profit_bps: Decimal
    min_size_usd: Decimal


class GateTriangularControllerConfig(ControllerConfigBase):
    """Configuration for Triangular Arbitrage Controller"""
    
    controller_name: str = "gate_triangular_controller"
    controller_type: str = "directional"
    connector: str = Field(default="gate_io", description="Connector name")
    
    # Base currencies for triangular paths
    base_currencies: List[str] = Field(
        default=["USDT", "BTC", "ETH"],
        description="Base currencies to consider for paths"
    )
    
    # Trading symbols to monitor
    symbols: List[str] = Field(
        default=[
            "BTC-USDT", "ETH-USDT", "ETH-BTC",
            "BNB-USDT", "BNB-BTC", "BNB-ETH",
            "SOL-USDT", "SOL-BTC", "SOL-ETH"
        ],
        description="Trading pairs to include in path search"
    )
    
    # Arbitrage parameters
    min_profit_bps: Decimal = Field(
        default=Decimal("20"),
        description="Minimum profit in bps after all fees"
    )
    slippage_buffer_bps: Decimal = Field(
        default=Decimal("5"),
        description="Slippage buffer per leg"
    )
    
    # Position sizing
    position_size_pct: Decimal = Field(
        default=Decimal("0.05"),
        description="Position size as percentage of available balance"
    )
    max_position_usd: Decimal = Field(
        default=Decimal("5000"),
        description="Maximum position size in USD"
    )
    
    # Execution
    use_maker_orders: bool = Field(
        default=False,
        description="Use maker orders (slower but cheaper)"
    )
    max_execution_time: int = Field(
        default=10,
        description="Maximum time for complete execution (seconds)"
    )
    atomic_execution: bool = Field(
        default=True,
        description="Cancel all if one leg fails"
    )
    
    # Risk management
    max_concurrent_arbs: int = Field(default=2)
    cooldown_seconds: int = Field(default=5)
    max_daily_trades: int = Field(default=100)
    
    # Fee configuration (will be overridden by conf_fee_overrides.yml)
    maker_fee_bps: Decimal = Field(default=Decimal("2.5"))  # 0.025% with 75% rebate
    taker_fee_bps: Decimal = Field(default=Decimal("5.0"))  # 0.05% with 75% rebate
    
    @validator("symbols")
    def validate_symbols(cls, v) -> bool:
        if len(v) < 3:
            raise ValueError("Need at least 3 symbols for triangular arbitrage")
        return v


@dataclass
class ActiveArbitrage:
    """Track active arbitrage execution"""
    path: TriangularPath
    executors: List[PositionExecutor]
    start_time: datetime
    completed_legs: int = 0
    failed: bool = False
    pnl: Decimal = Decimal("0")


class GateTriangularController(ControllerBase):
    """
    Triangular Arbitrage Controller for Gate.io
    Finds and executes profitable triangular paths with net-fee optimization
    """
    
    def __init__(self, config: GateTriangularControllerConfig):
        super().__init__(config)
        self.config = config
        
        # Graph for path finding
        self._market_graph = nx.DiGraph()
        self._symbol_map: Dict[Tuple[str, str], str] = {}  # (base, quote) -> symbol
        
        # Tracking
        self._active_arbs: Dict[str, ActiveArbitrage] = {}
        self._completed_arbs: List[ActiveArbitrage] = []
        self._daily_trades = 0
        self._last_execution = datetime.now()
        
        # Performance metrics
        self._total_pnl = Decimal("0")
        self._successful_arbs = 0
        self._failed_arbs = 0
        self._avg_execution_time = 0
        
    async def start(self) -> None:
        """Initialize the controller"""
        await super().start()
        self.logger.info(f"Starting {self.config.controller_name}")
        
        # Load fee overrides
        await self._load_fee_overrides()
        
        # Build market graph
        self._build_market_graph()
        
        # Start monitoring
        asyncio.create_task(self._monitor_opportunities())
        asyncio.create_task(self._monitor_executions())
        
    async def stop(self) -> None:
        """Cleanup on stop"""
        self.logger.info(f"Stopping {self.config.controller_name}")
        
        # Cancel active arbitrages
        for arb_id, arb in self._active_arbs.items():
            await self._cancel_arbitrage(arb)
            
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
            
    def _build_market_graph(self) -> None:
        """Build directed graph of market relationships"""
        self._market_graph.clear()
        
        for symbol in self.config.symbols:
            parts = symbol.split("-")
            if len(parts) != 2:
                continue
                
            base, quote = parts
            
            # Add edges for both directions
            self._market_graph.add_edge(quote, base, symbol=symbol, side="buy")
            self._market_graph.add_edge(base, quote, symbol=symbol, side="sell")
            
            # Store symbol mapping
            self._symbol_map[(base, quote)] = symbol
            self._symbol_map[(quote, base)] = symbol
            
        self.logger.info(f"Built market graph with {len(self._market_graph.nodes)} currencies "
                        f"and {len(self._market_graph.edges)} edges")
        
    async def _monitor_opportunities(self) -> None:
        """Monitor for triangular arbitrage opportunities"""
        while self.is_active:
            try:
                # Check cooldown
                if (datetime.now() - self._last_execution).seconds < self.config.cooldown_seconds:
                    await asyncio.sleep(1)
                    continue
                    
                # Check daily limit
                if self._daily_trades >= self.config.max_daily_trades:
                    await asyncio.sleep(60)
                    continue
                    
                # Check concurrent limit
                if len(self._active_arbs) >= self.config.max_concurrent_arbs:
                    await asyncio.sleep(1)
                    continue
                    
                # Find opportunities
                opportunities = await self._find_opportunities()
                
                # Execute best opportunity
                if opportunities:
                    best = max(opportunities, key=lambda x: x.net_profit_bps)
                    if best.net_profit_bps > self.config.min_profit_bps:
                        await self._execute_arbitrage(best)
                        self._last_execution = datetime.now()
                        
                await asyncio.sleep(0.1)  # Fast scanning
                
            except Exception as e:
                self.logger.error(f"Error monitoring opportunities: {e}")
                await asyncio.sleep(5)
                
    async def _find_opportunities(self) -> List[TriangularPath]:
        """Find all profitable triangular paths"""
        opportunities = []
        
        try:
            connector = self.connectors[self.config.connector]
            
            # Find all triangular cycles
            for base in self.config.base_currencies:
                cycles = list(nx.simple_cycles(self._market_graph))
                triangular_cycles = [c for c in cycles if len(c) == 4 and c[0] == c[-1] == base]
                
                for cycle in triangular_cycles:
                    path = await self._evaluate_path(cycle, connector)
                    if path and path.net_profit_bps > 0:
                        opportunities.append(path)
                        
        except Exception as e:
            self.logger.error(f"Error finding opportunities: {e}")
            
        return opportunities
        
    async def _evaluate_path(self, cycle: List[str], connector: ConnectorBase) -> Optional[TriangularPath]:
        """Evaluate profitability of a triangular path"""
        try:
            pairs = []
            sides = []
            prices = []
            sizes = []
            
            # Start with 1000 USDT equivalent
            amount = Decimal("1000")
            
            for i in range(len(cycle) - 1):
                from_curr = cycle[i]
                to_curr = cycle[i + 1]
                
                # Get symbol and side
                edge_data = self._market_graph[from_curr][to_curr]
                symbol = edge_data["symbol"]
                side = edge_data["side"]
                
                pairs.append(symbol)
                sides.append(side)
                
                # Get orderbook
                ob = connector.get_order_book(symbol)
                if not ob:
                    return None
                    
                # Get price based on side
                if side == "buy":
                    price = ob.get_price(False)  # Ask price for buying
                else:
                    price = ob.get_price(True)   # Bid price for selling
                    
                prices.append(price)
                
                # Calculate output amount
                if side == "buy":
                    amount = amount / price
                else:
                    amount = amount * price
                    
                # Apply fees
                fee_bps = self.config.taker_fee_bps if not self.config.use_maker_orders else self.config.maker_fee_bps
                amount = amount * (1 - fee_bps / 10000)
                
                # Apply slippage buffer
                amount = amount * (1 - self.config.slippage_buffer_bps / 10000)
                
                sizes.append(amount)
                
            # Calculate net profit
            final_amount = amount
            net_profit = final_amount - Decimal("1000")
            net_profit_bps = (net_profit / Decimal("1000")) * 10000
            
            # Calculate minimum size based on exchange rules
            min_size_usd = await self._calculate_min_size(pairs, connector)
            
            if net_profit_bps > 0:
                return TriangularPath(
                    path=cycle,
                    pairs=pairs,
                    sides=sides,
                    prices=prices,
                    sizes=sizes,
                    net_profit_bps=net_profit_bps,
                    min_size_usd=min_size_usd
                )
                
        except Exception as e:
            self.logger.debug(f"Error evaluating path {cycle}: {e}")
            
        return None
        
    async def _calculate_min_size(self, pairs: List[str], connector: ConnectorBase) -> Decimal:
        """Calculate minimum size for the path"""
        min_size = Decimal("0")
        
        for symbol in pairs:
            rules = connector.trading_rules.get(symbol)
            if rules:
                min_size = max(min_size, rules.min_notional_size)
                
        return min_size
        
    async def _execute_arbitrage(self, path: TriangularPath) -> None:
        """Execute triangular arbitrage atomically"""
        try:
            arb_id = f"tri_{datetime.now().timestamp()}"
            executors = []
            
            # Calculate actual position size
            connector = self.connectors[self.config.connector]
            balance = connector.get_available_balance(path.path[0])
            position_size = min(
                balance * self.config.position_size_pct,
                self.config.max_position_usd,
                path.min_size_usd * Decimal("1.1")  # 10% buffer above minimum
            )
            
            if position_size < path.min_size_usd:
                self.logger.warning(f"Insufficient balance for path {path.pairs}")
                return
                
            # Create executors for each leg
            current_amount = position_size
            
            for i, (symbol, side, price) in enumerate(zip(path.pairs, path.sides, path.prices)):
                # Calculate order amount
                if side == "buy":
                    order_amount = current_amount / price
                else:
                    order_amount = current_amount
                    
                # Create executor
                executor_config = {
                    "controller_id": self.config.controller_name,
                    "trading_pair": symbol,
                    "connector_name": self.config.connector,
                    "side": TradeType.BUY if side == "buy" else TradeType.SELL,
                    "amount": order_amount,
                    "order_type": OrderType.MARKET if not self.config.use_maker_orders else OrderType.LIMIT,
                    "price": price if self.config.use_maker_orders else None,
                    "time_limit": self.config.max_execution_time
                }
                
                executor = PositionExecutor(
                    strategy=self,
                    config=executor_config
                )
                executors.append(executor)
                
                # Update amount for next leg
                if side == "buy":
                    current_amount = order_amount * price
                else:
                    current_amount = order_amount / price
                    
                # Deduct fees
                fee_bps = self.config.taker_fee_bps if not self.config.use_maker_orders else self.config.maker_fee_bps
                current_amount = current_amount * (1 - fee_bps / 10000)
                
            # Start all executors
            arb = ActiveArbitrage(
                path=path,
                executors=executors,
                start_time=datetime.now()
            )
            self._active_arbs[arb_id] = arb
            
            # Execute legs in sequence (atomic)
            for i, executor in enumerate(executors):
                await executor.start()
                
                # Wait for fill or timeout
                filled = await self._wait_for_fill(executor, self.config.max_execution_time)
                
                if not filled:
                    arb.failed = True
                    if self.config.atomic_execution:
                        # Cancel remaining legs
                        await self._cancel_arbitrage(arb)
                        self._failed_arbs += 1
                        self.logger.warning(f"Failed to execute leg {i+1} of {path.pairs}")
                        return
                        
                arb.completed_legs += 1
                
            # Mark as successful
            self._successful_arbs += 1
            self._daily_trades += 1
            
            self.logger.info(f"Executed triangular arbitrage: {' -> '.join(path.pairs)} "
                           f"profit={path.net_profit_bps:.2f}bps")
            
        except Exception as e:
            self.logger.error(f"Error executing arbitrage: {e}")
            self._failed_arbs += 1
            
    async def _wait_for_fill(self, executor: PositionExecutor, timeout: int) -> bool:
        """Wait for order to fill or timeout"""
        start_time = datetime.now()
        
        while (datetime.now() - start_time).seconds < timeout:
            if executor.is_closed:
                return True
            await asyncio.sleep(0.1)
            
        return False
        
    async def _cancel_arbitrage(self, arb: ActiveArbitrage) -> None:
        """Cancel all legs of an arbitrage"""
        for executor in arb.executors:
            if executor.is_active:
                await executor.early_stop()
                
    async def _monitor_executions(self) -> None:
        """Monitor active arbitrage executions"""
        while self.is_active:
            try:
                for arb_id, arb in list(self._active_arbs.items()):
                    # Check timeout
                    if (datetime.now() - arb.start_time).seconds > self.config.max_execution_time * 3:
                        await self._cancel_arbitrage(arb)
                        del self._active_arbs[arb_id]
                        self._completed_arbs.append(arb)
                        
                    # Check if all legs completed
                    elif arb.completed_legs == len(arb.executors):
                        # Calculate PnL
                        total_pnl = sum(e.get_net_pnl_quote() for e in arb.executors)
                        arb.pnl = total_pnl
                        self._total_pnl += total_pnl
                        
                        del self._active_arbs[arb_id]
                        self._completed_arbs.append(arb)
                        
                        # Update average execution time
                        exec_time = (datetime.now() - arb.start_time).seconds
                        self._avg_execution_time = (self._avg_execution_time + exec_time) / 2
                        
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error monitoring executions: {e}")
                await asyncio.sleep(5)
                
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
        
        # Active arbitrages
        lines.append(f"Active Arbitrages: {len(self._active_arbs)}")
    def to_format_status(self) -> List[str]:
        """
        V2 Framework: Format status for display
        """
        lines = []
        lines.append(f"Controller: {self.config.controller_name}")
        lines.append(f"Status: {'Active' if self.is_active else 'Inactive'}")
        return lines
        
        for arb_id, arb in self._active_arbs.items():
            path_str = " -> ".join(arb.path.pairs)
            progress = f"{arb.completed_legs}/{len(arb.executors)}"
            lines.append(f"  {path_str}: {progress} legs")
            
        # Performance metrics
        total_arbs = self._successful_arbs + self._failed_arbs
        success_rate = (self._successful_arbs / max(total_arbs, 1)) * 100
        
        lines.append(f"\nPerformance:")
        lines.append(f"  Total PnL: ${self._total_pnl:.2f}")
        lines.append(f"  Success Rate: {success_rate:.1f}%")
        lines.append(f"  Successful: {self._successful_arbs}")
        lines.append(f"  Failed: {self._failed_arbs}")
        lines.append(f"  Avg Execution: {self._avg_execution_time:.1f}s")
        lines.append(f"  Daily Trades: {self._daily_trades}/{self.config.max_daily_trades}")
        
        # Recent completions
        if self._completed_arbs:
            lines.append(f"\nRecent Completions:")
            for arb in self._completed_arbs[-3:]:
                path_str = " -> ".join(arb.path.pairs[:3])
                status = "SUCCESS" if not arb.failed else "FAILED"
                lines.append(f"  {path_str}: {status} PnL=${arb.pnl:.2f}")
                
        # Market graph info
        lines.append(f"\nMarket Graph:")
        lines.append(f"  Currencies: {len(self._market_graph.nodes)}")
        lines.append(f"  Trading Pairs: {len(self.config.symbols)}")
        
        return "\n".join(lines)
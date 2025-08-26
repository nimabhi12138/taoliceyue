#!/usr/bin/env python3
"""
Gate.io Triangular Arbitrage Controller
Triangular arbitrage paths (A/B, B/C, C/A) with net-fee edge optimization
"""

import asyncio
import logging
import time
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from itertools import permutations

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.strategy.strategy_v2_base import StrategyV2Base

from .fee_model import FeeModel
from .risk_manager import RiskManager


@dataclass
class TriangularPath:
    """Represents a triangular arbitrage path"""
    leg1_pair: str
    leg2_pair: str  
    leg3_pair: str
    leg1_side: TradeType  # BUY or SELL
    leg2_side: TradeType
    leg3_side: TradeType
    leg1_price: Decimal
    leg2_price: Decimal
    leg3_price: Decimal
    leg1_amount: Decimal
    leg2_amount: Decimal
    leg3_amount: Decimal
    gross_profit_pct: Decimal
    net_profit_pct: Decimal
    total_fees: Decimal
    confidence: Decimal


@dataclass
class TriangularOpportunity:
    """Triangular arbitrage opportunity"""
    path: TriangularPath
    base_currency: str
    starting_amount: Decimal
    expected_profit: Decimal
    execution_sequence: List[Dict]


class GateTriangularController(StrategyV2Base):
    """
    Gate.io Triangular Arbitrage Controller
    
    Finds and executes triangular arbitrage opportunities with optimal routing
    and maker preference for fee minimization.
    """
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Configuration
        self.connector_name = config.get("connector", "gate_io")
        self.base_currencies = config.get("base_currencies", ["USDT", "BTC", "ETH"])
        self.quote_currencies = config.get("quote_currencies", ["USDT", "BTC", "ETH", "BNB"])
        self.min_profitability_bps = Decimal(str(config.get("min_profitability_bps", "8")))
        self.max_position_size = Decimal(str(config.get("max_position_size", "1.0")))
        self.slippage_buffer_bps = Decimal(str(config.get("slippage_buffer_bps", "3")))
        self.execution_timeout = config.get("execution_timeout", 10)  # seconds
        self.min_liquidity_threshold = Decimal(str(config.get("min_liquidity_threshold", "0.1")))
        self.max_price_age_ms = config.get("max_price_age_ms", 1000)  # 1 second
        
        # Advanced config
        self.prefer_maker_orders = config.get("prefer_maker_orders", True)
        self.atomic_execution = config.get("atomic_execution", True)
        self.rollback_on_partial = config.get("rollback_on_partial", True)
        
        # Components
        self.fee_model = FeeModel(config.get("fee_override_path"))
        self.risk_manager = RiskManager(config.get("risk_config", {}))
        
        # State
        self.trading_pairs: List[str] = []
        self.triangular_paths: List[List[str]] = []
        self.active_executions: Dict[str, Dict] = {}
        self.price_cache: Dict[str, Dict] = {}
        self.last_scan_time = 0
        
        self.is_active = True
        self.name = "GateTriangularController"
        
        # Initialize trading pairs and paths
        self._initialize_trading_pairs()
        self._build_triangular_paths()
        
    def _initialize_trading_pairs(self):
        """Initialize available trading pairs"""
        connector = self.connectors.get(self.connector_name)
        if not connector:
            return
            
        # Get all available trading pairs from the connector
        try:
            all_pairs = connector.trading_pairs
            
            # Filter pairs based on our target currencies
            for pair in all_pairs:
                base, quote = pair.split("-")
                if (base in self.base_currencies or base in self.quote_currencies) and \
                   (quote in self.base_currencies or quote in self.quote_currencies):
                    self.trading_pairs.append(pair)
                    
            self.logger.info(f"Initialized {len(self.trading_pairs)} trading pairs")
            
        except Exception as e:
            self.logger.error(f"Error initializing trading pairs: {e}")
            
    def _build_triangular_paths(self):
        """Build all possible triangular arbitrage paths"""
        currencies = list(set(self.base_currencies + self.quote_currencies))
        
        # Generate all triangular combinations
        for base_curr in currencies:
            for intermediate_curr in currencies:
                for quote_curr in currencies:
                    if len(set([base_curr, intermediate_curr, quote_curr])) == 3:
                        # Check if all required pairs exist
                        pair1 = f"{base_curr}-{intermediate_curr}"
                        pair2 = f"{intermediate_curr}-{quote_curr}"
                        pair3 = f"{quote_curr}-{base_curr}"
                        
                        # Also check reverse pairs
                        pair1_rev = f"{intermediate_curr}-{base_curr}"
                        pair2_rev = f"{quote_curr}-{intermediate_curr}"
                        pair3_rev = f"{base_curr}-{quote_curr}"
                        
                        # Find valid path
                        valid_path = self._find_valid_path([
                            (pair1, pair1_rev),
                            (pair2, pair2_rev),
                            (pair3, pair3_rev)
                        ])
                        
                        if valid_path:
                            self.triangular_paths.append(valid_path)
                            
        self.logger.info(f"Built {len(self.triangular_paths)} triangular paths")
        
    def _find_valid_path(self, pair_options: List[Tuple[str, str]]) -> Optional[List[str]]:
        """Find a valid triangular path from pair options"""
        for combo in [(0, 0, 0), (0, 0, 1), (0, 1, 0), (0, 1, 1),
                      (1, 0, 0), (1, 0, 1), (1, 1, 0), (1, 1, 1)]:
            path = [pair_options[i][combo[i]] for i in range(3)]
            if all(pair in self.trading_pairs for pair in path):
                return path
        return None
        
    async def process_tick(self):
        """Main processing loop"""
        try:
            # Update price cache
            await self.update_price_cache()
            
            # Scan for opportunities
            await self.scan_opportunities()
            
            # Manage active executions
            await self.manage_executions()
            
        except Exception as e:
            self.logger.error(f"Error in process_tick: {e}")
            
    async def update_price_cache(self):
        """Update price cache for all trading pairs"""
        if time.time() - self.last_scan_time < 0.1:  # Update every 100ms
            return
            
        connector = self.connectors.get(self.connector_name)
        if not connector:
            return
            
        current_time = time.time() * 1000  # milliseconds
        
        for pair in self.trading_pairs:
            try:
                order_book = connector.get_order_book(pair)
                if order_book and order_book.best_bid_price and order_book.best_ask_price:
                    self.price_cache[pair] = {
                        "bid": order_book.best_bid_price,
                        "ask": order_book.best_ask_price,
                        "bid_size": order_book.best_bid_entries[0].amount if order_book.best_bid_entries else Decimal("0"),
                        "ask_size": order_book.best_ask_entries[0].amount if order_book.best_ask_entries else Decimal("0"),
                        "timestamp": current_time
                    }
            except Exception as e:
                self.logger.debug(f"Error updating price for {pair}: {e}")
                
        self.last_scan_time = time.time()
        
    async def scan_opportunities(self):
        """Scan for triangular arbitrage opportunities"""
        current_time = time.time() * 1000
        
        for path in self.triangular_paths:
            try:
                opportunity = await self.analyze_triangular_path(path, current_time)
                if opportunity and opportunity.expected_profit > 0:
                    await self.execute_triangular_opportunity(opportunity)
            except Exception as e:
                self.logger.debug(f"Error analyzing path {path}: {e}")
                
    async def analyze_triangular_path(
        self, 
        path: List[str], 
        current_time: float
    ) -> Optional[TriangularOpportunity]:
        """Analyze a triangular path for arbitrage opportunity"""
        
        # Check if price data is fresh
        for pair in path:
            price_data = self.price_cache.get(pair)
            if not price_data or (current_time - price_data["timestamp"]) > self.max_price_age_ms:
                return None
                
        # Try both directions (starting with different currencies)
        best_opportunity = None
        
        for base_currency in self.base_currencies:
            opportunity = self._calculate_triangular_profit(path, base_currency)
            if opportunity and (not best_opportunity or 
                              opportunity.expected_profit > best_opportunity.expected_profit):
                best_opportunity = opportunity
                
        return best_opportunity
        
    def _calculate_triangular_profit(
        self, 
        path: List[str], 
        base_currency: str
    ) -> Optional[TriangularOpportunity]:
        """Calculate profit for a triangular path starting with base currency"""
        
        try:
            starting_amount = self.max_position_size
            current_amount = starting_amount
            current_currency = base_currency
            
            execution_sequence = []
            total_fees = Decimal("0")
            
            # Simulate execution through the triangle
            for i, pair in enumerate(path):
                pair_base, pair_quote = pair.split("-")
                price_data = self.price_cache.get(pair)
                
                if not price_data:
                    return None
                    
                # Determine trade direction
                if current_currency == pair_base:
                    # Sell base for quote
                    side = TradeType.SELL
                    price = price_data["bid"]
                    available_size = price_data["bid_size"]
                    next_currency = pair_quote
                    next_amount = current_amount * price
                elif current_currency == pair_quote:
                    # Buy base with quote
                    side = TradeType.BUY
                    price = price_data["ask"]
                    available_size = price_data["ask_size"]
                    next_currency = pair_base
                    next_amount = current_amount / price
                else:
                    # Can't trade this pair with current currency
                    return None
                    
                # Check liquidity
                required_size = current_amount if side == TradeType.SELL else current_amount / price
                if available_size < required_size:
                    return None
                    
                # Calculate fees
                trade_type = TradeType.BUY if self.prefer_maker_orders else TradeType.SELL  # Simplified
                fee = self.fee_model.calculate_trading_cost(
                    connector=self.connector_name,
                    trade_type=trade_type,
                    amount=required_size,
                    price=price
                )
                
                total_fees += fee
                next_amount -= fee  # Subtract fee from proceeds
                
                execution_sequence.append({
                    "pair": pair,
                    "side": side,
                    "price": price,
                    "amount": required_size,
                    "fee": fee
                })
                
                current_amount = next_amount
                current_currency = next_currency
                
            # Check if we end up with the starting currency
            if current_currency != base_currency:
                return None
                
            # Calculate profit
            final_amount = current_amount
            gross_profit = final_amount - starting_amount
            profit_pct = (gross_profit / starting_amount) * Decimal("100")
            
            # Apply slippage buffer
            effective_profit_pct = profit_pct - (self.slippage_buffer_bps / Decimal("100"))
            
            if effective_profit_pct < (self.min_profitability_bps / Decimal("100")):
                return None
                
            # Build triangular path object
            triangular_path = TriangularPath(
                leg1_pair=path[0],
                leg2_pair=path[1],
                leg3_pair=path[2],
                leg1_side=execution_sequence[0]["side"],
                leg2_side=execution_sequence[1]["side"],
                leg3_side=execution_sequence[2]["side"],
                leg1_price=execution_sequence[0]["price"],
                leg2_price=execution_sequence[1]["price"],
                leg3_price=execution_sequence[2]["price"],
                leg1_amount=execution_sequence[0]["amount"],
                leg2_amount=execution_sequence[1]["amount"],
                leg3_amount=execution_sequence[2]["amount"],
                gross_profit_pct=profit_pct,
                net_profit_pct=effective_profit_pct,
                total_fees=total_fees,
                confidence=Decimal("0.7")  # Base confidence
            )
            
            return TriangularOpportunity(
                path=triangular_path,
                base_currency=base_currency,
                starting_amount=starting_amount,
                expected_profit=gross_profit,
                execution_sequence=execution_sequence
            )
            
        except Exception as e:
            self.logger.debug(f"Error calculating triangular profit: {e}")
            return None
            
    async def execute_triangular_opportunity(self, opportunity: TriangularOpportunity):
        """Execute a triangular arbitrage opportunity"""
        
        # Check risk limits
        can_trade, violations = self.risk_manager.check_risk_limits()
        if not can_trade:
            self.logger.warning(f"Risk limits violated: {violations}")
            return
            
        execution_id = f"tri_{int(time.time() * 1000)}"
        
        self.logger.info(
            f"Executing triangular arbitrage {execution_id}: "
            f"profit={opportunity.expected_profit:.6f} "
            f"({opportunity.path.net_profit_pct:.3f}%)"
        )
        
        try:
            if self.atomic_execution:
                await self._execute_atomic_triangular(execution_id, opportunity)
            else:
                await self._execute_sequential_triangular(execution_id, opportunity)
                
        except Exception as e:
            self.logger.error(f"Error executing triangular opportunity: {e}")
            await self._rollback_execution(execution_id)
            
    async def _execute_atomic_triangular(self, execution_id: str, opportunity: TriangularOpportunity):
        """Execute triangular arbitrage atomically"""
        connector = self.connectors.get(self.connector_name)
        if not connector:
            return
            
        # Track execution
        self.active_executions[execution_id] = {
            "opportunity": opportunity,
            "start_time": time.time(),
            "status": "executing",
            "orders": [],
            "completed_legs": 0
        }
        
        # Execute all legs simultaneously (if exchange supports it)
        tasks = []
        for i, leg in enumerate(opportunity.execution_sequence):
            task = self._execute_leg(execution_id, i, leg, connector)
            tasks.append(task)
            
        # Wait for all legs to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check results
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        
        if success_count == len(opportunity.execution_sequence):
            # All legs successful
            await self._complete_triangular_execution(execution_id, True)
        else:
            # Some legs failed - rollback
            self.logger.warning(f"Triangular execution {execution_id} failed, rolling back")
            await self._rollback_execution(execution_id)
            
    async def _execute_sequential_triangular(self, execution_id: str, opportunity: TriangularOpportunity):
        """Execute triangular arbitrage sequentially"""
        connector = self.connectors.get(self.connector_name)
        if not connector:
            return
            
        # Track execution
        self.active_executions[execution_id] = {
            "opportunity": opportunity,
            "start_time": time.time(),
            "status": "executing",
            "orders": [],
            "completed_legs": 0
        }
        
        # Execute legs sequentially
        for i, leg in enumerate(opportunity.execution_sequence):
            try:
                success = await self._execute_leg(execution_id, i, leg, connector)
                if success:
                    self.active_executions[execution_id]["completed_legs"] += 1
                else:
                    # Leg failed - rollback previous legs if needed
                    if self.rollback_on_partial:
                        await self._rollback_execution(execution_id)
                    return
                    
            except Exception as e:
                self.logger.error(f"Error executing leg {i}: {e}")
                if self.rollback_on_partial:
                    await self._rollback_execution(execution_id)
                return
                
        # All legs completed
        await self._complete_triangular_execution(execution_id, True)
        
    async def _execute_leg(
        self, 
        execution_id: str, 
        leg_index: int, 
        leg: Dict, 
        connector: ConnectorBase
    ) -> bool:
        """Execute a single leg of triangular arbitrage"""
        try:
            order_type = OrderType.LIMIT_MAKER if self.prefer_maker_orders else OrderType.MARKET
            
            if leg["side"] == TradeType.BUY:
                order_id = connector.buy(
                    trading_pair=leg["pair"],
                    amount=leg["amount"],
                    order_type=order_type,
                    price=leg["price"] if order_type == OrderType.LIMIT_MAKER else None
                )
            else:
                order_id = connector.sell(
                    trading_pair=leg["pair"],
                    amount=leg["amount"],
                    order_type=order_type,
                    price=leg["price"] if order_type == OrderType.LIMIT_MAKER else None
                )
                
            # Track the order
            self.active_executions[execution_id]["orders"].append({
                "leg_index": leg_index,
                "order_id": order_id,
                "pair": leg["pair"],
                "side": leg["side"],
                "amount": leg["amount"],
                "price": leg["price"]
            })
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error executing leg {leg_index}: {e}")
            return False
            
    async def _complete_triangular_execution(self, execution_id: str, success: bool):
        """Complete triangular execution and record results"""
        if execution_id not in self.active_executions:
            return
            
        execution = self.active_executions[execution_id]
        opportunity = execution["opportunity"]
        
        # Calculate actual PnL (simplified)
        actual_pnl = opportunity.expected_profit if success else Decimal("0")
        
        # Record trade
        self.risk_manager.record_trade(
            symbol=opportunity.path.leg1_pair,  # Use first pair as symbol
            pnl=actual_pnl,
            size=opportunity.starting_amount,
            success=success
        )
        
        execution["status"] = "completed" if success else "failed"
        execution["end_time"] = time.time()
        execution["pnl"] = actual_pnl
        
        self.logger.info(
            f"Triangular execution {execution_id} {'completed' if success else 'failed'}: "
            f"PnL={actual_pnl:.6f}"
        )
        
        # Clean up after some time
        asyncio.create_task(self._cleanup_execution(execution_id, delay=60))
        
    async def _rollback_execution(self, execution_id: str):
        """Rollback a failed triangular execution"""
        if execution_id not in self.active_executions:
            return
            
        execution = self.active_executions[execution_id]
        connector = self.connectors.get(self.connector_name)
        
        if not connector:
            return
            
        # Cancel all pending orders
        for order in execution["orders"]:
            try:
                connector.cancel(order["pair"], order["order_id"])
            except Exception as e:
                self.logger.error(f"Error canceling order {order['order_id']}: {e}")
                
        execution["status"] = "rolled_back"
        self.logger.warning(f"Rolled back triangular execution {execution_id}")
        
    async def _cleanup_execution(self, execution_id: str, delay: int = 60):
        """Clean up execution record after delay"""
        await asyncio.sleep(delay)
        if execution_id in self.active_executions:
            del self.active_executions[execution_id]
            
    async def manage_executions(self):
        """Manage active executions and timeouts"""
        current_time = time.time()
        
        for execution_id, execution in list(self.active_executions.items()):
            if execution["status"] == "executing":
                elapsed = current_time - execution["start_time"]
                if elapsed > self.execution_timeout:
                    self.logger.warning(f"Triangular execution {execution_id} timed out")
                    await self._rollback_execution(execution_id)
                    
    def get_status(self) -> str:
        """Get controller status"""
        status_lines = [
            f"Trading pairs: {len(self.trading_pairs)}",
            f"Triangular paths: {len(self.triangular_paths)}",
            f"Active executions: {len(self.active_executions)}",
        ]
        
        # Risk status
        risk_status = self.risk_manager.get_risk_status()
        status_lines.append(f"Can trade: {risk_status['can_trade']}")
        status_lines.append(f"Total PnL: {risk_status['metrics']['total_pnl']:.4f}")
        status_lines.append(f"Win rate: {risk_status['metrics']['win_rate']:.2%}")
        
        # Recent executions
        for execution_id, execution in list(self.active_executions.items())[-3:]:
            status = execution["status"]
            elapsed = time.time() - execution["start_time"]
            status_lines.append(f"{execution_id}: {status}, {elapsed:.1f}s")
            
        return "\n".join(status_lines)
        
    def stop(self):
        """Stop the controller"""
        self.is_active = False
        
        # Cancel all active executions
        for execution_id in list(self.active_executions.keys()):
            asyncio.create_task(self._rollback_execution(execution_id))
            
        self.logger.info("Gate Triangular Controller stopped")
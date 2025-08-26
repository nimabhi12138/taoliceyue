"""
Gate.io Arbitrage Legacy Script
ScriptStrategyBase implementation for backward compatibility
"""

import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Optional
from datetime import datetime

from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.core.data_type.common import OrderType, TradeType

logger = logging.getLogger(__name__)


class GateArbLegacy(ScriptStrategyBase):
    """
    Legacy arbitrage script using ScriptStrategyBase
    Simplified version for backward compatibility
    """
    
    # Markets to monitor
    markets = {
        "gate_io": ["BTC-USDT", "ETH-USDT", "BNB-USDT"],
        "gate_io_perpetual": ["BTC-USDT", "ETH-USDT"]
    }
    
    def __init__(self):
        super().__init__()
        self.last_check = 0
        self.check_interval = 1  # Check every second
        self.active_arbs = {}
        self.total_pnl = Decimal("0")
        
        # Load configuration
        self.min_profit_bps = Decimal("20")
        self.position_size_pct = Decimal("0.05")
        self.max_position_usd = Decimal("5000")
        
        # Fee configuration (with 75% rebate)
        self.spot_maker_fee = Decimal("0.00025")
        self.spot_taker_fee = Decimal("0.0005")
        self.perp_maker_fee = Decimal("0.00005")
        self.perp_taker_fee = Decimal("0.00015")
        
    def on_tick(self):
        """
        Called on each tick
        """
        current_time = self.current_timestamp
        
        # Check for opportunities at interval
        if current_time - self.last_check >= self.check_interval:
            self._check_arbitrage_opportunities()
            self.last_check = current_time
            
    def _check_arbitrage_opportunities(self):
        """
        Check for arbitrage opportunities
        """
        # Check spot-perp basis
        self._check_spot_perp_basis()
        
        # Check triangular opportunities
        self._check_triangular_arbitrage()
        
        # Monitor active positions
        self._monitor_positions()
        
    def _check_spot_perp_basis(self):
        """
        Check spot-perpetual basis arbitrage
        """
        for symbol in ["BTC-USDT", "ETH-USDT"]:
            try:
                # Get spot price
                spot_connector = self.connectors.get("gate_io")
                perp_connector = self.connectors.get("gate_io_perpetual")
                
                if not spot_connector or not perp_connector:
                    continue
                    
                spot_mid = spot_connector.get_mid_price(symbol)
                perp_mid = perp_connector.get_mid_price(symbol)
                
                if not spot_mid or not perp_mid:
                    continue
                    
                # Calculate basis
                basis = perp_mid - spot_mid
                basis_bps = (basis / spot_mid) * 10000
                
                # Calculate net profit after fees
                total_fee_bps = (self.spot_taker_fee + self.perp_taker_fee) * 10000
                net_profit_bps = abs(basis_bps) - total_fee_bps - 5  # 5 bps slippage
                
                # Check if profitable
                if net_profit_bps > self.min_profit_bps:
                    self.logger.info(f"Spot-Perp Opportunity: {symbol} "
                                   f"basis={basis_bps:.2f}bps "
                                   f"net={net_profit_bps:.2f}bps")
                    self._execute_spot_perp_arbitrage(symbol, basis_bps > 0)
                    
            except Exception as e:
                self.logger.error(f"Error checking spot-perp for {symbol}: {e}")
                
    def _check_triangular_arbitrage(self):
        """
        Check triangular arbitrage opportunities
        """
        # Simplified triangular check
        paths = [
            ["USDT", "BTC", "ETH", "USDT"],
            ["USDT", "ETH", "BNB", "USDT"]
        ]
        
        for path in paths:
            try:
                profit = self._calculate_triangular_profit(path)
                if profit > self.min_profit_bps:
                    self.logger.info(f"Triangular Opportunity: {' -> '.join(path)} "
                                   f"profit={profit:.2f}bps")
                    self._execute_triangular_arbitrage(path)
                    
            except Exception as e:
                self.logger.debug(f"Error checking triangular path {path}: {e}")
                
    def _calculate_triangular_profit(self, path: List[str]) -> Decimal:
        """
        Calculate profit for a triangular path
        """
        # Simplified calculation
        # In production, would calculate actual path profitability
        return Decimal("0")  # Placeholder
        
    def _execute_spot_perp_arbitrage(self, symbol: str, long_spot: bool):
        """
        Execute spot-perpetual arbitrage
        """
        try:
            # Calculate position size
            balance = self._get_available_balance("USDT")
            position_size = min(
                balance * self.position_size_pct,
                self.max_position_usd
            )
            
            if position_size < 10:  # Min size check
                return
                
            # Place orders
            if long_spot:
                # Buy spot, sell perp
                self.buy(self.connectors["gate_io"], symbol, position_size)
                self.sell(self.connectors["gate_io_perpetual"], symbol, position_size)
            else:
                # Sell spot, buy perp
                self.sell(self.connectors["gate_io"], symbol, position_size)
                self.buy(self.connectors["gate_io_perpetual"], symbol, position_size)
                
            # Track position
            self.active_arbs[f"{symbol}_{self.current_timestamp}"] = {
                "symbol": symbol,
                "size": position_size,
                "direction": "long_spot" if long_spot else "short_spot",
                "entry_time": datetime.now()
            }
            
        except Exception as e:
            self.logger.error(f"Error executing spot-perp arbitrage: {e}")
            
    def _execute_triangular_arbitrage(self, path: List[str]):
        """
        Execute triangular arbitrage
        """
        # Simplified execution
        # In production, would execute atomic triangular trades
        pass
        
    def _monitor_positions(self):
        """
        Monitor active arbitrage positions
        """
        for arb_id, position in list(self.active_arbs.items()):
            # Check if position should be closed
            # Simplified - would check actual PnL and exit conditions
            pass
            
    def _get_available_balance(self, token: str) -> Decimal:
        """
        Get available balance for a token
        """
        total_balance = Decimal("0")
        for connector in self.connectors.values():
            balance = connector.get_available_balance(token)
            if balance:
                total_balance += balance
        return total_balance
        
    def format_status(self) -> str:
        """
        Format status for display
        """
        lines = []
        lines.append("\n" + "=" * 50)
        lines.append("Gate.io Arbitrage Legacy Status")
        lines.append("=" * 50)
        
        # Active positions
        lines.append(f"Active Positions: {len(self.active_arbs)}")
        for arb_id, pos in self.active_arbs.items():
            lines.append(f"  {pos['symbol']}: {pos['direction']} ${pos['size']:.2f}")
            
        # Performance
        lines.append(f"\nTotal PnL: ${self.total_pnl:.2f}")
        
        # Market status
        lines.append(f"\nMonitoring:")
        for connector_name, symbols in self.markets.items():
            lines.append(f"  {connector_name}: {', '.join(symbols)}")
            
        return "\n".join(lines)
#!/usr/bin/env python3
"""
Risk Manager for Gate.io Arbitrage
Handles position sizing, exposure limits, and circuit breakers
"""

import logging
import time
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from hummingbot.connector.connector_base import ConnectorBase


@dataclass
class RiskMetrics:
    """Risk metrics tracking"""
    total_pnl: Decimal = Decimal("0")
    session_pnl: Decimal = Decimal("0")
    max_drawdown: Decimal = Decimal("0")
    current_drawdown: Decimal = Decimal("0")
    win_rate: Decimal = Decimal("0")
    total_trades: int = 0
    winning_trades: int = 0
    error_count: int = 0
    last_error_time: Optional[float] = None
    positions: Dict[str, Decimal] = field(default_factory=dict)
    exposure_by_symbol: Dict[str, Decimal] = field(default_factory=dict)


@dataclass
class TradeResult:
    """Individual trade result for tracking"""
    timestamp: float
    symbol: str
    pnl: Decimal
    size: Decimal
    success: bool


class RiskManager:
    """
    Comprehensive risk management for arbitrage strategies
    Implements Kelly sizing, exposure limits, and circuit breakers
    """
    
    def __init__(self, config: Dict):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = config
        self.metrics = RiskMetrics()
        self.trade_history: List[TradeResult] = []
        
        # Risk parameters from config
        self.max_position_size = Decimal(str(config.get("max_position_size", "1.0")))
        self.max_total_exposure = Decimal(str(config.get("max_total_exposure", "10.0")))
        self.max_symbol_exposure = Decimal(str(config.get("max_symbol_exposure", "2.0")))
        self.max_session_loss = Decimal(str(config.get("max_session_loss", "0.1")))  # 10%
        self.max_drawdown = Decimal(str(config.get("max_drawdown", "0.05")))  # 5%
        self.max_error_rate = Decimal(str(config.get("max_error_rate", "0.1")))  # 10%
        self.error_window = config.get("error_window", 300)  # 5 minutes
        self.kelly_multiplier = Decimal(str(config.get("kelly_multiplier", "0.25")))  # 25% of Kelly
        self.min_win_rate = Decimal(str(config.get("min_win_rate", "0.4")))  # 40%
        self.min_trade_count = config.get("min_trade_count", 10)
        
        self.circuit_breaker_active = False
        self.circuit_breaker_reason = ""
        
    def calculate_kelly_size(
        self,
        win_probability: Decimal,
        avg_win: Decimal,
        avg_loss: Decimal,
        available_capital: Decimal
    ) -> Decimal:
        """
        Calculate position size using Kelly criterion
        
        Args:
            win_probability: Probability of winning (0-1)
            avg_win: Average winning amount
            avg_loss: Average losing amount
            available_capital: Available capital for trading
            
        Returns:
            Recommended position size
        """
        if avg_loss <= 0 or win_probability <= 0:
            return Decimal("0")
            
        # Kelly formula: f = (bp - q) / b
        # where b = avg_win/avg_loss, p = win_probability, q = 1-p
        b = avg_win / avg_loss
        p = win_probability
        q = Decimal("1") - p
        
        kelly_fraction = (b * p - q) / b
        
        # Apply safety multiplier and cap
        kelly_fraction = max(Decimal("0"), kelly_fraction * self.kelly_multiplier)
        kelly_fraction = min(kelly_fraction, Decimal("0.1"))  # Max 10% of capital
        
        position_size = kelly_fraction * available_capital
        
        self.logger.debug(
            f"Kelly calculation - Win%: {p:.3f}, B: {b:.3f}, "
            f"Kelly: {kelly_fraction:.3f}, Size: {position_size:.4f}"
        )
        
        return position_size
        
    def get_position_size(
        self,
        symbol: str,
        expected_return: Decimal,
        available_capital: Decimal,
        confidence: Decimal = Decimal("1.0")
    ) -> Decimal:
        """
        Get recommended position size for a trade
        
        Args:
            symbol: Trading symbol
            expected_return: Expected return from the trade
            available_capital: Available capital
            confidence: Confidence level (0-1)
            
        Returns:
            Recommended position size
        """
        if self.circuit_breaker_active:
            self.logger.warning(f"Circuit breaker active: {self.circuit_breaker_reason}")
            return Decimal("0")
            
        # Use historical data for Kelly sizing if available
        if len(self.trade_history) >= self.min_trade_count:
            symbol_trades = [t for t in self.trade_history if t.symbol == symbol]
            
            if len(symbol_trades) >= 5:  # Minimum for statistical relevance
                wins = [t for t in symbol_trades if t.pnl > 0]
                losses = [t for t in symbol_trades if t.pnl < 0]
                
                if wins and losses:
                    win_rate = Decimal(len(wins)) / Decimal(len(symbol_trades))
                    avg_win = sum(t.pnl for t in wins) / len(wins)
                    avg_loss = abs(sum(t.pnl for t in losses) / len(losses))
                    
                    kelly_size = self.calculate_kelly_size(win_rate, avg_win, avg_loss, available_capital)
                else:
                    kelly_size = available_capital * Decimal("0.01")  # Conservative fallback
            else:
                kelly_size = available_capital * Decimal("0.02")  # Initial conservative size
        else:
            kelly_size = available_capital * Decimal("0.02")  # Initial conservative size
            
        # Apply confidence adjustment
        kelly_size *= confidence
        
        # Apply hard limits
        kelly_size = min(kelly_size, self.max_position_size)
        
        # Check symbol exposure
        current_exposure = self.metrics.exposure_by_symbol.get(symbol, Decimal("0"))
        max_additional = self.max_symbol_exposure - current_exposure
        kelly_size = min(kelly_size, max_additional)
        
        # Check total exposure
        total_exposure = sum(self.metrics.exposure_by_symbol.values())
        max_total_additional = self.max_total_exposure - total_exposure
        kelly_size = min(kelly_size, max_total_additional)
        
        return max(Decimal("0"), kelly_size)
        
    def check_risk_limits(self) -> Tuple[bool, List[str]]:
        """
        Check all risk limits and return status
        
        Returns:
            Tuple of (can_trade, violations)
        """
        violations = []
        
        # Check session loss limit
        if self.metrics.session_pnl < -self.max_session_loss:
            violations.append(f"Session loss limit exceeded: {self.metrics.session_pnl:.4f}")
            
        # Check drawdown limit
        if self.metrics.current_drawdown > self.max_drawdown:
            violations.append(f"Drawdown limit exceeded: {self.metrics.current_drawdown:.4f}")
            
        # Check error rate
        recent_errors = self._count_recent_errors()
        recent_trades = len([t for t in self.trade_history 
                           if t.timestamp > time.time() - self.error_window])
        
        if recent_trades > 0:
            error_rate = Decimal(recent_errors) / Decimal(recent_trades)
            if error_rate > self.max_error_rate:
                violations.append(f"Error rate too high: {error_rate:.3f}")
                
        # Check win rate (if enough trades)
        if len(self.trade_history) >= self.min_trade_count:
            if self.metrics.win_rate < self.min_win_rate:
                violations.append(f"Win rate too low: {self.metrics.win_rate:.3f}")
                
        # Check total exposure
        total_exposure = sum(self.metrics.exposure_by_symbol.values())
        if total_exposure > self.max_total_exposure:
            violations.append(f"Total exposure exceeded: {total_exposure:.4f}")
            
        can_trade = len(violations) == 0
        
        if violations and not self.circuit_breaker_active:
            self.activate_circuit_breaker("; ".join(violations))
        elif not violations and self.circuit_breaker_active:
            self.deactivate_circuit_breaker()
            
        return can_trade, violations
        
    def activate_circuit_breaker(self, reason: str):
        """Activate circuit breaker"""
        self.circuit_breaker_active = True
        self.circuit_breaker_reason = reason
        self.logger.warning(f"Circuit breaker activated: {reason}")
        
    def deactivate_circuit_breaker(self):
        """Deactivate circuit breaker"""
        self.circuit_breaker_active = False
        self.circuit_breaker_reason = ""
        self.logger.info("Circuit breaker deactivated")
        
    def record_trade(
        self,
        symbol: str,
        pnl: Decimal,
        size: Decimal,
        success: bool = True
    ):
        """Record a trade result"""
        trade = TradeResult(
            timestamp=time.time(),
            symbol=symbol,
            pnl=pnl,
            size=size,
            success=success
        )
        
        self.trade_history.append(trade)
        
        # Update metrics
        self.metrics.total_pnl += pnl
        self.metrics.session_pnl += pnl
        self.metrics.total_trades += 1
        
        if success and pnl > 0:
            self.metrics.winning_trades += 1
            
        if not success:
            self.metrics.error_count += 1
            self.metrics.last_error_time = time.time()
            
        # Update win rate
        if self.metrics.total_trades > 0:
            self.metrics.win_rate = Decimal(self.metrics.winning_trades) / Decimal(self.metrics.total_trades)
            
        # Update drawdown
        if self.metrics.total_pnl > self.metrics.max_drawdown:
            # New high water mark
            self.metrics.max_drawdown = self.metrics.total_pnl
            self.metrics.current_drawdown = Decimal("0")
        else:
            self.metrics.current_drawdown = self.metrics.max_drawdown - self.metrics.total_pnl
            
        # Update position tracking
        if symbol not in self.metrics.exposure_by_symbol:
            self.metrics.exposure_by_symbol[symbol] = Decimal("0")
        self.metrics.exposure_by_symbol[symbol] += size
        
        # Clean up old trades (keep last 1000)
        if len(self.trade_history) > 1000:
            self.trade_history = self.trade_history[-1000:]
            
    def update_position(self, symbol: str, size: Decimal):
        """Update position size for a symbol"""
        self.metrics.exposure_by_symbol[symbol] = size
        
    def _count_recent_errors(self) -> int:
        """Count errors in the recent time window"""
        cutoff = time.time() - self.error_window
        return len([t for t in self.trade_history 
                   if not t.success and t.timestamp > cutoff])
                   
    def get_risk_status(self) -> Dict:
        """Get current risk status"""
        can_trade, violations = self.check_risk_limits()
        
        return {
            "can_trade": can_trade,
            "violations": violations,
            "circuit_breaker_active": self.circuit_breaker_active,
            "circuit_breaker_reason": self.circuit_breaker_reason,
            "metrics": {
                "total_pnl": float(self.metrics.total_pnl),
                "session_pnl": float(self.metrics.session_pnl),
                "max_drawdown": float(self.metrics.max_drawdown),
                "current_drawdown": float(self.metrics.current_drawdown),
                "win_rate": float(self.metrics.win_rate),
                "total_trades": self.metrics.total_trades,
                "winning_trades": self.metrics.winning_trades,
                "error_count": self.metrics.error_count,
                "total_exposure": float(sum(self.metrics.exposure_by_symbol.values())),
                "exposure_by_symbol": {k: float(v) for k, v in self.metrics.exposure_by_symbol.items()}
            }
        }
        
    def reset_session(self):
        """Reset session metrics"""
        self.metrics.session_pnl = Decimal("0")
        self.deactivate_circuit_breaker()
        self.logger.info("Risk manager session reset")
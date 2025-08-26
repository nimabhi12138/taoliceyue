#!/usr/bin/env python3
"""
Test suite for Kelly Criterion calculations in Risk Manager
"""

import pytest
from decimal import Decimal
from pathlib import Path

# Add the parent directory to sys.path to import our modules
import sys
sys.path.append(str(Path(__file__).parent.parent))

from controllers.arbitrage.risk_manager import RiskManager


class TestKellyCriterion:
    """Test cases for Kelly Criterion implementation"""
    
    def setup_method(self):
        """Setup test environment"""
        self.config = {
            "max_position_size": "1.0",
            "max_total_exposure": "10.0",
            "max_symbol_exposure": "2.0",
            "max_session_loss": "0.1",
            "max_drawdown": "0.05",
            "kelly_multiplier": "0.25",
            "min_win_rate": "0.4",
            "min_trade_count": 10
        }
        self.risk_manager = RiskManager(self.config)
    
    def test_kelly_calculation_basic(self):
        """Test basic Kelly criterion calculation"""
        win_probability = Decimal("0.6")  # 60% win rate
        avg_win = Decimal("100.0")        # Average win $100
        avg_loss = Decimal("50.0")        # Average loss $50
        available_capital = Decimal("1000.0")
        
        kelly_size = self.risk_manager.calculate_kelly_size(
            win_probability, avg_win, avg_loss, available_capital
        )
        
        # Kelly formula: f = (bp - q) / b
        # where b = avg_win/avg_loss = 100/50 = 2
        # p = 0.6, q = 0.4
        # f = (2 * 0.6 - 0.4) / 2 = (1.2 - 0.4) / 2 = 0.8 / 2 = 0.4
        # With 25% multiplier: 0.4 * 0.25 = 0.1
        # Position size: 1000 * 0.1 = 100
        
        expected = Decimal("100.0")
        assert abs(kelly_size - expected) < Decimal("0.01")
    
    def test_kelly_calculation_negative(self):
        """Test Kelly criterion with negative expected value"""
        win_probability = Decimal("0.3")  # 30% win rate (bad)
        avg_win = Decimal("100.0")
        avg_loss = Decimal("100.0")
        available_capital = Decimal("1000.0")
        
        kelly_size = self.risk_manager.calculate_kelly_size(
            win_probability, avg_win, avg_loss, available_capital
        )
        
        # Kelly formula should give negative result
        # f = (1 * 0.3 - 0.7) / 1 = -0.4
        # Negative kelly should return 0
        assert kelly_size == Decimal("0")
    
    def test_kelly_calculation_edge_cases(self):
        """Test Kelly criterion edge cases"""
        available_capital = Decimal("1000.0")
        
        # Zero win probability
        kelly_size = self.risk_manager.calculate_kelly_size(
            Decimal("0"), Decimal("100"), Decimal("50"), available_capital
        )
        assert kelly_size == Decimal("0")
        
        # Zero average loss
        kelly_size = self.risk_manager.calculate_kelly_size(
            Decimal("0.6"), Decimal("100"), Decimal("0"), available_capital
        )
        assert kelly_size == Decimal("0")
    
    def test_kelly_with_multiplier(self):
        """Test Kelly sizing with different multipliers"""
        # Test with different multiplier
        config = self.config.copy()
        config["kelly_multiplier"] = "0.5"  # 50% of Kelly
        risk_manager = RiskManager(config)
        
        win_probability = Decimal("0.6")
        avg_win = Decimal("100.0")
        avg_loss = Decimal("50.0")
        available_capital = Decimal("1000.0")
        
        kelly_size = risk_manager.calculate_kelly_size(
            win_probability, avg_win, avg_loss, available_capital
        )
        
        # With 50% multiplier, should be double the 25% case
        expected = Decimal("200.0")  # 100 * 2
        assert abs(kelly_size - expected) < Decimal("0.01")
    
    def test_kelly_size_cap(self):
        """Test Kelly sizing maximum cap"""
        # Extreme parameters that would give very high Kelly
        win_probability = Decimal("0.9")  # 90% win rate
        avg_win = Decimal("1000.0")
        avg_loss = Decimal("10.0")
        available_capital = Decimal("1000.0")
        
        kelly_size = self.risk_manager.calculate_kelly_size(
            win_probability, avg_win, avg_loss, available_capital
        )
        
        # Should be capped at 10% of capital
        max_expected = available_capital * Decimal("0.1")  # 100
        assert kelly_size <= max_expected
    
    def test_get_position_size_no_history(self):
        """Test position sizing with no trading history"""
        symbol = "BTC-USDT"
        expected_return = Decimal("0.01")  # 1%
        available_capital = Decimal("1000.0")
        
        position_size = self.risk_manager.get_position_size(
            symbol, expected_return, available_capital
        )
        
        # Should use conservative initial sizing (2% of capital)
        expected = available_capital * Decimal("0.02")
        assert position_size == expected
    
    def test_get_position_size_with_history(self):
        """Test position sizing with trading history"""
        symbol = "BTC-USDT"
        
        # Add some trading history
        for i in range(15):  # More than min_trade_count
            pnl = Decimal("10.0") if i % 3 != 0 else Decimal("-5.0")  # 67% win rate
            self.risk_manager.record_trade(symbol, pnl, Decimal("0.1"), True)
        
        expected_return = Decimal("0.01")
        available_capital = Decimal("1000.0")
        
        position_size = self.risk_manager.get_position_size(
            symbol, expected_return, available_capital
        )
        
        # Should use Kelly sizing based on history
        # With 67% win rate and good win/loss ratio, should be > initial conservative sizing
        conservative_size = available_capital * Decimal("0.02")
        assert position_size >= conservative_size
    
    def test_get_position_size_with_confidence(self):
        """Test position sizing with confidence adjustment"""
        symbol = "BTC-USDT"
        expected_return = Decimal("0.01")
        available_capital = Decimal("1000.0")
        confidence = Decimal("0.5")  # 50% confidence
        
        position_size = self.risk_manager.get_position_size(
            symbol, expected_return, available_capital, confidence
        )
        
        # Should be reduced by confidence factor
        base_size = available_capital * Decimal("0.02")
        expected = base_size * confidence
        assert position_size == expected
    
    def test_get_position_size_exposure_limits(self):
        """Test position sizing with exposure limits"""
        symbol = "BTC-USDT"
        expected_return = Decimal("0.01")
        available_capital = Decimal("1000.0")
        
        # Set up existing exposure
        self.risk_manager.metrics.exposure_by_symbol[symbol] = Decimal("1.8")  # Near limit
        
        position_size = self.risk_manager.get_position_size(
            symbol, expected_return, available_capital
        )
        
        # Should be limited by remaining symbol exposure
        max_symbol_exposure = Decimal(self.config["max_symbol_exposure"])
        current_exposure = self.risk_manager.metrics.exposure_by_symbol[symbol]
        max_additional = max_symbol_exposure - current_exposure
        
        assert position_size <= max_additional
    
    def test_get_position_size_total_exposure_limit(self):
        """Test position sizing with total exposure limit"""
        symbol = "BTC-USDT"
        expected_return = Decimal("0.01")
        available_capital = Decimal("1000.0")
        
        # Set up high total exposure
        self.risk_manager.metrics.exposure_by_symbol["ETH-USDT"] = Decimal("9.0")
        
        position_size = self.risk_manager.get_position_size(
            symbol, expected_return, available_capital
        )
        
        # Should be limited by remaining total exposure
        max_total_exposure = Decimal(self.config["max_total_exposure"])
        total_exposure = sum(self.risk_manager.metrics.exposure_by_symbol.values())
        max_additional = max_total_exposure - total_exposure
        
        assert position_size <= max_additional
    
    def test_get_position_size_circuit_breaker(self):
        """Test position sizing with circuit breaker active"""
        # Activate circuit breaker
        self.risk_manager.activate_circuit_breaker("Test circuit breaker")
        
        symbol = "BTC-USDT"
        expected_return = Decimal("0.01")
        available_capital = Decimal("1000.0")
        
        position_size = self.risk_manager.get_position_size(
            symbol, expected_return, available_capital
        )
        
        # Should return 0 when circuit breaker is active
        assert position_size == Decimal("0")
    
    def test_kelly_with_insufficient_history(self):
        """Test Kelly sizing with insufficient trading history"""
        symbol = "BTC-USDT"
        
        # Add minimal history (less than 5 trades for the symbol)
        for i in range(3):
            pnl = Decimal("10.0")
            self.risk_manager.record_trade(symbol, pnl, Decimal("0.1"), True)
        
        expected_return = Decimal("0.01")
        available_capital = Decimal("1000.0")
        
        position_size = self.risk_manager.get_position_size(
            symbol, expected_return, available_capital
        )
        
        # Should fall back to conservative sizing
        expected = available_capital * Decimal("0.02")
        assert position_size == expected
    
    def test_kelly_with_mixed_history(self):
        """Test Kelly sizing with wins and losses"""
        symbol = "BTC-USDT"
        
        # Add mixed trading history
        wins = [Decimal("15.0"), Decimal("20.0"), Decimal("10.0"), Decimal("25.0")]
        losses = [Decimal("-8.0"), Decimal("-12.0")]
        
        for pnl in wins + losses:
            success = pnl > 0
            self.risk_manager.record_trade(symbol, pnl, Decimal("0.1"), success)
        
        # Need more total trades to trigger Kelly
        for i in range(10):
            pnl = Decimal("5.0") if i % 2 == 0 else Decimal("-3.0")
            success = pnl > 0
            self.risk_manager.record_trade(symbol, pnl, Decimal("0.1"), success)
        
        expected_return = Decimal("0.01")
        available_capital = Decimal("1000.0")
        
        position_size = self.risk_manager.get_position_size(
            symbol, expected_return, available_capital
        )
        
        # Should use Kelly sizing
        assert position_size > Decimal("0")
        assert position_size <= Decimal(self.config["max_position_size"])


if __name__ == "__main__":
    pytest.main([__file__])
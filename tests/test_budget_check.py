#!/usr/bin/env python3
"""
Test suite for Budget and Balance Checking
"""

import pytest
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Add the parent directory to sys.path to import our modules
import sys
sys.path.append(str(Path(__file__).parent.parent))

from controllers.arbitrage.risk_manager import RiskManager


class TestBudgetCheck:
    """Test cases for budget and balance checking functionality"""
    
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
        
    def test_basic_position_size_calculation(self):
        """Test basic position size calculation within budget"""
        symbol = "BTC-USDT"
        expected_return = Decimal("0.01")  # 1%
        available_capital = Decimal("1000.0")
        
        position_size = self.risk_manager.get_position_size(
            symbol, expected_return, available_capital
        )
        
        # Should return a reasonable position size
        assert position_size > 0
        assert position_size <= self.risk_manager.max_position_size
        
    def test_zero_capital_budget(self):
        """Test position sizing with zero available capital"""
        symbol = "BTC-USDT"
        expected_return = Decimal("0.01")
        available_capital = Decimal("0.0")
        
        position_size = self.risk_manager.get_position_size(
            symbol, expected_return, available_capital
        )
        
        # Should return zero position size with no capital
        assert position_size == Decimal("0")
        
    def test_negative_expected_return(self):
        """Test position sizing with negative expected return"""
        symbol = "BTC-USDT"
        expected_return = Decimal("-0.01")  # -1% expected loss
        available_capital = Decimal("1000.0")
        
        position_size = self.risk_manager.get_position_size(
            symbol, expected_return, available_capital
        )
        
        # Should return zero or very small position size for negative returns
        assert position_size <= Decimal("0.01")  # Very conservative
        
    def test_symbol_exposure_limit(self):
        """Test symbol exposure limit enforcement"""
        symbol = "BTC-USDT"
        expected_return = Decimal("0.05")  # High return
        available_capital = Decimal("1000.0")
        
        # Set existing exposure near limit
        self.risk_manager.metrics.exposure_by_symbol[symbol] = Decimal("1.9")
        
        position_size = self.risk_manager.get_position_size(
            symbol, expected_return, available_capital
        )
        
        # Should be limited by remaining symbol exposure
        max_additional = self.risk_manager.max_symbol_exposure - Decimal("1.9")
        assert position_size <= max_additional
        
    def test_total_exposure_limit(self):
        """Test total exposure limit enforcement"""
        symbol = "BTC-USDT"
        expected_return = Decimal("0.05")
        available_capital = Decimal("1000.0")
        
        # Set high exposure for other symbols
        self.risk_manager.metrics.exposure_by_symbol["ETH-USDT"] = Decimal("8.0")
        self.risk_manager.metrics.exposure_by_symbol["BNB-USDT"] = Decimal("1.5")
        
        position_size = self.risk_manager.get_position_size(
            symbol, expected_return, available_capital
        )
        
        # Should be limited by remaining total exposure
        total_exposure = Decimal("8.0") + Decimal("1.5")
        max_additional = self.risk_manager.max_total_exposure - total_exposure
        assert position_size <= max_additional
        
    def test_exposure_at_exact_limit(self):
        """Test behavior when exposure is at exact limit"""
        symbol = "BTC-USDT"
        expected_return = Decimal("0.05")
        available_capital = Decimal("1000.0")
        
        # Set exposure exactly at limit
        self.risk_manager.metrics.exposure_by_symbol[symbol] = self.risk_manager.max_symbol_exposure
        
        position_size = self.risk_manager.get_position_size(
            symbol, expected_return, available_capital
        )
        
        # Should return zero when at limit
        assert position_size == Decimal("0")
        
    def test_exposure_over_limit(self):
        """Test behavior when exposure is over limit"""
        symbol = "BTC-USDT"
        expected_return = Decimal("0.05")
        available_capital = Decimal("1000.0")
        
        # Set exposure over limit (edge case)
        self.risk_manager.metrics.exposure_by_symbol[symbol] = self.risk_manager.max_symbol_exposure + Decimal("0.1")
        
        position_size = self.risk_manager.get_position_size(
            symbol, expected_return, available_capital
        )
        
        # Should return zero when over limit
        assert position_size == Decimal("0")
        
    def test_position_size_hard_cap(self):
        """Test position size hard cap enforcement"""
        symbol = "BTC-USDT"
        expected_return = Decimal("0.5")  # Very high return
        available_capital = Decimal("100000.0")  # Very high capital
        
        position_size = self.risk_manager.get_position_size(
            symbol, expected_return, available_capital
        )
        
        # Should never exceed max position size regardless of other factors
        assert position_size <= self.risk_manager.max_position_size
        
    def test_confidence_factor_application(self):
        """Test confidence factor reduces position size"""
        symbol = "BTC-USDT"
        expected_return = Decimal("0.02")
        available_capital = Decimal("1000.0")
        
        # Get position size with full confidence
        full_confidence_size = self.risk_manager.get_position_size(
            symbol, expected_return, available_capital, Decimal("1.0")
        )
        
        # Get position size with half confidence
        half_confidence_size = self.risk_manager.get_position_size(
            symbol, expected_return, available_capital, Decimal("0.5")
        )
        
        # Half confidence should result in smaller position
        assert half_confidence_size <= full_confidence_size * Decimal("0.5")
        
    def test_zero_confidence_factor(self):
        """Test zero confidence factor returns zero position"""
        symbol = "BTC-USDT"
        expected_return = Decimal("0.02")
        available_capital = Decimal("1000.0")
        
        position_size = self.risk_manager.get_position_size(
            symbol, expected_return, available_capital, Decimal("0.0")
        )
        
        # Zero confidence should result in zero position
        assert position_size == Decimal("0")
        
    def test_budget_with_existing_positions(self):
        """Test budget calculation with existing positions"""
        # Setup existing positions
        self.risk_manager.metrics.exposure_by_symbol["BTC-USDT"] = Decimal("0.5")
        self.risk_manager.metrics.exposure_by_symbol["ETH-USDT"] = Decimal("0.3")
        
        # Test new position sizing
        symbol = "ADA-USDT"
        expected_return = Decimal("0.02")
        available_capital = Decimal("1000.0")
        
        position_size = self.risk_manager.get_position_size(
            symbol, expected_return, available_capital
        )
        
        # Should account for existing exposure
        total_exposure = Decimal("0.5") + Decimal("0.3") + position_size
        assert total_exposure <= self.risk_manager.max_total_exposure
        
    def test_budget_update_after_trade(self):
        """Test budget updates after recording trades"""
        symbol = "BTC-USDT"
        initial_exposure = Decimal("0.5")
        
        # Set initial exposure
        self.risk_manager.metrics.exposure_by_symbol[symbol] = initial_exposure
        
        # Record a trade
        trade_size = Decimal("0.2")
        self.risk_manager.record_trade(symbol, Decimal("10.0"), trade_size, True)
        
        # Exposure should be updated
        # Note: Implementation may vary - this tests the general concept
        updated_exposure = self.risk_manager.metrics.exposure_by_symbol[symbol]
        assert updated_exposure != initial_exposure  # Should change
        
    def test_session_loss_budget_impact(self):
        """Test session loss impact on position sizing"""
        symbol = "BTC-USDT"
        expected_return = Decimal("0.02")
        available_capital = Decimal("1000.0")
        
        # Record significant session losses
        self.risk_manager.metrics.session_pnl = -self.risk_manager.max_session_loss * Decimal("0.9")
        
        position_size = self.risk_manager.get_position_size(
            symbol, expected_return, available_capital
        )
        
        # Should still allow some trading but be more conservative
        assert position_size >= Decimal("0")  # Still allow some trading
        
    def test_circuit_breaker_budget_impact(self):
        """Test circuit breaker completely stops position sizing"""
        symbol = "BTC-USDT"
        expected_return = Decimal("0.02")
        available_capital = Decimal("1000.0")
        
        # Activate circuit breaker
        self.risk_manager.activate_circuit_breaker("Test circuit breaker")
        
        position_size = self.risk_manager.get_position_size(
            symbol, expected_return, available_capital
        )
        
        # Should return zero when circuit breaker is active
        assert position_size == Decimal("0")
        
    def test_multiple_symbol_budget_allocation(self):
        """Test budget allocation across multiple symbols"""
        symbols = ["BTC-USDT", "ETH-USDT", "BNB-USDT"]
        expected_return = Decimal("0.02")
        available_capital = Decimal("1000.0")
        
        total_allocated = Decimal("0")
        
        for symbol in symbols:
            position_size = self.risk_manager.get_position_size(
                symbol, expected_return, available_capital
            )
            
            # Update exposure as if position was taken
            self.risk_manager.metrics.exposure_by_symbol[symbol] = position_size
            total_allocated += position_size
            
        # Total allocation should not exceed total exposure limit
        assert total_allocated <= self.risk_manager.max_total_exposure
        
    def test_budget_precision_handling(self):
        """Test budget calculations with high precision decimals"""
        symbol = "BTC-USDT"
        expected_return = Decimal("0.00123456789")  # High precision
        available_capital = Decimal("1000.123456789")  # High precision
        
        position_size = self.risk_manager.get_position_size(
            symbol, expected_return, available_capital
        )
        
        # Should handle precision correctly
        assert isinstance(position_size, Decimal)
        assert position_size >= Decimal("0")
        
    def test_budget_with_very_small_amounts(self):
        """Test budget calculations with very small amounts"""
        symbol = "BTC-USDT"
        expected_return = Decimal("0.0001")  # 0.01%
        available_capital = Decimal("0.001")  # Very small capital
        
        position_size = self.risk_manager.get_position_size(
            symbol, expected_return, available_capital
        )
        
        # Should handle small amounts gracefully
        assert position_size >= Decimal("0")
        assert position_size <= available_capital
        
    def test_budget_edge_case_max_values(self):
        """Test budget calculations at maximum values"""
        symbol = "BTC-USDT"
        expected_return = Decimal("1.0")  # 100% return
        available_capital = Decimal("999999.0")  # Very large capital
        
        position_size = self.risk_manager.get_position_size(
            symbol, expected_return, available_capital
        )
        
        # Should still respect limits even with extreme inputs
        assert position_size <= self.risk_manager.max_position_size
        assert position_size <= self.risk_manager.max_symbol_exposure
        
    def test_budget_consistency_multiple_calls(self):
        """Test budget calculation consistency across multiple calls"""
        symbol = "BTC-USDT"
        expected_return = Decimal("0.02")
        available_capital = Decimal("1000.0")
        confidence = Decimal("0.8")
        
        # Get position size multiple times with same inputs
        size1 = self.risk_manager.get_position_size(symbol, expected_return, available_capital, confidence)
        size2 = self.risk_manager.get_position_size(symbol, expected_return, available_capital, confidence)
        size3 = self.risk_manager.get_position_size(symbol, expected_return, available_capital, confidence)
        
        # Should return consistent results
        assert size1 == size2 == size3
        
    def test_budget_position_update_mechanism(self):
        """Test position update mechanism for budget tracking"""
        symbol = "BTC-USDT"
        new_position_size = Decimal("0.5")
        
        # Update position
        self.risk_manager.update_position(symbol, new_position_size)
        
        # Verify position was updated
        assert self.risk_manager.metrics.exposure_by_symbol[symbol] == new_position_size
        
        # Update again with different size
        updated_size = Decimal("0.8")
        self.risk_manager.update_position(symbol, updated_size)
        
        # Should reflect new size
        assert self.risk_manager.metrics.exposure_by_symbol[symbol] == updated_size


if __name__ == "__main__":
    pytest.main([__file__])
"""
Test Budget Checks and Risk Management
"""

import unittest
from decimal import Decimal


class TestBudgetCheck(unittest.TestCase):
    """Test budget allocation and risk management"""
    
    def setUp(self):
        """Set up test parameters"""
        self.total_balance = Decimal("10000")  # $10,000 USDT
        self.max_exposure_pct = Decimal("0.5")  # 50% max exposure
        self.max_position_usd = Decimal("5000")  # $5,000 max per position
        self.min_order_size = Decimal("10")  # $10 minimum
        
    def test_position_size_with_percentage_limit(self):
        """Test position sizing with percentage limits"""
        # 10% position size
        position_pct = Decimal("0.1")
        position_size = self.total_balance * position_pct
        
        self.assertEqual(position_size, Decimal("1000"))
        self.assertLessEqual(position_size, self.max_position_usd)
        
    def test_position_size_with_absolute_cap(self):
        """Test position sizing with absolute cap"""
        # Try to use 60% of balance
        position_pct = Decimal("0.6")
        position_size = self.total_balance * position_pct
        
        # Should be capped at max_position_usd
        capped_size = min(position_size, self.max_position_usd)
        
        self.assertEqual(position_size, Decimal("6000"))
        self.assertEqual(capped_size, Decimal("5000"))
        
    def test_minimum_order_size_check(self):
        """Test minimum order size validation"""
        # Small balance scenario
        small_balance = Decimal("50")
        position_pct = Decimal("0.1")
        position_size = small_balance * position_pct
        
        # $5 is below minimum
        self.assertEqual(position_size, Decimal("5"))
        self.assertLess(position_size, self.min_order_size)
        
        # Should not trade
        can_trade = position_size >= self.min_order_size
        self.assertFalse(can_trade)
        
    def test_multiple_position_budget_allocation(self):
        """Test budget allocation across multiple positions"""
        num_strategies = 4
        positions_per_strategy = 3
        total_positions = num_strategies * positions_per_strategy
        
        # Allocate budget
        budget_per_position = self.total_balance * self.max_exposure_pct / total_positions
        
        # Each position gets equal share of 50% exposure
        expected_per_position = Decimal("5000") / 12  # ~$416
        self.assertAlmostEqual(float(budget_per_position), float(expected_per_position), places=0)
        
        # Check total exposure
        total_exposure = budget_per_position * total_positions
        self.assertEqual(total_exposure, self.total_balance * self.max_exposure_pct)
        
    def test_circuit_breaker_daily_loss_limit(self):
        """Test circuit breaker with daily loss limit"""
        daily_loss_limit = Decimal("1000")  # $1,000 daily loss limit
        current_daily_pnl = Decimal("-950")  # Already lost $950
        
        # Check if should continue trading
        remaining_budget = daily_loss_limit + current_daily_pnl
        
        self.assertEqual(remaining_budget, Decimal("50"))
        
        # Should stop if next trade could exceed limit
        max_position_risk = self.max_position_usd * Decimal("0.02")  # 2% stop loss
        can_trade = remaining_budget > max_position_risk
        
        self.assertFalse(can_trade)  # Should stop trading
        
    def test_drawdown_calculation(self):
        """Test maximum drawdown calculation"""
        pnl_history = [
            Decimal("0"),
            Decimal("100"),
            Decimal("250"),  # Peak
            Decimal("150"),
            Decimal("50"),   # Drawdown of 200
            Decimal("120"),
            Decimal("80"),    # Drawdown of 170
        ]
        
        # Calculate max drawdown
        peak = Decimal("0")
        max_drawdown = Decimal("0")
        
        for pnl in pnl_history:
            peak = max(peak, pnl)
            drawdown = peak - pnl
            max_drawdown = max(max_drawdown, drawdown)
            
        self.assertEqual(max_drawdown, Decimal("200"))
        
        # Check drawdown percentage
        if peak > 0:
            drawdown_pct = (max_drawdown / peak) * 100
            self.assertEqual(drawdown_pct, Decimal("80"))  # 80% drawdown
            
    def test_leverage_constraints(self):
        """Test leverage constraints for perpetual positions"""
        max_leverage = Decimal("2")  # 2x max leverage
        collateral = Decimal("1000")
        
        # Calculate max position size with leverage
        max_position = collateral * max_leverage
        
        self.assertEqual(max_position, Decimal("2000"))
        
        # Check margin requirement
        position_size = Decimal("1500")
        required_margin = position_size / max_leverage
        
        self.assertEqual(required_margin, Decimal("750"))
        self.assertLessEqual(required_margin, collateral)
        
    def test_concurrent_position_limits(self):
        """Test concurrent position limits"""
        max_open_positions = 5
        current_positions = [
            {"symbol": "BTC-USDT", "size": Decimal("1000")},
            {"symbol": "ETH-USDT", "size": Decimal("800")},
            {"symbol": "BNB-USDT", "size": Decimal("500")},
            {"symbol": "SOL-USDT", "size": Decimal("400")},
        ]
        
        # Check if can open new position
        can_open_new = len(current_positions) < max_open_positions
        self.assertTrue(can_open_new)
        
        # Add one more
        current_positions.append({"symbol": "DOGE-USDT", "size": Decimal("300")})
        
        # Now at limit
        can_open_new = len(current_positions) < max_open_positions
        self.assertFalse(can_open_new)
        
    def test_risk_adjusted_sizing(self):
        """Test risk-adjusted position sizing"""
        base_size = Decimal("1000")
        
        # Different risk scenarios
        scenarios = [
            {"volatility": Decimal("0.01"), "multiplier": Decimal("1.0")},  # Low vol
            {"volatility": Decimal("0.03"), "multiplier": Decimal("0.7")},  # Med vol
            {"volatility": Decimal("0.05"), "multiplier": Decimal("0.5")},  # High vol
        ]
        
        for scenario in scenarios:
            adjusted_size = base_size * scenario["multiplier"]
            
            # Higher volatility should result in smaller positions
            if scenario["volatility"] > Decimal("0.03"):
                self.assertLess(adjusted_size, base_size)
            else:
                self.assertLessEqual(adjusted_size, base_size)


if __name__ == "__main__":
    unittest.main()
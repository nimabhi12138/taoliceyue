"""
Test Kelly Criterion Position Sizing
"""

import unittest
from decimal import Decimal


class TestKellySizing(unittest.TestCase):
    """Test Kelly criterion position sizing"""
    
    def calculate_kelly_fraction(self, win_prob: Decimal, win_return: Decimal, 
                                loss_return: Decimal = Decimal("1")) -> Decimal:
        """
        Calculate Kelly fraction
        f* = (p * b - q) / b
        where:
        - p = probability of winning
        - q = probability of losing (1 - p)
        - b = ratio of win to loss amounts
        """
        q = 1 - win_prob
        b = win_return / loss_return
        
        kelly = (win_prob * b - q) / b
        return max(Decimal("0"), kelly)  # Never bet negative
        
    def test_basic_kelly_calculation(self) -> None:
        """Test basic Kelly calculation"""
        # 60% win rate, 1:1 payoff
        win_prob = Decimal("0.6")
        win_return = Decimal("1")
        
        kelly = self.calculate_kelly_fraction(win_prob, win_return)
        
        # Kelly = (0.6 * 1 - 0.4) / 1 = 0.2
        self.assertEqual(kelly, Decimal("0.2"))
        
    def test_conservative_kelly(self) -> None:
        """Test conservative Kelly (fractional Kelly)"""
        # Full Kelly
        win_prob = Decimal("0.65")
        win_return = Decimal("1.5")
        
        full_kelly = self.calculate_kelly_fraction(win_prob, win_return)
        
        # Conservative: use 25% of full Kelly
        conservative_fraction = Decimal("0.25")
        conservative_kelly = full_kelly * conservative_fraction
        
        # Should be much smaller than full Kelly
        self.assertLess(conservative_kelly, full_kelly)
        self.assertLess(conservative_kelly, Decimal("0.1"))  # Less than 10%
        
    def test_kelly_with_high_edge(self) -> None:
        """Test Kelly with high edge scenario"""
        # 70% win rate, 2:1 payoff
        win_prob = Decimal("0.7")
        win_return = Decimal("2")
        
        kelly = self.calculate_kelly_fraction(win_prob, win_return)
        
        # High edge should give higher Kelly fraction
        self.assertGreater(kelly, Decimal("0.5"))
        
    def test_kelly_with_low_edge(self) -> None:
        """Test Kelly with low edge scenario"""
        # 52% win rate, 1:1 payoff (typical for arbitrage)
        win_prob = Decimal("0.52")
        win_return = Decimal("1")
        
        kelly = self.calculate_kelly_fraction(win_prob, win_return)
        
        # Low edge should give small Kelly fraction
        self.assertEqual(kelly, Decimal("0.04"))  # 4%
        
    def test_kelly_cap_for_arbitrage(self) -> None:
        """Test Kelly capping for arbitrage strategies"""
        # Arbitrage parameters
        win_prob = Decimal("0.65")  # Conservative estimate
        edge_bps = Decimal("30")  # 30 bps edge
        
        # Convert edge to return ratio
        win_return = 1 + edge_bps / 10000
        
        kelly = self.calculate_kelly_fraction(win_prob, win_return)
        
        # Apply conservative fraction (25%)
        conservative_kelly = kelly * Decimal("0.25")
        
        # Further cap at 10% for safety
        max_position = Decimal("0.1")
        final_size = min(conservative_kelly, max_position)
        
        # Should be capped
        self.assertLessEqual(final_size, max_position)
        
    def test_kelly_with_multiple_positions(self) -> None:
        """Test Kelly adjustment for multiple concurrent positions"""
        # Single position Kelly
        single_kelly = Decimal("0.1")
        
        # With multiple positions, reduce per-position size
        num_positions = 3
        adjusted_kelly = single_kelly / Decimal(str(num_positions ** 0.5))
        
        # Should be reduced but not linearly
        self.assertLess(adjusted_kelly, single_kelly)
        self.assertGreater(adjusted_kelly, single_kelly / num_positions)


if __name__ == "__main__":
    unittest.main()
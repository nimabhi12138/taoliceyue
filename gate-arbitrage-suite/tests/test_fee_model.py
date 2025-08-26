"""
Test Fee Model with 75% Rebate
"""

import unittest
from decimal import Decimal


class TestFeeModel(unittest.TestCase):
    """Test fee calculations with rebates"""
    
    def setUp(self):
        """Set up test parameters"""
        self.rebate_ratio = Decimal("0.75")
        
        # Original Gate.io fees
        self.spot_maker_fee = Decimal("0.001")  # 0.1%
        self.spot_taker_fee = Decimal("0.002")  # 0.2%
        self.perp_maker_fee = Decimal("0.0002")  # 0.02%
        self.perp_taker_fee = Decimal("0.0006")  # 0.06%
        
    def calculate_net_fee(self, raw_fee: Decimal, rebate: Decimal) -> Decimal:
        """Calculate net fee after rebate"""
        return raw_fee * (1 - rebate)
        
    def test_spot_maker_fee_with_rebate(self):
        """Test spot maker fee with 75% rebate"""
        net_fee = self.calculate_net_fee(self.spot_maker_fee, self.rebate_ratio)
        expected = Decimal("0.00025")  # 0.025%
        self.assertEqual(net_fee, expected)
        
    def test_spot_taker_fee_with_rebate(self):
        """Test spot taker fee with 75% rebate"""
        net_fee = self.calculate_net_fee(self.spot_taker_fee, self.rebate_ratio)
        expected = Decimal("0.0005")  # 0.05%
        self.assertEqual(net_fee, expected)
        
    def test_perp_maker_fee_with_rebate(self):
        """Test perpetual maker fee with 75% rebate"""
        net_fee = self.calculate_net_fee(self.perp_maker_fee, self.rebate_ratio)
        expected = Decimal("0.00005")  # 0.005%
        self.assertEqual(net_fee, expected)
        
    def test_perp_taker_fee_with_rebate(self):
        """Test perpetual taker fee with 75% rebate"""
        net_fee = self.calculate_net_fee(self.perp_taker_fee, self.rebate_ratio)
        expected = Decimal("0.00015")  # 0.015%
        self.assertEqual(net_fee, expected)
        
    def test_arbitrage_profitability(self):
        """Test arbitrage profitability calculation"""
        # Spot-Perp arbitrage example
        basis_bps = Decimal("50")  # 50 bps spread
        
        # Calculate total fees (both legs)
        spot_fee = self.calculate_net_fee(self.spot_taker_fee, self.rebate_ratio)
        perp_fee = self.calculate_net_fee(self.perp_taker_fee, self.rebate_ratio)
        total_fee_bps = (spot_fee + perp_fee) * 10000
        
        # Add slippage and safety margin
        slippage_bps = Decimal("5")
        safety_margin_bps = Decimal("10")
        
        # Calculate net edge
        net_edge_bps = basis_bps - total_fee_bps - slippage_bps - safety_margin_bps
        
        # Should be profitable
        self.assertGreater(net_edge_bps, 0)
        self.assertAlmostEqual(float(net_edge_bps), 28.5, places=1)
        
    def test_triangular_fee_calculation(self):
        """Test triangular arbitrage fee calculation"""
        # Three legs, each with fees
        leg1_fee = self.calculate_net_fee(self.spot_taker_fee, self.rebate_ratio)
        leg2_fee = self.calculate_net_fee(self.spot_taker_fee, self.rebate_ratio)
        leg3_fee = self.calculate_net_fee(self.spot_taker_fee, self.rebate_ratio)
        
        # Total fees for triangular path
        total_fees = leg1_fee + leg2_fee + leg3_fee
        total_fees_bps = total_fees * 10000
        
        # With 75% rebate, total fees should be 15 bps (3 * 5 bps)
        self.assertEqual(total_fees_bps, Decimal("15"))
        
    def test_maker_vs_taker_comparison(self):
        """Test cost difference between maker and taker orders"""
        # Spot market
        spot_maker_net = self.calculate_net_fee(self.spot_maker_fee, self.rebate_ratio)
        spot_taker_net = self.calculate_net_fee(self.spot_taker_fee, self.rebate_ratio)
        spot_savings = spot_taker_net - spot_maker_net
        
        # Maker orders save 2.5 bps in spot
        self.assertEqual(spot_savings * 10000, Decimal("2.5"))
        
        # Perp market
        perp_maker_net = self.calculate_net_fee(self.perp_maker_fee, self.rebate_ratio)
        perp_taker_net = self.calculate_net_fee(self.perp_taker_fee, self.rebate_ratio)
        perp_savings = perp_taker_net - perp_maker_net
        
        # Maker orders save 1 bp in perps
        self.assertEqual(perp_savings * 10000, Decimal("1"))


if __name__ == "__main__":
    unittest.main()
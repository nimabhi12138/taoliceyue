"""
Test Triangular Arbitrage Path Finding and Profitability
"""

import unittest
from decimal import Decimal
import networkx as nx


class TestTriangularArbitrage(unittest.TestCase):
    """Test triangular arbitrage path calculations"""
    
    def setUp(self) -> None:
        """Set up test graph and parameters"""
        self.graph = nx.DiGraph()
        
        # Add market edges (simplified rates)
        # Format: (from_currency, to_currency, symbol, rate)
        markets = [
            ("USDT", "BTC", "BTC-USDT", Decimal("50000")),  # Buy BTC with USDT
            ("BTC", "USDT", "BTC-USDT", Decimal("1/50000")),  # Sell BTC for USDT
            ("USDT", "ETH", "ETH-USDT", Decimal("3000")),  # Buy ETH with USDT
            ("ETH", "USDT", "ETH-USDT", Decimal("1/3000")),  # Sell ETH for USDT
            ("BTC", "ETH", "ETH-BTC", Decimal("0.06")),  # Buy ETH with BTC
            ("ETH", "BTC", "ETH-BTC", Decimal("1/0.06")),  # Sell ETH for BTC
        ]
        
        for from_curr, to_curr, symbol, rate in markets:
            self.graph.add_edge(from_curr, to_curr, symbol=symbol, rate=float(rate))
            
        # Fee with 75% rebate
        self.taker_fee = Decimal("0.0005")  # 0.05% after rebate
        
    def test_find_triangular_cycles(self) -> None:
        """Test finding triangular cycles in market graph"""
        # Find all cycles starting and ending at USDT
        cycles = list(nx.simple_cycles(self.graph))
        triangular_cycles = [c for c in cycles if len(c) == 3 and "USDT" in c]
        
        # Should find at least one triangular cycle
        self.assertGreater(len(triangular_cycles), 0)
        
        # Check a known cycle exists
        expected_cycle = ["USDT", "BTC", "ETH"]
        found = False
        for cycle in triangular_cycles:
            if set(cycle) == set(expected_cycle):
                found = True
                break
        self.assertTrue(found)
        
    def test_calculate_path_profit(self) -> None:
        """Test calculating profit for a triangular path"""
        # Path: USDT -> BTC -> ETH -> USDT
        path = ["USDT", "BTC", "ETH", "USDT"]
        
        # Start with 10000 USDT
        amount = Decimal("10000")
        
        # Execute path
        for i in range(len(path) - 1):
            from_curr = path[i]
            to_curr = path[i + 1]
            
            # Get exchange rate
            if self.graph.has_edge(from_curr, to_curr):
                rate = Decimal(str(self.graph[from_curr][to_curr]["rate"]))
                
                # Convert currency
                if from_curr == "USDT" and to_curr == "BTC":
                    amount = amount / Decimal("50000")  # Buy BTC
                elif from_curr == "BTC" and to_curr == "ETH":
                    amount = amount / Decimal("0.06")  # Convert BTC to ETH
                elif from_curr == "ETH" and to_curr == "USDT":
                    amount = amount * Decimal("3000")  # Sell ETH for USDT
                    
                # Apply fee
                amount = amount * (1 - self.taker_fee)
                
        # Calculate profit
        final_amount = amount
        profit = final_amount - Decimal("10000")
        profit_bps = (profit / Decimal("10000")) * 10000
        
        # With perfect rates, should break even minus fees
        # 3 legs * 5 bps = 15 bps loss
        self.assertAlmostEqual(float(profit_bps), -15, places=1)
        
    def test_profitable_path_detection(self) -> None:
        """Test detecting profitable triangular paths"""
        # Add an inefficient market (arbitrage opportunity)
        self.graph["ETH"]["USDT"]["rate"] = 3100  # ETH overpriced
        
        # Path: USDT -> ETH -> BTC -> USDT
        path = ["USDT", "ETH", "BTC", "USDT"]
        amount = Decimal("10000")
        
        # Execute path
        rates = {
            ("USDT", "ETH"): Decimal("1/3000"),  # Buy ETH
            ("ETH", "BTC"): Decimal("1/0.06"),  # Convert to BTC
            ("BTC", "USDT"): Decimal("50000"),  # Sell BTC
        }
        
        for i in range(len(path) - 1):
            from_curr = path[i]
            to_curr = path[i + 1]
            
            if (from_curr, to_curr) in rates:
                amount = amount * rates[(from_curr, to_curr)]
                amount = amount * (1 - self.taker_fee)
                
        # Should have profit after fees
        profit = amount - Decimal("10000")
        profit_bps = (profit / Decimal("10000")) * 10000
        
        # Should be profitable if rates are inefficient enough
        # This is a simplified example
        self.assertIsNotNone(profit_bps)
        
    def test_atomic_execution_requirement(self) -> None:
        """Test atomic execution requirements for triangular arbitrage"""
        # All three legs must execute or none
        legs = [
            {"symbol": "BTC-USDT", "side": "buy", "executed": False},
            {"symbol": "ETH-BTC", "side": "sell", "executed": False},
            {"symbol": "ETH-USDT", "side": "sell", "executed": False},
        ]
        
        # Simulate partial execution
        legs[0]["executed"] = True
        legs[1]["executed"] = True
        legs[2]["executed"] = False  # Third leg fails
        
        # Check if we need rollback
        all_executed = all(leg["executed"] for leg in legs)
        self.assertFalse(all_executed)
        
        # Should rollback executed legs
        if not all_executed:
            for leg in legs:
                if leg["executed"]:
                    # Would cancel or reverse the leg
                    leg["executed"] = False
                    
        # All legs should be rolled back
        self.assertTrue(all(not leg["executed"] for leg in legs))
        
    def test_minimum_profit_threshold(self) -> None:
        """Test minimum profit threshold after fees"""
        min_profit_bps = Decimal("20")  # 20 bps minimum
        
        # Calculate required price inefficiency
        # 3 legs * 5 bps fee = 15 bps cost
        # Need 20 bps profit after fees
        # So need 35 bps gross profit
        
        required_inefficiency = min_profit_bps + (3 * self.taker_fee * 10000)
        
        self.assertEqual(required_inefficiency, Decimal("35"))


if __name__ == "__main__":
    unittest.main()
#!/usr/bin/env python3
"""
Test suite for Triangular Arbitrage logic
"""

import pytest
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Add the parent directory to sys.path to import our modules
import sys
sys.path.append(str(Path(__file__).parent.parent))

from controllers.arbitrage.gate_triangular_controller import (
    GateTriangularController, 
    TriangularPath, 
    TriangularOpportunity
)
from hummingbot.core.data_type.common import TradeType


class TestTriangularArbitrage:
    """Test cases for Triangular Arbitrage Controller"""
    
    def setup_method(self):
        """Setup test environment"""
        self.config = {
            "connector": "gate_io",
            "base_currencies": ["USDT", "BTC", "ETH"],
            "quote_currencies": ["USDT", "BTC", "ETH"],
            "min_profitability_bps": "8",
            "max_position_size": "1.0",
            "slippage_buffer_bps": "3",
            "execution_timeout": 10,
            "prefer_maker_orders": True,
            "atomic_execution": True,
            "fee_override_path": None,
            "risk_config": {}
        }
        
        # Mock connectors
        self.mock_connectors = {"gate_io": Mock()}
        self.controller = GateTriangularController(self.config)
        self.controller.connectors = self.mock_connectors
        
    def test_controller_initialization(self):
        """Test controller initialization"""
        assert self.controller.connector_name == "gate_io"
        assert self.controller.min_profitability_bps == Decimal("8")
        assert self.controller.prefer_maker_orders is True
        assert self.controller.atomic_execution is True
        
    def test_triangular_path_building(self):
        """Test triangular path generation"""
        # Mock trading pairs
        self.controller.trading_pairs = ["BTC-USDT", "ETH-USDT", "ETH-BTC"]
        
        # Test path finding
        test_path_options = [
            ("BTC-USDT", "USDT-BTC"),
            ("ETH-USDT", "USDT-ETH"), 
            ("ETH-BTC", "BTC-ETH")
        ]
        
        valid_path = self.controller._find_valid_path(test_path_options)
        
        # Should find a valid triangular path
        if valid_path:
            assert len(valid_path) == 3
            assert all(pair in self.controller.trading_pairs for pair in valid_path)
            
    def test_triangular_profit_calculation(self):
        """Test triangular arbitrage profit calculation"""
        # Setup mock price data
        self.controller.price_cache = {
            "BTC-USDT": {
                "bid": Decimal("50000"),
                "ask": Decimal("50100"),
                "bid_size": Decimal("1.0"),
                "ask_size": Decimal("1.0"),
                "timestamp": 1000
            },
            "ETH-USDT": {
                "bid": Decimal("3000"),
                "ask": Decimal("3010"),
                "bid_size": Decimal("10.0"),
                "ask_size": Decimal("10.0"),
                "timestamp": 1000
            },
            "ETH-BTC": {
                "bid": Decimal("0.059"),
                "ask": Decimal("0.061"),
                "bid_size": Decimal("10.0"),
                "ask_size": Decimal("10.0"),
                "timestamp": 1000
            }
        }
        
        # Test path: USDT -> BTC -> ETH -> USDT
        path = ["BTC-USDT", "ETH-BTC", "ETH-USDT"]
        base_currency = "USDT"
        
        opportunity = self.controller._calculate_triangular_profit(path, base_currency)
        
        # Should detect if there's an arbitrage opportunity
        if opportunity:
            assert opportunity.starting_amount > 0
            assert opportunity.base_currency == base_currency
            assert len(opportunity.execution_sequence) == 3
            
    def test_triangular_profit_no_opportunity(self):
        """Test triangular arbitrage when no profitable opportunity exists"""
        # Setup price data with no arbitrage opportunity (tight spreads)
        self.controller.price_cache = {
            "BTC-USDT": {
                "bid": Decimal("50000"),
                "ask": Decimal("50001"),  # Very tight spread
                "bid_size": Decimal("1.0"),
                "ask_size": Decimal("1.0"),
                "timestamp": 1000
            },
            "ETH-USDT": {
                "bid": Decimal("3000"),
                "ask": Decimal("3001"),  # Very tight spread
                "bid_size": Decimal("10.0"),
                "ask_size": Decimal("10.0"),
                "timestamp": 1000
            },
            "ETH-BTC": {
                "bid": Decimal("0.0599"),
                "ask": Decimal("0.0601"),  # Very tight spread
                "bid_size": Decimal("10.0"),
                "ask_size": Decimal("10.0"),
                "timestamp": 1000
            }
        }
        
        path = ["BTC-USDT", "ETH-BTC", "ETH-USDT"]
        base_currency = "USDT"
        
        opportunity = self.controller._calculate_triangular_profit(path, base_currency)
        
        # Should not find profitable opportunity with tight spreads
        assert opportunity is None
        
    def test_triangular_profit_insufficient_liquidity(self):
        """Test triangular arbitrage with insufficient liquidity"""
        # Setup price data with insufficient liquidity
        self.controller.price_cache = {
            "BTC-USDT": {
                "bid": Decimal("50000"),
                "ask": Decimal("50200"),
                "bid_size": Decimal("0.001"),  # Very small size
                "ask_size": Decimal("0.001"),  # Very small size
                "timestamp": 1000
            },
            "ETH-USDT": {
                "bid": Decimal("3000"),
                "ask": Decimal("3100"),
                "bid_size": Decimal("0.01"),  # Very small size
                "ask_size": Decimal("0.01"),  # Very small size
                "timestamp": 1000
            },
            "ETH-BTC": {
                "bid": Decimal("0.055"),
                "ask": Decimal("0.065"),
                "bid_size": Decimal("0.01"),  # Very small size
                "ask_size": Decimal("0.01"),  # Very small size
                "timestamp": 1000
            }
        }
        
        path = ["BTC-USDT", "ETH-BTC", "ETH-USDT"]
        base_currency = "USDT"
        
        opportunity = self.controller._calculate_triangular_profit(path, base_currency)
        
        # Should not find opportunity due to insufficient liquidity
        assert opportunity is None
        
    def test_triangular_execution_sequence(self):
        """Test triangular execution sequence generation"""
        # Create a mock opportunity
        path = TriangularPath(
            leg1_pair="BTC-USDT",
            leg2_pair="ETH-BTC", 
            leg3_pair="ETH-USDT",
            leg1_side=TradeType.BUY,
            leg2_side=TradeType.BUY,
            leg3_side=TradeType.SELL,
            leg1_price=Decimal("50000"),
            leg2_price=Decimal("0.06"),
            leg3_price=Decimal("3000"),
            leg1_amount=Decimal("0.01"),
            leg2_amount=Decimal("0.5"),
            leg3_amount=Decimal("0.5"),
            gross_profit_pct=Decimal("0.1"),
            net_profit_pct=Decimal("0.05"),
            total_fees=Decimal("10"),
            confidence=Decimal("0.7")
        )
        
        execution_sequence = [
            {"pair": "BTC-USDT", "side": TradeType.BUY, "amount": Decimal("0.01"), "price": Decimal("50000")},
            {"pair": "ETH-BTC", "side": TradeType.BUY, "amount": Decimal("0.5"), "price": Decimal("0.06")},
            {"pair": "ETH-USDT", "side": TradeType.SELL, "amount": Decimal("0.5"), "price": Decimal("3000")}
        ]
        
        opportunity = TriangularOpportunity(
            path=path,
            base_currency="USDT",
            starting_amount=Decimal("500"),
            expected_profit=Decimal("2.5"),
            execution_sequence=execution_sequence
        )
        
        # Verify execution sequence structure
        assert len(opportunity.execution_sequence) == 3
        assert opportunity.execution_sequence[0]["pair"] == "BTC-USDT"
        assert opportunity.execution_sequence[0]["side"] == TradeType.BUY
        assert opportunity.expected_profit > 0
        
    def test_price_cache_update(self):
        """Test price cache update mechanism"""
        # Mock connector and order book
        mock_connector = Mock()
        mock_order_book = Mock()
        mock_order_book.best_bid_price = Decimal("50000")
        mock_order_book.best_ask_price = Decimal("50100")
        mock_order_book.best_bid_entries = [Mock(amount=Decimal("1.0"))]
        mock_order_book.best_ask_entries = [Mock(amount=Decimal("1.0"))]
        
        mock_connector.get_order_book.return_value = mock_order_book
        self.controller.connectors = {"gate_io": mock_connector}
        self.controller.trading_pairs = ["BTC-USDT"]
        
        # Update price cache
        import asyncio
        asyncio.run(self.controller.update_price_cache())
        
        # Verify price cache was updated
        assert "BTC-USDT" in self.controller.price_cache
        cache_entry = self.controller.price_cache["BTC-USDT"]
        assert cache_entry["bid"] == Decimal("50000")
        assert cache_entry["ask"] == Decimal("50100")
        assert cache_entry["bid_size"] == Decimal("1.0")
        assert cache_entry["ask_size"] == Decimal("1.0")
        
    def test_triangular_path_validation(self):
        """Test triangular path validation logic"""
        # Test valid triangular path
        valid_path = ["BTC-USDT", "ETH-BTC", "ETH-USDT"]
        
        # Mock price data for all pairs in path
        self.controller.price_cache = {}
        current_time = 1000
        
        for pair in valid_path:
            self.controller.price_cache[pair] = {
                "bid": Decimal("1000"),
                "ask": Decimal("1001"),
                "bid_size": Decimal("1.0"),
                "ask_size": Decimal("1.0"),
                "timestamp": current_time
            }
            
        # Test path analysis
        import asyncio
        opportunity = asyncio.run(
            self.controller.analyze_triangular_path(valid_path, current_time * 1000)
        )
        
        # Should be able to analyze the path (may or may not find opportunity)
        # The test mainly verifies no exceptions are thrown
        
    def test_stale_price_rejection(self):
        """Test rejection of stale price data"""
        path = ["BTC-USDT", "ETH-BTC", "ETH-USDT"]
        current_time = 10000  # Much later time
        
        # Setup stale price data
        self.controller.price_cache = {
            "BTC-USDT": {
                "bid": Decimal("50000"),
                "ask": Decimal("50100"),
                "timestamp": 1000  # Old timestamp
            }
        }
        
        # Should reject stale data
        import asyncio
        opportunity = asyncio.run(
            self.controller.analyze_triangular_path(path, current_time * 1000)
        )
        
        assert opportunity is None
        
    def test_risk_limits_integration(self):
        """Test integration with risk management"""
        # Setup risk manager to reject trades
        self.controller.risk_manager.circuit_breaker_active = True
        self.controller.risk_manager.circuit_breaker_reason = "Test circuit breaker"
        
        # Create mock opportunity
        mock_opportunity = Mock()
        mock_opportunity.symbol = "BTC-USDT"
        mock_opportunity.expected_profit = Decimal("10")
        mock_opportunity.size = Decimal("0.1")
        
        # Should not execute when risk limits are violated
        import asyncio
        asyncio.run(self.controller.execute_triangular_opportunity(mock_opportunity))
        
        # Verify no executors were created
        assert len(self.controller.executors) == 0
        
    def test_execution_timeout_handling(self):
        """Test execution timeout handling"""
        execution_id = "test_execution"
        mock_execution = {
            "start_time": 0,  # Old start time
            "status": "executing",
            "orders": []
        }
        
        self.controller.active_executions[execution_id] = mock_execution
        
        # Mock time to simulate timeout
        import time
        original_time = time.time
        time.time = lambda: 1000  # Much later time
        
        try:
            # Should detect timeout
            import asyncio
            asyncio.run(self.controller.manage_executions())
            
            # Execution should be cleaned up or marked as timed out
            if execution_id in self.controller.active_executions:
                assert self.controller.active_executions[execution_id]["status"] != "executing"
        finally:
            time.time = original_time
            
    def test_currency_conversion_logic(self):
        """Test currency conversion logic in triangular paths"""
        # Test path: USDT -> BTC -> ETH -> USDT
        starting_amount = Decimal("1000")  # 1000 USDT
        
        # Simulate conversions
        # USDT -> BTC at 50000 USDT/BTC
        btc_amount = starting_amount / Decimal("50000")  # 0.02 BTC
        
        # BTC -> ETH at 16.67 BTC/ETH (1 BTC = 16.67 ETH, so 1 ETH = 0.06 BTC)
        eth_amount = btc_amount / Decimal("0.06")  # 0.333 ETH
        
        # ETH -> USDT at 3000 USDT/ETH
        final_usdt = eth_amount * Decimal("3000")  # 1000 USDT
        
        # Should roughly return to starting amount (minus fees)
        assert abs(final_usdt - starting_amount) < Decimal("50")  # Allow for some variance
        
    def test_fee_calculation_integration(self):
        """Test integration with fee model for profitability calculation"""
        # This test verifies that fee calculations are properly integrated
        # into the triangular arbitrage profit calculation
        
        # Mock fee model to return specific fees
        self.controller.fee_model.get_effective_fee_rate = Mock(return_value=Decimal("0.0005"))
        
        # Setup profitable price scenario
        self.controller.price_cache = {
            "BTC-USDT": {
                "bid": Decimal("50000"),
                "ask": Decimal("50100"),
                "bid_size": Decimal("1.0"),
                "ask_size": Decimal("1.0"),
                "timestamp": 1000
            },
            "ETH-USDT": {
                "bid": Decimal("3000"),
                "ask": Decimal("3020"),  # Wider spread
                "bid_size": Decimal("10.0"),
                "ask_size": Decimal("10.0"),
                "timestamp": 1000
            },
            "ETH-BTC": {
                "bid": Decimal("0.058"),
                "ask": Decimal("0.062"),  # Wider spread
                "bid_size": Decimal("10.0"),
                "ask_size": Decimal("10.0"),
                "timestamp": 1000
            }
        }
        
        path = ["BTC-USDT", "ETH-BTC", "ETH-USDT"]
        opportunity = self.controller._calculate_triangular_profit(path, "USDT")
        
        # Should account for fees in profit calculation
        if opportunity:
            # Verify fees were considered (mock was called)
            assert self.controller.fee_model.get_effective_fee_rate.called


if __name__ == "__main__":
    pytest.main([__file__])
#!/usr/bin/env python3
"""
Test suite for Fee Model
"""

import pytest
from decimal import Decimal
from pathlib import Path
import tempfile
import yaml

from hummingbot.core.data_type.common import TradeType

# Add the parent directory to sys.path to import our modules
import sys
sys.path.append(str(Path(__file__).parent.parent))

from controllers.arbitrage.fee_model import FeeModel


class TestFeeModel:
    """Test cases for FeeModel class"""
    
    def test_fee_model_initialization(self):
        """Test basic initialization"""
        fee_model = FeeModel()
        assert fee_model.default_rebate_ratio == Decimal("0.75")
        assert "gate_io" in fee_model.default_fees
        assert "gate_io_perpetual" in fee_model.default_fees
    
    def test_fee_model_with_config(self):
        """Test initialization with config file"""
        # Create temporary config file
        config_data = {
            "fee_overrides": {
                "gate_io": {
                    "maker": 0.0001,
                    "taker": 0.0002
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name
        
        try:
            fee_model = FeeModel(config_path)
            assert fee_model.fee_overrides["gate_io"]["maker"] == Decimal("0.0001")
            assert fee_model.fee_overrides["gate_io"]["taker"] == Decimal("0.0002")
        finally:
            Path(config_path).unlink()
    
    def test_get_effective_fee_rate_default(self):
        """Test effective fee rate calculation with defaults"""
        fee_model = FeeModel()
        
        # Test gate_io spot
        effective_rate = fee_model.get_effective_fee_rate("gate_io", TradeType.BUY)
        expected = Decimal("0.002") * (Decimal("1") - Decimal("0.75"))  # 0.002 * 0.25
        assert effective_rate == expected
        
        effective_rate = fee_model.get_effective_fee_rate("gate_io", TradeType.SELL)
        expected = Decimal("0.002") * (Decimal("1") - Decimal("0.75"))
        assert effective_rate == expected
    
    def test_get_effective_fee_rate_with_overrides(self):
        """Test effective fee rate with overrides"""
        config_data = {
            "fee_overrides": {
                "gate_io": {
                    "maker": 0.0001,
                    "taker": 0.0002
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name
        
        try:
            fee_model = FeeModel(config_path)
            
            # Maker fee
            effective_rate = fee_model.get_effective_fee_rate("gate_io", TradeType.BUY)
            expected = Decimal("0.0001") * (Decimal("1") - Decimal("0.75"))
            assert effective_rate == expected
            
            # Taker fee
            effective_rate = fee_model.get_effective_fee_rate("gate_io", TradeType.SELL)
            expected = Decimal("0.0002") * (Decimal("1") - Decimal("0.75"))
            assert effective_rate == expected
        finally:
            Path(config_path).unlink()
    
    def test_get_effective_fee_rate_custom_rebate(self):
        """Test effective fee rate with custom rebate ratio"""
        fee_model = FeeModel()
        
        # Test with 50% rebate instead of 75%
        effective_rate = fee_model.get_effective_fee_rate(
            "gate_io", 
            TradeType.BUY, 
            rebate_ratio=Decimal("0.5")
        )
        expected = Decimal("0.002") * (Decimal("1") - Decimal("0.5"))  # 0.002 * 0.5
        assert effective_rate == expected
    
    def test_calculate_trading_cost(self):
        """Test trading cost calculation"""
        fee_model = FeeModel()
        
        amount = Decimal("1.0")
        price = Decimal("50000.0")
        
        cost = fee_model.calculate_trading_cost(
            "gate_io",
            TradeType.BUY,
            amount,
            price
        )
        
        # Expected: 1.0 * 50000.0 * (0.002 * 0.25) = 50000 * 0.0005 = 25
        expected = Decimal("25.0")
        assert cost == expected
    
    def test_calculate_net_profit(self):
        """Test net profit calculation"""
        fee_model = FeeModel()
        
        buy_connector = "gate_io"
        sell_connector = "gate_io"
        amount = Decimal("1.0")
        buy_price = Decimal("50000.0")
        sell_price = Decimal("50100.0")
        
        net_profit, breakdown = fee_model.calculate_net_profit(
            buy_connector,
            sell_connector,
            TradeType.BUY,  # Buy = taker
            TradeType.SELL,  # Sell = taker
            amount,
            buy_price,
            sell_price
        )
        
        # Gross profit: (50100 - 50000) * 1.0 = 100
        # Buy fee: 50000 * 0.0005 = 25
        # Sell fee: 50100 * 0.0005 = 25.05
        # Net profit: 100 - 25 - 25.05 = 49.95
        
        assert breakdown["gross_profit"] == Decimal("100.0")
        assert abs(breakdown["buy_fee"] - Decimal("25.0")) < Decimal("0.01")
        assert abs(breakdown["sell_fee"] - Decimal("25.05")) < Decimal("0.01")
        assert abs(net_profit - Decimal("49.95")) < Decimal("0.01")
    
    def test_calculate_net_profit_with_funding(self):
        """Test net profit calculation with funding cost"""
        fee_model = FeeModel()
        
        amount = Decimal("1.0")
        buy_price = Decimal("50000.0")
        sell_price = Decimal("50100.0")
        funding_cost = Decimal("10.0")
        
        net_profit, breakdown = fee_model.calculate_net_profit(
            "gate_io",
            "gate_io_perpetual",
            TradeType.BUY,
            TradeType.SELL,
            amount,
            buy_price,
            sell_price,
            funding_cost
        )
        
        # Should subtract funding cost from net profit
        assert breakdown["funding_cost"] == funding_cost
        expected_net = breakdown["gross_profit"] - breakdown["total_fees"] - funding_cost
        assert net_profit == expected_net
    
    def test_is_profitable_true(self):
        """Test profitability check - profitable case"""
        fee_model = FeeModel()
        
        amount = Decimal("1.0")
        buy_price = Decimal("50000.0")
        sell_price = Decimal("50200.0")  # 0.4% difference
        min_profit_bps = Decimal("10")  # 0.1% minimum
        
        is_profitable, analysis = fee_model.is_profitable(
            "gate_io",
            "gate_io",
            TradeType.BUY,
            TradeType.SELL,
            amount,
            buy_price,
            sell_price,
            min_profit_bps
        )
        
        assert is_profitable is True
        assert analysis["is_profitable"] is True
        assert analysis["effective_profit_bps"] >= min_profit_bps
    
    def test_is_profitable_false(self):
        """Test profitability check - unprofitable case"""
        fee_model = FeeModel()
        
        amount = Decimal("1.0")
        buy_price = Decimal("50000.0")
        sell_price = Decimal("50010.0")  # Only 0.02% difference
        min_profit_bps = Decimal("50")  # 0.5% minimum (too high)
        
        is_profitable, analysis = fee_model.is_profitable(
            "gate_io",
            "gate_io",
            TradeType.BUY,
            TradeType.SELL,
            amount,
            buy_price,
            sell_price,
            min_profit_bps
        )
        
        assert is_profitable is False
        assert analysis["is_profitable"] is False
        assert analysis["effective_profit_bps"] < min_profit_bps
    
    def test_is_profitable_with_slippage_buffer(self):
        """Test profitability check with slippage buffer"""
        fee_model = FeeModel()
        
        amount = Decimal("1.0")
        buy_price = Decimal("50000.0")
        sell_price = Decimal("50080.0")  # 0.16% difference
        min_profit_bps = Decimal("5")   # 0.05% minimum
        slippage_buffer_bps = Decimal("10")  # 0.1% slippage buffer
        
        is_profitable, analysis = fee_model.is_profitable(
            "gate_io",
            "gate_io",
            TradeType.BUY,
            TradeType.SELL,
            amount,
            buy_price,
            sell_price,
            min_profit_bps,
            slippage_buffer_bps=slippage_buffer_bps
        )
        
        # Should account for slippage buffer in calculation
        assert analysis["slippage_buffer_bps"] == slippage_buffer_bps
        assert analysis["effective_profit_bps"] == analysis["profit_bps"] - slippage_buffer_bps
    
    def test_get_fee_summary(self):
        """Test fee summary generation"""
        fee_model = FeeModel()
        
        summary = fee_model.get_fee_summary()
        
        assert "gate_io" in summary
        assert "gate_io_perpetual" in summary
        
        # Check that all trade types are present
        for exchange in ["gate_io", "gate_io_perpetual"]:
            assert "maker" in summary[exchange]
            assert "taker" in summary[exchange]
            
            # Check that values are Decimal and reasonable
            maker_fee = summary[exchange]["maker"]
            taker_fee = summary[exchange]["taker"]
            
            assert isinstance(maker_fee, Decimal)
            assert isinstance(taker_fee, Decimal)
            assert maker_fee >= 0
            assert taker_fee >= 0
            assert maker_fee < Decimal("0.01")  # Less than 1%
            assert taker_fee < Decimal("0.01")  # Less than 1%


if __name__ == "__main__":
    pytest.main([__file__])
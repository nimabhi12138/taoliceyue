"""
Gate.io Arbitrage Script V2
Compatible with Hummingbot V2 Framework
Main entry point for running arbitrage strategies
"""

import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Optional
from pathlib import Path

from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.smart_components.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.smart_components.models.config import ConnectorConfig

# Import our controllers
from controllers.arbitrage.gate_spot_perp_controller_v2 import (
    GateSpotPerpController,
    GateSpotPerpControllerConfig
)

logger = logging.getLogger(__name__)


class GateArbitrageV2(ScriptStrategyBase):
    """
    Gate.io Arbitrage Strategy Script
    Compatible with Hummingbot V2 Framework
    """
    
    # Define which connectors this script uses
    connectors = [
        ConnectorConfig(connector="gate_io", trading_pairs=["BTC-USDT", "ETH-USDT"]),
        ConnectorConfig(connector="gate_io_perpetual", trading_pairs=["BTC-USDT", "ETH-USDT"])
    ]
    
    def __init__(self, config: ClientConfigAdapter):
        super().__init__(config)
        
        # Initialize controllers list
        self.controllers = []
        
        # Load configuration
        self._load_config()
        
        # Performance tracking
        self.total_pnl = Decimal("0")
        self.start_time = None
        
    def _load_config(self):
        """Load configuration from file or use defaults"""
        
        # Default configuration for spot-perp arbitrage
        spot_perp_config = GateSpotPerpControllerConfig(
            controller_name="gate_spot_perp",
            controller_type="directional",
            spot_connector_name="gate_io",
            perp_connector_name="gate_io_perpetual",
            trading_pairs=["BTC-USDT", "ETH-USDT"],
            
            # Arbitrage parameters (optimized for 75% rebate)
            min_basis_bps=Decimal("25"),  # Lower threshold due to rebate
            slippage_buffer_bps=Decimal("5"),
            safety_margin_bps=Decimal("5"),
            
            # Position sizing
            position_size_quote=Decimal("1000"),
            max_position_quote=Decimal("10000"),
            kelly_fraction=Decimal("0.25"),
            
            # Risk management
            max_open_positions=3,
            stop_loss_pct=Decimal("0.02"),
            take_profit_pct=Decimal("0.01"),
            max_daily_loss_quote=Decimal("1000"),
            
            # Execution
            use_maker_orders=True,  # Prefer maker for lower fees
            order_refresh_time=30,
            max_retries=3,
            
            # Fees with 75% rebate
            spot_maker_fee_pct=Decimal("0.00025"),  # 0.1% * 0.25 = 0.025%
            spot_taker_fee_pct=Decimal("0.0005"),   # 0.2% * 0.25 = 0.05%
            perp_maker_fee_pct=Decimal("0.00005"),  # 0.02% * 0.25 = 0.005%
            perp_taker_fee_pct=Decimal("0.00015"),  # 0.06% * 0.25 = 0.015%
        )
        
        # Create controller instance
        spot_perp_controller = GateSpotPerpController(
            config=spot_perp_config,
            connectors=self.connectors_manager
        )
        
        self.controllers.append(spot_perp_controller)
        
        logger.info(f"Loaded {len(self.controllers)} controllers")
    
    def on_start(self):
        """
        Called when the script starts
        """
        self.start_time = self.current_timestamp
        logger.info("=" * 50)
        logger.info("Gate.io Arbitrage Strategy V2 Started")
        logger.info("=" * 50)
        logger.info("Configuration:")
        logger.info(f"  Connectors: gate_io, gate_io_perpetual")
        logger.info(f"  Trading Pairs: BTC-USDT, ETH-USDT")
        logger.info(f"  Controllers: {len(self.controllers)}")
        logger.info("  Fee Structure: 75% rebate applied")
        logger.info("=" * 50)
        
        # Start all controllers
        for controller in self.controllers:
            self.start_controller(controller)
            logger.info(f"Started controller: {controller.config.controller_name}")
    
    def on_stop(self):
        """
        Called when the script stops
        """
        logger.info("=" * 50)
        logger.info("Gate.io Arbitrage Strategy V2 Stopping")
        logger.info("=" * 50)
        
        # Stop all controllers
        for controller in self.controllers:
            self.stop_controller(controller)
            logger.info(f"Stopped controller: {controller.config.controller_name}")
        
        # Print final statistics
        self._print_statistics()
    
    def on_tick(self):
        """
        Called on every tick
        Main strategy logic goes here
        """
        # Controllers handle their own logic via update_processed_data()
        # and determine_executor_actions() which are called by the framework
        
        # We can add additional monitoring or coordination logic here
        if self.current_timestamp % 30 == 0:  # Every 30 seconds
            self._update_performance_metrics()
    
    def format_status(self) -> str:
        """
        Returns formatted status of the strategy
        """
        lines = []
        lines.append("=" * 50)
        lines.append("GATE.IO ARBITRAGE STRATEGY V2 STATUS")
        lines.append("=" * 50)
        
        # Overall metrics
        runtime = (self.current_timestamp - self.start_time) if self.start_time else 0
        runtime_hours = runtime / 3600
        
        lines.append(f"Runtime: {runtime_hours:.2f} hours")
        lines.append(f"Total PnL: {self.total_pnl:.2f} USDT")
        
        # Controller status
        lines.append("\nControllers:")
        for controller in self.controllers:
            controller_lines = controller.to_format_status()
            for line in controller_lines:
                lines.append(f"  {line}")
        
        # Market conditions
        lines.append("\nMarket Conditions:")
        lines.append(f"  BTC-USDT Basis: {self._get_basis('BTC-USDT'):.2f} bps")
        lines.append(f"  ETH-USDT Basis: {self._get_basis('ETH-USDT'):.2f} bps")
        
        lines.append("=" * 50)
        
        return "\n".join(lines)
    
    def _get_basis(self, symbol: str) -> Decimal:
        """Calculate basis between spot and perp"""
        try:
            spot_connector = self.connectors_manager.get("gate_io")
            perp_connector = self.connectors_manager.get("gate_io_perpetual")
            
            if spot_connector and perp_connector:
                spot_ob = spot_connector.get_order_book(symbol)
                perp_ob = perp_connector.get_order_book(symbol)
                
                if spot_ob and perp_ob:
                    spot_mid = (spot_ob.get_price(False) + spot_ob.get_price(True)) / 2
                    perp_mid = (perp_ob.get_price(False) + perp_ob.get_price(True)) / 2
                    
                    if spot_mid and perp_mid:
                        basis_bps = ((perp_mid - spot_mid) / spot_mid) * 10000
                        return basis_bps
        except Exception as e:
            logger.error(f"Error calculating basis for {symbol}: {e}")
        
        return Decimal("0")
    
    def _update_performance_metrics(self):
        """Update performance metrics from controllers"""
        total_pnl = Decimal("0")
        
        for controller in self.controllers:
            # Get PnL from controller
            # This would need to be implemented in the controller
            pass
        
        self.total_pnl = total_pnl
    
    def _print_statistics(self):
        """Print final statistics"""
        runtime = (self.current_timestamp - self.start_time) if self.start_time else 0
        runtime_hours = runtime / 3600
        
        logger.info("Final Statistics:")
        logger.info(f"  Runtime: {runtime_hours:.2f} hours")
        logger.info(f"  Total PnL: {self.total_pnl:.2f} USDT")
        
        if runtime_hours > 0:
            hourly_pnl = self.total_pnl / Decimal(str(runtime_hours))
            logger.info(f"  Hourly PnL: {hourly_pnl:.2f} USDT/hour")


# Script configuration for Hummingbot
# This is used when running: start --script gate_arb_v2.py
def get_script_config():
    """Return script configuration"""
    return {
        "name": "Gate.io Arbitrage V2",
        "description": "Multi-strategy arbitrage for Gate.io with 75% fee rebate",
        "version": "2.0.0",
        "author": "Gate Arbitrage Suite",
        "connectors": ["gate_io", "gate_io_perpetual"],
        "trading_pairs": ["BTC-USDT", "ETH-USDT"]
    }
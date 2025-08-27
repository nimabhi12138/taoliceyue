#!/usr/bin/env python3
"""
Gate.io Arbitrage Launcher V2
Production-grade arbitrage suite for Hummingbot 2.x
Supports spot-perp, spot-spot, triangular, and statistical arbitrage
"""

import asyncio
import logging
import sys
import importlib
from pathlib import Path
from typing import Dict, List, Optional

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.connector.connector_base import ConnectorBase

# Add the current directory to Python path for controller imports
sys.path.append(str(Path(__file__).parent.parent))

# Import arbitrage controllers
try:
    from controllers.arbitrage.gate_spot_perp_controller import GateSpotPerpController
    from controllers.arbitrage.gate_triangular_controller import GateTriangularController
    from controllers.arbitrage.gate_spot_spot_controller import GateSpotSpotController
    from controllers.arbitrage.gate_stat_arb_controller import GateStatArbController
except ImportError as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Could not import arbitrage controllers: {e}")
    logger.warning("Please ensure the controllers directory is in the correct location.")


class GateArbLauncherV2(ScriptStrategyBase):
    """
    Gate.io Arbitrage Launcher V2 - Wrapper for multiple arbitrage controllers
    """

    # Configuration
    markets = {}  # Will be populated from config
    
    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        self.controllers = []
        self.active_strategies = {}
        
        # Initialize connectors properly
        self.connectors = connectors
        
        self.setup_logging()
        self.load_controllers()
        
    def setup_logging(self):
        """Setup structured logging for arbitrage activities"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(self.__class__.__name__)
        
    async def on_tick(self):
        """Main tick handler - delegates to active controllers"""
        if not self.ready_to_trade:
            return
            
        # Process all active controllers
        for controller in self.controllers:
            if controller.is_active:
                try:
                    await controller.process_tick()
                except Exception as e:
                    self.logger.error(f"Controller {controller.name} error: {e}")
                    
    def did_fill_order(self, event):
        """Handle order fill events"""
        for controller in self.controllers:
            if hasattr(controller, 'handle_order_fill'):
                controller.handle_order_fill(event)
                
    def format_status(self) -> str:
        """Return formatted status for all controllers"""
        status_lines = ["=== Gate.io Arbitrage Suite Status ==="]
        
        for controller in self.controllers:
            if hasattr(controller, 'get_status'):
                status_lines.append(f"\n{controller.name}:")
                status_lines.append(controller.get_status())
                
        return "\n".join(status_lines)

    def start(self, clock, timestamp):
        """Initialize and start all controllers"""
        super().start(clock, timestamp)
        self.logger.info("Gate.io Arbitrage Suite V2 started")
        
    def stop(self, clock):
        """Stop all controllers gracefully"""
        for controller in self.controllers:
            if hasattr(controller, 'stop'):
                controller.stop()
        super().stop(clock)
        self.logger.info("Gate.io Arbitrage Suite V2 stopped")
    
    def load_controllers(self):
        """Dynamically load arbitrage controllers from configuration"""
        try:
            # This would typically load from the script configuration
            # For now, create a sample configuration
            controllers_config = [
                {
                    "type": "GateSpotPerpController",
                    "config": {
                        "spot_connector": "gate_io",
                        "perp_connector": "gate_io_perpetual",
                        "trading_pairs": ["BTC-USDT", "ETH-USDT"],
                        "min_profitability_bps": 8
                    }
                },
                {
                    "type": "GateTriangularController", 
                    "config": {
                        "connector": "gate_io",
                        "base_currencies": ["USDT", "BTC", "ETH"],
                        "min_profitability_bps": 8
                    }
                }
            ]
            
            for controller_config in controllers_config:
                controller = self.create_controller(controller_config)
                if controller:
                    self.controllers.append(controller)
                    self.logger.info(f"Loaded controller: {controller_config['type']}")
                    
        except Exception as e:
            self.logger.error(f"Error loading controllers: {e}")
    
    def create_controller(self, config: Dict):
        """Create a controller instance from configuration"""
        try:
            controller_type = config["type"]
            controller_config = config["config"]
            
            # Map controller types to classes
            controller_classes = {
                "GateSpotPerpController": GateSpotPerpController,
                "GateTriangularController": GateTriangularController,
                "GateSpotSpotController": GateSpotSpotController,
                "GateStatArbController": GateStatArbController
            }
            
            if controller_type in controller_classes:
                controller_class = controller_classes[controller_type]
                
                # Pass connectors to the controller config
                controller_config["connectors"] = self.connectors
                
                return controller_class(controller_config)
            else:
                self.logger.error(f"Unknown controller type: {controller_type}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error creating controller {config['type']}: {e}")
            return None
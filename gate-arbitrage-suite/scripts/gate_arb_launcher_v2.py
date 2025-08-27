from typing import List
"""
Gate.io Arbitrage Launcher Script v2
Loads and runs multiple controllers using Hummingbot 2.x architecture
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, List
import yaml

from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.smart_components.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.smart_components.controllers.controller_base import ControllerBase

# Import our controllers
from controllers.arbitrage.gate_spot_perp_controller import GateSpotPerpController, GateSpotPerpControllerConfig
from controllers.arbitrage.gate_spot_spot_controller import GateSpotSpotController, GateSpotSpotControllerConfig
from controllers.arbitrage.gate_triangular_controller import GateTriangularController, GateTriangularControllerConfig
from controllers.arbitrage.gate_stat_arb_controller import GateStatArbController, GateStatArbControllerConfig

logger = logging.getLogger(__name__)


class GateArbLauncherV2(ScriptStrategyBase):
    """
    Main launcher script that loads and manages multiple arbitrage controllers
    """
    
    # Map controller types to classes
    CONTROLLER_CLASSES = {
        "gate_spot_perp_controller": (GateSpotPerpController, GateSpotPerpControllerConfig),
        "gate_spot_spot_controller": (GateSpotSpotController, GateSpotSpotControllerConfig),
        "gate_triangular_controller": (GateTriangularController, GateTriangularControllerConfig),
        "gate_stat_arb_controller": (GateStatArbController, GateStatArbControllerConfig),
    }
    
    def __init__(self, connectors: Dict[str, any], config: Dict[str, any]):
        super().__init__(connectors, config)
        self.controllers: List[ControllerBase] = []
        self._status_report_interval = 30
        self._last_status_report = 0
        
    def on_start(self) -> None:
        """
        Called when the script starts
        """
        self.logger.info("Starting Gate.io Arbitrage Suite v2")
        
        # Load controller configurations
        controller_configs = self.config.get("controllers", [])
        
        if not controller_configs:
            self.logger.warning("No controllers configured. Add controller configs to conf/scripts/gate_arb_launcher_v2.yml")
            return
            
        # Initialize controllers
        for controller_config_path in controller_configs:
            try:
                self._load_controller(controller_config_path)
            except Exception as e:
                self.logger.error(f"Failed to load controller from {controller_config_path}: {e}")
                
        self.logger.info(f"Loaded {len(self.controllers)} controllers")
        
        # Start all controllers
        for controller in self.controllers:
            asyncio.create_task(controller.start())
            
    def on_stop(self) -> None:
        """
        Called when the script stops
        """
        self.logger.info("Stopping Gate.io Arbitrage Suite v2")
        
        # Stop all controllers
        for controller in self.controllers:
            asyncio.create_task(controller.stop())
            
    def _load_controller(self, config_path: str) -> None:
        """
        Load a controller from configuration file
        """
        try:
            # Load configuration
            full_path = Path("conf/controllers") / config_path
            with open(full_path, "r") as f:
                config_dict = yaml.safe_load(f)
                
            # Get controller type
            controller_type = config_dict.get("controller_name")
            if not controller_type:
                raise ValueError(f"No controller_name in {config_path}")
                
            # Get controller class and config class
            if controller_type not in self.CONTROLLER_CLASSES:
                raise ValueError(f"Unknown controller type: {controller_type}")
                
            controller_class, config_class = self.CONTROLLER_CLASSES[controller_type]
            
            # Create configuration object
            config = config_class(**config_dict)
            
            # Create controller
            controller = controller_class(config)
            controller.connectors = self.connectors
            
            self.controllers.append(controller)
            self.logger.info(f"Loaded controller: {controller_type} from {config_path}")
            
        except Exception as e:
            self.logger.error(f"Error loading controller from {config_path}: {e}")
            raise
            
    def on_tick(self) -> None:
        """
        Called on each tick (every second by default)
        """
        # Report status periodically
        current_time = self.current_timestamp
        if current_time - self._last_status_report >= self._status_report_interval:
            self._report_status()
            self._last_status_report = current_time
            
    def _report_status(self):
        """
        Report status of all controllers
        """
        try:
            self.logger.info("\n" + "=" * 60)
            self.logger.info("GATE.IO ARBITRAGE SUITE STATUS REPORT")
            self.logger.info("=" * 60)
            
            for controller in self.controllers:
                status = controller.format_status()
                self.logger.info(status)
                
            # Overall metrics
            total_pnl = sum(getattr(c, "_total_pnl", 0) for c in self.controllers)
            total_trades = sum(getattr(c, "_total_trades", 0) for c in self.controllers)
            
            self.logger.info(f"\n{'=' * 60}")
            self.logger.info(f"OVERALL METRICS")
            self.logger.info(f"{'=' * 60}")
            self.logger.info(f"Total PnL: ${total_pnl:.2f}")
            self.logger.info(f"Total Trades: {total_trades}")
            self.logger.info(f"Active Controllers: {len([c for c in self.controllers if getattr(c, 'is_active', False)])}/{len(self.controllers)}")
            
        except Exception as e:
            self.logger.error(f"Error reporting status: {e}")
            
    def format_status(self) -> str:
        """
        Format status for display
        """
        lines = []
        lines.append("\n" + "=" * 60)
        lines.append("GATE.IO ARBITRAGE SUITE v2")
        lines.append("=" * 60)
        
        lines.append(f"Active Controllers: {len(self.controllers)}")
        
        for controller in self.controllers:
            lines.append(f"  - {controller.config.controller_name}: {'Active' if getattr(controller, 'is_active', False) else 'Inactive'}")
            
        # Quick summary
        total_pnl = sum(getattr(c, "_total_pnl", 0) for c in self.controllers)
        total_trades = sum(getattr(c, "_total_trades", 0) for c in self.controllers)
        
        lines.append(f"\nQuick Summary:")
        lines.append(f"  Total PnL: ${total_pnl:.2f}")
        lines.append(f"  Total Trades: {total_trades}")
        
        return "\n".join(lines)
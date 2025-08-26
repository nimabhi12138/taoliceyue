#!/usr/bin/env python3
"""
Gate.io Arbitrage Launcher V2
Production-grade arbitrage suite for Hummingbot 2.x
Supports spot-perp, spot-spot, triangular, and statistical arbitrage
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.utils.async_utils import safe_ensure_future


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
        self.setup_logging()
        
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
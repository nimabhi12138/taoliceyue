#!/usr/bin/env python3
"""
FastAPI Backend for Gate.io Arbitrage Web Admin UI
Provides REST API for managing Hummingbot configurations and monitoring
"""

import asyncio
import json
import logging
import os
import subprocess
import time
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Depends, Security, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Gate.io Arbitrage Admin API",
    description="Web Admin interface for Gate.io Arbitrage Suite",
    version="1.0.0"
)

# Security
security = HTTPBasic()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
HUMMINGBOT_ROOT = os.environ.get("HUMMINGBOT_ROOT", "/hummingbot")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "password123")

# Pydantic models
class ExchangeCredentials(BaseModel):
    exchange: str
    api_key: str
    secret_key: str
    passphrase: Optional[str] = None
    testnet: bool = False

class ControllerConfig(BaseModel):
    controller_name: str
    controller_type: str
    config: Dict
    enabled: bool = True

class ScriptConfig(BaseModel):
    script_name: str
    config_file: str
    controllers: List[str]
    enabled: bool = True

class BotStatus(BaseModel):
    name: str
    status: str
    uptime: Optional[int] = None
    pnl: Optional[float] = None
    trades: Optional[int] = None

class SystemStatus(BaseModel):
    timestamp: datetime
    bots: List[BotStatus]
    system_health: Dict
    balances: Dict

# Authentication
def authenticate_user(credentials: HTTPBasicCredentials = Security(security)):
    """Authenticate user with basic auth"""
    if credentials.username != ADMIN_USERNAME or credentials.password != ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# Helper functions
def get_hummingbot_path(relative_path: str) -> Path:
    """Get absolute path within Hummingbot directory"""
    return Path(HUMMINGBOT_ROOT) / relative_path

def load_yaml_file(file_path: Path) -> Dict:
    """Load YAML configuration file"""
    try:
        if file_path.exists():
            with open(file_path, 'r') as f:
                return yaml.safe_load(f) or {}
        return {}
    except Exception as e:
        logger.error(f"Error loading YAML file {file_path}: {e}")
        return {}

def save_yaml_file(file_path: Path, data: Dict):
    """Save data to YAML configuration file"""
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w') as f:
            yaml.safe_dump(data, f, default_flow_style=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving YAML file {file_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save configuration: {e}")

# API Routes

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Gate.io Arbitrage Admin API", "version": "1.0.0"}

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now()}

# Credentials Management
@app.get("/api/credentials")
async def list_credentials(user: str = Depends(authenticate_user)) -> List[str]:
    """List configured exchange credentials"""
    try:
        cred_path = get_hummingbot_path("conf")
        exchanges = []
        
        for file_path in cred_path.glob("*_api_key"):
            exchange_name = file_path.stem.replace("_api_key", "")
            exchanges.append(exchange_name)
            
        return exchanges
    except Exception as e:
        logger.error(f"Error listing credentials: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/credentials")
async def add_credentials(
    credentials: ExchangeCredentials,
    user: str = Depends(authenticate_user)
) -> Dict:
    """Add exchange credentials"""
    try:
        conf_path = get_hummingbot_path("conf")
        
        # Save API key
        api_key_file = conf_path / f"{credentials.exchange}_api_key"
        with open(api_key_file, 'w') as f:
            f.write(credentials.api_key)
            
        # Save secret key
        secret_key_file = conf_path / f"{credentials.exchange}_secret_key"
        with open(secret_key_file, 'w') as f:
            f.write(credentials.secret_key)
            
        # Save passphrase if provided
        if credentials.passphrase:
            passphrase_file = conf_path / f"{credentials.exchange}_passphrase"
            with open(passphrase_file, 'w') as f:
                f.write(credentials.passphrase)
                
        # Update exchange config if needed
        if credentials.testnet:
            # Add testnet configuration logic here
            pass
            
        return {"message": f"Credentials added for {credentials.exchange}"}
        
    except Exception as e:
        logger.error(f"Error adding credentials: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/credentials/{exchange}")
async def remove_credentials(
    exchange: str,
    user: str = Depends(authenticate_user)
) -> Dict:
    """Remove exchange credentials"""
    try:
        conf_path = get_hummingbot_path("conf")
        
        files_to_remove = [
            f"{exchange}_api_key",
            f"{exchange}_secret_key", 
            f"{exchange}_passphrase"
        ]
        
        for filename in files_to_remove:
            file_path = conf_path / filename
            if file_path.exists():
                file_path.unlink()
                
        return {"message": f"Credentials removed for {exchange}"}
        
    except Exception as e:
        logger.error(f"Error removing credentials: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Configuration Management
@app.get("/api/controllers")
async def list_controllers(user: str = Depends(authenticate_user)) -> List[Dict]:
    """List available controller configurations"""
    try:
        controllers_path = get_hummingbot_path("conf/controllers")
        controllers = []
        
        if controllers_path.exists():
            for config_file in controllers_path.glob("*.yml"):
                config = load_yaml_file(config_file)
                controllers.append({
                    "name": config_file.stem,
                    "type": config.get("controller_type", "unknown"),
                    "enabled": config.get("enabled", True),
                    "config": config
                })
                
        return controllers
        
    except Exception as e:
        logger.error(f"Error listing controllers: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/controllers/{controller_name}")
async def get_controller_config(
    controller_name: str,
    user: str = Depends(authenticate_user)
) -> Dict:
    """Get specific controller configuration"""
    try:
        config_path = get_hummingbot_path(f"conf/controllers/{controller_name}.yml")
        config = load_yaml_file(config_path)
        
        if not config:
            raise HTTPException(status_code=404, detail="Controller not found")
            
        return config
        
    except Exception as e:
        logger.error(f"Error getting controller config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/controllers")
async def create_controller_config(
    controller: ControllerConfig,
    user: str = Depends(authenticate_user)
) -> Dict:
    """Create new controller configuration"""
    try:
        config_path = get_hummingbot_path(f"conf/controllers/{controller.controller_name}.yml")
        
        config_data = {
            "controller_type": controller.controller_type,
            "enabled": controller.enabled,
            **controller.config
        }
        
        save_yaml_file(config_path, config_data)
        
        return {"message": f"Controller {controller.controller_name} created successfully"}
        
    except Exception as e:
        logger.error(f"Error creating controller config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/controllers/{controller_name}")
async def update_controller_config(
    controller_name: str,
    controller: ControllerConfig,
    user: str = Depends(authenticate_user)
) -> Dict:
    """Update controller configuration"""
    try:
        config_path = get_hummingbot_path(f"conf/controllers/{controller_name}.yml")
        
        config_data = {
            "controller_type": controller.controller_type,
            "enabled": controller.enabled,
            **controller.config
        }
        
        save_yaml_file(config_path, config_data)
        
        return {"message": f"Controller {controller_name} updated successfully"}
        
    except Exception as e:
        logger.error(f"Error updating controller config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/controllers/{controller_name}")
async def delete_controller_config(
    controller_name: str,
    user: str = Depends(authenticate_user)
) -> Dict:
    """Delete controller configuration"""
    try:
        config_path = get_hummingbot_path(f"conf/controllers/{controller_name}.yml")
        
        if config_path.exists():
            config_path.unlink()
            return {"message": f"Controller {controller_name} deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Controller not found")
            
    except Exception as e:
        logger.error(f"Error deleting controller config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Bot Management
@app.get("/api/bots/status")
async def get_bots_status(user: str = Depends(authenticate_user)) -> SystemStatus:
    """Get status of all running bots"""
    try:
        # This is a simplified implementation
        # In practice, you'd query the actual Hummingbot instances
        
        bots = []
        
        # Check for running Hummingbot processes
        try:
            result = subprocess.run(['pgrep', '-f', 'hummingbot'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    if pid:
                        bots.append(BotStatus(
                            name=f"hummingbot-{pid}",
                            status="running",
                            uptime=None,  # Could be calculated from process start time
                            pnl=0.0,      # Would be fetched from bot API
                            trades=0      # Would be fetched from bot API
                        ))
        except Exception as e:
            logger.warning(f"Error checking bot processes: {e}")
            
        system_health = {
            "cpu_usage": 0.0,    # Could use psutil
            "memory_usage": 0.0,  # Could use psutil
            "disk_space": 0.0     # Could use shutil.disk_usage
        }
        
        balances = {
            "USDT": 0.0,  # Would be fetched from exchange APIs
            "BTC": 0.0,
            "ETH": 0.0
        }
        
        return SystemStatus(
            timestamp=datetime.now(),
            bots=bots,
            system_health=system_health,
            balances=balances
        )
        
    except Exception as e:
        logger.error(f"Error getting bots status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/bots/start/{script_name}")
async def start_bot(
    script_name: str,
    config_name: Optional[str] = None,
    user: str = Depends(authenticate_user)
) -> Dict:
    """Start a Hummingbot script"""
    try:
        hummingbot_path = get_hummingbot_path("")
        
        cmd = [
            "python",
            str(hummingbot_path / "bin" / "hummingbot_quickstart.py"),
            "start",
            "--script", script_name
        ]
        
        if config_name:
            cmd.extend(["--conf", config_name])
            
        # Start the bot in background
        process = subprocess.Popen(
            cmd,
            cwd=hummingbot_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        return {
            "message": f"Bot started with script {script_name}",
            "pid": process.pid
        }
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/bots/stop/{bot_name}")
async def stop_bot(
    bot_name: str,
    user: str = Depends(authenticate_user)
) -> Dict:
    """Stop a running bot"""
    try:
        # This would implement bot stopping logic
        # Could use bot API or process management
        
        return {"message": f"Bot {bot_name} stopped"}
        
    except Exception as e:
        logger.error(f"Error stopping bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Fee Configuration
@app.get("/api/fees")
async def get_fee_config(user: str = Depends(authenticate_user)) -> Dict:
    """Get current fee configuration"""
    try:
        fee_config_path = get_hummingbot_path("conf/examples/conf_fee_overrides.yml")
        return load_yaml_file(fee_config_path)
        
    except Exception as e:
        logger.error(f"Error getting fee config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/fees")
async def update_fee_config(
    fee_config: Dict,
    user: str = Depends(authenticate_user)
) -> Dict:
    """Update fee configuration"""
    try:
        fee_config_path = get_hummingbot_path("conf/examples/conf_fee_overrides.yml")
        save_yaml_file(fee_config_path, fee_config)
        
        return {"message": "Fee configuration updated successfully"}
        
    except Exception as e:
        logger.error(f"Error updating fee config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Logs
@app.get("/api/logs")
async def get_logs(
    lines: int = 100,
    user: str = Depends(authenticate_user)
) -> Dict:
    """Get recent log entries"""
    try:
        log_path = get_hummingbot_path("logs")
        logs = []
        
        # Get most recent log file
        if log_path.exists():
            log_files = sorted(log_path.glob("*.log"), key=os.path.getmtime, reverse=True)
            if log_files:
                with open(log_files[0], 'r') as f:
                    log_lines = f.readlines()
                    logs = log_lines[-lines:] if len(log_lines) > lines else log_lines
                    
        return {
            "logs": [line.strip() for line in logs],
            "timestamp": datetime.now()
        }
        
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Templates
@app.get("/api/templates/controllers")
async def get_controller_templates(user: str = Depends(authenticate_user)) -> Dict:
    """Get controller configuration templates"""
    templates = {
        "gate_spot_perp_controller": {
            "controller_type": "GateSpotPerpController",
            "spot_connector": "gate_io",
            "perp_connector": "gate_io_perpetual",
            "trading_pairs": ["BTC-USDT", "ETH-USDT"],
            "min_profitability_bps": 5,
            "max_position_size": 1.0,
            "risk_config": {
                "max_total_exposure": 10.0,
                "max_session_loss": 0.1
            }
        },
        "gate_triangular_controller": {
            "controller_type": "GateTriangularController",
            "connector": "gate_io",
            "base_currencies": ["USDT", "BTC", "ETH"],
            "min_profitability_bps": 8,
            "max_position_size": 1.0,
            "risk_config": {
                "max_total_exposure": 5.0,
                "max_session_loss": 0.05
            }
        }
    }
    
    return templates

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
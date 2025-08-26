"""
FastAPI Backend for Gate.io Arbitrage Suite Web UI
Provides REST API for managing arbitrage strategies
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import yaml
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime
import subprocess
import os
from decimal import Decimal

# Security
security = HTTPBasic()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Gate.io Arbitrage Suite API",
    description="Web API for managing Gate.io arbitrage strategies",
    version="2.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration paths
CONFIG_BASE_PATH = Path("/hummingbot/conf")
CONTROLLERS_PATH = CONFIG_BASE_PATH / "controllers" / "arbitrage"
SCRIPTS_PATH = CONFIG_BASE_PATH / "scripts"
LOGS_PATH = Path("/hummingbot/logs")

# Models
class Credentials(BaseModel):
    exchange: str
    api_key: str
    api_secret: str
    api_passphrase: Optional[str] = None

class ControllerConfig(BaseModel):
    controller_name: str
    config: Dict[str, Any]

class BotCommand(BaseModel):
    command: str
    args: Optional[List[str]] = []

class StatusResponse(BaseModel):
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None

# Authentication
def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify admin credentials"""
    # Load from environment or config
    correct_username = os.getenv("ADMIN_USER", "admin")
    correct_password = os.getenv("ADMIN_PASSWORD", "changeme")
    
    if credentials.username != correct_username or credentials.password != correct_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# Endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Gate.io Arbitrage Suite API v2.0.0"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/credentials/add", response_model=StatusResponse)
async def add_credentials(creds: Credentials, username: str = Depends(verify_credentials)):
    """Add exchange credentials"""
    try:
        # In production, use Hummingbot's encrypted storage
        # This is a simplified version
        config_file = CONFIG_BASE_PATH / f"{creds.exchange}_config.yml"
        
        config = {
            "exchange": creds.exchange,
            "api_key": creds.api_key,
            "api_secret": "***",  # Don't save in plain text
            "timestamp": datetime.now().isoformat()
        }
        
        with open(config_file, "w") as f:
            yaml.dump(config, f)
            
        return StatusResponse(
            status="success",
            message=f"Credentials for {creds.exchange} added successfully"
        )
    except Exception as e:
        logger.error(f"Error adding credentials: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/controllers/templates", response_model=List[str])
async def get_controller_templates(username: str = Depends(verify_credentials)):
    """Get available controller templates"""
    templates = [
        "gate_spot_perp_controller",
        "gate_spot_spot_controller",
        "gate_triangular_controller",
        "gate_stat_arb_controller"
    ]
    return templates

@app.get("/controllers/list", response_model=List[Dict[str, Any]])
async def list_controllers(username: str = Depends(verify_credentials)):
    """List all controller configurations"""
    try:
        controllers = []
        if CONTROLLERS_PATH.exists():
            for config_file in CONTROLLERS_PATH.glob("*.yml"):
                with open(config_file, "r") as f:
                    config = yaml.safe_load(f)
                    controllers.append({
                        "name": config_file.stem,
                        "type": config.get("controller_name"),
                        "path": str(config_file),
                        "config": config
                    })
        return controllers
    except Exception as e:
        logger.error(f"Error listing controllers: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/controllers/create", response_model=StatusResponse)
async def create_controller(controller: ControllerConfig, username: str = Depends(verify_credentials)):
    """Create a new controller configuration"""
    try:
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{controller.controller_name}_{timestamp}.yml"
        config_path = CONTROLLERS_PATH / filename
        
        # Ensure directory exists
        CONTROLLERS_PATH.mkdir(parents=True, exist_ok=True)
        
        # Save configuration
        with open(config_path, "w") as f:
            yaml.dump(controller.config, f)
            
        return StatusResponse(
            status="success",
            message=f"Controller configuration created: {filename}",
            data={"path": str(config_path)}
        )
    except Exception as e:
        logger.error(f"Error creating controller: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/controllers/update/{controller_name}", response_model=StatusResponse)
async def update_controller(
    controller_name: str,
    config: Dict[str, Any],
    username: str = Depends(verify_credentials)
):
    """Update an existing controller configuration"""
    try:
        config_path = CONTROLLERS_PATH / f"{controller_name}.yml"
        if not config_path.exists():
            raise HTTPException(status_code=404, detail="Controller not found")
            
        with open(config_path, "w") as f:
            yaml.dump(config, f)
            
        return StatusResponse(
            status="success",
            message=f"Controller {controller_name} updated successfully"
        )
    except Exception as e:
        logger.error(f"Error updating controller: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/controllers/delete/{controller_name}", response_model=StatusResponse)
async def delete_controller(controller_name: str, username: str = Depends(verify_credentials)):
    """Delete a controller configuration"""
    try:
        config_path = CONTROLLERS_PATH / f"{controller_name}.yml"
        if not config_path.exists():
            raise HTTPException(status_code=404, detail="Controller not found")
            
        config_path.unlink()
        
        return StatusResponse(
            status="success",
            message=f"Controller {controller_name} deleted successfully"
        )
    except Exception as e:
        logger.error(f"Error deleting controller: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/bot/start", response_model=StatusResponse)
async def start_bot(command: BotCommand, username: str = Depends(verify_credentials)):
    """Start the Hummingbot with specified configuration"""
    try:
        # Build command
        cmd = ["docker", "exec", "hummingbot", "start"]
        if command.command == "launcher":
            cmd.extend(["--script", "gate_arb_launcher_v2.py"])
            cmd.extend(["--conf", "conf_gate_arb_launcher_v2.yml"])
        else:
            cmd.extend(command.args)
            
        # Execute command
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return StatusResponse(
                status="success",
                message="Bot started successfully",
                data={"output": result.stdout}
            )
        else:
            raise Exception(result.stderr)
            
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/bot/stop", response_model=StatusResponse)
async def stop_bot(username: str = Depends(verify_credentials)):
    """Stop the running bot"""
    try:
        cmd = ["docker", "exec", "hummingbot", "stop"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        return StatusResponse(
            status="success",
            message="Bot stopped successfully"
        )
    except Exception as e:
        logger.error(f"Error stopping bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/bot/status", response_model=Dict[str, Any])
async def get_bot_status(username: str = Depends(verify_credentials)):
    """Get current bot status"""
    try:
        # Check if Hummingbot container is running
        cmd = ["docker", "ps", "--filter", "name=hummingbot", "--format", "json"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.stdout:
            container_info = json.loads(result.stdout.strip())
            running = container_info.get("State") == "running"
        else:
            running = False
            
        # Get latest status from logs
        status_data = {
            "running": running,
            "timestamp": datetime.now().isoformat(),
            "controllers": [],
            "total_pnl": 0,
            "active_positions": 0
        }
        
        # Parse latest log for status
        if LOGS_PATH.exists():
            log_files = sorted(LOGS_PATH.glob("*.log"), key=lambda x: x.stat().st_mtime)
            if log_files:
                latest_log = log_files[-1]
                # Parse last 100 lines for status
                with open(latest_log, "r") as f:
                    lines = f.readlines()[-100:]
                    for line in lines:
                        if "Total PnL:" in line:
                            try:
                                pnl_str = line.split("Total PnL:")[1].split()[0]
                                status_data["total_pnl"] = float(pnl_str.replace("$", ""))
                            except:
                                pass
                                
        return status_data
        
    except Exception as e:
        logger.error(f"Error getting bot status: {e}")
        return {"running": False, "error": str(e)}

@app.get("/logs/tail", response_model=List[str])
async def tail_logs(lines: int = 100, username: str = Depends(verify_credentials)):
    """Get last N lines of logs"""
    try:
        if not LOGS_PATH.exists():
            return []
            
        log_files = sorted(LOGS_PATH.glob("*.log"), key=lambda x: x.stat().st_mtime)
        if not log_files:
            return []
            
        latest_log = log_files[-1]
        with open(latest_log, "r") as f:
            all_lines = f.readlines()
            return all_lines[-lines:]
            
    except Exception as e:
        logger.error(f"Error reading logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics/summary", response_model=Dict[str, Any])
async def get_metrics_summary(username: str = Depends(verify_credentials)):
    """Get summary of trading metrics"""
    try:
        # This would connect to a database or parse logs in production
        metrics = {
            "total_pnl_24h": 0,
            "total_trades_24h": 0,
            "win_rate": 0,
            "active_strategies": 0,
            "total_volume_24h": 0,
            "best_performing_strategy": None,
            "worst_performing_strategy": None,
            "timestamp": datetime.now().isoformat()
        }
        
        # Parse logs or connect to database for real metrics
        # ...
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/balances", response_model=Dict[str, Any])
async def get_balances(username: str = Depends(verify_credentials)):
    """Get current account balances"""
    try:
        # This would connect to Hummingbot's API in production
        balances = {
            "gate_io": {
                "USDT": 10000,
                "BTC": 0.5,
                "ETH": 10
            },
            "gate_io_perpetual": {
                "USDT": 5000
            },
            "timestamp": datetime.now().isoformat()
        }
        
        return balances
        
    except Exception as e:
        logger.error(f"Error getting balances: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
#!/usr/bin/env python3
"""
Gate.io Arbitrage Suite - Health Check Script
Production monitoring and system validation
"""

import asyncio
import sys
import json
import time
import psutil
import subprocess
from pathlib import Path
from typing import Dict, List, Any
from decimal import Decimal
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class HealthChecker:
    """Production health checker for Gate.io Arbitrage Suite"""
    
    def __init__(self, hummingbot_path: str = None):
        self.hummingbot_path = Path(hummingbot_path) if hummingbot_path else Path.home() / "hummingbot"
        self.checks = []
        self.results = {}
        
    def add_check(self, name: str, func, critical: bool = False):
        """Add a health check"""
        self.checks.append({
            "name": name,
            "func": func,
            "critical": critical
        })
        
    async def run_all_checks(self) -> Dict[str, Any]:
        """Run all health checks"""
        logger.info("Starting health check suite...")
        
        start_time = time.time()
        passed = 0
        failed = 0
        warnings = 0
        
        for check in self.checks:
            try:
                logger.info(f"Running check: {check['name']}")
                result = await check["func"]()
                
                self.results[check["name"]] = {
                    "status": result.get("status", "unknown"),
                    "message": result.get("message", ""),
                    "data": result.get("data", {}),
                    "critical": check["critical"],
                    "timestamp": time.time()
                }
                
                if result["status"] == "pass":
                    passed += 1
                elif result["status"] == "fail":
                    failed += 1
                    if check["critical"]:
                        logger.error(f"CRITICAL FAILURE: {check['name']} - {result['message']}")
                else:
                    warnings += 1
                    
            except Exception as e:
                logger.error(f"Health check '{check['name']}' failed with exception: {e}")
                self.results[check["name"]] = {
                    "status": "error", 
                    "message": str(e),
                    "critical": check["critical"],
                    "timestamp": time.time()
                }
                failed += 1
                
        duration = time.time() - start_time
        
        summary = {
            "overall_status": "healthy" if failed == 0 else "unhealthy",
            "passed": passed,
            "failed": failed, 
            "warnings": warnings,
            "duration": duration,
            "timestamp": time.time(),
            "checks": self.results
        }
        
        logger.info(f"Health check completed: {passed} passed, {failed} failed, {warnings} warnings")
        return summary
        
    async def check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            warnings = []
            if cpu_percent > 80:
                warnings.append(f"High CPU usage: {cpu_percent}%")
            if memory.percent > 85:
                warnings.append(f"High memory usage: {memory.percent}%")
            if disk.percent > 90:
                warnings.append(f"High disk usage: {disk.percent}%")
                
            status = "pass" if not warnings else "warn"
            
            return {
                "status": status,
                "message": "; ".join(warnings) if warnings else "System resources OK",
                "data": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_available_gb": memory.available / (1024**3),
                    "disk_percent": disk.percent,
                    "disk_free_gb": disk.free / (1024**3)
                }
            }
        except Exception as e:
            return {"status": "fail", "message": f"Failed to check system resources: {e}"}
            
    async def check_hummingbot_installation(self) -> Dict[str, Any]:
        """Check Hummingbot installation"""
        try:
            if not self.hummingbot_path.exists():
                return {"status": "fail", "message": f"Hummingbot path not found: {self.hummingbot_path}"}
                
            required_dirs = ["scripts", "conf"]
            optional_dirs = ["bin", "hummingbot"]  # bin might be in different location
            missing_dirs = [d for d in required_dirs if not (self.hummingbot_path / d).exists()]
            
            if missing_dirs:
                return {"status": "fail", "message": f"Missing Hummingbot directories: {missing_dirs}"}
                
            return {
                "status": "pass",
                "message": "Hummingbot installation OK",
                "data": {"path": str(self.hummingbot_path)}
            }
        except Exception as e:
            return {"status": "fail", "message": f"Failed to check Hummingbot: {e}"}
            
    async def check_arbitrage_controllers(self) -> Dict[str, Any]:
        """Check arbitrage controller files"""
        try:
            controllers_path = self.hummingbot_path / "controllers" / "arbitrage"
            
            required_controllers = [
                "gate_spot_perp_controller.py",
                "gate_triangular_controller.py", 
                "gate_spot_spot_controller.py",
                "gate_stat_arb_controller.py",
                "fee_model.py",
                "risk_manager.py"
            ]
            
            missing_files = []
            for controller in required_controllers:
                if not (controllers_path / controller).exists():
                    missing_files.append(controller)
                    
            if missing_files:
                return {"status": "fail", "message": f"Missing controller files: {missing_files}"}
                
            return {
                "status": "pass",
                "message": "All arbitrage controllers found",
                "data": {"controllers": required_controllers}
            }
        except Exception as e:
            return {"status": "fail", "message": f"Failed to check controllers: {e}"}
            
    async def check_configuration_files(self) -> Dict[str, Any]:
        """Check configuration files"""
        try:
            conf_path = self.hummingbot_path / "conf"
            
            required_configs = [
                "examples/conf_fee_overrides.yml",
                "examples/conf_v2_with_controllers.yml"
            ]
            
            missing_configs = []
            for config in required_configs:
                if not (conf_path / config).exists():
                    missing_configs.append(config)
                    
            if missing_configs:
                return {"status": "fail", "message": f"Missing config files: {missing_configs}"}
                
            return {
                "status": "pass", 
                "message": "Configuration files OK",
                "data": {"configs": required_configs}
            }
        except Exception as e:
            return {"status": "fail", "message": f"Failed to check configs: {e}"}
            
    async def check_python_dependencies(self) -> Dict[str, Any]:
        """Check Python dependencies"""
        try:
            import sys
            sys.path.append(str(self.hummingbot_path))
            
            # Test critical imports
            test_imports = [
                ("decimal", "Decimal"),
                ("asyncio", None),
                ("pandas", "pd"),
                ("numpy", "np")
            ]
            
            missing_imports = []
            for module, alias in test_imports:
                try:
                    if alias:
                        exec(f"import {module} as {alias}")
                    else:
                        exec(f"import {module}")
                except ImportError:
                    missing_imports.append(module)
                    
            if missing_imports:
                return {"status": "fail", "message": f"Missing Python modules: {missing_imports}"}
                
            # Test controller imports
            try:
                from controllers.arbitrage.fee_model import FeeModel
                from controllers.arbitrage.risk_manager import RiskManager
                controller_imports_ok = True
            except ImportError as e:
                return {"status": "fail", "message": f"Controller import failed: {e}"}
                
            return {
                "status": "pass",
                "message": "Python dependencies OK",
                "data": {"python_version": sys.version}
            }
        except Exception as e:
            return {"status": "fail", "message": f"Failed to check dependencies: {e}"}
            
    async def check_web_ui_status(self) -> Dict[str, Any]:
        """Check Web UI status"""
        try:
            webui_path = self.hummingbot_path / "webui"
            
            if not webui_path.exists():
                return {"status": "warn", "message": "Web UI not installed"}
                
            # Check if Docker is running
            try:
                result = subprocess.run(["docker", "ps"], capture_output=True, text=True)
                if result.returncode != 0:
                    return {"status": "warn", "message": "Docker not running"}
            except FileNotFoundError:
                return {"status": "warn", "message": "Docker not installed"}
                
            # Check if Web UI containers are running
            try:
                result = subprocess.run(
                    ["docker-compose", "ps", "-q"], 
                    cwd=webui_path, 
                    capture_output=True, 
                    text=True
                )
                containers = result.stdout.strip().split('\n') if result.stdout.strip() else []
                
                if not containers:
                    return {"status": "warn", "message": "Web UI containers not running"}
                    
                return {
                    "status": "pass",
                    "message": "Web UI running",
                    "data": {"containers": len(containers)}
                }
            except Exception:
                return {"status": "warn", "message": "Could not check Web UI containers"}
                
        except Exception as e:
            return {"status": "warn", "message": f"Failed to check Web UI: {e}"}
            
    async def check_gate_io_connectivity(self) -> Dict[str, Any]:
        """Check Gate.io API connectivity"""
        try:
            import aiohttp
            import ssl
            
            # Test basic connectivity to Gate.io
            timeout = aiohttp.ClientTimeout(total=10)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                try:
                    async with session.get("https://api.gateio.ws/api/v4/spot/currencies") as response:
                        if response.status == 200:
                            return {
                                "status": "pass",
                                "message": "Gate.io API connectivity OK",
                                "data": {"status_code": response.status}
                            }
                        else:
                            return {
                                "status": "warn", 
                                "message": f"Gate.io API returned status {response.status}"
                            }
                except Exception as e:
                    return {"status": "warn", "message": f"Gate.io API connection failed: {e}"}
                    
        except ImportError:
            return {"status": "warn", "message": "aiohttp not available for connectivity test"}
        except Exception as e:
            return {"status": "fail", "message": f"Failed to test connectivity: {e}"}


async def main():
    """Main health check entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Gate.io Arbitrage Suite Health Check")
    parser.add_argument("--hummingbot-path", default=None, help="Path to Hummingbot installation")
    parser.add_argument("--output", choices=["json", "text"], default="text", help="Output format")
    parser.add_argument("--exit-code", action="store_true", help="Exit with non-zero code on failures")
    
    args = parser.parse_args()
    
    checker = HealthChecker(args.hummingbot_path)
    
    # Add all health checks
    checker.add_check("system_resources", checker.check_system_resources)
    checker.add_check("hummingbot_installation", checker.check_hummingbot_installation, critical=True)
    checker.add_check("arbitrage_controllers", checker.check_arbitrage_controllers, critical=True)
    checker.add_check("configuration_files", checker.check_configuration_files, critical=True)
    checker.add_check("python_dependencies", checker.check_python_dependencies, critical=True)
    checker.add_check("web_ui_status", checker.check_web_ui_status)
    checker.add_check("gate_io_connectivity", checker.check_gate_io_connectivity)
    
    # Run all checks
    results = await checker.run_all_checks()
    
    # Output results
    if args.output == "json":
        print(json.dumps(results, indent=2))
    else:
        print("\n" + "="*60)
        print("  GATE.IO ARBITRAGE SUITE HEALTH CHECK")
        print("="*60)
        print(f"Overall Status: {results['overall_status'].upper()}")
        print(f"Checks: {results['passed']} passed, {results['failed']} failed, {results['warnings']} warnings")
        print(f"Duration: {results['duration']:.2f}s")
        print()
        
        for check_name, check_result in results['checks'].items():
            status_icon = "✓" if check_result['status'] == "pass" else "⚠" if check_result['status'] == "warn" else "✗"
            critical_marker = " [CRITICAL]" if check_result.get('critical') else ""
            print(f"{status_icon} {check_name}{critical_marker}: {check_result['message']}")
            
        print("\n" + "="*60)
    
    # Exit with appropriate code
    if args.exit_code and results['failed'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
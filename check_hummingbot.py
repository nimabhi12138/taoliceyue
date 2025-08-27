#!/usr/bin/env python3
"""
Hummingbot Compatibility Checker
Deep check for Hummingbot-specific requirements and best practices
"""

import re
from pathlib import Path
from typing import Dict, List


class HummingbotChecker:
    """Check Hummingbot-specific compatibility"""
    
    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self.errors = []
        self.warnings = []
        
    def check_all(self) -> bool:
        """Run all Hummingbot compatibility checks"""
        print("🤖 Starting Hummingbot compatibility check...")
        
        # Check script strategies
        self.check_script_strategy_compatibility()
        
        # Check controller compatibility
        self.check_controller_compatibility()
        
        # Check configuration compatibility
        self.check_config_compatibility()
        
        # Check Hummingbot API usage
        self.check_api_usage()
        
        self.print_summary()
        return len(self.errors) == 0
    
    def check_script_strategy_compatibility(self):
        """Check script strategy Hummingbot compatibility"""
        print("\n📜 Checking script strategy compatibility...")
        
        script_files = list((self.root_path / "scripts").glob("*.py"))
        
        for script_file in script_files:
            if script_file.name.startswith("__"):
                continue
                
            print(f"  📄 {script_file.name}")
            
            with open(script_file, 'r') as f:
                content = f.read()
            
            if "ScriptStrategyBase" not in content:
                continue
            
            # Check required Hummingbot patterns
            checks = [
                # Required methods
                ("def on_tick(self)", "on_tick method signature"),
                ("def format_status(self)", "format_status method signature"),
                ("def __init__(self, connectors", "__init__ with connectors parameter"),
                
                # Required properties
                ("markets = {", "markets class attribute"),
                ("self.ready_to_trade", "ready_to_trade property usage"),
                
                # Best practices
                ("self.logger", "logger usage"),
                ("self.connectors", "connectors attribute"),
            ]
            
            for pattern, description in checks:
                if pattern in content:
                    print(f"    ✅ {description}")
                else:
                    # Special checks for alternatives
                    if pattern == "def on_tick(self)" and "def on_tick(" in content:
                        print(f"    ✅ {description} (alternative signature)")
                    elif pattern == "self.ready_to_trade" and "ready_to_trade" in content:
                        print(f"    ✅ {description}")
                    else:
                        self.warnings.append(f"{script_file.name}: Missing {description}")
                        print(f"    ⚠️  Missing {description}")
            
            # Check for common mistakes
            mistakes = [
                ("import hummingbot", "Direct hummingbot import (should be specific)"),
                ("time.sleep(", "Blocking sleep in async context"),
                ("print(", "Using print instead of logger"),
            ]
            
            for pattern, issue in mistakes:
                if pattern in content:
                    self.warnings.append(f"{script_file.name}: {issue}")
                    print(f"    ⚠️  {issue}")
    
    def check_controller_compatibility(self):
        """Check controller Hummingbot compatibility"""
        print("\n🎮 Checking controller compatibility...")
        
        controller_files = list((self.root_path / "controllers" / "arbitrage").glob("*.py"))
        
        for controller_file in controller_files:
            if controller_file.name.startswith("__") or controller_file.name in ["fee_model.py", "risk_manager.py"]:
                continue
                
            print(f"  📄 {controller_file.name}")
            
            with open(controller_file, 'r') as f:
                content = f.read()
            
            # Check StrategyV2Base usage
            if "StrategyV2Base" in content:
                checks = [
                    ("def __init__(self, config", "__init__ with config parameter"),
                    ("super().__init__(config)", "proper super() initialization"),
                    ("async def process_tick", "async process_tick method"),
                    ("self.connectors", "connectors access"),
                    ("self.logger", "logger setup"),
                ]
                
                for pattern, description in checks:
                    if pattern in content:
                        print(f"    ✅ {description}")
                    else:
                        # Check alternatives
                        if pattern == "super().__init__(config)" and "super().__init__" in content:
                            print(f"    ✅ {description}")
                        else:
                            self.warnings.append(f"{controller_file.name}: Missing {description}")
                            print(f"    ⚠️  Missing {description}")
            
            # Check for proper async patterns
            if "async def" in content:
                if "await" not in content:
                    self.warnings.append(f"{controller_file.name}: async methods without await")
                    print(f"    ⚠️  async methods without await")
                else:
                    print(f"    ✅ Proper async/await usage")
    
    def check_config_compatibility(self):
        """Check configuration Hummingbot compatibility"""
        print("\n⚙️ Checking configuration compatibility...")
        
        yaml_files = list(self.root_path.rglob("*.yml"))
        
        for yaml_file in yaml_files:
            print(f"  📄 {yaml_file.name}")
            
            try:
                with open(yaml_file, 'r') as f:
                    content = f.read()
                
                # Check script configs
                if "script_config" in content or "conf/scripts/" in str(yaml_file):
                    required_fields = [
                        ("script_file_name:", "script file name"),
                        ("markets:", "markets definition"),
                    ]
                    
                    for field, description in required_fields:
                        if field in content:
                            print(f"    ✅ {description}")
                        else:
                            self.warnings.append(f"{yaml_file.name}: Missing {description}")
                            print(f"    ⚠️  Missing {description}")
                
                # Check controller configs
                if "controller_config" in content or "conf/controllers/" in str(yaml_file):
                    required_fields = [
                        ("controller_name:", "controller name"),
                        ("controller_type:", "controller type"),
                    ]
                    
                    for field, description in required_fields:
                        if field in content:
                            print(f"    ✅ {description}")
                        else:
                            self.warnings.append(f"{yaml_file.name}: Missing {description}")
                            print(f"    ⚠️  Missing {description}")
                
                # Check Gate.io specific configs
                if "gate_io" in content:
                    if "maker:" in content and "taker:" in content:
                        print(f"    ✅ Gate.io fee configuration")
                    else:
                        print(f"    ℹ️  Gate.io configuration present")
                        
            except Exception as e:
                self.errors.append(f"{yaml_file.name}: Error reading - {e}")
                print(f"    ❌ Error reading: {e}")
    
    def check_api_usage(self):
        """Check Hummingbot API usage patterns"""
        print("\n🔌 Checking API usage patterns...")
        
        py_files = list(self.root_path.rglob("*.py"))
        
        for py_file in py_files:
            if py_file.name.startswith("__") or "test_" in py_file.name:
                continue
                
            try:
                with open(py_file, 'r') as f:
                    content = f.read()
                
                # Skip files without Hummingbot imports
                if "hummingbot" not in content:
                    continue
                    
                print(f"  📄 {py_file.name}")
                
                # Check proper import patterns
                good_patterns = [
                    ("from hummingbot.strategy.script_strategy_base", "ScriptStrategyBase import"),
                    ("from hummingbot.strategy.strategy_v2_base", "StrategyV2Base import"),
                    ("from hummingbot.connector.connector_base", "ConnectorBase import"),
                    ("from hummingbot.core.data_type.common", "Common types import"),
                ]
                
                found_imports = []
                for pattern, description in good_patterns:
                    if pattern in content:
                        found_imports.append(description)
                        print(f"    ✅ {description}")
                
                if not found_imports:
                    print(f"    ℹ️  No standard Hummingbot imports found")
                
                # Check for deprecated patterns
                deprecated_patterns = [
                    ("from hummingbot.strategy.strategy_base import StrategyBase", "Use StrategyV2Base instead"),
                    ("from hummingbot.core.utils.async_utils", "Some async utils are deprecated"),
                ]
                
                for pattern, warning in deprecated_patterns:
                    if pattern in content:
                        self.warnings.append(f"{py_file.name}: {warning}")
                        print(f"    ⚠️  {warning}")
                
                # Check for proper error handling
                if "try:" in content and "except:" in content:
                    print(f"    ✅ Error handling present")
                elif "try:" in content:
                    print(f"    ✅ Error handling present")
                    
            except Exception as e:
                self.warnings.append(f"Error checking {py_file.name}: {e}")
    
    def print_summary(self):
        """Print check summary"""
        print("\n" + "="*60)
        print("🤖 HUMMINGBOT COMPATIBILITY SUMMARY")
        print("="*60)
        
        if not self.errors and not self.warnings:
            print("🎉 All Hummingbot compatibility checks passed!")
        else:
            if self.errors:
                print(f"❌ {len(self.errors)} errors found:")
                for i, error in enumerate(self.errors, 1):
                    print(f"  {i}. {error}")
            
            if self.warnings:
                print(f"\n⚠️  {len(self.warnings)} warnings found:")
                for i, warning in enumerate(self.warnings, 1):
                    print(f"  {i}. {warning}")
        
        print("="*60)


if __name__ == "__main__":
    checker = HummingbotChecker("/workspace")
    checker.check_all()
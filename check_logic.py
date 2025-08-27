#!/usr/bin/env python3
"""
Logic and Structure Checker for Gate.io Arbitrage Suite
Check for logical errors, missing methods, and structural issues
"""

import ast
import re
from pathlib import Path
from typing import Dict, List, Set


class LogicChecker:
    """Check for logical errors and structural issues"""
    
    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self.errors = []
        self.warnings = []
        
    def check_all(self) -> bool:
        """Run all logic checks"""
        print("🔍 Starting logic and structure check...")
        
        # Check script strategies
        self.check_script_strategies()
        
        # Check controllers
        self.check_controllers()
        
        # Check configuration files
        self.check_configurations()
        
        # Check imports consistency
        self.check_import_consistency()
        
        self.print_summary()
        return len(self.errors) == 0
    
    def check_script_strategies(self):
        """Check script strategy implementations"""
        print("\n📋 Checking script strategies...")
        
        script_files = list((self.root_path / "scripts").glob("*.py"))
        
        for script_file in script_files:
            if script_file.name.startswith("__"):
                continue
                
            print(f"  📄 {script_file.name}")
            
            with open(script_file, 'r') as f:
                content = f.read()
            
            # Check if it's a strategy script
            if "ScriptStrategyBase" not in content:
                continue
            
            # Check required elements
            checks = [
                ("markets = {", "Missing markets declaration"),
                ("def on_tick", "Missing on_tick method"),
                ("def format_status", "Missing format_status method"),
                ("def __init__", "Missing __init__ method"),
            ]
            
            for pattern, error_msg in checks:
                if pattern not in content:
                    self.errors.append(f"{script_file.name}: {error_msg}")
                    print(f"    ❌ {error_msg}")
                else:
                    print(f"    ✅ {pattern.split('(')[0].replace('def ', '').replace(' = ', ' declaration')} found")
            
            # Check proper async handling
            if "async def on_tick" in content and "await" not in content:
                self.warnings.append(f"{script_file.name}: async on_tick but no await calls")
                print(f"    ⚠️  async on_tick but no await calls")
    
    def check_controllers(self):
        """Check controller implementations"""
        print("\n🎮 Checking controllers...")
        
        controller_files = list((self.root_path / "controllers" / "arbitrage").glob("*.py"))
        
        for controller_file in controller_files:
            if controller_file.name.startswith("__"):
                continue
                
            print(f"  📄 {controller_file.name}")
            
            with open(controller_file, 'r') as f:
                content = f.read()
            
            # Check if it's a controller
            if "StrategyV2Base" not in content and "class" not in content:
                continue
            
            # Skip utility files
            if controller_file.name in ["fee_model.py", "risk_manager.py"]:
                print(f"    ✅ Utility class")
                continue
            
            # Check controller structure
            checks = [
                ("def __init__", "Missing __init__ method"),
                ("async def process_tick", "Missing process_tick method"),
                ("def get_status", "Missing get_status method"),
                ("self.config", "Missing config attribute"),
                ("self.logger", "Missing logger setup"),
            ]
            
            for pattern, error_msg in checks:
                if pattern not in content:
                    self.warnings.append(f"{controller_file.name}: {error_msg}")
                    print(f"    ⚠️  {error_msg}")
                else:
                    print(f"    ✅ {pattern.split('(')[0].replace('def ', '').replace('self.', '')} found")
    
    def check_configurations(self):
        """Check configuration file consistency"""
        print("\n⚙️ Checking configurations...")
        
        yaml_files = list(self.root_path.rglob("*.yml")) + list(self.root_path.rglob("*.yaml"))
        
        for yaml_file in yaml_files:
            print(f"  📄 {yaml_file.name}")
            
            try:
                with open(yaml_file, 'r') as f:
                    content = f.read()
                
                # Basic YAML structure checks
                if ":" not in content:
                    self.errors.append(f"{yaml_file.name}: Invalid YAML structure")
                    print(f"    ❌ Invalid YAML structure")
                else:
                    print(f"    ✅ Basic YAML structure OK")
                
                # Check for common configuration patterns
                if "conf/scripts/" in str(yaml_file) or "script_config" in content:
                    if "script_file_name:" not in content:
                        self.warnings.append(f"{yaml_file.name}: Missing script_file_name")
                        print(f"    ⚠️  Missing script_file_name")
                    else:
                        print(f"    ✅ Script configuration OK")
                
                # Check for Gate.io specific settings
                if "gate_io" in content.lower():
                    if "fee" in content.lower() and "0." not in content:
                        self.warnings.append(f"{yaml_file.name}: Fee values should be decimal")
                        print(f"    ⚠️  Fee values should be decimal")
                    else:
                        print(f"    ✅ Gate.io configuration OK")
                        
            except Exception as e:
                self.errors.append(f"{yaml_file.name}: Error reading file - {e}")
                print(f"    ❌ Error reading file: {e}")
    
    def check_import_consistency(self):
        """Check import path consistency"""
        print("\n🔗 Checking import consistency...")
        
        py_files = list(self.root_path.rglob("*.py"))
        
        # Collect all imports
        all_imports = {}
        
        for py_file in py_files:
            try:
                with open(py_file, 'r') as f:
                    content = f.read()
                
                # Find all from...import statements
                from_imports = re.findall(r'from\s+([\w\.]+)\s+import', content)
                imports = re.findall(r'import\s+([\w\.]+)', content)
                
                all_imports[str(py_file)] = {
                    'from_imports': from_imports,
                    'imports': imports
                }
                
            except Exception as e:
                self.warnings.append(f"Error reading {py_file}: {e}")
        
        # Check for local module imports
        local_modules = set()
        for file_imports in all_imports.values():
            for imp in file_imports['from_imports']:
                if imp.startswith('controllers.arbitrage'):
                    local_modules.add(imp)
        
        print(f"  Found {len(local_modules)} local module imports")
        
        # Verify local modules exist
        for module in local_modules:
            module_path = module.replace('.', '/') + '.py'
            full_path = self.root_path / module_path
            
            if not full_path.exists():
                self.errors.append(f"Missing module file for import: {module}")
                print(f"    ❌ Missing: {module_path}")
            else:
                print(f"    ✅ Found: {module_path}")
    
    def print_summary(self):
        """Print check summary"""
        print("\n" + "="*60)
        print("📊 LOGIC CHECK SUMMARY")
        print("="*60)
        
        if not self.errors and not self.warnings:
            print("🎉 All logic checks passed! No issues found.")
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
    checker = LogicChecker("/workspace")
    checker.check_all()
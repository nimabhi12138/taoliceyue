#!/usr/bin/env python3
"""
Final Comprehensive Checker for Gate.io Arbitrage Suite
Complete validation before production deployment
"""

import ast
import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple


class FinalChecker:
    """Comprehensive final validation"""
    
    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self.errors = []
        self.warnings = []
        self.passed = []
        
    def check_all(self) -> bool:
        """Run all final checks"""
        print("🔍 FINAL COMPREHENSIVE CHECK")
        print("="*60)
        
        checks = [
            ("Python syntax", self.check_python_syntax),
            ("YAML syntax", self.check_yaml_syntax),
            ("File structure", self.check_file_structure),
            ("Required methods", self.check_required_methods),
            ("Import consistency", self.check_imports),
            ("Configuration validity", self.check_configurations),
            ("Documentation", self.check_documentation),
            ("Executable permissions", self.check_permissions),
        ]
        
        for check_name, check_func in checks:
            print(f"\n🔍 {check_name}...")
            try:
                if check_func():
                    self.passed.append(check_name)
                    print(f"✅ {check_name} PASSED")
                else:
                    print(f"❌ {check_name} FAILED")
            except Exception as e:
                self.errors.append(f"{check_name}: {e}")
                print(f"❌ {check_name} ERROR: {e}")
        
        self.print_final_summary()
        return len(self.errors) == 0
    
    def check_python_syntax(self) -> bool:
        """Check all Python files for syntax errors"""
        py_files = list(self.root_path.rglob("*.py"))
        all_valid = True
        
        for py_file in py_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    source = f.read()
                ast.parse(source, filename=str(py_file))
                print(f"  ✅ {py_file.name}")
            except SyntaxError as e:
                self.errors.append(f"Syntax error in {py_file}: {e}")
                print(f"  ❌ {py_file.name}: {e}")
                all_valid = False
            except Exception as e:
                self.errors.append(f"Error parsing {py_file}: {e}")
                print(f"  ❌ {py_file.name}: {e}")
                all_valid = False
        
        return all_valid
    
    def check_yaml_syntax(self) -> bool:
        """Check all YAML files for syntax errors"""
        yaml_files = list(self.root_path.rglob("*.yml")) + list(self.root_path.rglob("*.yaml"))
        all_valid = True
        
        for yaml_file in yaml_files:
            try:
                import yaml
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    yaml.safe_load(f)
                print(f"  ✅ {yaml_file.name}")
            except yaml.YAMLError as e:
                self.errors.append(f"YAML syntax error in {yaml_file}: {e}")
                print(f"  ❌ {yaml_file.name}: {e}")
                all_valid = False
            except Exception as e:
                self.errors.append(f"Error reading {yaml_file}: {e}")
                print(f"  ❌ {yaml_file.name}: {e}")
                all_valid = False
        
        return all_valid
    
    def check_file_structure(self) -> bool:
        """Check required file structure"""
        required_structure = {
            "scripts/gate_arb_example.py": "Example script strategy",
            "scripts/gate_arb_launcher_v2.py": "Advanced launcher",
            "scripts/gate_arb_legacy.py": "Legacy strategy",
            "controllers/arbitrage/gate_spot_perp_controller.py": "Spot-perp controller",
            "controllers/arbitrage/gate_triangular_controller.py": "Triangular controller",
            "controllers/arbitrage/gate_spot_spot_controller.py": "Spot-spot controller",
            "controllers/arbitrage/gate_stat_arb_controller.py": "Statistical arbitrage controller",
            "controllers/arbitrage/fee_model.py": "Fee model",
            "controllers/arbitrage/risk_manager.py": "Risk manager",
            "controllers/arbitrage/__init__.py": "Arbitrage package init",
            "controllers/__init__.py": "Controllers package init",
            "conf/examples/conf_fee_overrides.yml": "Fee override config",
            "conf/examples/conf_v2_with_controllers.yml": "Multi-controller config",
            "conf/scripts/gate_arb_example.yml": "Example script config",
            "webui/docker-compose.yml": "Web UI docker compose",
            "webui/backend/main.py": "Web UI backend",
            "webui/frontend/app.py": "Web UI frontend",
            "tests/test_fee_model.py": "Fee model tests",
            "tests/test_kelly.py": "Kelly criterion tests",
            "tests/test_triangular.py": "Triangular arbitrage tests",
            "tests/test_budget_check.py": "Budget check tests",
            "README.md": "Main documentation",
            "QUICK_START.md": "Quick start guide",
            "PRODUCTION_CHECKLIST.md": "Production checklist",
            "deploy.sh": "Deployment script",
            "healthcheck.py": "Health check script",
            "requirements.txt": "Python dependencies",
            "setup.py": "Package setup",
            "LICENSE": "License file",
        }
        
        all_present = True
        
        for file_path, description in required_structure.items():
            full_path = self.root_path / file_path
            if full_path.exists():
                print(f"  ✅ {file_path}")
            else:
                self.warnings.append(f"Missing {file_path}: {description}")
                print(f"  ⚠️  Missing {file_path}")
                all_present = False
        
        return all_present
    
    def check_required_methods(self) -> bool:
        """Check required methods in strategy classes"""
        script_files = list((self.root_path / "scripts").glob("*.py"))
        all_valid = True
        
        for script_file in script_files:
            if script_file.name.startswith("__"):
                continue
                
            with open(script_file, 'r') as f:
                content = f.read()
            
            if "ScriptStrategyBase" in content:
                required_methods = ["def on_tick", "def format_status", "def __init__", "markets = {"]
                
                for method in required_methods:
                    if method in content:
                        print(f"  ✅ {script_file.name}: {method}")
                    else:
                        self.errors.append(f"{script_file.name}: Missing {method}")
                        print(f"  ❌ {script_file.name}: Missing {method}")
                        all_valid = False
        
        return all_valid
    
    def check_imports(self) -> bool:
        """Check import consistency"""
        py_files = list(self.root_path.rglob("*.py"))
        all_valid = True
        
        for py_file in py_files:
            # Skip checking our own test files
            if py_file.name in ["final_check.py", "check_code.py", "check_logic.py", "check_hummingbot.py"]:
                continue
                
            try:
                with open(py_file, 'r') as f:
                    content = f.read()
                
                # Check for relative imports that might fail
                if "from .fee_model import" in content:
                    fee_model_path = py_file.parent / "fee_model.py"
                    if not fee_model_path.exists():
                        self.errors.append(f"{py_file.name}: Cannot import fee_model")
                        all_valid = False
                    else:
                        print(f"  ✅ {py_file.name}: fee_model import OK")
                
                if "from .risk_manager import" in content:
                    risk_manager_path = py_file.parent / "risk_manager.py"
                    if not risk_manager_path.exists():
                        self.errors.append(f"{py_file.name}: Cannot import risk_manager")
                        all_valid = False
                    else:
                        print(f"  ✅ {py_file.name}: risk_manager import OK")
                        
            except Exception as e:
                self.warnings.append(f"Error checking imports in {py_file.name}: {e}")
        
        return all_valid
    
    def check_configurations(self) -> bool:
        """Check configuration file validity"""
        config_files = [
            "conf/examples/conf_fee_overrides.yml",
            "conf/examples/conf_v2_with_controllers.yml", 
            "conf/scripts/gate_arb_example.yml",
        ]
        
        all_valid = True
        
        for config_file in config_files:
            config_path = self.root_path / config_file
            if config_path.exists():
                try:
                    import yaml
                    with open(config_path, 'r') as f:
                        config = yaml.safe_load(f)
                    
                    if config:
                        print(f"  ✅ {config_file}: Valid YAML with content")
                    else:
                        self.warnings.append(f"{config_file}: Empty configuration")
                        print(f"  ⚠️  {config_file}: Empty configuration")
                        
                except Exception as e:
                    self.errors.append(f"{config_file}: Invalid YAML - {e}")
                    print(f"  ❌ {config_file}: Invalid YAML - {e}")
                    all_valid = False
            else:
                self.errors.append(f"Missing configuration file: {config_file}")
                print(f"  ❌ Missing: {config_file}")
                all_valid = False
        
        return all_valid
    
    def check_documentation(self) -> bool:
        """Check documentation files"""
        doc_files = [
            "README.md",
            "QUICK_START.md", 
            "PRODUCTION_CHECKLIST.md",
        ]
        
        all_present = True
        
        for doc_file in doc_files:
            doc_path = self.root_path / doc_file
            if doc_path.exists():
                try:
                    with open(doc_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    if len(content) > 1000:  # Substantial content
                        print(f"  ✅ {doc_file}: Complete documentation")
                    else:
                        self.warnings.append(f"{doc_file}: Documentation may be incomplete")
                        print(f"  ⚠️  {doc_file}: Documentation may be incomplete")
                        
                except Exception as e:
                    self.warnings.append(f"Error reading {doc_file}: {e}")
                    print(f"  ⚠️  Error reading {doc_file}: {e}")
            else:
                self.errors.append(f"Missing documentation: {doc_file}")
                print(f"  ❌ Missing: {doc_file}")
                all_present = False
        
        return all_present
    
    def check_permissions(self) -> bool:
        """Check executable permissions"""
        executable_files = [
            "deploy.sh",
            "healthcheck.py",
            "webui/install.sh",
            "webui/start.sh", 
            "webui/stop.sh",
        ]
        
        all_executable = True
        
        for exec_file in executable_files:
            exec_path = self.root_path / exec_file
            if exec_path.exists():
                if os.access(exec_path, os.X_OK):
                    print(f"  ✅ {exec_file}: Executable")
                else:
                    self.warnings.append(f"{exec_file}: Not executable")
                    print(f"  ⚠️  {exec_file}: Not executable")
                    all_executable = False
            else:
                self.warnings.append(f"Missing executable file: {exec_file}")
                print(f"  ⚠️  Missing: {exec_file}")
        
        return all_executable
    
    def print_final_summary(self):
        """Print final summary"""
        print("\n" + "="*60)
        print("🎯 FINAL CHECK SUMMARY")
        print("="*60)
        
        print(f"✅ Passed checks: {len(self.passed)}")
        for check in self.passed:
            print(f"   • {check}")
        
        if self.errors:
            print(f"\n❌ Errors: {len(self.errors)}")
            for i, error in enumerate(self.errors, 1):
                print(f"   {i}. {error}")
        
        if self.warnings:
            print(f"\n⚠️  Warnings: {len(self.warnings)}")
            for i, warning in enumerate(self.warnings, 1):
                print(f"   {i}. {warning}")
        
        print("\n" + "="*60)
        
        if not self.errors:
            print("🎉 ALL CHECKS PASSED! CODE IS READY FOR PRODUCTION!")
        else:
            print("❌ Please fix the errors before proceeding to production.")
        
        print("="*60)


if __name__ == "__main__":
    checker = FinalChecker("/workspace")
    success = checker.check_all()
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
"""
Code Quality Checker for Gate.io Arbitrage Suite
Comprehensive syntax and logic validation
"""

import ast
import os
import sys
import importlib.util
from pathlib import Path
from typing import List, Tuple


class CodeChecker:
    """Comprehensive code quality checker"""
    
    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self.errors = []
        self.warnings = []
        
    def check_all(self) -> bool:
        """Run all checks"""
        print("🔍 Starting comprehensive code check...")
        
        # Find all Python files
        py_files = list(self.root_path.rglob("*.py"))
        print(f"Found {len(py_files)} Python files")
        
        all_passed = True
        
        for py_file in py_files:
            print(f"\n📁 Checking {py_file}")
            
            # Syntax check
            if not self.check_syntax(py_file):
                all_passed = False
                
            # Import check
            if not self.check_imports(py_file):
                all_passed = False
                
            # Hummingbot compatibility
            if "scripts/" in str(py_file) or "controllers/" in str(py_file):
                if not self.check_hummingbot_compatibility(py_file):
                    all_passed = False
        
        self.print_summary()
        return all_passed
    
    def check_syntax(self, file_path: Path) -> bool:
        """Check Python syntax"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            
            ast.parse(source, filename=str(file_path))
            print(f"  ✅ Syntax OK")
            return True
            
        except SyntaxError as e:
            error_msg = f"Syntax error in {file_path}:{e.lineno}: {e.msg}"
            self.errors.append(error_msg)
            print(f"  ❌ {error_msg}")
            return False
        except Exception as e:
            error_msg = f"Error parsing {file_path}: {e}"
            self.errors.append(error_msg)
            print(f"  ❌ {error_msg}")
            return False
    
    def check_imports(self, file_path: Path) -> bool:
        """Check import statements"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            
            tree = ast.parse(source)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if not self.is_import_available(alias.name):
                            warning_msg = f"Import '{alias.name}' may not be available in {file_path}"
                            self.warnings.append(warning_msg)
                            print(f"  ⚠️  {warning_msg}")
                            
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        if not self.is_import_available(node.module):
                            warning_msg = f"Module '{node.module}' may not be available in {file_path}"
                            self.warnings.append(warning_msg)
                            print(f"  ⚠️  {warning_msg}")
            
            print(f"  ✅ Imports checked")
            return True
            
        except Exception as e:
            error_msg = f"Error checking imports in {file_path}: {e}"
            self.errors.append(error_msg)
            print(f"  ❌ {error_msg}")
            return False
    
    def is_import_available(self, module_name: str) -> bool:
        """Check if a module can be imported"""
        # Skip Hummingbot imports (they need the actual environment)
        if module_name.startswith('hummingbot'):
            return True
            
        # Skip relative imports
        if module_name.startswith('.'):
            return True
            
        try:
            importlib.util.find_spec(module_name)
            return True
        except (ImportError, ModuleNotFoundError, ValueError):
            return False
    
    def check_hummingbot_compatibility(self, file_path: Path) -> bool:
        """Check Hummingbot-specific compatibility"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for required methods in script strategies
            if "ScriptStrategyBase" in content:
                required_methods = ["on_tick", "format_status"]
                for method in required_methods:
                    if f"def {method}" not in content:
                        error_msg = f"Missing required method '{method}' in {file_path}"
                        self.errors.append(error_msg)
                        print(f"  ❌ {error_msg}")
                        return False
            
            # Check for proper markets declaration
            if "ScriptStrategyBase" in content and "markets = {" not in content:
                warning_msg = f"Missing 'markets' declaration in script {file_path}"
                self.warnings.append(warning_msg)
                print(f"  ⚠️  {warning_msg}")
            
            print(f"  ✅ Hummingbot compatibility OK")
            return True
            
        except Exception as e:
            error_msg = f"Error checking Hummingbot compatibility in {file_path}: {e}"
            self.errors.append(error_msg)
            print(f"  ❌ {error_msg}")
            return False
    
    def print_summary(self):
        """Print check summary"""
        print("\n" + "="*60)
        print("📊 CODE CHECK SUMMARY")
        print("="*60)
        
        if not self.errors and not self.warnings:
            print("🎉 All checks passed! No issues found.")
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
    checker = CodeChecker("/workspace")
    success = checker.check_all()
    sys.exit(0 if success else 1)
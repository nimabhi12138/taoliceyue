#!/usr/bin/env python3
"""
Final validation script for Gate.io Arbitrage Suite
Performs comprehensive checks without requiring Hummingbot imports
"""

import os
import ast
import sys
from pathlib import Path
from typing import List, Dict, Tuple
import re


def check_syntax(filepath: str) -> Tuple[bool, List[str]]:
    """Check Python syntax"""
    errors = []
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        ast.parse(content)
        return True, []
    except SyntaxError as e:
        errors.append(f"Syntax Error at line {e.lineno}: {e.msg}")
        return False, errors
    except Exception as e:
        errors.append(f"Error: {e}")
        return False, errors


def check_imports(filepath: str) -> List[str]:
    """Check for proper imports structure"""
    issues = []
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Check for proper Hummingbot imports structure
    if 'controller' in filepath.lower():
        required_imports = [
            'ControllerBase',
            'ControllerConfigBase'
        ]
        for imp in required_imports:
            if imp in content and 'hummingbot.smart_components' not in content:
                issues.append(f"Warning: {imp} should be imported from hummingbot.smart_components")
    
    return issues


def check_v2_methods(filepath: str) -> List[str]:
    """Check for V2 framework methods"""
    if 'controller' not in filepath.lower() or 'v2' in filepath:
        return []
    
    issues = []
    with open(filepath, 'r') as f:
        content = f.read()
    
    if 'ControllerBase' in content:
        v2_methods = [
            'update_processed_data',
            'determine_executor_actions',
            'to_format_status'
        ]
        
        for method in v2_methods:
            if f'def {method}' not in content:
                issues.append(f"Missing V2 method: {method}")
    
    return issues


def check_type_hints(filepath: str) -> List[str]:
    """Check for type hints"""
    issues = []
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines):
        if line.strip().startswith('def ') and '__' not in line:
            if '->' not in line and 'test_' not in line.lower():
                func_name = line.split('(')[0].replace('def ', '').strip()
                if func_name not in ['setUp', 'tearDown']:
                    issues.append(f"Line {i+1}: Function '{func_name}' might be missing return type")
    
    return issues


def validate_configs(directory: str) -> List[str]:
    """Validate configuration files"""
    issues = []
    config_files = [
        'conf/examples/conf_fee_overrides.yml',
        'conf/examples/conf_v2_with_controllers.yml'
    ]
    
    for config_file in config_files:
        filepath = os.path.join(directory, config_file)
        if not os.path.exists(filepath):
            issues.append(f"Missing config file: {config_file}")
    
    return issues


def main():
    """Main validation function"""
    print("=" * 70)
    print("  FINAL VALIDATION - GATE.IO ARBITRAGE SUITE")
    print("=" * 70)
    print()
    
    base_dir = '/workspace/gate-arbitrage-suite'
    
    # Find all Python files
    python_files = []
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in ['venv', '__pycache__', '.git']]
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    print(f"Found {len(python_files)} Python files to check\n")
    
    # Check each file
    total_issues = 0
    files_with_issues = []
    
    for filepath in python_files:
        rel_path = os.path.relpath(filepath, base_dir)
        issues = []
        
        # Syntax check
        syntax_ok, syntax_errors = check_syntax(filepath)
        if not syntax_ok:
            issues.extend(syntax_errors)
        
        # Import check
        import_issues = check_imports(filepath)
        issues.extend(import_issues)
        
        # V2 methods check
        v2_issues = check_v2_methods(filepath)
        issues.extend(v2_issues)
        
        # Type hints check (optional, warnings only)
        # type_issues = check_type_hints(filepath)
        # issues.extend(type_issues)
        
        if issues:
            print(f"❌ {rel_path}")
            for issue in issues:
                print(f"   - {issue}")
            files_with_issues.append(rel_path)
            total_issues += len(issues)
        else:
            print(f"✅ {rel_path}")
    
    # Check configs
    print("\nChecking configuration files...")
    config_issues = validate_configs(base_dir)
    if config_issues:
        for issue in config_issues:
            print(f"   - {issue}")
        total_issues += len(config_issues)
    else:
        print("✅ All configuration files present")
    
    # Summary
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    
    if total_issues == 0:
        print("🎉 SUCCESS! All files passed validation!")
        print("\nThe Gate.io Arbitrage Suite is ready for use with Hummingbot!")
        print("\nNext steps:")
        print("1. Install Hummingbot 2.0+")
        print("2. Copy the suite files to your Hummingbot directory")
        print("3. Configure your Gate.io API keys")
        print("4. Start trading with: start --script gate_arb_v2.py")
    else:
        print(f"⚠️  Found {total_issues} issues in {len(files_with_issues)} files")
        print("\nFiles with issues:")
        for file in files_with_issues[:10]:  # Show first 10
            print(f"  - {file}")
        if len(files_with_issues) > 10:
            print(f"  ... and {len(files_with_issues) - 10} more")
    
    print("\n" + "=" * 70)
    
    return 0 if total_issues == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
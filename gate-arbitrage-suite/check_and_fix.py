#!/usr/bin/env python3
"""
Comprehensive code checker and fixer for Gate.io Arbitrage Suite
Checks all Python files for syntax errors, import issues, and Hummingbot compatibility
"""

import os
import ast
import sys
import importlib.util
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import re


class CodeChecker:
    """Check and fix Python code issues"""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.fixed = []
        self.files_checked = 0
        self.files_with_errors = 0
        
    def check_file(self, filepath: str) -> List[str]:
        """Check a single Python file for issues"""
        issues = []
        
        try:
            with open(filepath, 'r') as f:
                content = f.read()
            
            # 1. Check syntax with AST
            try:
                ast.parse(content)
            except SyntaxError as e:
                issues.append(f"Syntax Error at line {e.lineno}: {e.msg}")
                
            # 2. Check imports
            import_issues = self.check_imports(content, filepath)
            issues.extend(import_issues)
            
            # 3. Check Hummingbot specific patterns
            hb_issues = self.check_hummingbot_patterns(content, filepath)
            issues.extend(hb_issues)
            
            # 4. Check type hints
            type_issues = self.check_type_hints(content)
            issues.extend(type_issues)
            
            # 5. Check common Python issues
            python_issues = self.check_python_patterns(content)
            issues.extend(python_issues)
            
        except Exception as e:
            issues.append(f"Error reading file: {e}")
            
        return issues
    
    def check_imports(self, content: str, filepath: str) -> List[str]:
        """Check for import issues"""
        issues = []
        import_lines = [line for line in content.split('\n') if line.strip().startswith(('import ', 'from '))]
        
        # Check for Hummingbot imports
        hummingbot_imports = {
            'hummingbot.smart_components': 'V2 Framework',
            'hummingbot.smart_components': 'Legacy V2 (may need update)',
            'hummingbot.core': 'Core components',
            'hummingbot.connector': 'Connector components'
        }
        
        for line in import_lines:
            for pattern, desc in hummingbot_imports.items():
                if pattern in line:
                    # Check if using correct import path
                    if 'strategy_v2' in line and 'smart_components' not in line:
                        issues.append(f"Warning: Using legacy import path: {line.strip()}")
                        issues.append(f"  Consider updating to: {line.replace('strategy_v2', 'smart_components')}")
                        
        # Check for missing imports
        required_imports = {
            'controller': ['ControllerBase', 'ControllerConfigBase'],
            'executor': ['ExecutorAction', 'CreateExecutorAction', 'StopExecutorAction'],
        }
        
        filename = os.path.basename(filepath)
        if 'controller' in filename.lower():
            for imp in required_imports['controller']:
                if imp not in content:
                    issues.append(f"Warning: Missing import for {imp}")
                    
        return issues
    
    def check_hummingbot_patterns(self, content: str, filepath: str) -> List[str]:
        """Check for Hummingbot-specific patterns"""
        issues = []
        
        # Check controller methods
        if 'controller' in filepath.lower():
            required_methods = [
                'update_processed_data',
                'determine_executor_actions',
                'to_format_status'
            ]
            
            for method in required_methods:
                if f'def {method}' not in content:
                    issues.append(f"Missing required V2 method: {method}")
                    
            # Check for async def
            if 'async def update_processed_data' not in content:
                issues.append("update_processed_data should be async")
                
            if 'async def determine_executor_actions' not in content:
                issues.append("determine_executor_actions should be async")
                
        # Check for proper config class
        if 'Config' in content and 'ControllerConfigBase' in content:
            if 'controller_type' not in content:
                issues.append("Missing controller_type in config (required for V2)")
                
        return issues
    
    def check_type_hints(self, content: str) -> List[str]:
        """Check for proper type hints"""
        issues = []
        
        # Find function definitions without type hints
        func_pattern = r'def\s+(\w+)\s*\([^)]*\)\s*:'
        matches = re.findall(func_pattern, content)
        
        for match in matches:
            if match not in ['__init__', '__str__', '__repr__']:
                func_line = next((line for line in content.split('\n') if f'def {match}' in line), None)
                if func_line and '->' not in func_line:
                    issues.append(f"Warning: Function '{match}' missing return type hint")
                    
        return issues
    
    def check_python_patterns(self, content: str) -> List[str]:
        """Check for common Python issues"""
        issues = []
        
        # Check for proper exception handling
        if 'except Exception:' in content or 'except Exception:' in content:
            issues.append("Warning: Bare except clause found - specify exception type")
            
        # Check for print statements (should use logger)
        if 'print(' in content and 'print_' not in content:
            issues.append("Warning: logger.info() found - use logger instead")
            
        # Check for hardcoded values
        hardcoded_patterns = [
            (r'0\.75', "Hardcoded rebate ratio - use config"),
            (r'gate_io', "Hardcoded connector name - use config"),
            (r'localhost', "Hardcoded hostname - use config"),
        ]
        
        for pattern, message in hardcoded_patterns:
            if re.search(pattern, content):
                issues.append(f"Warning: {message}")
                
        return issues
    
    def fix_common_issues(self, filepath: str) -> bool:
        """Attempt to fix common issues automatically"""
        try:
            with open(filepath, 'r') as f:
                content = f.read()
            
            original_content = content
            
            # Fix 1: Update legacy imports
            content = content.replace(
                'hummingbot.smart_components',
                'hummingbot.smart_components'
            )
            
            # Fix 2: Add missing controller_type
            if 'ControllerConfigBase' in content and 'controller_type' not in content:
                # Find the config class
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if 'controller_name' in line and '=' in line:
                        # Add controller_type after controller_name
                        indent = len(line) - len(line.lstrip())
                        new_line = ' ' * indent + 'controller_type: str = "directional"'
                        lines.insert(i + 1, new_line)
                        content = '\n'.join(lines)
                        break
            
            # Fix 3: Replace print with logger
            if 'print(' in content:
                if 'import logging' not in content:
                    # Add logging import
                    import_section_end = 0
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if line.startswith('import ') or line.startswith('from '):
                            import_section_end = i
                    lines.insert(import_section_end + 1, 'import logging')
                    lines.insert(import_section_end + 2, '')
                    lines.insert(import_section_end + 3, 'logger = logging.getLogger(__name__)')
                    content = '\n'.join(lines)
                
                # Replace print statements
                content = re.sub(r'print\((.*?)\)', r'logger.info(\1)', content)
            
            # Fix 4: Add type hints to common methods
            content = self.add_type_hints(content)
            
            if content != original_content:
                with open(filepath, 'w') as f:
                    f.write(content)
                return True
                
        except Exception as e:
            logger.info(f"Error fixing {filepath}: {e}")
            
        return False
    
    def add_type_hints(self, content: str) -> str:
        """Add type hints to methods"""
        # Add return type hints for common methods
        replacements = [
            (r'def update_processed_data\(self\):', 
             'def update_processed_data(self) -> None:'),
            (r'def determine_executor_actions\(self\):',
             'def determine_executor_actions(self) -> List[ExecutorAction]:'),
            (r'def to_format_status\(self\):',
             'def to_format_status(self) -> List[str]:'),
            (r'def start\(self\):',
             'def start(self) -> None:'),
            (r'def stop\(self\):',
             'def stop(self) -> None:'),
        ]
        
        for pattern, replacement in replacements:
            content = re.sub(pattern, replacement, content)
            
        # Add List import if needed
        if 'List[' in content and 'from typing import' in content:
            if 'List' not in content.split('from typing import')[1].split('\n')[0]:
                content = content.replace(
                    'from typing import',
                    'from typing import List,'
                )
                
        return content
    
    def check_all_files(self, directory: str = '.') -> Dict:
        """Check all Python files in directory"""
        results = {
            'total_files': 0,
            'files_with_errors': [],
            'files_fixed': [],
            'all_issues': {}
        }
        
        # Find all Python files
        python_files = []
        for root, dirs, files in os.walk(directory):
            # Skip virtual environments and cache
            dirs[:] = [d for d in dirs if d not in ['venv', '__pycache__', '.git']]
            
            for file in files:
                if file.endswith('.py'):
                    python_files.append(os.path.join(root, file))
        
        # Check each file
        for filepath in python_files:
            logger.info(f"Checking: {filepath}")
            issues = self.check_file(filepath)
            
            if issues:
                results['files_with_errors'].append(filepath)
                results['all_issues'][filepath] = issues
                
                # Try to fix
                if self.fix_common_issues(filepath):
                    results['files_fixed'].append(filepath)
                    logger.info(f"  Fixed: {filepath}")
                    
                    # Re-check after fixing
                    new_issues = self.check_file(filepath)
                    if new_issues:
                        results['all_issues'][filepath] = new_issues
                    else:
                        results['all_issues'].pop(filepath)
                        results['files_with_errors'].remove(filepath)
            
            results['total_files'] += 1
        
        return results


def main() -> None:
    """Main function"""
    logger.info("=" * 60)
    logger.info("  GATE.IO ARBITRAGE SUITE - CODE CHECKER AND FIXER")
    logger.info("=" * 60)
    logger.info()
    
    checker = CodeChecker()
    
    # Check all files
    logger.info("Starting comprehensive code check...\n")
    results = checker.check_all_files('/workspace/gate-arbitrage-suite')
    
    # Print results
    logger.info("\n" + "=" * 60)
    logger.info("RESULTS")
    logger.info("=" * 60)
    
    logger.info(f"Total files checked: {results['total_files']}")
    logger.info(f"Files with issues: {len(results['files_with_errors'])}")
    logger.info(f"Files automatically fixed: {len(results['files_fixed'])}")
    
    if results['all_issues']:
        logger.info("\n" + "=" * 60)
        logger.info("REMAINING ISSUES")
        logger.info("=" * 60)
        
        for filepath, issues in results['all_issues'].items():
            logger.info(f"\n{filepath}:")
            for issue in issues:
                logger.info(f"  - {issue}")
    else:
        logger.info("\n✅ All issues have been fixed!")
    
    logger.info("\n" + "=" * 60)
    
    # Return exit code
    return 0 if not results['all_issues'] else 1


if __name__ == "__main__":
    sys.exit(main())
#!/usr/bin/env python3
"""
Fix all f-string issues in controller files
"""

import re


def fix_fstring_issues(filepath: str):
    """Fix f-string syntax errors"""
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    fixed_lines = []
    for i, line in enumerate(lines):
        # Check if line has unclosed f-string
        if 'lines.append(f"' in line:
            # Count quotes
            quote_count = line.count('"')
            if quote_count % 2 != 0:  # Odd number of quotes = unclosed
                # Add closing quote and parenthesis
                if not line.rstrip().endswith('")'):
                    line = line.rstrip() + '")\n'
        
        fixed_lines.append(line)
    
    # Write back
    with open(filepath, 'w') as f:
        f.writelines(fixed_lines)
    
    print(f"Fixed f-strings in: {filepath}")


# Fix all controller files
controllers = [
    '/workspace/gate-arbitrage-suite/controllers/arbitrage/gate_spot_perp_controller.py',
    '/workspace/gate-arbitrage-suite/controllers/arbitrage/gate_spot_spot_controller.py',
    '/workspace/gate-arbitrage-suite/controllers/arbitrage/gate_triangular_controller.py',
    '/workspace/gate-arbitrage-suite/controllers/arbitrage/gate_stat_arb_controller.py'
]

for controller in controllers:
    try:
        fix_fstring_issues(controller)
    except Exception as e:
        print(f"Error fixing {controller}: {e}")
#!/usr/bin/env python3
"""
Fix string literal errors in controller files
"""

import re


def fix_controller_file(filepath: str):
    """Fix string errors in a controller file"""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Fix pattern 1: lines.append(f"\n{'=' * 50}  -> lines.append(f"\n{'=' * 50}")
    content = re.sub(
        r'lines\.append\(f"\\n\{\'=\' \* 50\}$',
        r'lines.append(f"\\n{\'=\' * 50}")',
        content,
        flags=re.MULTILINE
    )
    
    # Fix pattern 2: lines.append(f"{'=' * 50}  -> lines.append(f"{'=' * 50}")
    content = re.sub(
        r'lines\.append\(f"\{\'=\' \* 50\}$',
        r'lines.append(f"{\'=\' * 50}")',
        content,
        flags=re.MULTILINE
    )
    
    # Fix orphaned ")
    lines = content.split('\n')
    fixed_lines = []
    for line in lines:
        if line.strip() == '")':
            continue  # Skip orphaned quotes
        fixed_lines.append(line)
    
    content = '\n'.join(fixed_lines)
    
    # Write back
    with open(filepath, 'w') as f:
        f.write(content)
    print(f"Fixed: {filepath}")


# Fix all problematic controller files
controllers = [
    '/workspace/gate-arbitrage-suite/controllers/arbitrage/gate_spot_perp_controller.py',
    '/workspace/gate-arbitrage-suite/controllers/arbitrage/gate_spot_spot_controller.py',
    '/workspace/gate-arbitrage-suite/controllers/arbitrage/gate_triangular_controller.py',
    '/workspace/gate-arbitrage-suite/controllers/arbitrage/gate_stat_arb_controller.py'
]

for controller in controllers:
    try:
        fix_controller_file(controller)
    except Exception as e:
        print(f"Error fixing {controller}: {e}")
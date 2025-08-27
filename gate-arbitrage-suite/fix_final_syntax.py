#!/usr/bin/env python3
"""
Final syntax fixes for controller files
"""


def fix_file(filepath: str):
    """Fix final syntax issues"""
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    fixed_lines = []
    for line in lines:
        # Fix escaped quotes in f-strings
        if r"{\'=\' * 50}" in line:
            line = line.replace(r"{\'=\' * 50}", "{'=' * 50}")
        
        # Remove lines that are just formatting attempts
        if line.strip() in ['lines.append(f"Spot-Perp Arbitrage Controller Status")',
                             'lines.append(f"Spot-Spot Arbitrage Controller Status")',
                             'lines.append(f"Triangular Arbitrage Controller Status")',
                             'lines.append(f"Statistical Arbitrage Controller Status")']:
            # These lines are probably misplaced
            if 'pass' in fixed_lines[-1]:
                continue  # Skip this line
        
        fixed_lines.append(line)
    
    # Write back
    with open(filepath, 'w') as f:
        f.writelines(fixed_lines)
    print(f"Fixed: {filepath}")


# Fix all controller files
controllers = [
    '/workspace/gate-arbitrage-suite/controllers/arbitrage/gate_spot_perp_controller.py',
    '/workspace/gate-arbitrage-suite/controllers/arbitrage/gate_spot_spot_controller.py',
    '/workspace/gate-arbitrage-suite/controllers/arbitrage/gate_triangular_controller.py',
    '/workspace/gate-arbitrage-suite/controllers/arbitrage/gate_stat_arb_controller.py'
]

for controller in controllers:
    try:
        fix_file(controller)
    except Exception as e:
        print(f"Error: {e}")
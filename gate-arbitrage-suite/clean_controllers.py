#!/usr/bin/env python3
"""
Clean all controller files by removing orphaned string fragments
"""


def clean_controller(filepath: str):
    """Remove orphaned string fragments and fix syntax"""
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    cleaned_lines = []
    skip_next = False
    
    for i, line in enumerate(lines):
        if skip_next:
            skip_next = False
            continue
            
        # Skip orphaned string fragments
        if line.strip().startswith('/"') or line.strip().startswith('}")'):
            continue
        if line.strip().startswith('/{') and '"}' in line:
            continue
        if line.strip() == '"")':
            continue
            
        # Check for return lines followed by orphaned strings
        if line.strip() == 'return lines':
            # Check if next line is an orphaned string
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line.startswith('/"') or next_line.startswith('/{'):
                    skip_next = True
        
        cleaned_lines.append(line)
    
    # Write back
    with open(filepath, 'w') as f:
        f.writelines(cleaned_lines)
    
    print(f"Cleaned: {filepath}")


# Clean all controller files
controllers = [
    '/workspace/gate-arbitrage-suite/controllers/arbitrage/gate_spot_perp_controller.py',
    '/workspace/gate-arbitrage-suite/controllers/arbitrage/gate_spot_spot_controller.py',
    '/workspace/gate-arbitrage-suite/controllers/arbitrage/gate_triangular_controller.py',
    '/workspace/gate-arbitrage-suite/controllers/arbitrage/gate_stat_arb_controller.py'
]

for controller in controllers:
    try:
        clean_controller(controller)
    except Exception as e:
        print(f"Error cleaning {controller}: {e}")
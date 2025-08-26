#!/usr/bin/env python3
"""
Gate.io Arbitrage Suite - Installation Verification Script
Checks that all components are properly installed and configured
"""

import sys
import os
import importlib
import yaml
from pathlib import Path
from decimal import Decimal


class Colors:
    """Terminal colors for output"""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    """Print a section header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*50}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*50}{Colors.ENDC}")


def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.ENDC}")


def print_warning(text):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.ENDC}")


def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.ENDC}")


def check_python_version():
    """Check Python version"""
    print_header("Checking Python Version")
    
    version = sys.version_info
    if version.major == 3 and version.minor >= 10:
        print_success(f"Python {version.major}.{version.minor}.{version.micro} is supported")
        return True
    else:
        print_error(f"Python {version.major}.{version.minor} is not supported. Please use Python 3.10+")
        return False


def check_hummingbot_installation():
    """Check if Hummingbot is installed"""
    print_header("Checking Hummingbot Installation")
    
    try:
        # Check for Hummingbot directory structure
        hummingbot_paths = [
            "~/hummingbot",
            "/opt/hummingbot",
            "../hummingbot",
            os.environ.get("HUMMINGBOT_DIR", "")
        ]
        
        hummingbot_found = False
        hummingbot_dir = None
        
        for path in hummingbot_paths:
            expanded_path = os.path.expanduser(path)
            if os.path.exists(expanded_path):
                hummingbot_dir = expanded_path
                hummingbot_found = True
                break
        
        if hummingbot_found:
            print_success(f"Hummingbot found at: {hummingbot_dir}")
            
            # Check for V2 framework
            v2_indicators = [
                os.path.join(hummingbot_dir, "hummingbot/smart_components"),
                os.path.join(hummingbot_dir, "hummingbot/smart_components/controllers"),
                os.path.join(hummingbot_dir, "hummingbot/smart_components/executors")
            ]
            
            v2_found = all(os.path.exists(path) for path in v2_indicators)
            
            if v2_found:
                print_success("Hummingbot V2 Framework detected")
            else:
                print_warning("Hummingbot V2 Framework not found - please update Hummingbot")
            
            return hummingbot_dir
        else:
            print_error("Hummingbot not found. Please install Hummingbot first")
            print("  Visit: https://hummingbot.org/installation/")
            return None
            
    except Exception as e:
        print_error(f"Error checking Hummingbot: {e}")
        return None


def check_required_packages():
    """Check required Python packages"""
    print_header("Checking Required Packages")
    
    required_packages = [
        "pydantic",
        "yaml",
        "pandas",
        "numpy",
        "aiohttp",
        "websockets",
        "sqlalchemy",
        "networkx"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            importlib.import_module(package.replace("-", "_"))
            print_success(f"{package} is installed")
        except ImportError:
            print_error(f"{package} is NOT installed")
            missing_packages.append(package)
    
    if missing_packages:
        print_warning(f"\nInstall missing packages with:")
        print(f"  pip install {' '.join(missing_packages)}")
        return False
    
    return True


def check_suite_files():
    """Check if arbitrage suite files are present"""
    print_header("Checking Arbitrage Suite Files")
    
    required_files = {
        "Controllers": [
            "controllers/arbitrage/gate_spot_perp_controller_v2.py",
            "controllers/arbitrage/gate_triangular_controller.py",
            "controllers/arbitrage/gate_spot_spot_controller.py",
            "controllers/arbitrage/gate_stat_arb_controller.py"
        ],
        "Scripts": [
            "scripts/gate_arb_v2.py",
            "scripts/gate_arb_launcher_v2.py",
            "scripts/gate_arb_legacy.py"
        ],
        "Configurations": [
            "conf/examples/conf_fee_overrides.yml",
            "conf/examples/conf_v2_with_controllers.yml"
        ],
        "Utilities": [
            "utils/rate_limiter.py",
            "utils/metrics_exporter.py"
        ]
    }
    
    all_present = True
    
    for category, files in required_files.items():
        print(f"\n{category}:")
        for file in files:
            if os.path.exists(file):
                print_success(f"  {file}")
            else:
                print_error(f"  {file} NOT FOUND")
                all_present = False
    
    return all_present


def check_fee_configuration():
    """Check fee override configuration"""
    print_header("Checking Fee Configuration")
    
    fee_config_path = "conf/examples/conf_fee_overrides.yml"
    
    if not os.path.exists(fee_config_path):
        print_error(f"{fee_config_path} not found")
        return False
    
    try:
        with open(fee_config_path, 'r') as f:
            fee_config = yaml.safe_load(f)
        
        # Check Gate.io spot fees
        if "gate_io" in fee_config:
            spot_fees = fee_config["gate_io"]["default"]
            maker_fee = Decimal(str(spot_fees.get("maker_fee", 0)))
            taker_fee = Decimal(str(spot_fees.get("taker_fee", 0)))
            
            print(f"Gate.io Spot Fees:")
            print(f"  Maker: {maker_fee*100:.4f}% ({maker_fee*10000:.1f} bps)")
            print(f"  Taker: {taker_fee*100:.4f}% ({taker_fee*10000:.1f} bps)")
            
            # Check if 75% rebate is applied
            if maker_fee <= Decimal("0.00025") and taker_fee <= Decimal("0.0005"):
                print_success("  75% rebate appears to be configured")
            else:
                print_warning("  Fees don't reflect 75% rebate - please verify")
        
        # Check Gate.io perpetual fees
        if "gate_io_perpetual" in fee_config:
            perp_fees = fee_config["gate_io_perpetual"]["default"]
            maker_fee = Decimal(str(perp_fees.get("maker_fee", 0)))
            taker_fee = Decimal(str(perp_fees.get("taker_fee", 0)))
            
            print(f"\nGate.io Perpetual Fees:")
            print(f"  Maker: {maker_fee*100:.4f}% ({maker_fee*10000:.1f} bps)")
            print(f"  Taker: {taker_fee*100:.4f}% ({taker_fee*10000:.1f} bps)")
            
            if maker_fee <= Decimal("0.00005") and taker_fee <= Decimal("0.00015"):
                print_success("  75% rebate appears to be configured")
            else:
                print_warning("  Fees don't reflect 75% rebate - please verify")
        
        return True
        
    except Exception as e:
        print_error(f"Error reading fee configuration: {e}")
        return False


def check_docker_installation():
    """Check if Docker is installed (for Web UI)"""
    print_header("Checking Docker Installation (Optional)")
    
    docker_installed = os.system("which docker > /dev/null 2>&1") == 0
    docker_compose_installed = os.system("which docker-compose > /dev/null 2>&1") == 0
    
    if docker_installed:
        print_success("Docker is installed")
    else:
        print_warning("Docker not installed - Web UI will not be available")
        print("  Install with: sudo apt-get install docker.io")
    
    if docker_compose_installed:
        print_success("Docker Compose is installed")
    else:
        print_warning("Docker Compose not installed - Web UI will not be available")
        print("  Install with: sudo apt-get install docker-compose")
    
    return docker_installed and docker_compose_installed


def generate_installation_commands(hummingbot_dir):
    """Generate installation commands"""
    print_header("Installation Commands")
    
    if not hummingbot_dir:
        hummingbot_dir = "~/hummingbot"
    
    print("If files are missing, run these commands:\n")
    print(f"# Set Hummingbot directory")
    print(f"export HUMMINGBOT_DIR={hummingbot_dir}")
    print()
    print(f"# Copy controllers")
    print(f"cp -r controllers/* $HUMMINGBOT_DIR/hummingbot/smart_components/controllers/")
    print()
    print(f"# Copy scripts")
    print(f"cp scripts/* $HUMMINGBOT_DIR/scripts/")
    print()
    print(f"# Copy configurations")
    print(f"cp -r conf/* $HUMMINGBOT_DIR/conf/")
    print()
    print(f"# Copy utilities")
    print(f"cp -r utils/* $HUMMINGBOT_DIR/hummingbot/smart_components/utils/")


def main():
    """Main verification function"""
    print(f"{Colors.BOLD}")
    print("=" * 60)
    print("  GATE.IO ARBITRAGE SUITE - INSTALLATION VERIFICATION")
    print("=" * 60)
    print(f"{Colors.ENDC}")
    
    checks_passed = []
    
    # Run checks
    checks_passed.append(check_python_version())
    
    hummingbot_dir = check_hummingbot_installation()
    checks_passed.append(hummingbot_dir is not None)
    
    checks_passed.append(check_required_packages())
    checks_passed.append(check_suite_files())
    checks_passed.append(check_fee_configuration())
    
    # Optional checks
    check_docker_installation()
    
    # Summary
    print_header("Verification Summary")
    
    passed = sum(1 for x in checks_passed if x)
    total = len(checks_passed)
    
    if passed == total:
        print_success(f"All checks passed! ({passed}/{total})")
        print("\n🎉 Your Gate.io Arbitrage Suite is ready to use!")
        print("\nNext steps:")
        print("1. Start Hummingbot")
        print("2. Connect to Gate.io with: connect gate_io")
        print("3. Start arbitrage with: start --script gate_arb_v2.py")
    else:
        print_error(f"Some checks failed ({passed}/{total})")
        print("\n⚠️  Please fix the issues above before running the arbitrage suite")
        generate_installation_commands(hummingbot_dir)
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
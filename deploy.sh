#!/bin/bash
# Gate.io Arbitrage Suite - Production Deployment Script
# Ubuntu 22.04+ deployment automation

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
HUMMINGBOT_PATH="${HUMMINGBOT_PATH:-$HOME/hummingbot}"
SUITE_NAME="gate-arbitrage-suite"
BACKUP_DIR="$HOME/hb-backups/$(date +%Y%m%d_%H%M%S)"

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   error "This script should not be run as root"
fi

# Check Ubuntu version
if ! lsb_release -d | grep -q "Ubuntu"; then
    warn "This script is optimized for Ubuntu. Proceeding anyway..."
fi

log "Starting Gate.io Arbitrage Suite deployment..."

# Check if Hummingbot exists
if [ ! -d "$HUMMINGBOT_PATH" ]; then
    error "Hummingbot not found at $HUMMINGBOT_PATH. Please install Hummingbot first or set HUMMINGBOT_PATH environment variable."
fi

log "Found Hummingbot at: $HUMMINGBOT_PATH"

# Create backup
log "Creating backup..."
mkdir -p "$BACKUP_DIR"
if [ -d "$HUMMINGBOT_PATH/scripts" ]; then
    cp -r "$HUMMINGBOT_PATH/scripts" "$BACKUP_DIR/"
    log "Backed up existing scripts to: $BACKUP_DIR"
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
if [[ $(echo "$PYTHON_VERSION < 3.11" | bc -l) -eq 1 ]]; then
    error "Python 3.11+ required. Found: $PYTHON_VERSION"
fi

log "Python version check passed: $PYTHON_VERSION"

# Install system dependencies
log "Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    git \
    curl \
    jq \
    bc \
    htop \
    tree

# Install Docker (for Web UI)
if ! command -v docker &> /dev/null; then
    log "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    log "Docker installed. You may need to re-login for group changes to take effect."
fi

# Install Docker Compose
if ! command -v docker-compose &> /dev/null; then
    log "Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# Deploy arbitrage suite
log "Deploying arbitrage suite to Hummingbot..."

# Copy scripts
cp -r scripts/* "$HUMMINGBOT_PATH/scripts/"
log "Deployed scripts"

# Copy controllers
mkdir -p "$HUMMINGBOT_PATH/controllers"
cp -r controllers/* "$HUMMINGBOT_PATH/controllers/"
log "Deployed controllers"

# Copy configuration templates
mkdir -p "$HUMMINGBOT_PATH/conf/examples"
mkdir -p "$HUMMINGBOT_PATH/conf/controllers"
mkdir -p "$HUMMINGBOT_PATH/conf/scripts"
cp -r conf/examples/* "$HUMMINGBOT_PATH/conf/examples/"
cp -r conf/controllers/* "$HUMMINGBOT_PATH/conf/controllers/"
if [ -d "conf/scripts" ]; then
    cp -r conf/scripts/* "$HUMMINGBOT_PATH/conf/scripts/"
fi
log "Deployed configuration templates"

# Install Python dependencies
log "Installing Python dependencies..."
cd "$HUMMINGBOT_PATH"
if [ -f "requirements.txt" ]; then
    pip3 install -r requirements.txt
fi

# Install our requirements
if [ -f "$(dirname $0)/requirements.txt" ]; then
    pip3 install -r "$(dirname $0)/requirements.txt"
fi

# Setup Web UI
if [ -d "$(dirname $0)/webui" ]; then
    log "Setting up Web Admin UI..."
    cp -r "$(dirname $0)/webui" "$HUMMINGBOT_PATH/"
    cd "$HUMMINGBOT_PATH/webui"
    
    # Make scripts executable
    chmod +x install.sh start.sh stop.sh
    
    # Run Web UI installation
    ./install.sh
    
    log "Web Admin UI setup complete"
fi

# Set up systemd service (optional)
read -p "Would you like to set up systemd service for auto-restart? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log "Setting up systemd service..."
    
    sudo tee /etc/systemd/system/gate-arbitrage.service > /dev/null <<EOF
[Unit]
Description=Gate.io Arbitrage Suite
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HUMMINGBOT_PATH
ExecStart=$HUMMINGBOT_PATH/bin/hummingbot_quickstart.py start --script gate_arb_launcher_v2.py
Restart=always
RestartSec=10
Environment=PYTHONPATH=$HUMMINGBOT_PATH

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable gate-arbitrage.service
    log "Systemd service created. Use 'sudo systemctl start gate-arbitrage' to start."
fi

# Create helper scripts
log "Creating helper scripts..."

# Start script
cat > "$HUMMINGBOT_PATH/start_gate_arb.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
echo "Starting Gate.io Arbitrage Suite..."
echo "Available scripts:"
echo "1. gate_arb_example.py (Simple example)"
echo "2. gate_arb_launcher_v2.py (Advanced controller launcher)"
echo "3. gate_arb_legacy.py (Legacy strategy)"
echo ""
echo "Choose your startup method:"
echo "Basic: python bin/hummingbot_quickstart.py start --script gate_arb_example.py --conf conf/scripts/gate_arb_example.yml"
echo "Advanced: python bin/hummingbot_quickstart.py start --script gate_arb_launcher_v2.py --conf conf/examples/conf_v2_with_controllers.yml"
echo ""
echo "Starting basic example by default..."
python bin/hummingbot_quickstart.py start --script gate_arb_example.py --conf conf/scripts/gate_arb_example.yml
EOF

# Status script
cat > "$HUMMINGBOT_PATH/gate_arb_status.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
echo "=== Gate.io Arbitrage Suite Status ==="
echo "Hummingbot Path: $(pwd)"
echo "Python Version: $(python3 --version)"
echo "Controllers:"
find controllers -name "*.py" | head -10
echo "Scripts:"
find scripts -name "gate_*.py"
echo "Web UI Status:"
if [ -d "webui" ]; then
    cd webui && docker-compose ps
fi
EOF

chmod +x "$HUMMINGBOT_PATH/start_gate_arb.sh"
chmod +x "$HUMMINGBOT_PATH/gate_arb_status.sh"

# Final verification
log "Running deployment verification..."

# Check file structure
REQUIRED_FILES=(
    "scripts/gate_arb_launcher_v2.py"
    "scripts/gate_arb_legacy.py"
    "controllers/arbitrage/gate_spot_perp_controller.py"
    "controllers/arbitrage/gate_triangular_controller.py"
    "conf/examples/conf_fee_overrides.yml"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$HUMMINGBOT_PATH/$file" ]; then
        error "Missing required file: $file"
    fi
done

# Test Python imports
cd "$HUMMINGBOT_PATH"
python3 -c "
import sys
sys.path.append('.')
try:
    from controllers.arbitrage.fee_model import FeeModel
    from controllers.arbitrage.risk_manager import RiskManager
    print('✓ Controller imports successful')
except ImportError as e:
    print(f'✗ Import error: {e}')
    sys.exit(1)
"

log "Deployment verification completed successfully!"

# Summary
echo
echo "========================================"
echo "  Gate.io Arbitrage Suite Deployed!"
echo "========================================"
echo
info "📁 Installation Directory: $HUMMINGBOT_PATH"
info "📋 Backup Location: $BACKUP_DIR"
info "🚀 Start Command: ./start_gate_arb.sh"
info "📊 Status Command: ./gate_arb_status.sh"
echo
info "Next Steps:"
echo "1. Edit conf/examples/conf_fee_overrides.yml with your actual Gate.io fees"
echo "2. Add your Gate.io API credentials using Hummingbot"
echo "3. Review controller configurations in conf/controllers/"
echo "4. Start the Web UI: cd webui && ./start.sh"
echo "5. Run the arbitrage suite: ./start_gate_arb.sh"
echo
info "Documentation: README.md"
info "Web UI: http://localhost:8501 (after starting)"
echo
log "Deployment completed successfully!"
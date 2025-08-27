#!/bin/bash

# Gate.io Arbitrage Suite Quick Deploy Script
# 一键部署脚本 - One-click deployment for Ubuntu

set -e

echo "============================================"
echo "  Gate.io Arbitrage Suite Quick Deploy"
echo "  快速部署 Gate.io 套利系统"
echo "============================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}➜ $1${NC}"
}

# Check if running on Ubuntu
if ! grep -q "Ubuntu" /etc/os-release; then
    print_error "This script is designed for Ubuntu. Your system appears to be different."
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Step 1: Install system dependencies
print_info "Installing system dependencies / 安装系统依赖..."
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip git curl wget

# Step 2: Check for Hummingbot installation
HUMMINGBOT_PATH=""
if [ -d "$HOME/hummingbot" ]; then
    HUMMINGBOT_PATH="$HOME/hummingbot"
    print_success "Found Hummingbot at $HUMMINGBOT_PATH"
elif [ -d "/opt/hummingbot" ]; then
    HUMMINGBOT_PATH="/opt/hummingbot"
    print_success "Found Hummingbot at $HUMMINGBOT_PATH"
else
    print_error "Hummingbot not found!"
    echo "Please install Hummingbot first or specify the path:"
    read -p "Enter Hummingbot path (or press Enter to skip): " custom_path
    if [ -n "$custom_path" ]; then
        HUMMINGBOT_PATH="$custom_path"
    else
        print_info "Proceeding without Hummingbot integration..."
    fi
fi

# Step 3: Copy files to Hummingbot
if [ -n "$HUMMINGBOT_PATH" ]; then
    print_info "Copying arbitrage suite to Hummingbot / 复制套利系统到 Hummingbot..."
    
    # Create backup
    if [ -d "$HUMMINGBOT_PATH/controllers" ] || [ -d "$HUMMINGBOT_PATH/scripts" ]; then
        print_info "Creating backup / 创建备份..."
        backup_dir="$HUMMINGBOT_PATH/backup_$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$backup_dir"
        [ -d "$HUMMINGBOT_PATH/controllers" ] && cp -r "$HUMMINGBOT_PATH/controllers" "$backup_dir/"
        [ -d "$HUMMINGBOT_PATH/scripts" ] && cp -r "$HUMMINGBOT_PATH/scripts" "$backup_dir/"
        print_success "Backup created at $backup_dir"
    fi
    
    # Copy files
    cp -r controllers/* "$HUMMINGBOT_PATH/controllers/" 2>/dev/null || mkdir -p "$HUMMINGBOT_PATH/controllers" && cp -r controllers/* "$HUMMINGBOT_PATH/controllers/"
    cp -r scripts/* "$HUMMINGBOT_PATH/scripts/" 2>/dev/null || mkdir -p "$HUMMINGBOT_PATH/scripts" && cp -r scripts/* "$HUMMINGBOT_PATH/scripts/"
    cp -r conf/* "$HUMMINGBOT_PATH/conf/" 2>/dev/null || mkdir -p "$HUMMINGBOT_PATH/conf" && cp -r conf/* "$HUMMINGBOT_PATH/conf/"
    
    print_success "Files copied to Hummingbot"
fi

# Step 4: Setup Python virtual environment
print_info "Setting up Python environment / 设置 Python 环境..."
if [ ! -d "venv" ]; then
    python3.11 -m venv venv
fi
source venv/bin/activate

# Install requirements
pip install --upgrade pip
pip install -r requirements.txt || print_error "Some packages failed to install"

print_success "Python environment ready"

# Step 5: Configure fee rebates
print_info "Configuring fee rebates / 配置手续费返佣..."
echo ""
echo "Your current fee structure with 75% rebate:"
echo "您当前的手续费结构（75% 返佣后）："
echo "----------------------------------------"
echo "Spot 现货:"
echo "  Maker: 0.025% (Original 原始: 0.1%)"
echo "  Taker: 0.05%  (Original 原始: 0.2%)"
echo "Perpetual 永续:"
echo "  Maker: 0.005% (Original 原始: 0.02%)"
echo "  Taker: 0.015% (Original 原始: 0.06%)"
echo "----------------------------------------"
echo ""
read -p "Are these rates correct? 这些费率正确吗? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_info "Please edit conf/examples/conf_fee_overrides.yml manually"
    print_info "请手动编辑 conf/examples/conf_fee_overrides.yml"
fi

# Step 6: Setup Web UI
print_info "Setting up Web UI / 设置 Web 管理界面..."
cd webui

# Check Docker
if ! command -v docker &> /dev/null; then
    print_info "Docker not found. Installing Docker / 未找到 Docker，正在安装..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    print_success "Docker installed. Please log out and back in for group changes."
    print_success "Docker 已安装。请注销并重新登录以应用组更改。"
else
    print_success "Docker is already installed / Docker 已安装"
fi

# Make scripts executable
chmod +x install.sh start.sh stop.sh

# Run Web UI installation
./install.sh

cd ..

# Step 7: Create start script
print_info "Creating start script / 创建启动脚本..."
cat > start_arbitrage.sh << 'EOF'
#!/bin/bash
echo "Starting Gate.io Arbitrage Suite..."
echo "启动 Gate.io 套利系统..."

# Start Web UI
cd webui && ./start.sh && cd ..

echo ""
echo "============================================"
echo "  Gate.io Arbitrage Suite is running!"
echo "  Gate.io 套利系统正在运行！"
echo "============================================"
echo ""
echo "Web UI: http://localhost:8080"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "To start trading in Hummingbot / 在 Hummingbot 中开始交易:"
echo "  start --script gate_arb_launcher_v2.py --conf conf_gate_arb_launcher_v2.yml"
echo ""
echo "To stop: ./stop_arbitrage.sh"
echo "停止: ./stop_arbitrage.sh"
EOF

cat > stop_arbitrage.sh << 'EOF'
#!/bin/bash
echo "Stopping Gate.io Arbitrage Suite..."
echo "停止 Gate.io 套利系统..."

# Stop Web UI
cd webui && ./stop.sh && cd ..

echo "Stopped / 已停止"
EOF

chmod +x start_arbitrage.sh stop_arbitrage.sh

# Step 8: Run tests
print_info "Running tests / 运行测试..."
python -m pytest tests/ -q || print_error "Some tests failed"

# Step 9: Final summary
echo ""
echo "============================================"
print_success "Installation Complete! 安装完成！"
echo "============================================"
echo ""
echo "Next steps / 下一步:"
echo ""
echo "1. Configure Gate.io API keys / 配置 Gate.io API 密钥:"
echo "   - In Hummingbot: connect gate_io"
echo "   - In Web UI: http://localhost:8080"
echo ""
echo "2. Start the arbitrage suite / 启动套利系统:"
echo "   ./start_arbitrage.sh"
echo ""
echo "3. Monitor performance / 监控性能:"
echo "   http://localhost:8080"
echo ""
echo "4. Check logs / 查看日志:"
if [ -n "$HUMMINGBOT_PATH" ]; then
    echo "   tail -f $HUMMINGBOT_PATH/logs/*.log"
else
    echo "   Check your Hummingbot logs directory"
fi
echo ""
echo "============================================"
echo "Important / 重要提示:"
echo "- Start with small amounts for testing"
echo "- 先用小额资金测试"
echo "- Monitor the first few trades carefully"
echo "- 仔细监控前几笔交易"
echo "- Adjust parameters based on performance"
echo "- 根据性能调整参数"
echo "============================================"

# Save installation info
cat > installation_info.txt << EOF
Gate.io Arbitrage Suite Installation
Date: $(date)
Hummingbot Path: ${HUMMINGBOT_PATH:-"Not integrated"}
Python Version: $(python3.11 --version)
System: $(uname -a)
EOF

print_success "Installation info saved to installation_info.txt"
print_success "安装信息已保存到 installation_info.txt"
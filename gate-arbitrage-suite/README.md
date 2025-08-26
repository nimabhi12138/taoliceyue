# Gate.io Arbitrage Suite for Hummingbot 2.x

## Overview

Production-grade arbitrage suite optimized for Gate.io with 75% trading fee rebate. Includes multiple arbitrage strategies, risk management, and a lightweight Web Admin UI for non-developers.

## Features

- **Multiple Arbitrage Strategies**:
  - Spot-Perpetual Basis (Cash-and-Carry)
  - Spot-Spot Cross-Market
  - Triangular Arbitrage
  - Statistical Arbitrage (Pairs Trading)
  
- **Optimized for 75% Fee Rebate**: All strategies calculate profitability after net fees
- **Risk Management**: Kelly sizing, circuit breakers, position limits
- **Web Admin UI**: Easy configuration and monitoring for non-developers
- **Production Ready**: Comprehensive error handling, logging, and monitoring

## Architecture

```
gate-arbitrage-suite/
├── controllers/arbitrage/         # ControllerBase implementations
│   ├── gate_spot_perp_controller.py
│   ├── gate_spot_spot_controller.py
│   ├── gate_triangular_controller.py
│   └── gate_stat_arb_controller.py
├── scripts/                       # ScriptStrategyBase implementations
│   ├── gate_arb_launcher_v2.py
│   └── gate_arb_legacy.py
├── conf/                          # Configuration files
│   ├── examples/
│   ├── controllers/
│   └── scripts/
├── webui/                         # Web Admin Interface
│   ├── backend/                   # FastAPI
│   ├── frontend/                  # Streamlit
│   └── docker-compose.yml
└── tests/                         # Test suite
```

## Quick Start

### 1. Installation

```bash
# Copy this folder into your Hummingbot instance
cp -r gate-arbitrage-suite/* /path/to/hummingbot/

# Install Web UI dependencies
cd /path/to/hummingbot/webui
./install.sh
```

### 2. Configure Fee Rebates

Edit `conf/examples/conf_fee_overrides.yml` with your actual rebate rates:

```yaml
gate_io:
  maker_fee: 0.025  # 0.1% * 0.25 (75% rebate)
  taker_fee: 0.05   # 0.2% * 0.25 (75% rebate)

gate_io_perpetual:
  maker_fee: 0.005  # 0.02% * 0.25 (75% rebate)
  taker_fee: 0.015  # 0.06% * 0.25 (75% rebate)
```

### 3. Create Controller Configs

```bash
# Spot-Perp Arbitrage
create --controller-config arbitrage/gate_spot_perp_controller

# Spot-Spot Arbitrage
create --controller-config arbitrage/gate_spot_spot_controller

# Triangular Arbitrage
create --controller-config arbitrage/gate_triangular_controller

# Statistical Arbitrage
create --controller-config arbitrage/gate_stat_arb_controller
```

### 4. Create Script Config

```bash
# Create generic script config
create --script-config v2_with_controllers

# Or for legacy mode
create --script-config gate_arb_legacy
```

### 5. Start Trading

```bash
# Using controller-based approach (recommended)
start --script v2_with_controllers.py --conf conf_v2_with_controllers.yml

# Using legacy script approach
start --script gate_arb_legacy.py --conf conf/scripts/gate_arb_legacy.yml
```

### 6. Start Web UI

```bash
cd webui
./start.sh
# Access at http://localhost:8080
```

## Strategy Details

### Spot-Perpetual Basis Arbitrage

Exploits price differences between spot and perpetual markets:
- Monitors basis spread (perp - spot)
- Enters when spread > threshold + net fees + funding
- Maintains delta-neutral positions
- Auto-rebalances on drift

### Spot-Spot Cross-Market Arbitrage

Captures price inefficiencies across different spot markets:
- Monitors price differentials
- Prefers maker orders for lower fees
- Falls back to taker when edge is sufficient

### Triangular Arbitrage

Exploits pricing inefficiencies in three-way currency pairs:
- Path: A→B→C→A
- Calculates net edge after all fees
- Atomic execution with rollback on failure

### Statistical Arbitrage

Mean-reversion pairs trading:
- Cointegration analysis
- Z-score based entry/exit
- Half-life optimization
- Dynamic position sizing

## Risk Management

### Position Sizing
- Truncated Kelly Criterion
- Per-symbol exposure caps
- Total portfolio limits
- Leverage constraints (perps)

### Circuit Breakers
- Session loss limits
- Rolling drawdown monitoring
- Error rate monitoring
- Liquidity checks

### Execution Quality
- Post-only preference for maker fees
- IOC/FOK fallbacks
- Slippage guards
- Partial fill handling

## Configuration

### Controller Configs

Located in `conf/controllers/arbitrage/`:

```yaml
# gate_spot_perp_controller.yml
arbitrage:
  spot_connector: gate_io
  perp_connector: gate_io_perpetual
  symbols:
    - BTC-USDT
    - ETH-USDT
  min_basis_bps: 30  # After fees
  slippage_buffer_bps: 5
  position_size_pct: 0.1
  rebalance_threshold: 0.02
  funding_lookback_hours: 8
```

### Fee Overrides

Global fee configuration in `conf_fee_overrides.yml`:

```yaml
# Apply your VIP/rebate rates here
gate_io:
  BTC-USDT:
    maker_fee: 0.025  # 0.1% * (1 - 0.75 rebate)
    taker_fee: 0.05   # 0.2% * (1 - 0.75 rebate)
```

## Monitoring

### CLI Status

The strategies provide real-time status via `format_status()`:
- Current positions
- PnL (fee-adjusted)
- Hit rate
- Average slippage
- Circuit breaker status

### Web UI Dashboard

- Live balance tracking
- Position monitoring
- PnL charts
- Risk metrics
- Alert management

## Testing

```bash
# Run test suite
cd tests
pytest -q

# Individual tests
pytest test_fee_model.py
pytest test_kelly.py
pytest test_triangular.py
pytest test_budget_check.py
```

## Production Deployment

### System Requirements
- Ubuntu 22.04+
- Python 3.11+
- Docker & Docker Compose
- 4GB RAM minimum
- SSD recommended

### Security
- Use encrypted API key storage
- Enable firewall (ufw)
- Configure TLS for Web UI
- Regular backups

### Monitoring
- Set up log rotation
- Configure alerts
- Monitor system resources
- Track API rate limits

## Troubleshooting

### Common Issues

1. **Insufficient Balance**: Check minimum order sizes
2. **Rate Limits (429)**: Reduce request frequency
3. **Time Sync**: Run `sudo ntpdate -s time.nist.gov`
4. **Precision Errors**: Check symbol trading rules
5. **Funding Rates**: Monitor perp funding costs

## License

MIT License - See LICENSE file

---

# 《小白也能用：Ubuntu 部署与使用全流程（含网页管理）》

## 一、环境准备

### 1.1 系统要求
- Ubuntu 22.04 或更高版本
- 至少 4GB 内存
- 20GB 可用硬盘空间
- 稳定的网络连接

### 1.2 安装基础依赖

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装 Python 和基础工具
sudo apt install -y python3.11 python3.11-venv python3-pip git curl wget

# 安装 Docker（用于 Web UI）
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
# 重新登录以应用 docker 权限
```

## 二、安装 Hummingbot

### 2.1 使用 Docker 安装（推荐）

```bash
# 创建工作目录
mkdir ~/hummingbot && cd ~/hummingbot

# 下载并运行安装脚本
wget https://raw.githubusercontent.com/hummingbot/hummingbot/master/installation/docker-commands/create.sh
chmod +x create.sh
./create.sh

# 启动 Hummingbot
docker-compose up -d
```

### 2.2 源码安装（可选）

```bash
# 克隆仓库
git clone https://github.com/hummingbot/hummingbot.git
cd hummingbot

# 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
pip install -e .
```

## 三、部署套利系统

### 3.1 复制套利套件

```bash
# 将套利套件复制到 Hummingbot 目录
cp -r /path/to/gate-arbitrage-suite/* ~/hummingbot/

# 设置权限
chmod +x ~/hummingbot/webui/*.sh
```

### 3.2 配置返佣费率

编辑费率配置文件，应用您的 75% 返佣：

```bash
nano ~/hummingbot/conf/examples/conf_fee_overrides.yml
```

修改为您的实际费率（原始费率 × 0.25）：

```yaml
# Gate.io 现货费率（75% 返佣后）
gate_io:
  default:
    maker_fee: 0.025  # 原 0.1% × 0.25 = 0.025%
    taker_fee: 0.05   # 原 0.2% × 0.25 = 0.05%

# Gate.io 永续合约费率（75% 返佣后）
gate_io_perpetual:
  default:
    maker_fee: 0.005  # 原 0.02% × 0.25 = 0.005%
    taker_fee: 0.015  # 原 0.06% × 0.25 = 0.015%
```

## 四、配置 Gate.io API

### 4.1 获取 API 密钥

1. 登录 [Gate.io](https://www.gate.io)
2. 进入 "个人中心" → "API 管理"
3. 创建新的 API 密钥
4. **重要设置**：
   - 启用"现货交易"
   - 启用"合约交易"（如果使用永续）
   - 设置 IP 白名单（推荐）
   - 保存 API Key 和 Secret

### 4.2 在 Hummingbot 中配置

```bash
# 进入 Hummingbot
docker attach hummingbot

# 连接 Gate.io
>>> connect gate_io
# 输入 API key
# 输入 API secret

# 连接永续合约（如需要）
>>> connect gate_io_perpetual
# 输入相同或不同的 API 密钥

# 测试连接
>>> balance
```

## 五、启动 Web 管理界面

### 5.1 安装 Web UI

```bash
cd ~/hummingbot/webui
./install.sh
```

### 5.2 配置环境

```bash
# 复制环境配置
cp .env.example .env

# 编辑配置
nano .env
```

设置以下参数：

```env
# Hummingbot 连接
HUMMINGBOT_HOST=localhost
HUMMINGBOT_PORT=8211

# Web UI 设置
WEB_PORT=8080
API_PORT=8000

# 安全设置（修改默认密码！）
ADMIN_USER=admin
ADMIN_PASSWORD=your_secure_password_here
```

### 5.3 启动 Web UI

```bash
# 启动服务
./start.sh

# 查看状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

访问 Web 界面：`http://你的服务器IP:8080`

## 六、创建和运行策略

### 6.1 通过 Web UI 配置（推荐）

1. 登录 Web UI
2. 点击 "策略配置"
3. 选择策略类型：
   - **现货-永续套利**：稳定收益，低风险
   - **三角套利**：快速执行，需要低延迟
   - **统计套利**：需要历史数据分析
4. 设置参数：
   - 最小套利空间（基点）
   - 仓位大小（百分比）
   - 风险限制
5. 点击"创建配置"
6. 点击"启动策略"

### 6.2 通过命令行配置

```bash
# 进入 Hummingbot
docker attach hummingbot

# 创建现货-永续套利配置
>>> create --controller-config arbitrage/gate_spot_perp_controller

# 设置参数
# 交易对：BTC-USDT
# 最小基差：30 基点
# 仓位大小：10%
# 滑点缓冲：5 基点

# 创建脚本配置
>>> create --script-config v2_with_controllers

# 启动策略
>>> start --script v2_with_controllers.py --conf conf_v2_with_controllers.yml
```

## 七、监控和管理

### 7.1 查看策略状态

```bash
# 在 Hummingbot 中
>>> status

# 显示内容：
# - 当前仓位
# - 盈亏（扣除手续费后）
# - 命中率
# - 平均滑点
# - 风控状态
```

### 7.2 Web UI 监控面板

监控面板显示：
- 实时余额
- 持仓情况
- 累计收益曲线
- 风险指标
- 交易历史

### 7.3 设置告警

在 Web UI 中配置告警：
- 亏损超过阈值
- 错误率过高
- API 限速警告
- 仓位异常

## 八、常见问题排查

### 8.1 时间同步问题

```bash
# 安装 NTP
sudo apt install -y ntp

# 同步时间
sudo ntpdate -s time.nist.gov

# 检查时间
date
```

### 8.2 权限问题

```bash
# Docker 权限
sudo usermod -aG docker $USER
# 重新登录

# 文件权限
chmod +x ~/hummingbot/webui/*.sh
```

### 8.3 最小下单量错误

检查交易对的最小下单要求：
- BTC-USDT: 最小 0.0001 BTC
- ETH-USDT: 最小 0.001 ETH

在配置中调整：
```yaml
min_order_size:
  BTC-USDT: 0.0002
  ETH-USDT: 0.002
```

### 8.4 API 限速（429 错误）

```yaml
# 在控制器配置中调整
rate_limits:
  orders_per_second: 5
  requests_per_second: 10
  cooldown_seconds: 1
```

### 8.5 资金费率问题

永续合约需要考虑资金费率：
- 每 8 小时结算一次
- 可能为正或负
- 在 Web UI 中查看实时费率

## 九、生产环境注意事项

### 9.1 安全设置

```bash
# 启用防火墙
sudo ufw enable
sudo ufw allow 22/tcp  # SSH
sudo ufw allow 8080/tcp  # Web UI

# 配置 SSL/TLS
cd ~/hummingbot/webui/nginx
# 编辑 nginx.conf，配置 SSL 证书
```

### 9.2 备份策略

```bash
# 创建备份脚本
cat > ~/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR=~/backups/$(date +%Y%m%d)
mkdir -p $BACKUP_DIR
cp -r ~/hummingbot/conf $BACKUP_DIR/
cp -r ~/hummingbot/logs $BACKUP_DIR/
tar czf $BACKUP_DIR.tar.gz $BACKUP_DIR
rm -rf $BACKUP_DIR
# 保留最近 7 天的备份
find ~/backups -name "*.tar.gz" -mtime +7 -delete
EOF

chmod +x ~/backup.sh

# 添加定时任务
crontab -e
# 添加：0 2 * * * ~/backup.sh
```

### 9.3 自动重启

```bash
# 创建 systemd 服务
sudo nano /etc/systemd/system/hummingbot.service
```

```ini
[Unit]
Description=Hummingbot Trading Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/your_username/hummingbot
ExecStart=/usr/bin/docker-compose up
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# 启用服务
sudo systemctl enable hummingbot
sudo systemctl start hummingbot
```

### 9.4 日志管理

```bash
# 配置日志轮转
sudo nano /etc/logrotate.d/hummingbot
```

```
/home/*/hummingbot/logs/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
```

## 十、性能优化

### 10.1 网络优化

```bash
# 优化 TCP 设置
sudo sysctl -w net.core.rmem_max=134217728
sudo sysctl -w net.core.wmem_max=134217728
sudo sysctl -w net.ipv4.tcp_rmem="4096 87380 134217728"
sudo sysctl -w net.ipv4.tcp_wmem="4096 65536 134217728"
```

### 10.2 使用低延迟节点

选择靠近 Gate.io 服务器的 VPS：
- 香港
- 新加坡
- 日本

### 10.3 监控资源使用

```bash
# 安装监控工具
sudo apt install -y htop iotop nethogs

# 查看 CPU 和内存
htop

# 查看网络使用
nethogs
```

## 十一、收益优化建议

### 11.1 选择高流动性交易对
- BTC/USDT
- ETH/USDT
- 主流币种

### 11.2 调整策略参数
- 低波动期：降低最小套利空间
- 高波动期：提高风险限制

### 11.3 多策略组合
- 同时运行 2-3 个不相关策略
- 分散风险，提高收益稳定性

## 十二、联系支持

- **技术问题**：查看日志文件 `~/hummingbot/logs/`
- **策略调优**：根据历史数据回测
- **紧急停止**：`docker-compose stop` 或在 Web UI 点击"停止所有"

祝您交易顺利！记得始终使用小额资金测试新策略。
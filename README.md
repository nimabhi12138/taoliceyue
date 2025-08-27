# Gate.io Arbitrage Suite for Hummingbot 2.x

A production-grade arbitrage suite designed for Gate.io with 75% trading fee rebate optimization, featuring multiple arbitrage strategies and a lightweight Web Admin UI.

## 🚀 Features

- **Multiple Arbitrage Strategies**
  - Spot-Perpetual Basis Arbitrage (Cash-and-Carry)
  - Triangular Arbitrage with optimal routing
  - Cross-market Spot Arbitrage
  - Statistical Arbitrage (pairs trading)

- **Advanced Risk Management**
  - Kelly Criterion position sizing
  - Circuit breakers and exposure limits
  - Real-time drawdown monitoring
  - Comprehensive PnL tracking

- **Fee Optimization**
  - 75% rebate support for Gate.io VIP users
  - Maker-preference execution
  - Precise fee modeling with slippage buffers

- **Web Admin Interface**
  - User-friendly Streamlit frontend
  - FastAPI backend with REST API
  - Real-time monitoring and control
  - Configuration management

- **Production Ready**
  - Docker containerization
  - Comprehensive test suite
  - Structured logging
  - Health monitoring

## 📁 Repository Structure

```
gate-arbitrage-suite/
├── scripts/                          # Hummingbot script launchers
│   ├── gate_arb_launcher_v2.py      # Main launcher
│   └── gate_arb_legacy.py           # Legacy ScriptStrategyBase demo
├── controllers/arbitrage/            # Arbitrage controllers
│   ├── gate_spot_perp_controller.py # Spot-perp arbitrage
│   ├── gate_triangular_controller.py # Triangular arbitrage
│   ├── fee_model.py                 # Fee calculation engine
│   └── risk_manager.py              # Risk management
├── conf/examples/                    # Configuration examples
│   ├── conf_v2_with_controllers.yml # Multi-controller config
│   └── conf_fee_overrides.yml       # Fee override settings
├── webui/                           # Web Admin UI
│   ├── backend/                     # FastAPI backend
│   ├── frontend/                    # Streamlit frontend
│   ├── docker-compose.yml          # Docker setup
│   ├── install.sh                  # Installation script
│   ├── start.sh                    # Start script
│   └── stop.sh                     # Stop script
├── tests/                           # Test suite
│   ├── test_fee_model.py           # Fee model tests
│   ├── test_kelly.py               # Kelly sizing tests
│   └── test_triangular.py          # Triangular tests
└── README.md                       # This file
```

## 🔧 Installation & Setup

### Prerequisites

- Ubuntu 22.04+ (recommended)
- Hummingbot 2.x installation
- Gate.io API credentials with appropriate permissions
- Docker and Docker Compose (for Web UI)

### Quick Start

1. **Copy to Hummingbot Directory**
   ```bash
   # Navigate to your Hummingbot installation
   cd /path/to/your/hummingbot
   
   # Copy the arbitrage suite
   cp -r /path/to/gate-arbitrage-suite/* .
   ```

2. **Configure Fee Overrides**
   ```bash
   # Edit fee configuration with your actual rebated rates
   nano conf/examples/conf_fee_overrides.yml
   ```

3. **Create Controller Configurations**
   ```bash
   # Create spot-perp controller config
   ./create --controller-config arbitrage/gate_spot_perp_controller
   
   # Create triangular controller config
   ./create --controller-config arbitrage/gate_triangular_controller
   ```

4. **Create Generic Script Configuration**
   ```bash
   # Create main script config
   ./create --script-config v2_with_controllers
   ```

5. **Start Trading**
   ```bash
   # Start the arbitrage suite
   ./start --script gate_arb_launcher_v2.py --conf conf_v2_with_controllers.yml
   ```

### Web Admin UI Setup

1. **Install Web UI**
   ```bash
   cd webui
   chmod +x install.sh
   ./install.sh
   ```

2. **Configure Environment**
   ```bash
   # Edit .env file with your settings
   nano .env
   
   # Set HUMMINGBOT_PATH to your Hummingbot directory
   HUMMINGBOT_PATH=/path/to/your/hummingbot
   ```

3. **Start Web Interface**
   ```bash
   ./start.sh
   ```

4. **Access Web UI**
   - Open browser to `http://localhost:8501`
   - Login with credentials from `.env` file

## ⚙️ Configuration

### Fee Configuration

Edit `conf/examples/conf_fee_overrides.yml` to set your actual post-rebate fees:

```yaml
fee_overrides:
  gate_io:
    maker: 0.0005  # 0.05% after 75% rebate
    taker: 0.0005  # 0.05% after 75% rebate
  gate_io_perpetual:
    maker: 0.00005  # 0.005% after 75% rebate
    taker: 0.00015  # 0.015% after 75% rebate
```

### Controller Configuration

#### Spot-Perp Controller Example

```yaml
controller_type: GateSpotPerpController
spot_connector: gate_io
perp_connector: gate_io_perpetual
trading_pairs:
  - BTC-USDT
  - ETH-USDT
min_profitability_bps: 5      # 0.05% minimum profit
max_position_size: 1.0        # Maximum position size
slippage_buffer_bps: 2        # 0.02% slippage buffer
risk_config:
  max_total_exposure: 10.0
  max_session_loss: 0.1       # 10% session loss limit
  kelly_multiplier: 0.25      # 25% of Kelly sizing
```

#### Triangular Controller Example

```yaml
controller_type: GateTriangularController
connector: gate_io
base_currencies:
  - USDT
  - BTC
  - ETH
min_profitability_bps: 8      # 0.08% minimum for triangular
prefer_maker_orders: true
atomic_execution: true
rollback_on_partial: true
```

## 🎯 Strategy Details

### Spot-Perpetual Arbitrage

- **Mechanism**: Exploits basis differences between spot and perpetual contracts
- **Risk**: Delta-neutral hedging with funding rate considerations
- **Optimization**: Maker preference, funding cost modeling, time-based exits

### Triangular Arbitrage

- **Mechanism**: Exploits price inefficiencies across currency triangles
- **Risk**: Execution risk minimized through atomic/sequential execution
- **Optimization**: Optimal path finding, maker preference, rollback protection

### Risk Management

- **Kelly Sizing**: Dynamic position sizing based on historical performance
- **Circuit Breakers**: Automatic trading halts on loss/error thresholds
- **Exposure Limits**: Per-symbol and total exposure caps
- **Drawdown Monitoring**: Real-time maximum drawdown tracking

## 📊 Monitoring & Operations

### Web Admin Interface

The Web UI provides:

- **Dashboard**: Real-time PnL, positions, and system health
- **Bot Management**: Start/stop arbitrage bots
- **Configuration**: Edit controller settings and fee overrides
- **Credentials**: Manage exchange API keys
- **Logs**: Real-time log monitoring

### CLI Monitoring

```bash
# Check bot status
./status

# View live logs
tail -f logs/hummingbot.log

# Check specific controller performance
./status arbitrage
```

### Key Metrics

Monitor these critical metrics:

- **Net PnL**: After-fee profit/loss
- **Win Rate**: Percentage of profitable trades
- **Sharpe Ratio**: Risk-adjusted returns
- **Maximum Drawdown**: Largest peak-to-trough decline
- **Hit Rate**: Execution success rate

## 🧪 Testing

Run the test suite to validate functionality:

```bash
# Install test dependencies
pip install pytest

# Run all tests
pytest tests/ -v

# Run specific test categories
pytest tests/test_fee_model.py -v
pytest tests/test_kelly.py -v
pytest tests/test_triangular.py -v
```

## 🔒 Security & Production

### API Security

- Store API keys securely using Hummingbot's encrypted configuration
- Use IP whitelisting on Gate.io
- Enable 2FA for all accounts
- Regularly rotate API keys

### System Security

- Run with minimal privileges (non-root user)
- Use firewall to restrict access to Web UI
- Enable HTTPS for production Web UI deployment
- Regular security updates

### Production Checklist

- [ ] Configure actual rebated fees in `conf_fee_overrides.yml`
- [ ] Set appropriate position sizes and risk limits
- [ ] Test in paper trading mode first
- [ ] Set up monitoring and alerting
- [ ] Configure log rotation
- [ ] Set up automated backups
- [ ] Document incident response procedures

## 🛠️ Troubleshooting

### Common Issues

**1. Fee calculation errors**
- Verify `conf_fee_overrides.yml` values
- Check Gate.io VIP status and actual rates
- Ensure rebate ratios are correctly applied

**2. Controller not starting**
- Check Hummingbot 2.x compatibility
- Verify controller YAML syntax
- Check log files for specific errors

**3. Web UI connection issues**
- Verify Docker containers are running: `docker compose ps`
- Check firewall settings
- Ensure HUMMINGBOT_PATH is correctly set

**4. Insufficient profitability**
- Review min_profitability_bps settings
- Check market conditions and volatility
- Verify fee calculations

### Log Analysis

```bash
# Filter for arbitrage-related logs
grep -i "arbitrage" logs/hummingbot.log

# Check for errors
grep -i "error" logs/hummingbot.log | tail -20

# Monitor specific controller
grep "GateSpotPerpController" logs/hummingbot.log
```

## 📈 Performance Optimization

### Latency Optimization

- Use dedicated server close to Gate.io (Asia-Pacific)
- Optimize network settings
- Use SSD storage for logs and databases
- Consider dedicated network connection

### Strategy Tuning

- Adjust `min_profitability_bps` based on market conditions
- Optimize `slippage_buffer_bps` based on observed slippage
- Fine-tune risk parameters based on performance

### Resource Management

- Monitor CPU and memory usage
- Implement log rotation
- Regular database maintenance
- Monitor disk space usage

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

### Development Guidelines

- Follow PEP 8 style guidelines
- Add comprehensive tests for new features
- Update documentation for new functionality
- Use type hints for all functions
- Add proper error handling and logging

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This software is for educational and research purposes. Trading cryptocurrencies involves substantial risk of loss. Users are responsible for:

- Understanding the risks involved
- Complying with applicable laws and regulations
- Proper testing before live deployment
- Monitoring and maintaining their systems
- Managing their own risk appropriately

The authors and contributors are not responsible for any financial losses incurred through the use of this software.

---

# 《小白也能用：Ubuntu 部署与使用全流程（含网页管理）》

## 📖 概述

本套件是专为 Gate.io 交易所优化的 Hummingbot 2.x 套利系统，支持 75% 手续费返佣，包含多种套利策略和直观的网页管理界面。即使是编程小白也能轻松部署使用。

## 🎯 主要功能

- **多种套利策略**：现货-永续套利、三角套利、跨市场套利
- **智能风险管理**：Kelly 仓位管理、熔断机制、实时风控
- **费率优化**：支持 Gate.io VIP 用户 75% 手续费返佣
- **网页管理界面**：可视化监控和配置管理
- **生产级部署**：Docker 容器化、完整测试、监控告警

## 🚀 一、系统要求与准备

### 1.1 硬件要求

- **CPU**: 4核心以上推荐
- **内存**: 8GB 以上推荐  
- **存储**: 50GB 可用空间
- **网络**: 稳定网络连接，低延迟到新加坡/香港

### 1.2 软件要求

- **操作系统**: Ubuntu 22.04 LTS 或更新版本
- **权限**: 非 root 用户（具有 sudo 权限）

### 1.3 必备信息准备

在开始之前，请准备以下信息：

1. **Gate.io API 密钥**
   - 现货交易 API Key 和 Secret
   - 永续合约 API Key 和 Secret（如果使用现货-永续套利）
   - 确保 API 权限包含交易权限

2. **VIP 等级信息**
   - 确认你的 Gate.io VIP 等级
   - 获取实际的手续费率（返佣后）

3. **资金分配计划**
   - 决定用于套利的资金量
   - 不同币种的资金分配比例

## 🛠️ 二、安装 Hummingbot

### 2.1 安装 Hummingbot 2.x

```bash
# 创建工作目录
mkdir -p ~/trading && cd ~/trading

# 下载 Hummingbot
git clone https://github.com/hummingbot/hummingbot.git
cd hummingbot

# 安装依赖
./install

# 编译安装
./compile

# 初始化配置
./init
```

### 2.2 验证安装

```bash
# 启动 Hummingbot 检查安装
./start

# 在 Hummingbot 控制台中输入
connect gate_io

# 如果能看到连接选项说明安装成功
exit
```

## 📦 三、部署套利系统

### 3.1 下载套利套件

```bash
# 假设套利套件已下载到 ~/gate-arbitrage-suite
cd ~/trading/hummingbot

# 复制套利文件
cp -r ~/gate-arbitrage-suite/* .

# 设置权限
chmod +x webui/*.sh
```

### 3.2 配置手续费返佣

这是**最重要**的步骤，直接影响盈利计算的准确性。

```bash
# 编辑费率配置文件
nano conf/examples/conf_fee_overrides.yml
```

**重要**：将以下数值替换为你的实际费率（返佣后）：

```yaml
fee_overrides:
  gate_io:
    # 如果你的 VIP 等级返佣 75%，原始费率 0.2%
    # 实际费率 = 0.2% × (1 - 0.75) = 0.05%
    maker: 0.0005  # 替换为你的实际做市费率
    taker: 0.0005  # 替换为你的实际吃单费率
    
  gate_io_perpetual:
    # 永续合约费率（如果使用现货-永续套利）
    maker: 0.00005  # 替换为你的实际做市费率
    taker: 0.00015  # 替换为你的实际吃单费率
```

**如何获取实际费率**：
1. 登录 Gate.io 网站
2. 进入"用户中心" → "费率等级"
3. 查看当前 VIP 等级的手续费率
4. 计算返佣后费率：实际费率 = 原始费率 × (1 - 返佣比例)

### 3.3 添加 Gate.io API 密钥

#### 方法一：命令行添加（推荐）

```bash
./start

# 在 Hummingbot 控制台中：
connect gate_io

# 按提示输入：
# API Key: [你的现货 API Key]
# Secret Key: [你的现货 Secret Key]
# Testnet: No

# 如果使用永续合约套利，同样添加永续 API：
connect gate_io_perpetual

exit
```

#### 方法二：网页界面添加

稍后在网页管理界面中添加（见第四节）。

### 3.4 创建控制器配置

```bash
# 创建现货-永续套利控制器配置
./create --controller-config arbitrage/gate_spot_perp_controller

# 创建三角套利控制器配置  
./create --controller-config arbitrage/gate_triangular_controller

# 创建主配置文件
./create --script-config v2_with_controllers
```

按照向导提示进行配置，建议初次使用保持默认值。

## 🖥️ 四、安装网页管理界面

网页界面让你可以通过浏览器轻松管理套利机器人。

### 4.1 一键安装

```bash
cd webui
./install.sh
```

安装脚本会自动：
- 安装 Docker 和 Docker Compose
- 创建必要的目录结构
- 生成随机密码
- 创建配置文件

### 4.2 配置环境

```bash
# 编辑配置文件
nano .env

# 重要：设置 Hummingbot 路径
HUMMINGBOT_PATH=/home/你的用户名/trading/hummingbot

# 其他配置通常保持默认
```

### 4.3 启动网页界面

```bash
# 启动服务
./start.sh

# 查看启动状态
docker compose ps
```

如果看到所有服务状态为 "Up"，说明启动成功。

### 4.4 访问网页界面

1. 打开浏览器
2. 访问 `http://你的服务器IP:8501`
3. 使用以下凭据登录：
   - 用户名：`admin`
   - 密码：查看 `.env` 文件中的 `ADMIN_PASSWORD`

## 🎮 五、使用网页界面管理

### 5.1 添加 API 密钥

1. 点击左侧菜单 "Credentials"
2. 在 "Add New Exchange" 部分：
   - Exchange: 选择 `gate_io`
   - API Key: 输入你的现货 API Key
   - Secret Key: 输入你的现货 Secret Key
   - 点击 "Add Credentials"

3. 如需永续合约套利，重复以上步骤添加 `gate_io_perpetual`

### 5.2 配置套利策略

#### 现货-永续套利配置

1. 点击 "Controllers" 菜单
2. 点击 "Create New Controller"
3. 选择控制器类型：`gate_spot_perp_controller`
4. 配置关键参数：
   - **Trading Pairs**: 选择 `BTC-USDT`, `ETH-USDT`
   - **Min Profitability Bps**: 设置最小盈利（建议 5-10）
   - **Max Position Size**: 设置最大仓位（建议从 0.1 开始）
5. 点击 "Create Controller"

#### 三角套利配置

1. 选择控制器类型：`gate_triangular_controller`
2. 配置关键参数：
   - **Base Currencies**: 选择 `USDT`, `BTC`, `ETH`
   - **Min Profitability Bps**: 设置最小盈利（建议 8-15）
   - **Max Position Size**: 设置最大仓位（建议从 0.05 开始）

### 5.3 启动套利机器人

1. 点击 "Bot Management" 菜单
2. 在 "Start Bot" 部分：
   - Script: 选择 `gate_arb_launcher_v2.py`
   - Config Name: 输入 `conf_v2_with_controllers.yml`
3. 点击 "Start Bot"

### 5.4 监控运行状态

1. **仪表板监控**：
   - 点击 "Dashboard" 查看总体状态
   - 监控 PnL、交易次数、胜率等指标

2. **实时日志**：
   - 点击 "Logs" 查看详细运行日志
   - 开启 "Auto-refresh" 实时更新

3. **风险监控**：
   - 注意回撤和总仓位
   - 监控错误率和熔断状态

## ⚖️ 六、风险管理与参数调优

### 6.1 初始保守设置

**新手建议的保守参数**：

```yaml
# 现货-永续套利
min_profitability_bps: 8     # 0.08% 最小盈利
max_position_size: 0.1       # 0.1 BTC 最大仓位
slippage_buffer_bps: 3       # 0.03% 滑点缓冲

# 风险控制
max_session_loss: 0.05       # 5% 单次最大亏损
max_drawdown: 0.03           # 3% 最大回撤
kelly_multiplier: 0.2        # Kelly 系数的 20%
```

### 6.2 参数优化指南

**根据运行表现逐步调优**：

1. **盈利门槛调整**：
   - 如果交易机会太少：降低 `min_profitability_bps`
   - 如果亏损交易较多：提高 `min_profitability_bps`

2. **仓位大小调整**：
   - 根据资金量和风险承受能力调整 `max_position_size`
   - 建议单次仓位不超过总资金的 10%

3. **风险参数调整**：
   - 根据策略表现调整回撤限制
   - 监控熔断触发频率

### 6.3 监控关键指标

**每日必看指标**：

- **净 PnL**：扣除手续费后的实际盈亏
- **胜率**：盈利交易占比（目标 > 60%）
- **夏普比率**：风险调整后收益（目标 > 1.0）
- **最大回撤**：最大亏损幅度（控制在 5% 内）
- **成交率**：订单成功执行率（目标 > 95%）

## 🚨 七、常见问题与故障排查

### 7.1 连接问题

**问题**：无法连接 Gate.io API
```bash
# 检查网络连接
ping api.gate.io

# 检查 API 密钥权限
# 确保在 Gate.io 开启了现货交易权限

# 检查时间同步
sudo ntpdate -s time.nist.gov
```

**问题**：网页界面无法访问
```bash
# 检查 Docker 服务状态
docker compose ps

# 重启服务
./stop.sh && ./start.sh

# 检查防火墙设置
sudo ufw status
```

### 7.2 交易问题

**问题**：没有交易机会
- 检查 `min_profitability_bps` 是否设置过高
- 验证手续费配置是否正确
- 确认市场波动是否足够

**问题**：频繁亏损
- 检查实际手续费率是否与配置一致
- 增加滑点缓冲 `slippage_buffer_bps`
- 提高最小盈利门槛

**问题**：订单被拒绝
```bash
# 检查账户余额
# 确保有足够的基础货币和计价货币

# 检查最小下单量
# Gate.io 有最小下单量限制

# 检查 API 限速
# 避免下单过于频繁
```

### 7.3 系统问题

**问题**：内存使用过高
```bash
# 重启 Hummingbot
./stop
./start

# 清理日志文件
find logs/ -name "*.log" -mtime +7 -delete
```

**问题**：磁盘空间不足
```bash
# 清理 Docker 镜像
docker system prune -a

# 清理旧日志
rm logs/*.log.1 logs/*.log.2
```

## 🔧 八、生产环境优化

### 8.1 系统优化

**性能优化**：

```bash
# 增加文件描述符限制
echo "* soft nofile 65536" | sudo tee -a /etc/security/limits.conf
echo "* hard nofile 65536" | sudo tee -a /etc/security/limits.conf

# 优化网络参数
echo 'net.core.rmem_max = 134217728' | sudo tee -a /etc/sysctl.conf
echo 'net.core.wmem_max = 134217728' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

**定时任务设置**：

```bash
# 编辑定时任务
crontab -e

# 添加以下内容：

# 每天凌晨 2 点重启服务（可选）
0 2 * * * cd /home/你的用户名/trading/hummingbot && ./restart

# 每小时检查磁盘空间
0 * * * * df -h | grep -E '9[0-9]%' && echo "磁盘空间不足" | mail -s "警告" your@email.com

# 每天备份配置文件
0 1 * * * tar -czf /home/backup/config-$(date +\%Y\%m\%d).tar.gz /home/你的用户名/trading/hummingbot/conf/
```

### 8.2 监控与告警

**日志监控脚本**：

```bash
# 创建监控脚本
cat > ~/monitor.sh << 'EOF'
#!/bin/bash
LOG_FILE="/home/你的用户名/trading/hummingbot/logs/hummingbot.log"

# 检查错误日志
ERROR_COUNT=$(grep -c "ERROR" $LOG_FILE | tail -100)
if [ $ERROR_COUNT -gt 10 ]; then
    echo "错误日志过多: $ERROR_COUNT 条" | mail -s "Hummingbot 告警" your@email.com
fi

# 检查 PnL
LAST_PNL=$(grep "PnL" $LOG_FILE | tail -1)
echo "最新 PnL: $LAST_PNL"
EOF

chmod +x ~/monitor.sh

# 每 30 分钟运行一次监控
echo "*/30 * * * * /home/你的用户名/monitor.sh" | crontab -
```

### 8.3 安全加固

**防火墙设置**：

```bash
# 启用防火墙
sudo ufw enable

# 只允许必要端口
sudo ufw allow ssh
sudo ufw allow 8501/tcp  # 网页界面（限制 IP 访问更安全）

# 限制网页界面访问（推荐）
sudo ufw allow from 你的IP地址 to any port 8501
```

**API 密钥安全**：

1. 在 Gate.io 设置 IP 白名单
2. 定期轮换 API 密钥
3. 启用双重认证 (2FA)
4. 监控 API 使用情况

## 📊 九、盈利优化策略

### 9.1 市场时机选择

**最佳交易时间**：
- **亚洲时段**：北京时间 9:00-18:00（流动性较好）
- **欧美重叠时段**：北京时间 21:00-24:00（波动较大）
- **避开周末**：流动性较差，spread 较大

### 9.2 币种选择

**推荐交易对**：
1. **BTC-USDT**：流动性最好，spread 最小
2. **ETH-USDT**：次优选择，波动适中
3. **主流币**：BNB、ADA、DOT 等（注意流动性）

**避开的交易对**：
- 新上线的小币种
- 流动性极差的币种
- 即将下线的币种

### 9.3 资金配置建议

**多策略配置**（建议资金分配）：
- **现货-永续套利**：60%（稳定收益）
- **三角套利**：30%（高频小利）
- **应急资金**：10%（应对突发情况）

## 🎓 十、进阶使用技巧

### 10.1 批量操作

**批量创建配置**：

```bash
# 创建多个交易对的配置
for pair in BTC-USDT ETH-USDT BNB-USDT; do
    echo "创建 $pair 配置"
    # 使用 API 或脚本批量创建
done
```

### 10.2 数据分析

**导出交易数据**：

```bash
# 从日志提取交易数据
grep "Trade executed" logs/hummingbot.log > trades.log

# 分析盈利率
awk '/PnL/ {sum+=$NF; count++} END {print "平均PnL:", sum/count}' trades.log
```

### 10.3 自动化运维

**自动重启脚本**：

```bash
#!/bin/bash
# auto_restart.sh

HUMMINGBOT_DIR="/home/你的用户名/trading/hummingbot"
cd $HUMMINGBOT_DIR

# 检查进程是否运行
if ! pgrep -f "hummingbot" > /dev/null; then
    echo "$(date): Hummingbot 未运行，正在重启..."
    ./start --script gate_arb_launcher_v2.py --conf conf_v2_with_controllers.yml
    
    # 发送通知
    echo "Hummingbot 已重启于 $(date)" | mail -s "Hummingbot 重启通知" your@email.com
fi
```

## 🆘 技术支持与联系

### 获取帮助

1. **查看日志**：大多数问题都可以通过日志找到原因
2. **查阅文档**：参考 Hummingbot 官方文档
3. **社区支持**：加入 Hummingbot 中文社群

### 常用命令参考

```bash
# Hummingbot 相关
./start                    # 启动
./stop                     # 停止
./status                   # 查看状态
tail -f logs/hummingbot.log # 查看实时日志

# 网页界面相关
cd webui && ./start.sh     # 启动网页界面
cd webui && ./stop.sh      # 停止网页界面
docker compose logs -f     # 查看 Docker 日志

# 系统监控
htop                       # 查看系统资源
df -h                      # 查看磁盘空间
free -h                    # 查看内存使用
```

---

**祝你交易顺利，收益满满！** 🚀

记住：
- 从小仓位开始测试
- 密切监控初期表现
- 根据实际情况调整参数
- 保持耐心和纪律

如有问题，请参考故障排查部分或寻求技术支持。

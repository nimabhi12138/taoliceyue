# 🚀 Gate.io套利系统快速启动指南

## 📋 前置条件

1. **安装Hummingbot 2.x**
```bash
# 安装官方Hummingbot
git clone https://github.com/hummingbot/hummingbot.git
cd hummingbot
./install
```

2. **配置Gate.io连接器**
```bash
# 启动Hummingbot并配置API
python bin/hummingbot_quickstart.py
# 在Hummingbot中运行: connect gate_io
```

## ⚡ 快速部署

```bash
# 1. 下载套利套件
git clone <this-repository>
cd gate-arbitrage-suite

# 2. 一键部署
chmod +x deploy.sh
./deploy.sh

# 3. 配置费用返佣
# 编辑 $HUMMINGBOT_PATH/conf/examples/conf_fee_overrides.yml
# 设置您的实际费率（75%返佣后）

# 4. 启动套利系统
cd $HUMMINGBOT_PATH
./start_gate_arb.sh
```

## 🎯 启动选项

### 选项1: 简单示例（推荐新手）
```bash
python bin/hummingbot_quickstart.py start \
  --script gate_arb_example.py \
  --conf conf/scripts/gate_arb_example.yml
```

### 选项2: 高级控制器
```bash  
python bin/hummingbot_quickstart.py start \
  --script gate_arb_launcher_v2.py \
  --conf conf/examples/conf_v2_with_controllers.yml
```

### 选项3: 传统策略
```bash
python bin/hummingbot_quickstart.py start \
  --script gate_arb_legacy.py
```

## 🔧 配置说明

### 费用配置 (重要!)
编辑 `conf/examples/conf_fee_overrides.yml`:
```yaml
fee_overrides:
  gate_io:
    maker: 0.0005  # 0.2% * 0.25 = 0.05% (75%返佣后)
    taker: 0.0005  # 0.2% * 0.25 = 0.05% (75%返佣后)
  gate_io_perpetual:
    maker: 0.00005  # 0.02% * 0.25 = 0.005% (75%返佣后)
    taker: 0.00015  # 0.06% * 0.25 = 0.015% (75%返佣后)
```

### 风险参数
编辑 `conf/scripts/gate_arb_example.yml`:
```yaml
strategy_config:
  min_profitability: 0.0008  # 0.08%最小利润
  max_position_size: 0.1     # 最大仓位
  check_interval: 5.0        # 检查间隔(秒)
```

## 📊 监控

### Web界面
```bash
cd $HUMMINGBOT_PATH/webui
./start.sh
# 访问 http://localhost:8501
```

### 命令行监控
```bash
# 系统状态
./gate_arb_status.sh

# 健康检查
python healthcheck.py

# 查看日志
tail -f logs/gate_arbitrage.log
```

## 🆘 故障排查

### 常见问题

1. **导入错误**
```bash
# 检查Python路径
python -c "import sys; print(sys.path)"
# 检查控制器导入
python -c "from controllers.arbitrage.fee_model import FeeModel"
```

2. **连接器未找到**
```bash
# 确认Gate.io连接器已配置
python bin/hummingbot_quickstart.py
# 运行: connect gate_io
```

3. **配置文件错误**
```bash
# 验证YAML语法
python -c "import yaml; yaml.safe_load(open('conf/scripts/gate_arb_example.yml'))"
```

### 调试模式
```bash
# 启用调试日志
export LOG_LEVEL=DEBUG
python bin/hummingbot_quickstart.py start --script gate_arb_example.py
```

## 📞 支持

- **健康检查**: `python healthcheck.py`
- **状态检查**: `./gate_arb_status.sh`  
- **日志位置**: `$HUMMINGBOT_PATH/logs/`
- **配置位置**: `$HUMMINGBOT_PATH/conf/`

## ✅ 验证清单

- [ ] Hummingbot已安装并可运行
- [ ] Gate.io API已配置并测试通过
- [ ] 费用返佣配置正确(75%)
- [ ] 套利脚本可以启动
- [ ] 监控界面可以访问
- [ ] 日志正常输出

---

**🎉 现在您可以开始使用Gate.io套利系统了！**
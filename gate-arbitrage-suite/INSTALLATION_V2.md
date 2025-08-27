# Gate.io Arbitrage Suite - Hummingbot V2 Installation Guide

## 🎯 Quick Overview

This arbitrage suite is a **plugin for Hummingbot** that adds advanced arbitrage strategies optimized for Gate.io's 75% trading fee rebate program. It's designed to work with Hummingbot V2 Framework (2024 version).

## ✅ Compatibility

- **Hummingbot Version**: 2.0.0 or higher
- **Python**: 3.10 or higher
- **Supported Exchanges**: Gate.io (Spot & Perpetual)
- **Operating Systems**: Ubuntu 20.04+, macOS, Windows (WSL2)

## 📦 What This Suite Includes

1. **Controllers** (V2 Framework Compatible):
   - `gate_spot_perp_controller_v2.py` - Spot-Perpetual basis arbitrage
   - `gate_triangular_controller.py` - Triangular arbitrage
   - `gate_spot_spot_controller.py` - Cross-market spot arbitrage
   - `gate_stat_arb_controller.py` - Statistical arbitrage

2. **Scripts** (Entry Points):
   - `gate_arb_v2.py` - Main V2 framework script
   - `gate_arb_launcher_v2.py` - Multi-controller loader
   - `gate_arb_legacy.py` - Legacy compatibility script

3. **Optional Components**:
   - Web Admin UI (Docker-based)
   - Monitoring (Prometheus/Grafana)
   - Production deployment tools

## 🚀 Installation Steps

### Step 1: Install Hummingbot

```bash
# Clone Hummingbot repository
git clone https://github.com/hummingbot/hummingbot.git
cd hummingbot

# Install using Docker (Recommended)
docker pull hummingbot/hummingbot:latest

# OR install from source
./install.sh
```

### Step 2: Install Gate.io Arbitrage Suite

```bash
# Clone this repository
git clone https://github.com/your-repo/gate-arbitrage-suite.git
cd gate-arbitrage-suite

# Copy files to Hummingbot directory
# Assuming Hummingbot is installed at ~/hummingbot
HUMMINGBOT_DIR=~/hummingbot

# Copy controllers
cp -r controllers/* $HUMMINGBOT_DIR/hummingbot/smart_components/controllers/

# Copy scripts
cp scripts/* $HUMMINGBOT_DIR/scripts/

# Copy configurations
cp -r conf/* $HUMMINGBOT_DIR/conf/

# Copy utilities (optional)
cp -r utils/* $HUMMINGBOT_DIR/hummingbot/smart_components/utils/
```

### Step 3: Configure Fee Overrides (75% Rebate)

Edit the fee override file to apply your 75% rebate:

```bash
# Edit fee overrides
nano $HUMMINGBOT_DIR/conf/conf_fee_overrides.yml
```

Update with your actual rebated fees:
```yaml
# Gate.io with 75% rebate
gate_io:
  default:
    maker_fee: 0.00025  # 0.025% (0.1% * 0.25)
    taker_fee: 0.0005   # 0.05% (0.2% * 0.25)
    
gate_io_perpetual:
  default:
    maker_fee: 0.00005  # 0.005% (0.02% * 0.25)
    taker_fee: 0.00015  # 0.015% (0.06% * 0.25)
```

### Step 4: Connect to Gate.io

Start Hummingbot and add your Gate.io API credentials:

```bash
# Start Hummingbot
cd $HUMMINGBOT_DIR
./start.sh

# In Hummingbot terminal:
>>> connect gate_io
Enter your Gate.io API key >>> YOUR_API_KEY
Enter your Gate.io secret key >>> YOUR_SECRET_KEY

>>> connect gate_io_perpetual
Enter your Gate.io Perpetual API key >>> YOUR_PERP_API_KEY
Enter your Gate.io Perpetual secret key >>> YOUR_PERP_SECRET_KEY
```

### Step 5: Run the Arbitrage Strategy

```bash
# In Hummingbot terminal:

# Option 1: Run the main V2 script
>>> start --script gate_arb_v2.py

# Option 2: Use specific controller
>>> create --controller-config
What is your controller id? >>> my_spot_perp_arb
Select a controller (directional/market_making) >>> directional
Select a specific controller >>> gate_spot_perp_controller_v2

# Start with controller
>>> start --controller-id my_spot_perp_arb
```

## 🔧 Configuration Examples

### Basic Arbitrage Configuration

Create a controller configuration:

```yaml
# conf/controllers/my_arbitrage.yml
controller_name: gate_spot_perp_controller
controller_type: directional
spot_connector_name: gate_io
perp_connector_name: gate_io_perpetual
trading_pairs:
  - BTC-USDT
  - ETH-USDT
min_basis_bps: 25  # Lower due to rebate
position_size_quote: 1000
max_position_quote: 10000
use_maker_orders: true
```

### Advanced Multi-Strategy Configuration

```yaml
# conf/scripts/multi_arbitrage.yml
strategies:
  - type: spot_perp_arbitrage
    enabled: true
    config: conf/controllers/spot_perp.yml
  - type: triangular_arbitrage
    enabled: true
    config: conf/controllers/triangular.yml
  - type: statistical_arbitrage
    enabled: false
    config: conf/controllers/stat_arb.yml
    
risk_management:
  max_total_exposure: 50000
  daily_loss_limit: 1000
  circuit_breaker_enabled: true
```

## 📊 Monitoring (Optional)

### Quick Monitoring Setup

```bash
# Install monitoring stack
cd webui
./install.sh

# Start monitoring
./start.sh

# Access:
# - Web UI: http://localhost:8080
# - Grafana: http://localhost:3000
# - API Docs: http://localhost:8000/docs
```

## 🧪 Testing Your Setup

### 1. Test Connection

```python
# In Hummingbot terminal:
>>> balance
```

Should show your Gate.io balances.

### 2. Test Arbitrage Detection

```python
# In Hummingbot terminal:
>>> status
```

Should show arbitrage opportunities if any exist.

### 3. Paper Trading Test

```python
# In Hummingbot terminal:
>>> paper_trade on
>>> start --script gate_arb_v2.py
```

## ⚠️ Important Notes

1. **API Key Permissions**: Ensure your Gate.io API keys have:
   - Spot trading enabled
   - Futures trading enabled
   - Read permissions
   - NO withdrawal permissions (for security)

2. **Rate Limits**: Gate.io limits:
   - 10 requests/second for public endpoints
   - 5 orders/second for trading
   - Our suite includes automatic rate limiting

3. **Minimum Order Sizes**:
   - BTC: 0.0001 BTC minimum
   - ETH: 0.001 ETH minimum
   - USDT pairs: 1 USDT minimum

4. **VIP Level**: To get 75% rebate, you need:
   - VIP 1 or higher on Gate.io
   - Or participate in their rebate program

## 🛠️ Troubleshooting

### Issue: "Module not found" error

```bash
# Ensure paths are correct
export PYTHONPATH=$PYTHONPATH:~/hummingbot
```

### Issue: "Insufficient balance"

- Check minimum order sizes
- Ensure you have balance in both spot and futures accounts

### Issue: "Rate limit exceeded"

- Reduce `order_refresh_time` in configuration
- Enable `use_maker_orders: true`

### Issue: "No arbitrage opportunities found"

- This is normal during low volatility
- Check that fee overrides are correctly configured
- Verify both connectors are working

## 📈 Performance Optimization

1. **Use Maker Orders**: Always prefer maker orders for lower fees
2. **Optimize Position Sizing**: Start small, increase gradually
3. **Monitor Funding Rates**: Avoid high funding rate periods
4. **Use Multiple Pairs**: Diversify across BTC, ETH, and other majors

## 🔐 Security Best Practices

1. **Never share API keys**
2. **Use read-only keys when possible**
3. **Enable IP whitelisting on Gate.io**
4. **Run on a secure VPS**
5. **Use encrypted storage for credentials**

## 📚 Additional Resources

- [Hummingbot Documentation](https://docs.hummingbot.org/)
- [Gate.io API Documentation](https://www.gate.io/docs/developers/apiv4)
- [Video Tutorial](https://youtube.com/hummingbot)
- [Discord Support](https://discord.gg/hummingbot)

## 💬 Support

- **Hummingbot Discord**: [Join here](https://discord.gg/hummingbot)
- **GitHub Issues**: Report bugs on GitHub
- **Gate.io Support**: For exchange-specific issues

---

## 🚦 Quick Start Checklist

- [ ] Hummingbot installed and running
- [ ] Gate.io API keys configured
- [ ] Fee overrides set (75% rebate)
- [ ] Controllers copied to Hummingbot directory
- [ ] Scripts copied to scripts folder
- [ ] Test with paper trading first
- [ ] Monitor initial trades closely
- [ ] Gradually increase position sizes

**Ready to start arbitraging! 🚀**
# Gate.io Arbitrage Suite for Hummingbot 2.x (Spot–Perp, Spot–Spot, Triangular, Stat-Arb) + Web UI

This package provides a production-grade arbitrage suite tailored to Gate.io with a 75% trading fee rebate assumption, a global fee override file, multiple arbitrage controllers emitting `ExecutorAction`s (no raw order placement), unit tests, and a lightweight Web Admin UI (FastAPI backend + Streamlit frontend) that runs beside Hummingbot on Ubuntu via Docker Compose.

- Scripts in `scripts/`
- Controllers in `controllers/`
- Controller configs in `conf/controllers/`
- Script configs in `conf/scripts/` (created by CLI)
- Global net fee overrides in `conf/examples/conf_fee_overrides.yml`
- Targets Gate.io Spot (`gate_io`) and Gate.io Perpetuals (`gate_io_perpetual`)
- Provides run commands using Hummingbot’s generic loader `v2_with_controllers.py` (or our wrapper)

## Key Features

- Multiple arbitrage engines (all edge after net fees + slippage):
  - Spot–Perp Basis (cash-and-carry) on Gate (`gate_io` vs `gate_io_perpetual`)
  - Spot–Spot cross-market (intra-exchange or cross-venue via connector abstraction)
  - Triangular arbitrage with per-leg net fees and slippage buffers
  - Statistical pairs (optional): co-integration, z-score, half-life for mean-reversion
- Maker-preference micro-arb with post-only where viable; fallback to taker
- Global fee model with 75% rebate support via `conf_fee_overrides.yml`
- Risk management: truncated Kelly cap, exposure caps, circuit breakers
- Execution: emit `ExecutorAction`s for official Hummingbot executors
- Observability: JSON logs per controller, `format_status()` with KPIs
- Web UI: manage credentials, configs, start/stop bots, tail logs; Dockerized

## Compatibility

- Hummingbot 2.x
- Connector IDs: `gate_io` (spot), `gate_io_perpetual` (perps)
- Python 3.11+
- Uses Decimal for monetary math and exchange precision compliance
- Controllers compute and emit `ExecutorAction`s; leverage Hummingbot Executors

If Hummingbot APIs differ on your installed version, this package includes safe shims and clear notes. This repository does not place raw orders; it computes actions and expects Hummingbot’s official executors to manage order placement, partials, timeouts, and rollbacks.

## Repository Layout

- `scripts/`
  - `gate_arb_launcher_v2.py`: wrapper to use official loader or fallback
  - `gate_arb_legacy.py`: legacy `ScriptStrategyBase` demo (backup/compat)

- `controllers/arbitrage/`
  - `common.py`: fee model, risk sizing (Kelly), budget checks, controller base + shims
  - `gate_spot_perp_controller.py`
  - `gate_spot_spot_controller.py`
  - `gate_triangular_controller.py`
  - `gate_stat_arb_controller.py` (optional)

- `conf/examples/`
  - `conf_v2_with_controllers.yml`: generic script config referencing controllers
  - `conf_fee_overrides.yml`: sample with 75% rebate placeholders

- `conf/controllers/arbitrage/`
  - `gate_spot_perp_controller.yml`
  - `gate_spot_spot_controller.yml`
  - `gate_triangular_controller.yml`
  - `gate_stat_arb_controller.yml`

- `webui/`
  - `docker-compose.yml`, `.env.example`
  - `install.sh`, `start.sh`, `stop.sh`
  - `backend/` (FastAPI)
  - `frontend/` (Streamlit)
  - `nginx/` (optional reverse proxy)

- `tests/`
  - `test_fee_model.py`
  - `test_kelly.py`
  - `test_triangular.py`
  - `test_budget_check.py`

- `LICENSE`, `README.md`

## Fees & Slippage

- rebate_ratio = 0.75 (75% rebate assumption)
- Effective fee per leg: `eff_fee_bps = raw_bps * (1 - rebate_ratio)`
- Global overrides via `conf/examples/conf_fee_overrides.yml`:
  - You can set “post-rebate” values directly (raw × 0.25) or raw + rebate_ratio
- Net-edge condition:
  - Sum(path_edge_bps) > Sum(eff_fee_bps_legs) + slippage_buffer_bps + safety_margin_bps
- Perps include expected funding in net PnL

## Risk & Execution

- Truncated Kelly sizing with configurable caps
- Exposure caps by symbol and per-trade notional max
- Circuit breakers: session loss limit, rolling drawdown, error-rate spikes, liquidity thinning
- Executors: async parallel, post-only, IOC/FOK fallbacks, timeouts with cancel/replace and backoff
- Precision: Decimal and pre-validation (lot size, min notional)

## Observability

- JSON logs per controller
- `format_status()` string for HUMMINGBOT UI
- Optional Prometheus/CSV export hooks (stubs in `common.py` for extension)

## Create Configs (CLI UX)

- Create controller configs:
  - `create --controller-config arbitrage/gate_spot_perp_controller`
  - `create --controller-config arbitrage/gate_spot_spot_controller`
  - `create --controller-config arbitrage/gate_triangular_controller`
  - `create --controller-config arbitrage/gate_stat_arb_controller`

- Create generic script config:
  - `create --script-config v2_with_controllers`

## Start Commands

- Generic loader (preferred if present in your HB 2.x):
  - `start --script v2_with_controllers.py --conf conf_v2_with_controllers.yml`

- Wrapper script (auto-uses official loader if present):
  - `start --script gate_arb_launcher_v2.py --conf conf/examples/conf_v2_with_controllers.yml`

- Legacy script demo:
  - `start --script gate_arb_legacy.py --conf conf/scripts/gate_arb_legacy.yml`

Note: Place your final `conf_v2_with_controllers.yml` under `conf/scripts/` if your HB is configured that way, or reference the path you prefer. Controller configs live under `conf/controllers/`.

## Hummingbot Integration Notes (2.x)

- Controllers emit lists of `ExecutorAction` objects per tick. The official loader submits these to Hummingbot executors (Arbitrage, XEMM-style, etc.).
- If the official `v2_with_controllers.py` is absent, our `gate_arb_launcher_v2.py` will fallback to an internal minimal dispatcher that loads controller YAMLs, calls their `on_tick()` and prints/logs the actions. For live trading, prefer the official loader.

## Unit Tests

- Run `pytest -q` from repository root
- Tests cover fee model math (including 75% rebate), Kelly sizing, triangular net-edge, and budget/filters

## Acceptance Checklist

- Controllers initialize and run with Gate spot/perp; at least two engines are able to trade in paper/live mode via official executors
- Net-fee math honors 75% rebate via `conf_fee_overrides.yml`
- Circuit breakers and Kelly caps throttle risk
- Executors handle timeouts/partials with safe rollback (via Hummingbot)
- Web UI supports credentials, config CRUD, start/stop, and status/logs
- A full Chinese step-by-step guide is at the end of this README

---

## 《小白也能用：Ubuntu 部署与使用全流程（含网页管理）》

以下内容面向非程序员，手把手完成在 Ubuntu 22.04+ 上的部署与使用（含网页管理界面）。

### 一、准备环境
- 一台 Ubuntu 22.04+ 服务器（建议 x86_64）
- 已安装 git、Python 3.11（Hummingbot 2.x 要求）
- 拥有 Gate.io 的 API Key（Spot 与 Perp）

### 二、放置本套件
1) 将本目录整体复制到 Hummingbot 2.x 实例根目录（与 `scripts/`、`conf/` 等并列）。
2) 确认目录存在：`scripts/`, `controllers/`, `conf/`, `webui/`, `tests/`。

### 三、安装/启动 Hummingbot（若尚未安装）
- 参考官方文档安装 Hummingbot 2.x。
- 启动 Hummingbot（本地或 Docker 均可），确保可以执行 `start` 命令。

### 四、设置 75% 返佣（关键）
1) 编辑 `conf/examples/conf_fee_overrides.yml`：
   - 推荐直接填入“返佣后”的费率，即“原始费率 × 0.25”，示例（需改为你自己的实际值）：
```
connectors:
  gate_io:
    spot:
      maker_bps_post_rebate: 0.025
      taker_bps_post_rebate: 0.05
  gate_io_perpetual:
    perpetual:
      maker_bps_post_rebate: 0.005
      taker_bps_post_rebate: 0.04
```
   - 如果只知道原始费率，也可填写 `maker_bps`/`taker_bps`，并保留 `rebate_ratio: 0.75`，系统会自动折算净费率。

### 五、添加 Gate API Key
- 若启用了官方 Hummingbot Dashboard 或 REST API，可通过其 UI 完成 API Key 加密存储。
- 否则也可使用本 Web Admin 进行最小化管理（安全建议：优先使用 Hummingbot 官方加密存储）。

### 六、生成控制器配置（CLI 或 Web UI）
- CLI 方式（在 Hummingbot 内执行）：
  - 生成控制器配置：
    - `create --controller-config arbitrage/gate_spot_perp_controller`
    - `create --controller-config arbitrage/gate_spot_spot_controller`
    - `create --controller-config arbitrage/gate_triangular_controller`
    - `create --controller-config arbitrage/gate_stat_arb_controller`
  - 生成通用脚本配置：
    - `create --script-config v2_with_controllers`
- Web UI 方式：
  - 启动后在“Controller Templates”标签页加载模板，编辑参数并保存到 `conf/controllers/arbitrage/` 路径下。

### 七、启动 Web 管理界面
1) 安装 Docker 与 Compose 插件：
```
cd webui
./install.sh
```
2) 启动 Web UI（首次会生成 `.env`，请检查端口与认证）：
```
./start.sh
```
3) 浏览器访问：
- 后端：`http://<服务器IP>:8000/status`
- 前端：`http://<服务器IP>:8501`
4) 登录（如设置了 `WEBUI_USERNAME`/`WEBUI_PASSWORD`），完成：
- 修改费率覆盖
- 查看模板，保存控制器 YAML
- 启动/停止机器人
- 查看实时日志

### 八、启动/停止机器人（命令行）
- 使用官方通用加载器（优先）：
```
start --script v2_with_controllers.py --conf conf/examples/conf_v2_with_controllers.yml
```
- 使用包装脚本（自动检测官方加载器，否则用轻量分发器）：
```
start --script scripts/gate_arb_launcher_v2.py --conf conf/examples/conf_v2_with_controllers.yml
```
- 兼容演示（Legacy）：
```
start --script scripts/gate_arb_legacy.py --conf conf/scripts/gate_arb_legacy.yml
```

### 九、常见故障排查
- 权限：`webui/install.sh` 后执行 `sudo usermod -aG docker $USER && newgrp docker`
- 系统对时：确保服务器时间同步（NTP）
- 最小下单量/精度：若报错“低于最小名义金额/精度”，调大下单量或调整 `filters`
- 429/限速：提高 `tick_interval_seconds`、减少并发控制器或启用速率限制
- 资金费率（Perp）：在 `gate_spot_perp_controller.yml` 中提高阈值/降低仓位以覆盖资金费用
- 连接器/交易对：确认 `gate_io` 与 `gate_io_perpetual` 可用、交易对拼写正确

### 十、生产注意事项
- 安全：务必使用 Hummingbot 的加密存储 API Key；Web UI 开启基本认证，并在服务器层面设置防火墙只允许特定来源访问
- 备份：定期备份 `conf/` 与 `logs/`
- 日志：需要更强观测性时，可在 `controllers/.../common.py` 中扩展 Prometheus/CSV 导出
- 自动重启：使用 systemd/Docker restart 策略
- TLS/防火墙：生产上建议启用 Nginx + Let’s Encrypt 并限制来源网段

### 十一、验收要点
- 控制器在 Gate Spot/Perp 能初始化与运行（纸币或实盘）
- `conf_fee_overrides.yml` 的 75% 返佣净费率生效
- Kelly 上限与断路器能看到限流效果
- 执行器处理超时/部分成交并回滚（由 Hummingbot Executor 完成）
- Web UI 支持：凭证、配置 CRUD、启动/停止、状态/日志
- 全流程在纸币模式跑通

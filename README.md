# A股信号检测与回测系统

A股市场实时信号检测与历史回测系统，支持沪深300重点监控、技术指标信号、多渠道告警通知。

akshare：主要用户获取股票数据（历史与实时），提供丰富的股票、基金、指数、期权等数据接口。

akquant：AKQuant 是一款专为 量化投研 (Quantitative Research) 打造的高性能量化回测框架。它以 Rust 铸造极速撮合内核， 以 Python 链接数据与 AI 生态，旨在为量化投资者提供可靠高效的量化投研解决方案。参见[AKQuant](https://github.com/akfamily/akquant)


## 功能特性

- **实时信号检测**: 支持多种技术指标信号（金叉/死叉、RSI、超买超卖、成交量异动等）
- **三层扫描机制**: 
  - HS300成分股（5秒间隔）
  - 全市场股票（30秒间隔）
  - 行业板块（30秒间隔）
- **历史回测**: 支持任意时间段的策略回测，提供完整的绩效分析
- **多渠道通知**: 支持控制台、文件、邮件、钉钉机器人
- **REST API**: 提供HTTP接口进行服务管理和数据查询

## 环境要求

- Python 3.12+
- uv 包管理器

## 安装

```bash
# 克隆项目
git clone <repository-url>
cd stock-explorer

# 使用uv安装依赖
uv sync

# 或安装项目
uv pip install -e .
```

## 配置

配置文件位于 `config/config.yaml`，包含以下主要部分：

### 配置文件结构

```yaml
# 沪深300扫描配置
scan:
  hs300:
    enabled: true        # 是否启用HS300扫描
    interval: 5          # 扫描间隔（秒）
    strategies:          # 启用的策略
      - golden_cross     # 均线金叉
      - capital_flow     # 资金流向
      - limit_up         # 涨停

  market:
    enabled: true        # 是否启用全市场扫描
    interval: 30         # 扫描间隔（秒）
    strategies:          # 启用的策略
      - limit_up
      - volume_surge     # 成交量异动
      - high_turnover    # 高换手率

  industry:
    enabled: true        # 是否启用行业扫描
    interval: 30         # 扫描间隔（秒）
    industries:          # 监控的行业
      - 银行
      - 证券
      - 科技
      - 医药

# Redis配置
redis:
  enabled: true          # 是否启用Redis
  host: "localhost"     # Redis主机
  port: 6379            # Redis端口
  password: ""          # Redis密码
  db: 0                 # Redis数据库
  realtime_ttl: 10      # 实时数据缓存时间（秒）
  hs300_cache_ttl: 60   # HS300数据缓存时间（秒）

# SQLite配置
sqlite:
  enabled: true          # 是否启用SQLite
  path: "data/stock_explorer.db"  # 数据库文件路径

# 告警配置
alert:
  console: true          # 控制台通知
  file: true             # 文件通知
  file_path: "logs/signals.log"  # 日志文件路径

  email:
    enabled: false       # 是否启用邮件通知
    smtp_host: "smtp.example.com"  # SMTP服务器
    smtp_port: 465       # SMTP端口
    smtp_user: "user@example.com"  # 邮箱用户名
    smtp_password: "your_password"  # 邮箱密码
    from_addr: "stockbot@example.com"  # 发件人
    to_addrs:            # 收件人列表
      - "receiver1@example.com"

  dingtalk:
    enabled: false       # 是否启用钉钉通知
    webhook_url: "https://oapi.dingtalk.com/robot/send?access_token=xxx"  # 钉钉webhook
    secret: ""           # 钉钉密钥（可选）

  min_strength: "medium"  # 最小信号强度（low/medium/high）
  exclude_st: true       # 排除ST股票
  min_market_cap: 10000000000  # 最小市值（100亿）
  rate_limit_seconds: 60  # 通知频率限制（秒）

# API配置
api:
  enabled: false         # 是否启用API服务
  host: "0.0.0.0"       # API服务主机
  port: 8000            # API服务端口
```

### 如何修改配置文件

1. **编辑配置文件**：使用文本编辑器打开 `config/config.yaml` 文件

2. **修改扫描设置**：
   - 调整 `scan` 部分的 `enabled` 字段启用/禁用扫描
   - 修改 `interval` 字段调整扫描间隔
   - 在 `strategies` 列表中添加/删除启用的策略
   - 在 `industries` 列表中添加/删除监控的行业

3. **修改通知设置**：
   - 启用/禁用不同的通知渠道（console、file、email、dingtalk）
   - 配置邮件和钉钉的相关参数
   - 调整 `min_strength` 过滤信号强度
   - 修改 `min_market_cap` 设置最小市值

4. **修改服务设置**：
   - 启用/禁用 `redis` 缓存
   - 启用/禁用 `api` 服务

5. **保存配置**：修改完成后保存文件，系统会自动加载新的配置

### 配置示例

**示例1：启用邮件通知**
```yaml
alert:
  email:
    enabled: true
    smtp_host: "smtp.163.com"
    smtp_port: 465
    smtp_user: "your_email@163.com"
    smtp_password: "your_app_password"
    from_addr: "your_email@163.com"
    to_addrs:
      - "your_other_email@example.com"
```

**示例2：调整扫描策略**
```yaml
scan:
  hs300:
    strategies:
      - golden_cross
      - death_cross
      - rsi_oversold
      - rsi_overbought
```

**示例3：启用API服务**
```yaml
api:
  enabled: true
  host: "127.0.0.1"
  port: 8080
```

## 使用方法

### CLI 命令

#### 1. 启动常驻服务

```bash
# 启动信号检测守护进程
stock-explorer daemon

# 启动API服务
stock-explorer api
```

#### 2. 信号扫描

```bash
# 扫描HS300成分股
stock-explorer monitor-hs300

# 扫描全市场
stock-explorer monitor-all

# 扫描行业板块
stock-explorer monitor-industry
```

#### 3. 数据获取

```bash
# 获取HS300成分股
stock-explorer data-hs300

# 获取行业数据
stock-explorer data-industry
```

#### 4. 策略管理

```bash
# 列出所有信号检测策略
stock-explorer list-strategies

# 查看信号列表
stock-explorer list-signals
```

#### 5. 回测功能

```bash
# 执行回测
stock-explorer backtest --symbols 000001,000002 --start 2023-01-01 --end 2023-12-31
```

### Python API

```python
from stock_explorer.backtest.engine import BacktestEngine
from stock_explorer.backtest.analyzer import PerformanceAnalyzer
from stock_explorer.monitor.scanner import Scanner
from stock_explorer.service.manager import ServiceManager

# 回测示例
engine = BacktestEngine(initial_capital=1000000)
result = engine.run(
    symbols=["000001", "600000"],
    start_date="2023-01-01",
    end_date="2023-12-31",
)

analyzer = PerformanceAnalyzer()
metrics = analyzer.analyze(result.trades, result.equity_curve)
print(analyzer.generate_report(metrics))

# 实时扫描示例
from stock_explorer.config.settings import Settings
scanner = Scanner(Settings())
signals = scanner.scan_hs300()
for signal in signals:
    print(signal)
```

## 信号类型

| 信号类型 | 描述 | 方向 |
|---------|------|------|
| golden_cross | 均线金叉 | 看涨 |
| death_cross | 均线死叉 | 看跌 |
| rsi_oversold | RSI超卖 | 看涨 |
| rsi_overbought | RSI超买 | 看跌 |
| volume_surge | 成交量异动 | 观望 |
| limit_up | 涨停 | 观望 |
| limit_down | 跌停 | 观望 |
| breakout | 突破 | 看涨 |

## 项目结构

```
stock-explorer/
├── src/stock_explorer/
│   ├── backtest/        # 回测引擎
│   │   ├── engine.py    # 回测核心逻辑
│   │   └── analyzer.py  # 绩效分析
│   ├── cli/             # 命令行
│   │   └── commands.py  # CLI命令
│   ├── config/          # 配置管理
│   │   └── settings.py  # 配置加载
│   ├── data/            # 数据层
│   │   ├── fetcher.py   # 数据获取
│   │   ├── cache.py     # 缓存管理
│   │   └── storage.py   # SQLite存储
│   ├── logging/         # 日志
│   │   └── logger.py    # 日志配置
│   ├── monitor/         # 监控层
│   │   ├── scanner.py   # 信号扫描
│   │   └── notifier.py  # 通知发送
│   ├── service/         # 服务层
│   │   ├── manager.py   # 服务管理
│   │   ├── scheduler.py # 任务调度
│   │   └── api.py       # REST API
│   └── signal/          # 信号层
│       ├── base.py      # 信号模型
│       ├── indicators.py# 技术指标
│       ├── detectors.py # 信号检测
│       └── registry.py  # 信号注册
├── config/
│   └── config.yaml      # 配置文件
├── tests/               # 单元测试
└── docs/                # 文档
```

## Docker 部署

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install uv && uv sync

COPY . .

CMD ["python", "-m", "stock_explorer.cli.commands", "daemon-start"]
```

## 常见问题

### Q: 如何添加新的信号检测策略？

A: 在 `signal/detectors.py` 中继承 `SignalDetector` 类，实现 `detect` 方法，然后在 `signal/registry.py` 中注册。

### Q: 回测支持哪些数据周期？

A: 支持1分钟（1m）、5分钟（5m）、15分钟（15m）、日线（daily）、周线（weekly）、月线（monthly）。

### Q: 如何修改扫描间隔？

A: 在 `config/config.yaml` 中修改 `scan` 部分的间隔配置。

## 代码质量

### 语法检查

项目使用 ruff 进行代码语法检查和自动修复：

```bash
# 检查代码语法
uv run ruff check src

# 检查测试文件语法
uv run ruff check tests

# 自动修复语法问题
uv run ruff check src --fix
uv run ruff check tests --fix
```

### 测试

```bash
# 运行所有测试
uv run pytest

# 运行特定模块测试
uv run pytest tests/test_signal.py

# 运行带覆盖率
uv run pytest --cov=src/stock_explorer
```

## 许可证

MIT License

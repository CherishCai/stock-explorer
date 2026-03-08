# A股信号检测与回测系统 - 智能架构

## 1. 系统概述

### 1.1 核心定位
本系统是一个兼具**实时信号检测**和**历史数据回测**能力的A股量化投资系统，支持多策略信号检测、完整回测分析和实时监控告警。

### 1.2 技术栈
- **包管理**: uv (必须)
- **数据源**: akshare + akquant (必须)
- **Python版本**: >=3.12
- **数据存储**: SQLite + Redis
- **告警渠道**: 控制台、文件、邮件、钉钉机器人

## 2. 系统架构

### 2.1 整体架构
```
stock-explorer/
├── src/stock_explorer/
│   ├── data/                   # 数据层
│   │   ├── fetcher.py          # 数据抓取 (akshare)
│   │   ├── cache.py            # 缓存 (内存/Redis)
│   │   └── storage.py          # 存储 (SQLite)
│   ├── signal/                 # 信号检测层
│   │   ├── base.py             # 信号基类 & 协议
│   │   ├── indicators.py       # 技术指标计算
│   │   ├── detectors.py        # 技术面检测器
│   │   ├── detectors_fundamental.py  # 财经信号检测器
│   │   ├── detectors_sentiment.py   # 舆情信号检测器
│   │   └── registry.py         # 信号注册表
│   ├── backtest/               # 回测层 (akquant)
│   │   ├── engine.py           # 回测引擎 (akquant)
│   │   ├── context.py          # 回测上下文 (akquant)
│   │   └── analyzer.py         # 绩效分析 (akquant)
│   ├── monitor/                # 实时监控层
│   │   ├── collector.py        # 实时数据采集
│   │   ├── scanner.py          # 市场扫描 (三层扫描)
│   │   └── notifier.py         # 告警通知
│   ├── service/                # 常驻服务层
│   │   ├── manager.py          # 服务管理
│   │   ├── scheduler.py        # 任务调度
│   │   └── api.py              # REST API (可选)
│   ├── config/                 # 配置层
│   │   ├── settings.py         # 全局配置
│   │   └── loader.py           # 配置加载
│   ├── logging/                # 日志系统
│   │   └── logger.py           # 日志配置
│   └── cli/                    # CLI入口
│       └── commands.py          # 命令行
├── config/                     # 配置文件
│   └── config.yaml             # 主配置文件
├── data/                       # 数据目录
│   └── stock_explorer.db        # SQLite数据库
├── logs/                       # 日志目录
├── tests/                      # 测试
├── docs/                       # 文档
├── pyproject.toml              # uv配置
└── uv.lock
```

### 2.2 核心组件

#### 2.2.1 数据层

**DataFetcher**
- **职责**: 从akshare获取实时和历史股票数据
- **能力**:
  - 实时行情获取 (`fetch_realtime_quotes`)
  - 历史K线数据获取 (`fetch_historical_kline`)
  - 资金流向数据获取 (`fetch_individual_fund_flow`)
  - 龙虎榜数据获取 (`fetch_lhb_detail`)
  - 融资融券数据获取 (`fetch_margin_detail`)
  - 股东增减持数据获取 (`fetch_holder_trade`)
  - 指数成分股获取 (`fetch_hs300_constituents`)
  - 行业分类数据获取 (`fetch_industry_classification`)

**DataCache**
- **职责**: 管理数据缓存策略
- **能力**:
  - LRU内存缓存
  - Redis持久化缓存
  - 缓存失效管理

**DataStorage**
- **职责**: 管理数据持久化
- **能力**:
  - SQLite存储 (K线数据、信号日志、告警记录)
  - Redis缓存 (实时数据、排行榜)

#### 2.2.2 信号检测层

**技术指标计算**
- **职责**: 计算各种技术指标
- **能力**:
  - 趋势指标: SMA, EMA, MACD, AROON
  - 动量指标: RSI, KDJ, CCI, WR
  - 波动率指标: BOLL, ATR
  - 成交量指标: OBV, VR

**信号检测器**
- **技术面检测器**:
  - `GoldenCrossDetector`: 金叉买入信号
  - `DeathCrossDetector`: 死叉卖出信号
  - `BreakoutDetector`: 突破信号
  - `RSIDetector`: RSI超买超卖信号
  - `VolumeSurgeDetector`: 成交量异动信号

- **财经信号检测器**:
  - `CapitalFlowDetector`: 资金流向信号
  - `DragonTigerDetector`: 龙虎榜信号
  - `MarginDetector`: 融资融券信号
  - `HolderTradeDetector`: 股东增减持信号
  - `SectorFlowDetector`: 板块资金流信号

- **舆情信号检测器**:
  - `LimitUpDetector`: 涨停板信号
  - `HighTurnoverDetector`: 换手率异常信号
  - `BigRiseDetector`: 大涨信号
  - `MarketBreadthDetector`: 市场情绪信号

**SignalRegistry**
- **职责**: 管理信号检测器的注册和获取
- **能力**:
  - 注册新的信号检测器
  - 根据名称获取信号检测器
  - 列出所有可用的信号检测器
  - 根据类型筛选信号检测器

#### 2.2.3 回测层

**BacktestEngine**
- **职责**: 执行历史数据回测
- **能力**:
  - 模拟交易执行
  - 持仓管理
  - 净值计算
  - 交易成本模拟

**PerformanceAnalyzer**
- **职责**: 分析回测绩效
- **能力**:
  - 总收益率计算
  - 年化收益率计算
  - 最大回撤计算
  - 夏普比率计算
  - 胜率计算
  - 盈亏比计算

#### 2.2.4 实时监控层

**RealtimeCollector**
- **职责**: 实时数据采集
- **能力**:
  - 定时从akshare获取实时行情
  - 回调函数管理

**MarketScanner**
- **职责**: 市场扫描 (三层扫描体系)
- **能力**:
  - 沪深300扫描 (5秒间隔)
  - 全市场扫描 (30秒间隔)
  - 行业板块扫描 (30秒间隔)

**Notifier**
- **职责**: 多渠道告警通知
- **能力**:
  - 控制台通知
  - 文件通知
  - 邮件通知
  - 钉钉机器人通知
  - 告警频率控制

#### 2.2.5 服务层

**ServiceManager**
- **职责**: 管理常驻服务
- **能力**:
  - 服务启动/停止
  - 任务调度管理
  - 配置热加载

**TaskScheduler**
- **职责**: 定时任务调度
- **能力**:
  - 秒级精度调度
  - 并发任务执行
  - 任务状态监控

**APIService**
- **职责**: 提供REST API接口
- **能力**:
  - 查询实时信号
  - 获取历史信号
  - 修改监控配置
  - 手动触发扫描
  - WebSocket实时推送

## 3. 系统交互流程

### 3.1 常驻服务模式流程
```
ServiceManager 启动
    ↓
加载配置 (config.yaml)
    ↓
初始化数据层组件 (DataFetcher, DataCache, DataStorage)
    ↓
初始化信号检测层组件 (SignalRegistry, 各检测器)
    ↓
初始化监控层组件 (RealtimeCollector, MarketScanner, Notifier)
    ↓
启动 TaskScheduler
    ├── 沪深300高频扫描任务 (每5秒)
    ├── 全市场扫描任务 (每30秒)
    ├── 行业板块扫描任务 (每30秒)
    └── 定时数据同步任务 (每分钟)
    ↓
MarketScanner 执行扫描
    ↓
信号检测组件执行信号检测
    ↓
生成信号 → 通知 Notifier
    ↓
Notifier 多渠道发送告警
    ↓
DataStorage 记录信号和告警
    ↓
持续运行...
```

### 3.2 回测模式流程
```
用户执行回测命令
    ↓
BacktestEngine 初始化
    ↓
DataFetcher 获取历史数据
    ↓
遍历每个交易日
    ↓
对每只股票执行信号检测
    ↓
根据信号执行交易模拟
    ↓
记录每日持仓和净值
    ↓
PerformanceAnalyzer 分析绩效
    ↓
生成回测报告
```

### 3.3 实时监控模式流程
```
启动实时采集器
    ↓
RealtimeCollector 获取实时行情
    ↓
MarketScanner 执行扫描
    ↓
信号检测组件执行信号检测
    ↓
触发信号 → 通知 Notifier
    ↓
Notifier 发送告警
    ↓
DataStorage 记录信号日志
    ↓
等待下一个采集周期
```

## 4. 系统能力与特性

### 4.1 信号检测能力

#### 4.1.1 技术面信号
- **均线策略**: 金叉/死叉、均线排列
- **突破策略**: N日新高/新低、通道突破
- **超买超卖**: RSI超买超卖、KDJ超买超卖、布林带触及
- **成交量策略**: 放量异动、价量背离、OBV突破

#### 4.1.2 财经信号
- **资金流向**: 主力净流入/净流出
- **龙虎榜**: 机构买入/卖出、知名游资席位
- **融资融券**: 融资余额变化、融券余量变化
- **股东增减持**: 股东增持/减持、高管增持
- **板块资金流**: 行业主力净流入TOP、概念板块资金流向

#### 4.1.3 舆情信号
- **涨跌停**: 涨停板、跌停板、首次涨停、N连板
- **异动**: 换手率异常、量比异动、振幅异常、成交额突增
- **价格异动**: 大涨、大跌、大幅跳空缺口
- **市场情绪**: 市场涨跌幅分布、板块轮动、热点板块

### 4.2 回测能力
- **支持周期**: 1分钟、5分钟、15分钟、日线、周线、月线
- **绩效指标**: 总收益率、年化收益率、最大回撤、夏普比率、胜率、盈亏比
- **交易成本**: 支持手续费模拟

### 4.3 实时监控能力
- **三层扫描**: 沪深300(5秒)、全市场(30秒)、行业板块(30秒)
- **多渠道通知**: 控制台、文件、邮件、钉钉机器人
- **告警过滤**: 信号强度过滤、市值过滤、ST股票过滤
- **频率控制**: 同一股票信号60秒内不重复告警

### 4.4 API服务能力
- **REST API**: 查询信号、触发扫描、修改配置
- **WebSocket**: 实时信号推送
- **服务管理**: 启动/停止/重启服务、查看状态、查看日志

## 5. 系统配置与使用

### 5.1 配置文件结构
```yaml
# 扫描配置
scan:
  hs300:            # 沪深300扫描
    enabled: true
    interval: 5     # 扫描间隔(秒)
    strategies:     # 启用的策略
      - golden_cross
      - capital_flow
      - limit_up
  market:           # 全市场扫描
    enabled: true
    interval: 30    # 扫描间隔(秒)
    strategies:     # 启用的策略
      - limit_up
      - volume_surge
      - high_turnover
  industry:         # 行业板块扫描
    enabled: true
    interval: 30    # 扫描间隔(秒)
    industries:     # 监控的行业
      - 银行
      - 证券
      - 科技
      - 医药

# Redis配置
redis:
  enabled: true
  host: "localhost"
  port: 6379
  password: ""
  db: 0
  realtime_ttl: 10      # 实时数据缓存时间(秒)
  hs300_cache_ttl: 60   # HS300数据缓存时间(秒)

# SQLite配置
sqlite:
  enabled: true
  path: "data/stock_explorer.db"

# 告警配置
alert:
  console: true          # 控制台通知
  file: true             # 文件通知
  file_path: "logs/signals.log"
  email:                 # 邮件通知
    enabled: false
    smtp_host: "smtp.example.com"
    smtp_port: 465
    smtp_user: "user@example.com"
    smtp_password: "your_password"
    from_addr: "stockbot@example.com"
    to_addrs:
      - "receiver1@example.com"
  dingtalk:              # 钉钉通知
    enabled: false
    webhook_url: "https://oapi.dingtalk.com/robot/send?access_token=xxx"
    secret: ""           # 钉钉密钥(可选)
  min_strength: "medium"  # 最小信号强度(low/medium/high)
  exclude_st: true       # 排除ST股票
  min_market_cap: 10000000000  # 最小市值(100亿)
  rate_limit_seconds: 60  # 通知频率限制(秒)

# API配置
api:
  enabled: false         # 是否启用API服务
  host: "0.0.0.0"       # API服务主机
  port: 8000            # API服务端口
```

### 5.2 命令行使用

#### 5.2.1 启动常驻服务
```bash
# 启动信号检测守护进程
stock-explorer daemon start

# 启动API服务
stock-explorer api start
```

#### 5.2.2 信号扫描
```bash
# 扫描HS300成分股
stock-explorer monitor hs300

# 扫描全市场
stock-explorer monitor all

# 扫描行业板块
stock-explorer monitor industry
```

#### 5.2.3 数据获取
```bash
# 获取HS300成分股
stock-explorer data hs300

# 获取行业数据
stock-explorer data industry
```

#### 5.2.4 策略管理
```bash
# 列出所有信号检测策略
stock-explorer strategies list

# 查看信号列表
stock-explorer signals list
```

#### 5.2.5 回测功能
```bash
# 执行回测
stock-explorer backtest --symbols 000001,000002 --start 2023-01-01 --end 2023-12-31
```

### 5.3 Python API使用
```python
from stock_explorer.backtest.engine import BacktestEngine
from stock_explorer.backtest.analyzer import PerformanceAnalyzer
from stock_explorer.monitor.scanner import MarketScanner
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
scanner = MarketScanner(Settings())
signals = scanner.scan_hs300()
for signal in signals:
    print(signal)
```

## 6. 系统集成

### 6.1 数据源集成
- **akshare**: 提供丰富的股票、基金、指数、期权等数据接口
- **akquant**: 高性能量化回测框架，以Rust铸造极速撮合内核

### 6.2 存储系统集成
- **SQLite**: 存储历史K线数据、信号日志、告警记录
- **Redis**: 缓存实时数据、排行榜、信号计数器

### 6.3 通知系统集成
- **控制台**: 实时输出信号
- **文件**: 记录信号到日志文件
- **邮件**: 通过SMTP发送告警邮件
- **钉钉**: 通过Webhook发送钉钉消息

### 6.4 服务系统集成
- **系统服务**: 支持安装为Linux/macOS系统服务
- **后台运行**: 支持后台 daemon 模式运行
- **配置热加载**: 支持运行时重新加载配置

## 7. 性能优化

### 7.1 数据获取优化
- **批量获取**: 批量获取股票数据，减少API调用
- **缓存策略**: 合理设置缓存过期时间，减少重复请求
- **并行处理**: 并行执行数据获取和信号检测

### 7.2 扫描策略优化
- **分层扫描**: 沪深300高频扫描与全市场扫描分开执行
- **信号过滤**: 预先过滤不符合条件的股票
- **增量更新**: 只处理变化的数据

### 7.3 资源管理
- **连接池**: 使用连接池管理数据库连接
- **内存控制**: 合理控制内存使用，避免内存溢出
- **错误处理**: 完善的错误处理机制，确保系统稳定运行

## 8. 扩展性

### 8.1 信号检测器扩展
- **自定义检测器**: 继承 `SignalDetector` 类，实现 `detect` 方法
- **注册机制**: 在 `SignalRegistry` 中注册新的检测器

### 8.2 数据源扩展
- **支持新数据源**: 实现新的数据获取接口
- **数据格式适配**: 统一数据格式，便于不同数据源集成

### 8.3 通知渠道扩展
- **新通知渠道**: 实现 `AlertChannelBase` 接口，添加新的通知渠道
- **消息格式定制**: 自定义不同渠道的消息格式

### 8.4 回测策略扩展
- **自定义策略**: 实现新的回测策略
- **绩效指标扩展**: 添加新的绩效分析指标

## 9. 安全与可靠性

### 9.1 数据安全
- **敏感信息保护**: 配置文件中的敏感信息加密存储
- **API调用限制**: 合理控制API调用频率，避免被封

### 9.2 系统可靠性
- **容错机制**: 完善的错误处理和重试机制
- **监控告警**: 系统自身的运行状态监控
- **日志记录**: 详细的日志记录，便于问题排查

### 9.3 风险提示
- **免责声明**: 本系统仅供学习研究，不构成投资建议
- **回测局限性**: 回测结果不代表未来收益
- **实际交易风险**: 实际交易需谨慎，注意风险控制

## 10. 代码质量与编码规范

### 10.1 强制编码规则

#### 10.1.1 代码风格
- **代码格式化**: 使用 ruff 进行代码格式化和检查
- **行长度限制**: 每行代码不超过 100 个字符
- **Python 版本**: 代码必须兼容 Python 3.12+
- **类型注解**: 关键函数和方法必须添加类型注解

#### 10.1.2 静态分析
- **语法检查**: 必须通过 ruff 语法检查
- **类型检查**: 必须通过 mypy 类型检查
- **代码质量**: 必须通过 ruff 代码质量检查

#### 10.1.3 测试要求
- **测试覆盖率**: 新代码必须有对应的单元测试
- **覆盖率目标**: 核心模块测试覆盖率不低于 80%
- **测试执行**: 所有测试必须通过才能提交代码

### 10.2 代码质量工具

#### 10.2.1 代码检查
```bash
# 检查代码语法
uv run ruff check src

# 检查测试文件语法
uv run ruff check tests

# 自动修复语法问题
uv run ruff check src --fix
uv run ruff check tests --fix

# 类型检查
uv run mypy src
```

#### 10.2.2 测试执行
```bash
# 运行所有测试
uv run pytest

# 运行特定模块测试
uv run pytest tests/test_signal.py

# 运行带覆盖率
uv run pytest --cov=src/stock_explorer

# 运行带覆盖率报告
uv run pytest --cov=src/stock_explorer --cov-report=html
```

### 10.3 提交规范
- **代码提交前**: 必须运行所有测试并通过
- **提交信息**: 提交信息必须清晰描述更改内容
- **代码审查**: 重要更改必须经过代码审查

## 11. 总结

本智能系统通过模块化的架构设计，实现了A股市场的实时信号检测和历史数据回测功能。系统采用多层架构，包括数据层、信号检测层、回测层、实时监控层和服务层，各组件之间职责明确，协作高效。

系统支持多种技术指标信号、财经信号和舆情信号的检测，提供多渠道的告警通知，并支持完整的回测分析功能。通过合理的配置和优化，系统能够高效处理实时数据，及时发现市场机会，并通过多渠道通知用户。

未来，系统可以通过扩展新的信号检测器、数据源和通知渠道，进一步提升其功能和性能，为量化投资提供更强大的工具支持。
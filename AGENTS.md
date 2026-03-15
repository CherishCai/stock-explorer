# 股票信号检测与回测系统

## 1. 系统概述

### 1.1 核心定位
本系统是一个兼具**实时信号检测**和**历史数据回测**能力的股票量化投资系统，支持多策略信号检测、完整回测分析和实时监控告警。

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
│   ├── signal/                 # 信号检测层
│   ├── backtest/               # 回测层
│   ├── monitor/                # 实时监控层
│   ├── service/                # 常驻服务层
│   ├── config/                 # 配置层
│   ├── logging/                # 日志系统
│   └── cli/                    # CLI入口
├── config/                     # 配置文件
├── data/                       # 数据目录
├── logs/                       # 日志目录
├── tests/                      # 测试
├── docs/                       # 文档
├── pyproject.toml              # uv配置
└── uv.lock
```

### 2.2 核心组件

#### 2.2.1 数据层
- **DataFetcher**: 从akshare获取实时和历史股票数据
- **DataCache**: 管理数据缓存策略
- **DataStorage**: 管理数据持久化

#### 2.2.2 信号检测层
- **技术指标计算**: 计算各种技术指标
- **信号检测器**: 技术面、财经、舆情信号检测
- **SignalRegistry**: 管理信号检测器的注册和获取

#### 2.2.3 回测层
- **BacktestEngine**: 执行历史数据回测
- **PerformanceAnalyzer**: 分析回测绩效

#### 2.2.4 实时监控层
- **RealtimeCollector**: 实时数据采集
- **MarketScanner**: 市场扫描（三层扫描体系）
- **Notifier**: 多渠道告警通知

#### 2.2.5 服务层
- **ServiceManager**: 管理常驻服务
- **TaskScheduler**: 定时任务调度
- **APIService**: 提供REST API接口

## 3. 系统能力

### 3.1 信号检测能力
- **技术面信号**: 均线策略、突破策略、超买超卖、成交量策略
- **财经信号**: 资金流向、龙虎榜、融资融券、股东增减持、板块资金流
- **舆情信号**: 涨跌停、异动、价格异动、市场情绪

### 3.2 回测能力
- **支持周期**: 1分钟、5分钟、15分钟、日线、周线、月线
- **绩效指标**: 总收益率、年化收益率、最大回撤、夏普比率、胜率、盈亏比
- **交易成本**: 支持手续费模拟

### 3.3 实时监控能力
- **三层扫描**: 沪深300(5秒)、全市场(30秒)、行业板块(30秒)
- **多渠道通知**: 控制台、文件、邮件、钉钉机器人
- **告警过滤**: 信号强度过滤、市值过滤、ST股票过滤
- **频率控制**: 同一股票信号60秒内不重复告警

## 4. 系统使用

### 4.1 命令行使用
- **启动服务**: `stock-explorer daemon start`
- **信号扫描**: `stock-explorer monitor hs300|all|industry`
- **数据获取**: `stock-explorer data hs300|industry`
- **策略管理**: `stock-explorer strategies list`
- **回测功能**: `stock-explorer backtest --symbols 000001,000002 --start 2023-01-01 --end 2023-12-31`

### 4.2 Python API使用
```python
from stock_explorer.backtest.engine import BacktestEngine
from stock_explorer.monitor.scanner import MarketScanner

# 回测示例
engine = BacktestEngine(initial_capital=1000000)
result = engine.run(
    symbols=["000001", "600000"],
    start_date="2023-01-01",
    end_date="2023-12-31",
)

# 实时扫描示例
from stock_explorer.config.settings import Settings
scanner = MarketScanner(Settings())
signals = scanner.scan_hs300()
```

## 5. 代码质量与自动化测试

### 5.1 自动化检查流程
- **语法检查**: ruff 语法检查
- **类型检查**: mypy 类型检查
- **代码质量**: ruff 代码质量检查
- **测试执行**: 自动运行所有测试
- **覆盖率检查**: 确保核心模块测试覆盖率不低于 80%

### 5.2 自动化工具配置
- **pre-commit**: 代码提交前自动检查
- **CI/CD**: GitHub Actions 自动测试和代码质量检查

## 6. 总结

本系统通过模块化的架构设计，实现了股票市场的实时信号检测和历史数据回测功能。系统采用多层架构，各组件之间职责明确，协作高效。

系统支持多种技术指标信号、财经信号和舆情信号的检测，提供多渠道的告警通知，并支持完整的回测分析功能。通过合理的配置和优化，系统能够高效处理实时数据，及时发现市场机会，并通过多渠道通知用户。
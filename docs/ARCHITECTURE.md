# A股市场实时检测投资信号系统 - 架构规划

## 1. 系统概述

### 1.1 目标
构建一个兼具**实时信号检测**和**历史数据回测**能力的A股量化投资系统，支持多策略信号检测、完整回测分析和实时监控告警。

### 1.2 技术栈要求
- **包管理**: uv (必须)
- **数据源**: akshare + akquant (必须)
- **Python版本**: >=3.12

akshare：主要用户获取股票数据（历史与实时），提供丰富的股票、基金、指数、期权等数据接口。

akquant 重磅推荐：AKQuant 是一款专为 量化投研 (Quantitative Research) 打造的高性能量化回测框架。它以 Rust 铸造极速撮合内核， 以 Python 链接数据与 AI 生态，旨在为量化投资者提供可靠高效的量化投研解决方案。参见[AKQuant](https://github.com/akfamily/akquant)

---

## 2. 系统架构

```
stock-explorer/
├── src/stock_explorer/
│   ├── data/                   # 数据层
│   │   ├── fetcher.py          # 数据抓取 (akshare)
│   │   ├── cache.py            # 内存/Redis缓存
│   │   └── storage.py          # 持久化存储 (SQLite)
│   │
│   ├── signal/                 # 信号检测层
│   │   ├── base.py             # 信号基类 & 协议
│   │   ├── indicators.py       # 技术指标计算
│   │   ├── detectors.py        # 技术面检测器
│   │   ├── detectors_fundamental.py  # 财经信号检测器
│   │   ├── detectors_sentiment.py   # 舆情信号检测器
│   │   └── registry.py         # 信号注册表
│   │
│   ├── backtest/               # 回测层 (akquant)
│   │   ├── engine.py           # 回测引擎 (akquant)
│   │   ├── context.py          # 回测上下文 (akquant)
│   │   └── analyzer.py         # 绩效分析 (akquant)
│   │
│   ├── monitor/                # 实时监控层
│   │   ├── collector.py        # 实时数据采集
│   │   ├── scanner.py          # 市场扫描 (三层扫描)
│   │   └── notifier.py         # 告警通知
│   │
│   ├── service/                # 常驻服务层
│   │   ├── manager.py          # 服务管理器
│   │   ├── scheduler.py        # 任务调度器
│   │   └── api.py              # REST API (可选)
│   │
│   ├── config/                 # 配置层
│   │   ├── settings.py         # 全局配置
│   │   └── loader.py           # 配置加载器
│   │
│   ├── logging/                # 日志系统
│   │   └── logger.py           # 日志配置
│   │
│   └── cli/                    # CLI入口
│       └── commands.py          # 命令行
│
├── config/                     # 配置文件
│   └── config.yaml             # 主配置文件
│
├── data/                       # 数据目录
│   └── stock_explorer.db        # SQLite数据库
│
├── logs/                       # 日志目录
│
├── tests/                      # 测试
├── docs/                       # 文档
├── pyproject.toml              # uv配置
└── uv.lock
```

---

## 3. 核心模块设计

### 3.1 数据层 (data/)

**fetcher.py** - 数据获取 (akshare 全覆盖)
```python
# 核心功能
class DataFetcher:
    # ==================== 实时行情 ====================
    - fetch_realtime_quotes() -> DataFrame      # 全部A股实时行情
    - fetch_realtime_limit() -> DataFrame        # 涨跌停股票列表

    # ==================== 历史K线 ====================
    - fetch_historical_kline(symbol, start, end, period) -> DataFrame
    - fetch_minute_kline(symbol, start, end, period) -> DataFrame

    # ==================== 资金流向 ====================
    - fetch_individual_fund_flow(symbol, market) -> DataFrame
    - fetch_sector_fund_flow() -> DataFrame

    # ==================== 龙虎榜 ====================
    - fetch_lhb_detail(date) -> DataFrame
    - fetch_lhb_summary(date) -> DataFrame
    - fetch_lhb_institution(date) -> DataFrame

    # ==================== 融资融券 ====================
    - fetch_margin_detail(date) -> DataFrame
    - fetch_margin_stock(symbol) -> DataFrame

    # ==================== 股东增减持 ====================
    - fetch_holder_trade(symbol) -> DataFrame

    # ==================== 订单簿 ====================
    - fetch_bid_ask(symbol) -> DataFrame

    # ==================== 个股信息 ====================
    - fetch_stock_info(symbol) -> Dict
    - fetch_stock_fina_indicator(symbol) -> DataFrame

    # ==================== 指数成分股 (沪深300) ====================
    # 沪深300成分股 (akshare)
    - fetch_hs300_constituents() -> DataFrame
        # 获取沪深300指数成分股
        # akshare: stock_zh_index_cons_csindex(symbol="000300")
        # 返回: 代码、名称、权重、进入时间

    # ==================== 行业分类 ====================
    # 行业板块行情 (akshare)
    - fetch_industry_classification() -> DataFrame
        # 行业分类 (证监会分类)
        # 银行/证券/房地产/医药/电子等

    - fetch_industry_spot() -> DataFrame
        # 行业板块实时行情
        # 涨跌幅、换手率、资金流向

    - fetch_industry_hist(industry, start, end) -> DataFrame
        # 行业指数历史数据

    # ==================== 概念板块 ====================
    - fetch_concept_spot() -> DataFrame
        # 概念板块实时行情
        # 人工智能/新能源/半导体等

    # ==================== 大盘指数 ====================
    - fetch_index_spot() -> DataFrame
        # 大盘指数实时行情 (上证/深证/创业板/科创板)

    # ==================== 全市场股票列表 ====================
    - fetch_stock_list() -> DataFrame
        # 获取全部A股列表
        # 代码、名称、上市时间、市值
```

**cache.py** - 缓存策略
```python
# LRU内存缓存 + 持久化
class DataCache:
    - get(key: str) -> Optional[Any]
    - set(key: str, value: Any, ttl: int)
    - invalidate(pattern: str)
```

**storage.py** - 数据持久化 (SQLite + Redis)
```python
# SQLite: 历史K线、信号日志、告警记录、配置存储
# Redis: 缓存、实时数据、排行榜

# ==================== SQLite 表设计 ====================
class DataStorage:
    # K线数据表
    """
    CREATE TABLE kline_data (
        id INTEGER PRIMARY KEY,
        symbol TEXT NOT NULL,
        date TEXT NOT NULL,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume REAL,
        amount REAL,
        period TEXT,  -- daily/weekly/monthly/1min/5min/15min/30min/60min
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(symbol, date, period)
    )
    """

    # 信号记录表
    """
    CREATE TABLE signals (
        id INTEGER PRIMARY KEY,
        timestamp TIMESTAMP NOT NULL,
        symbol TEXT NOT NULL,
        name TEXT NOT NULL,
        signal_type TEXT NOT NULL,  -- technical/fundamental/sentiment
        direction TEXT NOT NULL,    -- buy/sell
        strength TEXT,              -- strong/medium/weak
        price REAL,
        message TEXT,
        metadata TEXT,  -- JSON
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """

    # 告警记录表
    """
    CREATE TABLE alerts (
        id INTEGER PRIMARY KEY,
        signal_id INTEGER,
        timestamp TIMESTAMP NOT NULL,
        channel TEXT NOT NULL,  -- console/file/email/dingtalk
        status TEXT NOT NULL,  -- sent/failed
        message TEXT,
        response TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(signal_id) REFERENCES signals(id)
    )
    """

    # 监控配置表
    """
    CREATE TABLE watchlist (
        id INTEGER PRIMARY KEY,
        symbol TEXT NOT NULL,
        name TEXT,
        category TEXT,  -- hs300/industry/custom
        enabled BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """

    # ==================== Redis 设计 ====================
    """
    Redis 键设计:
    - realtime:{symbol}        # 实时行情 (TTL: 10s)
    - hs300:list              # 沪深300成分股列表
    - industry:{name}:stocks  # 行业成分股
    - signal:counter:{name}   # 信号计数 (日期/总数)
    - alert:queue             # 告警队列
    - cache:quote:{symbol}    # 行情缓存 (TTL: 5s)
    - cache:hs300:quote       # 沪深300行情缓存 (TTL: 5s)
    """

    # ==================== 接口定义 ====================
    class DataStorage:
        # SQLite 操作
        - save_kline(df: DataFrame, symbol: str, period: str)
        - get_kline(symbol: str, start: date, end: date, period: str) -> DataFrame
        - save_signals(signals: list[Signal])
        - get_signals(start: date, end: date, filters: dict) -> DataFrame
        - save_alert(alert: Alert)
        - get_alerts(start: date, end: date, channel: str) -> DataFrame
        - save_watchlist(symbols: list[WatchItem])
        - get_watchlist(category: str) -> list[WatchItem]

        # Redis 操作
        - cache_realtime(data: dict, ttl: int = 10)
        - get_cached_realtime(symbol: str) -> Optional[dict]
        - cache_hs300_list(symbols: list[str])
        - get_hs300_list() -> list[str]
        - increment_signal_counter(name: str) -> int
        - get_signal_counter(name: str, date: str) -> int
        - push_alert_queue(alert: Alert)
        - pop_alert_queue() -> Optional[Alert]


# ==================== 时序数据库预留 ====================
# 可扩展支持 InfluxDB/TimescaleDB (可选)
"""
未来可扩展:
- stock_metrics:{symbol}     # 个股指标时序数据
- market_metrics             # 大盘指标时序
- signal_metrics             # 信号触发时序
"""
```

### 3.2 信号检测层 (signal/)

信号类型分为 **技术面信号** 和 **财经信号** 两大类：

#### A. 技术面信号 (基于K线/指标)

**indicators.py** - 技术指标
```python
# 趋势指标
- SMA(series, period)              # 简单移动平均
- EMA(series, period)              # 指数移动平均
- MACD(series, fast, slow, signal) # MACD指标
- AROON(series, period)            # 阿隆指标

# 动量指标
- RSI(series, period)              # 相对强弱指标
- KDJ(high, low, close)            # KDJ随机指标
- CCI(high, low, close, period)    # 商品通道指标
- WR(high, low, close, period)    # 威廉指标

# 波动率指标
- BOLL(series, period, std_dev)   # 布林带
- ATR(high, low, close, period)   # 平均真实波幅

# 成交量指标
- OBV(close, volume)               # 能量潮
- VR(close, volume, period)        # 成交量变异率
```

**detectors.py** - 技术面检测器
```python
# 1. 均线策略
class GoldenCrossDetector:     # 金叉买入 (MA5上穿MA20)
class DeathCrossDetector:      # 死叉卖出 (MA5下穿MA20)
class MaDirectionDetector:     # 均线多头/空头排列

# 2. 突破策略
class BreakoutDetector:        # N日新高/新低突破
class ChannelBreakoutDetector:  # 通道突破 (布林带/ATR通道)

# 3. 超买超卖
class RSIDetector:              # RSI超买(>70)/超卖(<30)
class KDJDetector:              # KDJ超买/超卖/J值反转
class BollingerBounceDetector: # 布林带触及上轨/下轨

# 4. 成交量策略
class VolumeSurgeDetector:      # 放量异动 (量能放大N倍)
class VolumePriceDivergence:    # 价量背离
class OBVBreakoutDetector:      # OBV创N日新高/新低
```

#### B. 财经信号 (基于市场/资金/舆情)

**detectors_fundamental.py** - 财经信号检测器

```python
# 1. 资金流向信号 (stock_individual_fund_flow)
class CapitalFlowDetector:
    # 主力净流入/净流出 (>0为流入)
    # 超大单、大单、中单、小单净流入
    # 5日/10日/20日主力净流入累计

# 2. 龙虎榜信号 (stock_lhb_stock_em)
class DragonTigerDetector:
    # 机构买入/卖出金额
    # 知名游资席位追踪
    # 买入占比 > 30%
    # 首次上榜/再次上榜

# 3. 融资融券信号 (stock_margin_detail)
class MarginDetector:
    # 融资余额大幅增加 (>20%)
    # 融券余量变化
    # 融资买入额突增

# 4. 股东增减持信号 (stock_holder_trade)
class HolderTradeDetector:
    # 股东增持 (>100万股)
    # 股东减持 (>100万股)
    # 高管增持

# 5. 板块资金流信号 (stock_sector_fund_flow_rank)
class SectorFlowDetector:
    # 行业主力净流入TOP
    # 概念板块资金流向
    # 板块资金持续流入天数

# 6. 订单簿信号 (stock_bid_ask_em)
class OrderBookDetector:
    # 委比 (买卖委托量比)
    # 大单挂单异动
    # 主动买入/卖出力量对比
```

#### C. 舆情/消息面信号

**detectors_sentiment.py** - 舆情信号检测器

```python
# 1. 涨跌停信号
class LimitUpDetector:          # 涨停板检测
class LimitDownDetector:       # 跌停板检测
class FirstLimitUpDetector:    # 首次涨停
class NDaysLimitUpDetector:    # N连板

# 2. 异动信号
class HighTurnoverDetector:     # 换手率异常 (>30%)
class BigVolumeRatioDetector:   # 量比异动 (>3.0)
class BigAmplitudeDetector:     # 振幅异常 (>15%)
class BigTurnoverDetector:      # 成交额突增

# 3. 价格异动
class BigRiseDetector:          # 大涨 (>7%)
class BigDropDetector:          # 大跌 (>-7%)
class BigOpenGapDetector:       # 大幅跳空缺口

# 4. 市场情绪信号
class MarketBreadthDetector:   # 市场涨跌幅分布
class SectorRotationDetector:  # 板块轮动检测
class HotSectorDetector:       # 热点板块检测
```

#### D. 信号组合与评分

```python
# 信号组合器
class SignalCombiner:
    # 多信号组合 (AND/OR逻辑)
    # 信号加权评分
    # 信号强度分级 (强/中/弱)

# 信号协议定义
class SignalDetector(Protocol):
    name: str
    signal_type: SignalType  # technical/fundamental/sentiment

    def detect(self, data: dict) -> Optional[Signal]:
        ...

class SignalType(Enum):
    TECHNICAL = "technical"           # 技术面
    CAPITAL_FLOW = "capital_flow"     # 资金流
    MARGIN = "margin"                 # 融资融券
    HOLDER = "holder"                 # 股东增减持
    SECTOR = "sector"                # 板块资金
    SENTIMENT = "sentiment"          # 市场情绪
    NEWS = "news"                    # 消息面
```

#### E. 信号注册表

**registry.py** - 信号注册
```python
class SignalRegistry:
    - register(name: str, detector: SignalDetector)
    - get(name: str) -> SignalDetector
    - list_all() -> list[str]
    - list_by_type(type: SignalType) -> list[str]
```

### 3.3 回测层 (backtest/)

**engine.py** - 回测引擎
```python
class BacktestEngine:
    def __init__(self, initial_capital: float, commission: float = 0.0003):
        - self.positions = {}
        - self.cash = initial_capital

    def run(
        self,
        symbols: list[str],
        detectors: dict[str, SignalDetector],
        start_date: date,
        end_date: date,
        period: str = "daily"
    ) -> BacktestResult:
        # 遍历历史数据
        # 执行信号检测
        # 模拟交易 (买入/卖出)
        # 记录每日净值

    def execute_signal(self, signal: Signal, price: float):
        # 买入: 检查现金 -> 更新持仓 -> 扣除手续费
        # 卖出: 检查持仓 -> 更新持仓 -> 扣除手续费
```

**analyzer.py** - 绩效分析
```python
class PerformanceAnalyzer:
    def analyze(self, result: BacktestResult) -> PerformanceMetrics:
        - total_return: float
        - annual_return: float
        - max_drawdown: float
        - sharpe_ratio: float
        - win_rate: float
        - profit_factor: float
        - trade_count: int
```

### 3.4 实时监控层 (monitor/)

**collector.py** - 数据采集
```python
class RealtimeCollector:
    def __init__(self, fetch_interval: int = 3):
        - start()
        - stop()
        - add_callback(callback: Callable[[DataFrame], None])

    # 定时从akshare获取实时行情
    # 调用注册的callback
```

**scanner.py** - 市场扫描 (三层扫描体系)
```python
class MarketScanner:
    """
    三层扫描体系:
    1. 沪深300层 (重点监控)
    2. 全市场层 (5000+股票)
    3. 行业板块层 (独立涨跌信号)
    """

    def __init__(self, detectors: dict[str, SignalDetector]):
        # 扫描模式:
        # 1. 沪深300扫描 (重点)
        # 2. 全市场扫描
        # 3. 行业板块扫描 (独立信号)

    # ==================== 沪深300扫描 (重点) ====================
    def get_hs300_symbols() -> list[str]:
        # 获取沪深300成分股列表
        # akshare: stock_zh_index_cons_csindex(symbol="000300")

    def scan_hs300(self) -> list[Signal]:
        """
        沪深300扫描 (重点关注)
        - 所有沪深300成分股实时监控
        - 更高的扫描频率 (3-5秒)
        - 独立告警通道
        """

    # ==================== 全市场扫描 ====================
    def scan_all(self) -> list[Signal]:
        """
        全市场扫描 (5000+股票)
        - 覆盖沪深京A股
        - 定时全量扫描 (30秒-1分钟)
        """

    # ==================== 行业板块扫描 ====================
    def get_industry_classification() -> dict[str, list[str]]:
        # 获取行业分类: 银行、证券、科技、医药等

    def scan_industry(self, industry: str) -> IndustrySignal:
        """
        行业独立涨跌信号
        - 行业涨幅排行
        - 行业资金流向
        - 行业内个股涨跌分布
        - 行业轮动信号
        """

class IndustrySignal:
    industry_name: str           # 行业名称
    change_pct: float            # 行业涨跌幅
    rank: int                    # 今日行业排名
    up_count: int                # 上涨家数
    down_count: int              # 下跌家数
    main_flow: float             # 主力净流入
    signals: list[Signal]        # 行业内的个股信号
    rotation_signal: RotationType  # 轮动信号 (进入/维持/退出)
```

**notifier.py** - 告警通知 (支持多渠道)
```python
from abc import ABC, abstractmethod
from enum import Enum
from pydantic import BaseModel

class AlertChannel(str, Enum):
    CONSOLE = "console"
    FILE = "file"
    EMAIL = "email"
    DINGTALK = "dingtalk"
    WEBHOOK = "webhook"

# ==================== 告警配置模型 ====================
class EmailConfig(BaseModel):
    enabled: bool = False
    smtp_host: str = "smtp.example.com"
    smtp_port: int = 465
    smtp_user: str
    smtp_password: str
    from_addr: str
    to_addrs: list[str]  # 多个收件人

class DingTalkConfig(BaseModel):
    enabled: bool = False
    webhook_url: str  # 钉钉机器人Webhook URL
    secret: str = ""  # 加签密钥 (可选)

class WebhookConfig(BaseModel):
    enabled: bool = False
    url: str
    headers: dict = {}  # 自定义请求头

class FileConfig(BaseModel):
    enabled: bool = True
    path: str = "logs/signals.log"

# ==================== 告警通道接口 ====================
class AlertChannelBase(ABC):
    @abstractmethod
    def send(self, message: str, signal: Signal) -> bool:
        """发送告警消息, 返回是否成功"""

    @abstractmethod
    def format_message(self, signal: Signal) -> str:
        """格式化告警消息"""

# ==================== 邮件告警 ====================
class EmailNotifier(AlertChannelBase):
    """
    邮件告警
    - 支持SMTP SSL/TLS
    - 支持HTML格式
    - 支持多个收件人
    """

    def __init__(self, config: EmailConfig):
        self.config = config

    def format_message(self, signal: Signal) -> str:
        return f"""
        <html>
        <body>
            <h2>股票信号告警</h2>
            <table>
                <tr><td><b>股票:</b></td><td>{signal.symbol} {signal.name}</td></tr>
                <tr><td><b>信号:</b></td><td>{signal.signal_type}</td></tr>
                <tr><td><b>方向:</b></td><td>{signal.direction}</td></tr>
                <tr><td><b>强度:</b></td><td>{signal.strength}</td></tr>
                <tr><td><b>价格:</b></td><td>{signal.price}</td></tr>
                <tr><td><b>时间:</b></td><td>{signal.timestamp}</td></tr>
            </table>
        </body>
        </html>
        """

    def send(self, message: str, signal: Signal) -> bool:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[股票信号] {signal.direction.upper()} - {signal.symbol}"
            msg['From'] = self.config.from_addr
            msg['To'] = ", ".join(self.config.to_addrs)

            html = self.format_message(signal)
            msg.attach(MIMEText(html, 'html', 'utf-8'))

            with smtplib.SMTP_SSL(
                self.config.smtp_host,
                self.config.smtp_port
            ) as server:
                server.login(self.config.smtp_user, self.config.smtp_password)
                server.sendmail(
                    self.config.from_addr,
                    self.config.to_addrs,
                    msg.as_string()
                )
            return True
        except Exception as e:
            print(f"Email send failed: {e}")
            return False

# ==================== 钉钉告警 ====================
class DingTalkNotifier(AlertChannelBase):
    """
    钉钉告警
    - 支持Webhook
    - 支持加签验证
    - 支持Markdown格式
    """

    def __init__(self, config: DingTalkConfig):
        self.config = config

    def format_message(self, signal: Signal) -> str:
        emoji = "🔔" if signal.direction == "buy" else "🔕"
        color = "red" if signal.direction == "buy" else "green"

        return f"""
{{
    "msgtype": "markdown",
    "markdown": {{
        "title": "股票信号告警",
        "text": "{emoji} **{signal.direction.upper()}信号**\\n\\n" +
               "> 股票: **{signal.symbol} {signal.name}**\\n\\n" +
               "> 信号: {signal.signal_type}\\n\\n" +
               "> 强度: {signal.strength}\\n\\n" +
               "> 价格: {signal.price}\\n\\n" +
               "> 时间: {signal.timestamp}"
    }}
}}
        """

    def send(self, message: str, signal: Signal) -> bool:
        import hmac
        import hashlib
        import base64
        import urllib.parse
        import time
        import requests

        try:
            timestamp = str(round(time.time() * 1000))
            secret_enc = self.config.secret.encode('utf-8')
            string_to_sign = f'{timestamp}\n{self.config.secret}'
            string_to_sign_enc = string_to_sign.encode('utf-8')
            hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
            sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))

            url = f"{self.config.webhook_url}&timestamp={timestamp}&sign={sign}"
            payload = self.format_message(signal)

            response = requests.post(url, data=payload.encode('utf-8'), headers={'Content-Type': 'application/json'})
            return response.json().get('errcode', 1) == 0
        except Exception as e:
            print(f"DingTalk send failed: {e}")
            return False

# ==================== 文件/控制台告警 ====================
class FileNotifier(AlertChannelBase):
    def __init__(self, config: FileConfig):
        self.config = config

    def format_message(self, signal: Signal) -> str:
        return f"[{signal.timestamp}] {signal.direction.upper()} - {signal.symbol} {signal.name} | {signal.signal_type} | {signal.strength}"

    def send(self, message: str, signal: Signal) -> bool:
        import os
        from pathlib import Path

        try:
            log_file = Path(self.config.path)
            log_file.parent.mkdir(parents=True, exist_ok=True)

            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(message + '\n')
            return True
        except Exception as e:
            print(f"File write failed: {e}")
            return False

class ConsoleNotifier(AlertChannelBase):
    def format_message(self, signal: Signal) -> str:
        from rich.console import Console
        from rich.table import Table

        table = Table(show_header=True)
        table.add_column("时间", style="cyan")
        table.add_column("方向", style="green" if signal.direction == "buy" else "red")
        table.add_column("股票", style="yellow")
        table.add_column("信号")
        table.add_column("强度")

        table.add_row(
            str(signal.timestamp),
            signal.direction.upper(),
            f"{signal.symbol} {signal.name}",
            signal.signal_type,
            signal.strength
        )

        console = Console()
        console.print(table)
        return ""

    def send(self, message: str, signal: Signal) -> bool:
        self.format_message(signal)
        return True

# ==================== 告警管理器 ====================
class NotifierManager:
    """
    告警管理器
    - 多通道并行发送
    - 失败重试机制
    - 告警频率控制 (防轰炸)
    """

    def __init__(self):
        self.channels: dict[AlertChannel, AlertChannelBase] = {}
        self.alert_history: dict[str, datetime] = {}  # 防止重复告警
        self.rate_limit_seconds: int = 60  # 同一股票60秒内不重复告警

    def register(self, channel: AlertChannel, notifier: AlertChannelBase):
        self.channels[channel] = notifier

    def notify(self, signal: Signal, channels: list[AlertChannel] = None):
        """发送告警到指定渠道"""

        # 检查频率限制
        if not self._check_rate_limit(signal):
            return

        if channels is None:
            channels = list(self.channels.keys())

        for channel in channels:
            if channel in self.channels:
                notifier = self.channels[channel]
                message = notifier.format_message(signal)
                success = notifier.send(message, signal)

                # 记录告警结果到数据库
                self._save_alert_record(signal, channel, success)

    def _check_rate_limit(self, signal: Signal) -> bool:
        """检查是否在频率限制内"""
        key = f"{signal.symbol}:{signal.signal_type}"
        now = datetime.now()

        if key in self.alert_history:
            last_alert = self.alert_history[key]
            if (now - last_alert).seconds < self.rate_limit_seconds:
                return False

        self.alert_history[key] = now
        return True

    def _save_alert_record(self, signal: Signal, channel: AlertChannel, success: bool):
        """保存告警记录到数据库"""
        pass  # 调用 storage.save_alert()
```

---

## 4. 核心数据流

### 4.1 CLI按次执行模式
```
用户执行命令
    ↓
单次数据获取
    ↓
单次信号检测
    ↓
输出结果
```

### 4.2 常驻服务模式 (重点)
```
服务启动
    ↓
加载配置 (监控列表、策略、告警规则)
    ↓
启动定时任务调度器
    ├── 沪深300高频扫描 (每5秒)
    ├── 全市场扫描 (每30秒)
    ├── 行业板块扫描 (每30秒)
    └── 定时数据同步 (每分钟)
    ↓
实时信号检测
    ↓
触发告警通知
    ↓
记录信号日志
    ↓
持续运行...
```

### 4.3 数据存储
```
用户配置
    ↓
加载历史数据 (akshare)
    ↓
遍历每个交易日
    ↓
对每只股票执行信号检测
    ↓
根据信号执行交易模拟
    ↓
记录每日持仓和净值
    ↓
生成绩效报告
```

### 4.4 实时监控模式
```
启动实时采集器 (定时任务)
    ↓
获取实时行情数据
    ↓
对持仓/自选股执行信号检测
    ↓
触发信号 → 告警通知
    ↓
记录信号日志
    ↓
等待下一个采集周期
```

---

## 5. CLI命令设计

```bash
# ==================== 回测命令 ====================
# 回测命令
stock-explorer backtest \
    --symbol 000001,600519 \
    --strategy golden_cross,rsi \
    --start 2023-01-01 \
    --end 2024-01-01 \
    --capital 100000

# ==================== 实时监控命令 ====================
# 沪深300重点监控 (推荐)
stock-explorer monitor hs300 \
    --strategy golden_cross,capital_flow \
    --interval 5

# 全市场扫描
stock-explorer monitor all \
    --strategy limit_up,volume_surge \
    --interval 30

# 行业板块监控
stock-explorer monitor industry \
    --industry 银行,证券,科技 \
    --strategy sector_rotation

# ==================== 数据获取命令 ====================
# 获取沪深300成分股
stock-explorer data hs300

# 获取行业列表
stock-explorer data industry

# 获取行业实时行情
stock-explorer data industry --name 银行

# 获取全市场股票列表
stock-explorer data stocks

# ==================== 信号查询命令 ====================
# 列出可用策略
stock-explorer strategies list

# 信号历史查询
stock-explorer signals --start 2024-01-01 --end 2024-03-01

# 沪深300信号查询
stock-explorer signals hs300 --today

# 行业信号查询
stock-explorer signals industry --name 银行
```

---

## 6. 常驻服务系统 (Daemon Service)

### 6.1 服务架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        StockExplorer Daemon                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐          │
│  │  Web UI     │   │   REST API   │   │  WebSocket  │          │
│  │  (可选)      │   │   (可选)      │   │  (实时推送)  │          │
│  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘          │
│         │                  │                  │                  │
│         └──────────────────┼──────────────────┘                  │
│                            │                                      │
│                    ┌───────▼───────┐                            │
│                    │   Service     │                            │
│                    │   Manager     │                            │
│                    └───────┬───────┘                            │
│                            │                                      │
│  ┌────────────────────────┼────────────────────────────────┐   │
│  │                  Task Scheduler                        │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────┐   │   │
│  │  │ HS300   │ │ Market  │ │Industry │ │Data Sync   │   │   │
│  │  │ Scanner │ │ Scanner │ │ Scanner │ │Scheduler   │   │   │
│  │  │  5s    │ │  30s    │ │  30s   │ │  60s      │   │   │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └──────┬────┘   │   │
│  └───────┼───────────┼───────────┼─────────────┼───────┘   │
│          │           │           │             │              │
│  ┌───────▼───────────▼───────────▼─────────────▼────────┐    │
│  │                  Signal Engine                      │    │
│  │   - Technical Analysis    - Fundamental Analysis    │    │
│  │   - Capital Flow          - Market Sentiment       │    │
│  └─────────────────────────────┬───────────────────────┘    │
│                                │                              │
│  ┌─────────────────────────────▼───────────────────────┐    │
│  │                  Notifier Service                   │    │
│  │   - Console       - File      - WebSocket          │    │
│  │   - Discord       -钉钉/微信 (扩展)                   │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────┐      │
│  │                  Data Storage (SQLite)              │      │
│  │   - K线数据   - 信号日志   - 告警记录   - 配置存储   │      │
│  └─────────────────────────────────────────────────────┘      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 服务组件

**service/manager.py** - 服务管理器
```python
class ServiceManager:
    """
    常驻服务管理器
    - 启动/停止服务
    - 任务调度
    - 配置热加载
    """

    def __init__(self, config_path: str):
        - self.scheduler = TaskScheduler()
        - self.data_fetcher = DataFetcher()
        - self.signal_engine = SignalEngine()
        - self.notifier = Notifier()

    def start(self):
        """启动服务"""
        - 加载配置文件
        - 初始化数据层
        - 启动定时任务
        - 注册信号处理器
        - 启动HTTP服务 (可选)

    def stop(self):
        """停止服务"""
        - 停止定时任务
        - 保存状态
        - 关闭连接

    def reload_config(self):
        """热重载配置"""
        - 重新加载监控列表
        - 调整扫描频率
```

**service/scheduler.py** - 任务调度器
```python
class TaskScheduler:
    """
    定时任务调度器
    - 支持秒级精度
    - 并发任务执行
    - 任务状态监控
    """

    def __init__(self):
        - self.tasks: dict[str, Task]

    def add_task(self, name: str, func: Callable, interval: int):
        """添加定时任务"""

    def start_all(self):
        """启动所有任务"""

    def stop_all(self):
        """停止所有任务"""

class Task:
    name: str
    func: Callable
    interval: int  # 秒
    last_run: datetime
    is_running: bool
```

**service/api.py** - REST API (可选)
```python
class APIService:
    """
    可选的REST API服务
    - 查询实时信号
    - 获取历史信号
    - 修改监控配置
    - 手动触发扫描
    """

    @app.get("/api/signals")
    def get_signals(limit: int = 100): ...

    @app.get("/api/hs300")
    def get_hs300_signals(): ...

    @app.get("/api/industry/{name}")
    def get_industry_signals(name: str): ...

    @app.post("/api/scan")
    def trigger_scan(mode: str): ...

    @app.websocket("/ws")
    async def websocket_signals(ws): ...  # 实时推送
```

**service/config.py** - 配置管理
```python
from pydantic import BaseModel
from typing import Optional

class ScanConfig(BaseModel):
    """扫描配置"""
    hs300_enabled: bool = True
    hs300_interval: int = 5
    hs300_strategies: list[str] = ["golden_cross", "capital_flow"]

    market_enabled: bool = True
    market_interval: int = 30
    market_strategies: list[str] = ["limit_up", "volume_surge"]

    industry_enabled: bool = True
    industry_interval: int = 30
    industries: list[str] = ["银行", "证券", "科技", "医药"]

class RedisConfig(BaseModel):
    """Redis配置"""
    enabled: bool = True
    host: str = "localhost"
    port: int = 6379
    password: Optional[str] = None
    db: int = 0

    # 缓存配置
    realtime_ttl: int = 10          # 实时行情缓存10秒
    hs300_cache_ttl: int = 60      # 沪深300列表缓存60秒
    quote_cache_ttl: int = 5       # 行情缓存5秒

class EmailConfig(BaseModel):
    """邮件告警配置"""
    enabled: bool = False
    smtp_host: str = "smtp.example.com"
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    from_addr: str = ""
    to_addrs: list[str] = []

class DingTalkConfig(BaseModel):
    """钉钉告警配置"""
    enabled: bool = False
    webhook_url: str = ""
    secret: str = ""

class AlertConfig(BaseModel):
    """告警配置"""
    console_enabled: bool = True
    file_enabled: bool = True
    file_path: str = "logs/signals.log"

    # 告警渠道
    email: EmailConfig = EmailConfig()
    dingtalk: DingTalkConfig = DingTalkConfig()

    # 告警过滤
    min_signal_strength: str = "medium"  # weak/medium/strong
    exclude_st: bool = True              # 排除ST股票
    min_market_cap: float = 10_000_000_000  # 最小市值100亿

    # 告警频率控制
    rate_limit_seconds: int = 60         # 同一股票信号60秒内不重复告警

class SQLiteConfig(BaseModel):
    """SQLite配置"""
    enabled: bool = True
    path: str = "data/stock_explorer.db"

    # 连接池
    pool_size: int = 5
    pool_timeout: int = 30

class AppConfig(BaseModel):
    """全局配置"""
    scan: ScanConfig
    redis: RedisConfig = RedisConfig()
    sqlite: SQLiteConfig = SQLiteConfig()
    alert: AlertConfig

    # 数据存储
    data_dir: str = "data"
    cache_ttl: int = 60

    # API服务 (可选)
    api_enabled: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 8000
```

### 6.3 配置文件 (config.yaml)

```yaml
# 沪深300扫描配置
scan:
  hs300:
    enabled: true
    interval: 5           # 5秒扫描一次
    strategies:
      - golden_cross
      - capital_flow
      - limit_up

  # 全市场扫描配置
  market:
    enabled: true
    interval: 30          # 30秒扫描一次
    strategies:
      - limit_up
      - volume_surge
      - high_turnover

  # 行业板块扫描配置
  industry:
    enabled: true
    interval: 30
    industries:
      - 银行
      - 证券
      - 房地产
      - 医药
      - 电子
      - 科技
      - 新能源

# Redis 配置
redis:
  enabled: true
  host: "localhost"
  port: 6379
  password: ""           # 如有密码
  db: 0

  # 缓存 TTL
  realtime_ttl: 10       # 实时行情缓存10秒
  hs300_cache_ttl: 60   # 沪深300列表缓存60秒

# SQLite 配置
sqlite:
  enabled: true
  path: "data/stock_explorer.db"

# 告警配置
alert:
  console: true
  file: true
  file_path: "logs/signals.log"

  # 邮件告警
  email:
    enabled: false
    smtp_host: "smtp.example.com"
    smtp_port: 465
    smtp_user: "user@example.com"
    smtp_password: "your_password"
    from_addr: "stockbot@example.com"
    to_addrs:
      - "receiver1@example.com"
      - "receiver2@example.com"

  # 钉钉告警
  dingtalk:
    enabled: false
    webhook_url: "https://oapi.dingtalk.com/robot/send?access_token=xxx"
    secret: ""            # 加签密钥 (可选)

  # 信号强度过滤
  min_strength: "medium"

  # 股票过滤
  exclude_st: true
  min_market_cap: 10000000000  # 100亿

  # 告警频率控制
  rate_limit_seconds: 60       # 同一股票60秒内不重复告警

# API 服务 (可选)
api:
  enabled: false
  host: "0.0.0.0"
  port: 8000
```

### 6.4 服务启动方式

```bash
# 前台运行
stock-explorer daemon start

# 后台运行
stock-explorer daemon start -d

# 停止服务
stock-explorer daemon stop

# 重启服务
stock-explorer daemon restart

# 查看状态
stock-explorer daemon status

# 查看日志
stock-explorer daemon logs

# 重新加载配置
stock-explorer daemon reload
```

### 6.5 系统服务化 (Linux/macOS)

```bash
# 安装为系统服务 (Linux systemd)
sudo stock-explorer daemon install

# 启动服务
sudo systemctl start stock-explorer

# 开机自启
sudo systemctl enable stock-explorer
```

---

## 7. pyproject.toml 依赖配置

```toml
[project]
name = "stock-explorer"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    # 数据源 (必须)
    "akquant>=0.1.60",
    "akshare>=1.18.35",

    # 核心依赖
    "pandas>=2.2.0",
    "numpy>=2.2.0",

    # 数据库
    "sqlalchemy>=2.0.36",
    "redis>=5.2.0",
    "aioredis>=2.0.1",

    # 告警通知
    "requests>=2.32.0",
    "aiohttp>=3.11.0",

    # CLI & UI
    "typer>=0.15.0",
    "rich>=13.9.0",
    "pydantic>=2.10.0",

    # 配置
    "pyyaml>=6.0.2",
    "toml>=0.10.2",

    # 工具
    "pyarrow>=18.0.0",
    "python-dotenv>=1.0.1",

    # 异步
    "asyncio>=3.4.3",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-cov>=6.0.0",
    "pytest-asyncio>=0.24.0",
    "pytest-timeout>=2.3.0",
    "ruff>=0.8.0",
    "mypy>=1.14.0",
    "pre-commit>=4.1.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

---

## 8. 注意事项

### 8.1 akquant 库
- pyproject.toml 中已配置 `akquant>=0.1.60`
- 需要确认该库的具体API用法
- 如果akquant主要用于实时推送，优先实现akshare实时行情作为主要数据源

### 8.2 数据源策略
- **实时数据**: akshare `stock_zh_a_spot_em()` (每3-5秒刷新)
- **历史数据**: akshare `stock_zh_a_hist()` (日线/分钟线)
- **akquant**: 作为实时推送的补充 (如果支持WebSocket)

### 8.3 性能考虑
- 实时扫描全市场(A股5000+只)需要优化
- 建议使用信号注册表 + 并行检测
- 历史数据建议本地缓存避免重复请求
- 沪深300高频扫描与全市场扫描分开执行

### 8.4 风险提示
- 本系统仅供学习研究，不构成投资建议
- 实际交易需谨慎
- 回测结果不代表未来收益

"""市场扫描模块 - 三层扫描体系"""

import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time
from typing import Any

from stock_explorer.data.cache import get_cache
from stock_explorer.data.fetcher import get_fetcher
from stock_explorer.logging.logger import get_logger
from stock_explorer.signal.base import Signal
from stock_explorer.signal.registry import SignalRegistry

logger = get_logger(__name__)


class MarketScanner:
    """市场扫描器 - 三层扫描体系

    功能特性:
    - 三层扫描：沪深300、全市场、行业板块
    - 并行处理：多线程并行扫描提高效率
    - 信号检测：支持多种技术指标信号
    - 数据缓存：减少重复数据获取
    - 异常处理：完善的错误处理机制
    """

    def __init__(self):
        """初始化市场扫描器

        初始化数据获取器、缓存和信号注册中心
        """
        import threading

        self.fetcher = get_fetcher()
        self.cache = get_cache()
        self.signal_registry = SignalRegistry()
        self.max_workers = 10  # 并行工作线程数
        self._quotes_cache = None  # 实时行情数据缓存
        self._quotes_timestamp = 0  # 缓存时间戳
        self._quotes_ttl = 60  # 缓存有效期（秒），增加到60秒以覆盖整个扫描周期
        self._quotes_lock = threading.Lock()  # 并发控制锁

    def is_market_open(self) -> bool:
        """检查当前时间是否在A股开盘时间内

        A股开盘时间：
        - 工作日（周一到周五）
        - 上午：9:30 - 11:30
        - 下午：13:00 - 15:00

        Returns:
            bool: 如果市场开盘返回True，否则返回False
        """
        from stock_explorer.config.settings import get_config

        # 检查配置是否设置了忽略市场开盘时间
        config = get_config()
        if config.ignore_market_hours:
            logger.info("忽略市场开盘时间检查")
            return True

        now = datetime.now()

        # 检查是否是工作日（周一到周五）
        if now.weekday() >= 5:  # 0=周一, 4=周五, 5=周六, 6=周日
            return False

        current_time = now.time()

        # 检查是否在上午交易时间
        morning_start = time(9, 30)
        morning_end = time(11, 30)
        if morning_start <= current_time <= morning_end:
            return True

        # 检查是否在下午交易时间
        afternoon_start = time(13, 0)
        afternoon_end = time(15, 0)
        return afternoon_start <= current_time <= afternoon_end

    def _detect_signal(self, stock_data: dict[str, Any], detectors: list) -> list[Signal]:
        """检测单个股票的信号"""
        signals: list = []
        for detector in detectors:
            try:
                signal = detector.detect(stock_data)
                if signal:
                    signals.append(signal)
                    logger.info(f"Signal detected: {signal.symbol} - {signal.message}")
            except Exception as e:
                logger.warning(f"Detection failed for {stock_data.get('symbol', '')}: {e}")
        return signals

    def _get_realtime_quotes(self):
        """获取实时行情数据，使用缓存机制

        确保在缓存有效期内只调用一次 fetch_realtime_quotes() 接口
        支持并发控制，避免重复的远程请求
        只在A股开盘时间获取实时行情

        Returns:
            DataFrame: 实时行情数据
        """
        import time

        import pandas as pd

        # 检查市场是否开盘
        if not self.is_market_open():
            logger.info("市场未开盘，返回空数据")
            return pd.DataFrame()

        current_time = time.time()

        # 检查缓存是否有效
        if (
            self._quotes_cache is not None
            and (current_time - self._quotes_timestamp) < self._quotes_ttl
        ):
            logger.info("使用缓存的实时行情数据")
            return self._quotes_cache

        # 缓存失效，需要重新获取数据
        # 使用锁确保同一时间只有一个线程发起远程请求
        with self._quotes_lock:
            # 再次检查市场是否开盘（防止在等待锁的过程中市场已收盘）
            if not self.is_market_open():
                logger.info("市场未开盘，返回空数据")
                return pd.DataFrame()

            # 再次检查缓存（防止在等待锁的过程中其他线程已经更新了缓存）
            current_time = time.time()
            if (
                self._quotes_cache is not None
                and (current_time - self._quotes_timestamp) < self._quotes_ttl
            ):
                logger.info("使用缓存的实时行情数据")
                return self._quotes_cache

            # 确实需要重新获取数据
            logger.info("从远程接口获取实时行情数据")
            quotes = self.fetcher.fetch_realtime_quotes()

            # 更新缓存
            if not quotes.empty:
                self._quotes_cache = quotes
                self._quotes_timestamp = current_time

        return quotes

    def scan_hs300(self, strategy_names: list[str], show_top: int = 0) -> list[Signal]:
        """扫描沪深300成分股

        扫描沪深300成分股，检测指定策略的信号

        Args:
            strategy_names: 策略名称列表

        Returns:
            list[Signal]: 检测到的信号列表
        """
        signals: list = []

        hs300_list = self._get_hs300_list()
        if not hs300_list:
            logger.warning("No HS300 constituents found")
            return signals

        logger.info(f"Scanning {len(hs300_list)} HS300 stocks...")

        quotes = self._get_realtime_quotes()
        if quotes.empty:
            logger.warning("Failed to fetch quotes")
            return signals

        quotes_dict = {str(row["代码"]): row.to_dict() for _, row in quotes.iterrows()}

        detectors = self.signal_registry.get_detectors(strategy_names)

        # 准备需要处理的股票数据
        stock_data_list = []
        for symbol_info in hs300_list:
            symbol = symbol_info.get("成分券代码", "")
            name = symbol_info.get("成分券名称", "")

            if symbol not in quotes_dict:
                continue

            quote = quotes_dict[symbol]

            stock_data = {
                "symbol": symbol,
                "name": name,
                "quote": quote,
            }
            stock_data_list.append(stock_data)

        # 显示前 N 只股票的数据
        if show_top > 0 and stock_data_list:
            from rich.console import Console
            from rich.table import Table

            console = Console()

            console.print(
                f"\n[cyan]扫描的股票示例（前 {min(show_top, len(stock_data_list))} 只）:[/cyan]"
            )
            table = Table(show_header=True, show_lines=True, row_styles=["", "dim"])
            table.add_column("代码", style="yellow", width=8)
            table.add_column("名称", style="green", width=12)
            table.add_column("最新价", justify="right", width=10)
            table.add_column("涨跌幅", justify="right", width=10)
            table.add_column("成交量", justify="right", width=12)
            table.add_column("成交额", justify="right", width=12)

            for stock_data in stock_data_list[:show_top]:
                code = str(stock_data.get("symbol", ""))
                name = str(stock_data.get("name", ""))
                quote = stock_data.get("quote", {})
                price = f"{quote.get('最新价', 0):.2f}" if "最新价" in quote else "N/A"
                change_pct = f"{quote.get('涨跌幅', 0):.2f}%" if "涨跌幅" in quote else "N/A"
                volume = f"{int(quote.get('成交量', 0)):,}" if "成交量" in quote else "N/A"
                amount = (
                    f"{float(quote.get('成交额', 0) / 10000):.2f}万" if "成交额" in quote else "N/A"
                )
                table.add_row(code, name, price, change_pct, volume, amount)

            console.print(table)
            console.print()

        # 并行处理股票数据
        if stock_data_list:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交任务
                future_to_stock = {
                    executor.submit(self._detect_signal, stock_data, detectors): stock_data
                    for stock_data in stock_data_list
                }

                # 收集结果
                for future in concurrent.futures.as_completed(future_to_stock):
                    try:
                        stock_signals = future.result()
                        signals.extend(stock_signals)
                    except Exception as e:
                        stock_data = future_to_stock[future]
                        logger.error(f"Error processing {stock_data.get('symbol', '')}: {e}")

        logger.info(f"HS300 scan completed: {len(signals)} signals found")
        return signals

    def scan_all(self, strategy_names: list[str], show_top: int = 0) -> list[Signal]:
        """扫描全市场

        扫描全市场股票，检测指定策略的信号

        Args:
            strategy_names: 策略名称列表

        Returns:
            list[Signal]: 检测到的信号列表
        """
        signals: list = []

        # 获取实时行情数据
        quotes = self._get_realtime_quotes()
        if quotes.empty:
            logger.warning("Failed to fetch quotes")
            return signals

        # 构建行情字典
        quotes_dict = {str(row["代码"]): row.to_dict() for _, row in quotes.iterrows()}

        # 获取缓存的全市场股票列表
        market_stocks = self._get_market_stocks()
        if not market_stocks:
            logger.warning("No market stocks found")
            return signals

        logger.info(f"Scanning {len(quotes_dict)} stocks...")

        detectors = self.signal_registry.get_detectors(strategy_names)

        # 准备需要处理的股票数据
        stock_data_list = []
        for stock_info in market_stocks:
            symbol = str(stock_info.get("代码", ""))
            name = str(stock_info.get("名称", ""))

            if symbol not in quotes_dict:
                continue

            quote = quotes_dict[symbol]

            stock_data = {
                "symbol": symbol,
                "name": name,
                "quote": quote,
            }
            stock_data_list.append(stock_data)

        # 显示前 N 只股票的数据
        if show_top > 0 and stock_data_list:
            from rich.console import Console
            from rich.table import Table

            console = Console()

            console.print(
                f"\n[cyan]扫描的股票示例（前 {min(show_top, len(stock_data_list))} 只）:[/cyan]"
            )
            table = Table(show_header=True, show_lines=True, row_styles=["", "dim"])
            table.add_column("代码", style="yellow", width=8)
            table.add_column("名称", style="green", width=12)
            table.add_column("最新价", justify="right", width=10)
            table.add_column("涨跌幅", justify="right", width=10)
            table.add_column("成交量", justify="right", width=12)
            table.add_column("成交额", justify="right", width=12)

            for stock_data in stock_data_list[:show_top]:
                code = str(stock_data.get("symbol", ""))
                name = str(stock_data.get("name", ""))
                quote = stock_data.get("quote", {})
                price = f"{quote.get('最新价', 0):.2f}" if "最新价" in quote else "N/A"
                change_pct = f"{quote.get('涨跌幅', 0):.2f}%" if "涨跌幅" in quote else "N/A"
                volume = f"{int(quote.get('成交量', 0)):,}" if "成交量" in quote else "N/A"
                amount = (
                    f"{float(quote.get('成交额', 0) / 10000):.2f}万" if "成交额" in quote else "N/A"
                )
                table.add_row(code, name, price, change_pct, volume, amount)

            console.print(table)
            console.print()

        # 并行处理股票数据
        if stock_data_list:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交任务
                future_to_stock = {
                    executor.submit(self._detect_signal, stock_data, detectors): stock_data
                    for stock_data in stock_data_list
                }

                # 收集结果
                for future in concurrent.futures.as_completed(future_to_stock):
                    try:
                        stock_signals = future.result()
                        signals.extend(stock_signals)
                    except Exception as e:
                        stock_data = future_to_stock[future]
                        logger.error(f"Error processing {stock_data.get('symbol', '')}: {e}")

        logger.info(f"Market scan completed: {len(signals)} signals found")
        return signals

    def scan_industry(
        self, industry: str, strategy_names: list[str], show_top: int = 0
    ) -> list[Signal]:
        """扫描特定行业

        扫描指定行业的股票，检测指定策略的信号

        Args:
            industry: 行业名称
            strategy_names: 策略名称列表

        Returns:
            list[Signal]: 检测到的信号列表
        """
        signals: list = []

        constituents = self.fetcher.fetch_stock_board_industry_cons(industry)
        if constituents.empty:
            logger.warning(f"No constituents found for industry: {industry}")
            return signals

        logger.info(f"Scanning {len(constituents)} stocks in {industry}...")

        quotes = self._get_realtime_quotes()
        if quotes.empty:
            return signals

        quotes_dict = {str(row["代码"]): row.to_dict() for _, row in quotes.iterrows()}

        detectors = self.signal_registry.get_detectors(strategy_names)

        # 准备需要处理的股票数据
        stock_data_list = []
        for _, row in constituents.iterrows():
            symbol = str(row.get("代码", ""))
            name = str(row.get("名称", ""))

            if symbol not in quotes_dict:
                continue

            quote = quotes_dict[symbol]

            stock_data = {
                "symbol": symbol,
                "name": name,
                "quote": quote,
            }
            stock_data_list.append(stock_data)

        # 并行处理股票数据
        if stock_data_list:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交任务
                future_to_stock = {
                    executor.submit(self._detect_signal, stock_data, detectors): stock_data
                    for stock_data in stock_data_list
                }

                # 收集结果
                for future in concurrent.futures.as_completed(future_to_stock):
                    try:
                        stock_signals = future.result()
                        signals.extend(stock_signals)
                    except Exception as e:
                        stock_data = future_to_stock[future]
                        logger.error(f"Error processing {stock_data.get('symbol', '')}: {e}")

        logger.info(f"Industry scan completed for {industry}: {len(signals)} signals found")
        return signals

    def get_industry_list(self) -> list[str]:
        """获取行业列表"""
        # 尝试从缓存获取完整数据
        cached_data = self.cache.get_industry_data()
        if cached_data:
            # 从缓存数据中提取行业名称列表
            logger.info("从缓存获取行业列表数据")
            return [item.get("板块名称", "") for item in cached_data if item.get("板块名称")]

        # 从远程接口获取
        df = self.fetcher.fetch_industry_classification()
        if df is not None and not df.empty:
            # 缓存完整数据
            full_data = df.to_dict("records")
            self.cache.cache_industry_data(full_data)
            logger.info("从远程接口获取行业列表数据并缓存")
            # 返回行业名称列表
            return df["板块名称"].tolist() if "板块名称" in df.columns else []
        return []

    def _get_hs300_list(self) -> list[dict]:
        """获取沪深300成分股列表"""
        cached = self.cache.get_hs300_list()
        if cached:
            logger.info("从缓存获取沪深300成分股数据")
            cached_list: list[dict] = cached
            return cached_list

        df = self.fetcher.fetch_hs300_constituents()
        if df is None or df.empty:
            return []

        result: list[dict] = df.to_dict("records")
        # 使用默认的TTL，不再硬编码
        self.cache.cache_hs300_list(result)
        logger.info("从远程接口获取沪深300成分股数据并缓存")
        return result

    def _get_market_stocks(self) -> list[dict]:
        """获取全市场股票列表"""
        cached = self.cache.get_market_stocks()
        if cached:
            logger.info("从缓存获取全市场股票列表数据")
            cached_list: list[dict] = cached
            return cached_list

        df = self.fetcher.fetch_stock_list()
        if df is None or df.empty:
            return []

        result: list[dict] = df.to_dict("records")
        # 使用默认的TTL，不再硬编码
        self.cache.cache_market_stocks(result)
        logger.info("从远程接口获取全市场股票列表数据并缓存")
        return result


_scanner_instance: MarketScanner | None = None


def get_scanner() -> MarketScanner:
    """获取扫描器单例"""
    global _scanner_instance
    if _scanner_instance is None:
        _scanner_instance = MarketScanner()
    return _scanner_instance

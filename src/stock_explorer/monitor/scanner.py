"""市场扫描模块 - 三层扫描体系"""

import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
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
        self.fetcher = get_fetcher()
        self.cache = get_cache()
        self.signal_registry = SignalRegistry()
        self.max_workers = 10  # 并行工作线程数

    def _detect_signal(self, stock_data: dict[str, Any], detectors: list) -> list[Signal]:
        """检测单个股票的信号"""
        signals = []
        for detector in detectors:
            try:
                signal = detector.detect(stock_data)
                if signal:
                    signals.append(signal)
                    logger.info(f"Signal detected: {signal.symbol} - {signal.message}")
            except Exception as e:
                logger.warning(f"Detection failed for {stock_data.get('symbol', '')}: {e}")
        return signals

    def scan_hs300(self, strategy_names: list[str]) -> list[Signal]:
        """扫描沪深300成分股

        扫描沪深300成分股，检测指定策略的信号

        Args:
            strategy_names: 策略名称列表

        Returns:
            list[Signal]: 检测到的信号列表
        """
        signals = []

        hs300_list = self._get_hs300_list()
        if not hs300_list:
            logger.warning("No HS300 constituents found")
            return signals

        logger.info(f"Scanning {len(hs300_list)} HS300 stocks...")

        quotes = self.fetcher.fetch_realtime_quotes()
        if quotes.empty:
            logger.warning("Failed to fetch quotes")
            return signals

        quotes_dict = {str(row["代码"]): row.to_dict() for _, row in quotes.iterrows()}

        detectors = self.signal_registry.get_detectors(strategy_names)

        # 准备需要处理的股票数据
        stock_data_list = []
        for symbol_info in hs300_list:
            symbol = symbol_info.get("代码", "")
            name = symbol_info.get("名称", "")

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

        logger.info(f"HS300 scan completed: {len(signals)} signals found")
        return signals

    def scan_all(self, strategy_names: list[str]) -> list[Signal]:
        """扫描全市场

        扫描全市场股票，检测指定策略的信号

        Args:
            strategy_names: 策略名称列表

        Returns:
            list[Signal]: 检测到的信号列表
        """
        signals = []

        quotes = self.fetcher.fetch_realtime_quotes()
        if quotes.empty:
            logger.warning("Failed to fetch quotes")
            return signals

        logger.info(f"Scanning {len(quotes)} stocks...")

        detectors = self.signal_registry.get_detectors(strategy_names)

        # 准备需要处理的股票数据
        stock_data_list = []
        for _, row in quotes.iterrows():
            symbol = str(row.get("代码", ""))
            name = str(row.get("名称", ""))

            stock_data = {
                "symbol": symbol,
                "name": name,
                "quote": row.to_dict(),
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

        logger.info(f"Market scan completed: {len(signals)} signals found")
        return signals

    def scan_industry(self, industry: str, strategy_names: list[str]) -> list[Signal]:
        """扫描特定行业

        扫描指定行业的股票，检测指定策略的信号

        Args:
            industry: 行业名称
            strategy_names: 策略名称列表

        Returns:
            list[Signal]: 检测到的信号列表
        """
        signals = []

        constituents = self.fetcher.fetch_stock_board_industry_cons(industry)
        if constituents.empty:
            logger.warning(f"No constituents found for industry: {industry}")
            return signals

        logger.info(f"Scanning {len(constituents)} stocks in {industry}...")

        quotes = self.fetcher.fetch_realtime_quotes()
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
        df = self.fetcher.fetch_industry_classification()
        if df is not None and not df.empty:
            return df["板块名称"].tolist() if "板块名称" in df.columns else []
        return []

    def _get_hs300_list(self) -> list[dict]:
        """获取沪深300成分股列表"""
        cached = self.cache.get_hs300_list()
        if cached:
            return cached

        df = self.fetcher.fetch_hs300_constituents()
        if df is None or df.empty:
            return []

        result = df.to_dict("records")
        self.cache.cache_hs300_list(result, ttl=3600)
        return result


_scanner_instance: MarketScanner | None = None


def get_scanner() -> MarketScanner:
    """获取扫描器单例"""
    global _scanner_instance
    if _scanner_instance is None:
        _scanner_instance = MarketScanner()
    return _scanner_instance

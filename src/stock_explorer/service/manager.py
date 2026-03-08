"""服务管理器 - 管理信号检测服务的启动、运行和停止"""
import asyncio
import concurrent.futures
import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum

from stock_explorer.config.settings import get_config
from stock_explorer.exceptions import ServiceError
from stock_explorer.logging.logger import get_logger
from stock_explorer.monitor.notifier import NotifierManager
from stock_explorer.monitor.scanner import MarketScanner

logger = get_logger(__name__)


class ServiceStatus(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class ServiceConfig:
    scan_interval_hs300: int = 5
    scan_interval_market: int = 30
    scan_interval_industry: int = 30
    enable_hs300_scan: bool = True
    enable_market_scan: bool = True
    enable_industry_scan: bool = True
    enable_notifications: bool = True
    hs300_strategies: str = "golden_cross,limit_up"
    market_strategies: str = "limit_up,volume_surge"
    industry_strategies: str = "limit_up,volume_surge"


class ServiceManager:
    def __init__(self, config: ServiceConfig | None = None):
        self.config = config or ServiceConfig()
        self.status = ServiceStatus.STOPPED
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []
        self._scanner: MarketScanner | None = None
        self._notifier: NotifierManager | None = None
        self._thread_pool: ThreadPoolExecutor | None = None

    def _signal_handler(self, signum, frame):
        logger.info(f"收到信号 {signum}, 准备停止服务...")
        self.stop()

    def _setup_signal_handlers(self):
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def start(self):
        if self.status == ServiceStatus.RUNNING:
            logger.warning("服务已在运行中")
            return

        self.status = ServiceStatus.STARTING
        logger.info("正在启动信号检测服务...")

        try:
            get_config()
            self._scanner = MarketScanner()
            self._notifier = NotifierManager()

            # 初始化线程池
            self._thread_pool = ThreadPoolExecutor(max_workers=5)

            self._stop_event.clear()
            self._setup_signal_handlers()

            if self.config.enable_hs300_scan:
                hs300_thread = threading.Thread(
                    target=self._run_hs300_scanner,
                    name="hs300-scanner",
                    daemon=True,
                )
                self._threads.append(hs300_thread)
                hs300_thread.start()
                logger.info("HS300 扫描线程已启动")

            if self.config.enable_market_scan:
                market_thread = threading.Thread(
                    target=self._run_market_scanner,
                    name="market-scanner",
                    daemon=True,
                )
                self._threads.append(market_thread)
                market_thread.start()
                logger.info("全市场扫描线程已启动")

            if self.config.enable_industry_scan:
                industry_thread = threading.Thread(
                    target=self._run_industry_scanner,
                    name="industry-scanner",
                    daemon=True,
                )
                self._threads.append(industry_thread)
                industry_thread.start()
                logger.info("行业扫描线程已启动")

            self.status = ServiceStatus.RUNNING
            logger.info("信号检测服务已启动")

        except Exception as e:
            logger.error(f"服务启动失败: {e}")
            self.status = ServiceStatus.ERROR
            # 清理资源
            if self._thread_pool:
                self._thread_pool.shutdown(wait=False)
            raise ServiceError(f"服务启动失败: {e}") from e

    def _run_hs300_scanner(self):
        while not self._stop_event.is_set():
            try:
                logger.debug("执行 HS300 扫描...")
                strategies = self.config.hs300_strategies.split(",")
                signals = self._scanner.scan_hs300(strategies)
                if signals and self.config.enable_notifications and self._thread_pool:
                    # 使用线程池并行发送信号
                    futures = []
                    for signal in signals:
                        future = self._thread_pool.submit(self._notifier.send, signal)
                        futures.append(future)
                    # 等待所有发送完成
                    for future in concurrent.futures.as_completed(futures):
                        try:
                            future.result()
                        except Exception as e:
                            logger.error(f"信号发送失败: {e}")
            except Exception as e:
                logger.error(f"HS300 扫描出错: {e}")

            self._stop_event.wait(self.config.scan_interval_hs300)

    def _run_market_scanner(self):
        while not self._stop_event.is_set():
            try:
                logger.debug("执行全市场扫描...")
                strategies = self.config.market_strategies.split(",")
                signals = self._scanner.scan_all(strategies)
                if signals and self.config.enable_notifications and self._thread_pool:
                    # 使用线程池并行发送信号
                    futures = []
                    for signal in signals:
                        future = self._thread_pool.submit(self._notifier.send, signal)
                        futures.append(future)
                    # 等待所有发送完成
                    for future in concurrent.futures.as_completed(futures):
                        try:
                            future.result()
                        except Exception as e:
                            logger.error(f"信号发送失败: {e}")
            except Exception as e:
                logger.error(f"全市场扫描出错: {e}")

            self._stop_event.wait(self.config.scan_interval_market)

    def _run_industry_scanner(self):
        while not self._stop_event.is_set():
            try:
                logger.debug("执行行业扫描...")
                strategies = self.config.industry_strategies.split(",")
                industry_list = self._scanner.get_industry_list()
                all_signals = []

                # 扫描所有行业
                for industry in industry_list[:10]:  # 限制扫描前10个行业，避免过多请求
                    try:
                        industry_signals = self._scanner.scan_industry(industry, strategies)
                        all_signals.extend(industry_signals)
                    except Exception as e:
                        logger.error(f"行业 {industry} 扫描出错: {e}")

                if all_signals and self.config.enable_notifications and self._thread_pool:
                    # 使用线程池并行发送信号
                    futures = []
                    for signal in all_signals:
                        future = self._thread_pool.submit(self._notifier.send, signal)
                        futures.append(future)
                    # 等待所有发送完成
                    for future in concurrent.futures.as_completed(futures):
                        try:
                            future.result()
                        except Exception as e:
                            logger.error(f"信号发送失败: {e}")
            except Exception as e:
                logger.error(f"行业扫描出错: {e}")

            self._stop_event.wait(self.config.scan_interval_industry)

    def stop(self):
        if self.status == ServiceStatus.STOPPED:
            logger.warning("服务已停止")
            return

        self.status = ServiceStatus.STOPPING
        logger.info("正在停止服务...")

        self._stop_event.set()

        for thread in self._threads:
            thread.join(timeout=5)

        # 关闭线程池
        if self._thread_pool:
            self._thread_pool.shutdown(wait=True, cancel_futures=True)
            logger.info("线程池已关闭")

        # 停止配置文件监控
        try:
            from stock_explorer.config.settings import ConfigLoader
            config_loader = ConfigLoader()
            if hasattr(config_loader, 'stop_watcher'):
                config_loader.stop_watcher()
        except Exception as e:
            logger.error(f"停止配置文件监控失败: {e}")

        self._threads.clear()
        self.status = ServiceStatus.STOPPED
        logger.info("服务已停止")

    def restart(self):
        logger.info("重启服务...")
        self.stop()
        time.sleep(2)
        self.start()

    def get_status(self) -> dict:
        return {
            "status": self.status.value,
            "threads": len(self._threads),
            "hs300_enabled": self.config.enable_hs300_scan,
            "market_enabled": self.config.enable_market_scan,
            "industry_enabled": self.config.enable_industry_scan,
        }


class AsyncServiceManager:
    def __init__(self, config: ServiceConfig | None = None):
        self.config = config or ServiceConfig()
        self.status = ServiceStatus.STOPPED
        self._tasks: list[asyncio.Task] = []
        self._scanner: MarketScanner | None = None
        self._notifier: NotifierManager | None = None
        self._semaphore: asyncio.Semaphore | None = None  # 用于控制并发数

    async def start(self):
        if self.status == ServiceStatus.RUNNING:
            logger.warning("服务已在运行中")
            return

        self.status = ServiceStatus.STARTING
        logger.info("正在启动异步信号检测服务...")

        try:
            get_config()
            self._scanner = MarketScanner()
            self._notifier = NotifierManager()
            # 初始化信号量，控制并发数
            self._semaphore = asyncio.Semaphore(5)

            if self.config.enable_hs300_scan:
                hs300_task = asyncio.create_task(self._run_hs300_scanner())
                self._tasks.append(hs300_task)

            if self.config.enable_market_scan:
                market_task = asyncio.create_task(self._run_market_scanner())
                self._tasks.append(market_task)

            if self.config.enable_industry_scan:
                industry_task = asyncio.create_task(self._run_industry_scanner())
                self._tasks.append(industry_task)

            self.status = ServiceStatus.RUNNING
            logger.info("异步信号检测服务已启动")

        except Exception as e:
            logger.error(f"服务启动失败: {e}")
            self.status = ServiceStatus.ERROR
            raise ServiceError(f"服务启动失败: {e}") from e

    async def _run_hs300_scanner(self):
        while self.status == ServiceStatus.RUNNING:
            try:
                strategies = self.config.hs300_strategies.split(",")
                # 使用信号量控制并发
                async with self._semaphore:
                    signals = await asyncio.to_thread(self._scanner.scan_hs300, strategies)
                    if signals and self.config.enable_notifications:
                        # 并行发送信号
                        tasks = []
                        for signal in signals:
                            task = asyncio.create_task(asyncio.to_thread(self._notifier.send, signal))
                            tasks.append(task)
                        # 等待所有发送完成
                        if tasks:
                            await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                logger.error(f"HS300 扫描出错: {e}")

            await asyncio.sleep(self.config.scan_interval_hs300)

    async def _run_market_scanner(self):
        while self.status == ServiceStatus.RUNNING:
            try:
                strategies = self.config.market_strategies.split(",")
                # 使用信号量控制并发
                async with self._semaphore:
                    signals = await asyncio.to_thread(self._scanner.scan_all, strategies)
                    if signals and self.config.enable_notifications:
                        # 并行发送信号
                        tasks = []
                        for signal in signals:
                            task = asyncio.create_task(asyncio.to_thread(self._notifier.send, signal))
                            tasks.append(task)
                        # 等待所有发送完成
                        if tasks:
                            await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                logger.error(f"全市场扫描出错: {e}")

            await asyncio.sleep(self.config.scan_interval_market)

    async def _run_industry_scanner(self):
        while self.status == ServiceStatus.RUNNING:
            try:
                strategies = self.config.industry_strategies.split(",")
                industry_list = await asyncio.to_thread(self._scanner.get_industry_list)
                all_signals = []

                # 扫描所有行业
                for industry in industry_list[:10]:  # 限制扫描前10个行业，避免过多请求
                    try:
                        # 使用信号量控制并发
                        async with self._semaphore:
                            industry_signals = await asyncio.to_thread(self._scanner.scan_industry, industry, strategies)
                            all_signals.extend(industry_signals)
                    except Exception as e:
                        logger.error(f"行业 {industry} 扫描出错: {e}")

                if all_signals and self.config.enable_notifications:
                    # 并行发送信号
                    tasks = []
                    for signal in all_signals:
                        task = asyncio.create_task(asyncio.to_thread(self._notifier.send, signal))
                        tasks.append(task)
                    # 等待所有发送完成
                    if tasks:
                        await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                logger.error(f"行业扫描出错: {e}")

            await asyncio.sleep(self.config.scan_interval_industry)

    async def stop(self):
        if self.status == ServiceStatus.STOPPED:
            return

        self.status = ServiceStatus.STOPPING
        logger.info("正在停止异步服务...")

        for task in self._tasks:
            task.cancel()

        await asyncio.gather(*self._tasks, return_exceptions=True)

        # 停止配置文件监控
        try:
            from stock_explorer.config.settings import ConfigLoader
            config_loader = ConfigLoader()
            if hasattr(config_loader, 'stop_watcher'):
                config_loader.stop_watcher()
        except Exception as e:
            logger.error(f"停止配置文件监控失败: {e}")

        self._tasks.clear()
        self.status = ServiceStatus.STOPPED
        logger.info("异步服务已停止")

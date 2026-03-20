"""服务管理器 - 管理信号检测服务的启动、运行和停止"""

import asyncio
import concurrent.futures
import signal
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, time
from enum import Enum

from stock_explorer.config.settings import get_config
from stock_explorer.data.cache import get_cache
from stock_explorer.data.fetcher import get_fetcher
from stock_explorer.data.storage import get_database
from stock_explorer.exceptions import ServiceError
from stock_explorer.logging.logger import get_logger
from stock_explorer.monitor.notifier import NotifierManager
from stock_explorer.monitor.scanner import MarketScanner
from stock_explorer.service.scheduler import TaskScheduler

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
    def __init__(self, config: ServiceConfig | None = None, pid_file: str | None = None):
        self.config = config or ServiceConfig()
        self.status = ServiceStatus.STOPPED
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []
        self._scanner: MarketScanner | None = None
        self._notifier: NotifierManager | None = None
        self._thread_pool: ThreadPoolExecutor | None = None
        self._database = get_database()
        self._cache = get_cache()
        self._fetcher = get_fetcher()
        self._scheduler = None
        self._pid_file = pid_file

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
            config = get_config()
            self._scanner = MarketScanner()
            from stock_explorer.monitor.notifier import create_notifier_manager

            self._notifier = create_notifier_manager(config.alert.model_dump())

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

            # 初始化任务调度器
            self._scheduler = TaskScheduler()

            # 添加每周三下午两点刷新缓存数据的任务
            # cron表达式：0 14 * * 3 表示每周三14:00执行
            self._scheduler.add_cron_task(
                name="refresh_cache", func=self._refresh_cache_data, cron_expr="0 14 * * 3"
            )

            # 启动任务调度器
            self._scheduler.start()
            logger.info("任务调度器已启动，添加了每周三下午两点刷新缓存的任务")

            self.status = ServiceStatus.RUNNING
            logger.info("信号检测服务已启动")

        except Exception as e:
            logger.error(f"服务启动失败: {e}")
            self.status = ServiceStatus.ERROR
            # 清理资源
            if self._thread_pool:
                self._thread_pool.shutdown(wait=False)
            raise ServiceError(f"服务启动失败: {e}") from e

    def _process_signals(self, signals):
        """处理检测到的信号"""
        if not signals:
            return

        # 保存信号到数据库
        try:
            signal_dicts = [
                {
                    "timestamp": signal.timestamp,
                    "symbol": signal.symbol,
                    "name": signal.name,
                    "signal_type": signal.signal_type.value,
                    "direction": signal.direction.value,
                    "strength": signal.strength.value,
                    "price": signal.price,
                    "message": signal.message,
                    "strategy": signal.strategy,
                    "metadata": {},
                }
                for signal in signals
            ]
            self._database.save_signals(signal_dicts)
        except Exception as e:
            logger.error(f"保存信号失败: {e}")

        # 发送通知
        if self.config.enable_notifications and self._thread_pool:
            futures = []
            for signal in signals:
                future = self._thread_pool.submit(self._notifier.notify, signal)
                futures.append(future)
            # 等待所有发送完成
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"信号发送失败: {e}")

    def _run_scanner(self, scanner_func, strategies, interval, error_prefix):
        """通用扫描方法"""
        while not self._stop_event.is_set():
            try:
                logger.info("检查市场是否开盘...")
                is_open = self.is_market_open()
                logger.info(f"市场开盘检查结果: {is_open}")
                if is_open:
                    logger.info(f"市场已开盘，开始{error_prefix}扫描...")
                    import time

                    start_time = time.time()
                    signals = scanner_func(strategies)
                    elapsed = time.time() - start_time
                    logger.info(
                        f"{error_prefix}扫描完成，结果: {len(signals)} 个信号，耗时: {elapsed:.2f}秒"
                    )
                    self._process_signals(signals)
                else:
                    logger.info(f"市场未开盘，暂停{error_prefix}扫描")
                    # 市场未开盘时，使用配置的扫描间隔
                    self._stop_event.wait(interval)  # 等待配置的扫描间隔后再次检查
                    continue
            except Exception as e:
                logger.error(f"{error_prefix} 扫描出错: {e}", exc_info=True)

            self._stop_event.wait(interval)

    def _run_hs300_scanner(self):
        """运行 HS300 扫描"""

        def scanner_func(strategies):
            logger.debug("执行 HS300 扫描...")
            return self._scanner.scan_hs300(strategies)

        strategies = self.config.hs300_strategies.split(",")
        self._run_scanner(scanner_func, strategies, self.config.scan_interval_hs300, "HS300")

    def _run_market_scanner(self):
        """运行全市场扫描"""

        def scanner_func(strategies):
            logger.debug("执行全市场扫描...")
            return self._scanner.scan_all(strategies)

        strategies = self.config.market_strategies.split(",")
        self._run_scanner(scanner_func, strategies, self.config.scan_interval_market, "全市场")

    def _run_industry_scanner(self):
        """运行行业扫描"""
        while not self._stop_event.is_set():
            try:
                # 检查市场是否开盘
                if self.is_market_open():
                    logger.debug("执行行业扫描...")
                    strategies = self.config.industry_strategies.split(",")
                    industry_list = self._scanner.get_industry_list()
                    all_signals = []

                    # 并行扫描所有行业
                    if industry_list and self._thread_pool:
                        futures = []
                        # 限制扫描前10个行业，避免过多请求
                        for industry in industry_list[:10]:
                            future = self._thread_pool.submit(
                                self._scanner.scan_industry, industry, strategies
                            )
                            futures.append((future, industry))

                        # 收集结果
                        for future, industry in futures:
                            try:
                                industry_signals = future.result()
                                all_signals.extend(industry_signals)
                            except Exception as e:
                                logger.error(f"行业 {industry} 扫描出错: {e}")
                    else:
                        # 后备方案：串行扫描
                        for industry in industry_list[:10]:
                            try:
                                industry_signals = self._scanner.scan_industry(industry, strategies)
                                all_signals.extend(industry_signals)
                            except Exception as e:
                                logger.error(f"行业 {industry} 扫描出错: {e}")

                    self._process_signals(all_signals)
                else:
                    logger.info("市场未开盘，暂停行业扫描")
                    # 市场未开盘时，使用配置的扫描间隔
                    self._stop_event.wait(
                        self.config.scan_interval_industry
                    )  # 等待配置的扫描间隔后再次检查
                    continue
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

        if self._thread_pool:
            self._thread_pool.shutdown(wait=True, cancel_futures=True)
            logger.info("线程池已关闭")

        try:
            from stock_explorer.config.settings import ConfigLoader

            config_loader = ConfigLoader()
            if hasattr(config_loader, "stop_watcher"):
                config_loader.stop_watcher()
        except Exception as e:
            logger.error(f"停止配置文件监控失败: {e}")

        if self._scheduler:
            try:
                self._scheduler.stop()
                logger.info("任务调度器已停止")
            except Exception as e:
                logger.error(f"停止任务调度器失败: {e}")

        self._threads.clear()
        self.status = ServiceStatus.STOPPED
        logger.info("服务已停止")

        self._cleanup_pid_file()

    def _cleanup_pid_file(self):
        if self._pid_file:
            try:
                from pathlib import Path

                pid_path = Path(self._pid_file)
                if pid_path.exists():
                    pid_path.unlink()
                    logger.info(f"PID 文件已删除: {self._pid_file}")
            except Exception as e:
                logger.error(f"删除 PID 文件失败: {e}")

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

    def _refresh_cache_data(self):
        """刷新缓存数据

        刷新行业列表和沪深300成分股数据
        调用远程失败不用重试
        """
        logger.info("开始刷新缓存数据...")

        try:
            # 刷新沪深300成分股
            logger.info("刷新沪深300成分股数据...")
            df = self._fetcher.fetch_hs300_constituents()
            if not df.empty:
                result = df.to_dict("records")
                self._cache.cache_hs300_list(result)
                logger.info(f"沪深300成分股数据刷新成功，共 {len(result)} 条")
            else:
                logger.warning("沪深300成分股数据获取失败")
        except Exception as e:
            logger.error(f"刷新沪深300成分股数据失败: {e}")

        try:
            # 刷新行业列表
            logger.info("刷新行业列表数据...")
            df = self._fetcher.fetch_industry_classification()
            if not df.empty:
                full_data = df.to_dict("records")
                self._cache.cache_industry_data(full_data)
                industry_list = df["板块名称"].tolist() if "板块名称" in df.columns else []
                logger.info(f"行业列表数据刷新成功，共 {len(industry_list)} 条")
            else:
                logger.warning("行业列表数据获取失败")
        except Exception as e:
            logger.error(f"刷新行业列表数据失败: {e}")

        logger.info("缓存数据刷新完成")


class AsyncServiceManager:
    def __init__(self, config: ServiceConfig | None = None):
        self.config = config or ServiceConfig()
        self.status = ServiceStatus.STOPPED
        self._tasks: list[asyncio.Task] = []
        self._scanner: MarketScanner | None = None
        self._notifier: NotifierManager | None = None
        self._semaphore: asyncio.Semaphore | None = None  # 用于控制并发数
        self._database = get_database()

    async def start(self):
        if self.status == ServiceStatus.RUNNING:
            logger.warning("服务已在运行中")
            return

        self.status = ServiceStatus.STARTING
        logger.info("正在启动异步信号检测服务...")

        try:
            config = get_config()
            self._scanner = MarketScanner()
            from stock_explorer.monitor.notifier import create_notifier_manager

            self._notifier = create_notifier_manager(config.alert.model_dump())
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

    async def _process_signals(self, signals):
        """处理检测到的信号"""
        if not signals:
            return

        # 保存信号到数据库
        try:
            signal_dicts = [
                {
                    "timestamp": signal.timestamp,
                    "symbol": signal.symbol,
                    "name": signal.name,
                    "signal_type": signal.signal_type.value,
                    "direction": signal.direction.value,
                    "strength": signal.strength.value,
                    "price": signal.price,
                    "message": signal.message,
                    "strategy": signal.strategy,
                    "metadata": {},
                }
                for signal in signals
            ]
            await asyncio.to_thread(self._database.save_signals, signal_dicts)
        except Exception as e:
            logger.error(f"保存信号失败: {e}")

        # 发送通知
        if self.config.enable_notifications:
            tasks = []
            for signal in signals:
                task = asyncio.create_task(asyncio.to_thread(self._notifier.notify, signal))
                tasks.append(task)
            # 等待所有发送完成
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    async def is_market_open(self) -> bool:
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

    async def _run_scanner(self, scanner_func, strategies, interval, error_prefix):
        """通用扫描方法"""
        while self.status == ServiceStatus.RUNNING:
            try:
                # 检查市场是否开盘
                if self.is_market_open():
                    async with self._semaphore:
                        signals = await asyncio.to_thread(scanner_func, strategies)
                        await self._process_signals(signals)
                else:
                    logger.info(f"市场未开盘，暂停{error_prefix}扫描")
                    # 市场未开盘时，使用配置的扫描间隔
                    await asyncio.sleep(interval)  # 等待配置的扫描间隔后再次检查
                    continue
            except Exception as e:
                logger.error(f"{error_prefix} 扫描出错: {e}")

            await asyncio.sleep(interval)

    async def _run_hs300_scanner(self):
        """运行 HS300 扫描"""

        def scanner_func(strategies):
            return self._scanner.scan_hs300(strategies)

        strategies = self.config.hs300_strategies.split(",")
        await self._run_scanner(scanner_func, strategies, self.config.scan_interval_hs300, "HS300")

    async def _run_market_scanner(self):
        """运行全市场扫描"""

        def scanner_func(strategies):
            return self._scanner.scan_all(strategies)

        strategies = self.config.market_strategies.split(",")
        await self._run_scanner(
            scanner_func, strategies, self.config.scan_interval_market, "全市场"
        )

    async def _run_industry_scanner(self):
        """运行行业扫描"""
        while self.status == ServiceStatus.RUNNING:
            try:
                # 检查市场是否开盘
                if self.is_market_open():
                    strategies = self.config.industry_strategies.split(",")
                    industry_list = await asyncio.to_thread(self._scanner.get_industry_list)
                    all_signals = []

                    # 扫描所有行业
                    for industry in industry_list[:10]:  # 限制扫描前10个行业，避免过多请求
                        try:
                            # 使用信号量控制并发
                            async with self._semaphore:
                                industry_signals = await asyncio.to_thread(
                                    self._scanner.scan_industry, industry, strategies
                                )
                                all_signals.extend(industry_signals)
                        except Exception as e:
                            logger.error(f"行业 {industry} 扫描出错: {e}")

                    await self._process_signals(all_signals)
                else:
                    logger.info("市场未开盘，暂停行业扫描")
                    # 市场未开盘时，使用配置的扫描间隔
                    await asyncio.sleep(
                        self.config.scan_interval_industry
                    )  # 等待配置的扫描间隔后再次检查
                    continue
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
            if hasattr(config_loader, "stop_watcher"):
                config_loader.stop_watcher()
        except Exception as e:
            logger.error(f"停止配置文件监控失败: {e}")

        self._tasks.clear()
        self.status = ServiceStatus.STOPPED
        logger.info("异步服务已停止")

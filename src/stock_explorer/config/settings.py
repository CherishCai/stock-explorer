"""配置模块 - 应用配置管理"""

import threading
import time
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from stock_explorer.exceptions import ConfigError
from stock_explorer.logging.logger import get_logger

logger = get_logger(__name__)


class ScanHS300Config(BaseModel):
    """沪深300扫描配置"""
    enabled: bool = True
    interval: int = 5
    strategies: list[str] = ["golden_cross", "capital_flow", "limit_up"]


class ScanMarketConfig(BaseModel):
    """全市场扫描配置"""
    enabled: bool = True
    interval: int = 30
    strategies: list[str] = ["limit_up", "volume_surge", "high_turnover"]


class ScanIndustryConfig(BaseModel):
    """行业板块扫描配置"""
    enabled: bool = True
    interval: int = 30
    industries: list[str] = ["银行", "证券", "科技", "医药"]


class ScanConfig(BaseModel):
    """扫描配置"""
    hs300: ScanHS300Config = Field(default_factory=ScanHS300Config)
    market: ScanMarketConfig = Field(default_factory=ScanMarketConfig)
    industry: ScanIndustryConfig = Field(default_factory=ScanIndustryConfig)


class RedisConfig(BaseModel):
    """Redis配置"""
    enabled: bool = True
    host: str = "localhost"
    port: int = 6379
    password: str | None = None
    db: int = 0
    realtime_ttl: int = 10
    hs300_cache_ttl: int = 60


class SQLiteConfig(BaseModel):
    """SQLite配置"""
    enabled: bool = True
    path: str = "data/stock_explorer.db"


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
    console: bool = True
    file: bool = True
    file_path: str = "logs/signals.log"
    email: EmailConfig = Field(default_factory=EmailConfig)
    dingtalk: DingTalkConfig = Field(default_factory=DingTalkConfig)
    min_strength: str = "medium"
    exclude_st: bool = True
    min_market_cap: float = 10_000_000_000
    rate_limit_seconds: int = 60


class APIConfig(BaseModel):
    """API服务配置"""
    enabled: bool = False
    host: str = "0.0.0.0"
    port: int = 8000


class AppConfig(BaseModel):
    """全局配置"""
    scan: ScanConfig = Field(default_factory=ScanConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    sqlite: SQLiteConfig = Field(default_factory=SQLiteConfig)
    alert: AlertConfig = Field(default_factory=AlertConfig)
    api: APIConfig = Field(default_factory=APIConfig)


class ConfigFileHandler(FileSystemEventHandler):
    """配置文件变化处理器"""

    def __init__(self, config_loader):
        self.config_loader = config_loader
        self.config_path = Path("config/config.yaml")

    def on_modified(self, event):
        """文件修改事件处理"""
        if event.src_path == str(self.config_path):
            logger.info("配置文件已修改，正在重新加载...")
            try:
                self.config_loader.load_from_file("config/config.yaml")
                logger.info("配置文件重新加载成功")
            except Exception as e:
                logger.error(f"配置文件重新加载失败: {e}")


class ConfigLoader:
    """配置加载器"""

    _instance: Optional["ConfigLoader"] = None
    _config: AppConfig | None = None
    _observer: Observer | None = None
    _watch_thread: threading.Thread | None = None
    _stop_event: threading.Event | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._config is None:
            # 尝试加载配置文件
            config_path = Path("config/config.yaml")
            if config_path.exists():
                self._config = self.load_from_file("config/config.yaml")
            else:
                self._config = self._load_default_config()

            # 启动配置文件监控
            self._start_watcher()

    def _load_default_config(self) -> AppConfig:
        """加载默认配置"""
        return AppConfig()

    def load_from_file(self, config_path: str) -> AppConfig:
        """从文件加载配置"""
        path = Path(config_path)
        if not path.exists():
            return self._load_default_config()

        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if data is None:
                return self._load_default_config()

            self._config = AppConfig(**data)
            return self._config
        except Exception as e:
            raise ConfigError(f"配置文件加载失败: {e}") from e

    def get_config(self) -> AppConfig:
        """获取配置"""
        if self._config is None:
            self._config = self._load_default_config()
        return self._config

    def reload(self, config_path: str | None = None) -> AppConfig:
        """重新加载配置"""
        if config_path:
            return self.load_from_file(config_path)
        return self.load_from_file("config/config.yaml")

    def _start_watcher(self):
        """启动配置文件监控"""
        try:
            self._stop_event = threading.Event()
            self._observer = Observer()
            config_path = Path("config")
            if config_path.exists():
                event_handler = ConfigFileHandler(self)
                self._observer.schedule(event_handler, str(config_path), recursive=False)
                self._observer.start()
                logger.info("配置文件监控已启动")

                # 启动监控线程
                self._watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
                self._watch_thread.start()
        except Exception as e:
            logger.error(f"启动配置文件监控失败: {e}")

    def _watch_loop(self):
        """监控循环"""
        while not self._stop_event.is_set():
            time.sleep(1)

    def stop_watcher(self):
        """停止配置文件监控"""
        try:
            if self._stop_event:
                self._stop_event.set()
            if self._observer:
                self._observer.stop()
                self._observer.join()
            if self._watch_thread:
                self._watch_thread.join(timeout=2)
            logger.info("配置文件监控已停止")
        except Exception as e:
            logger.error(f"停止配置文件监控失败: {e}")


def get_config() -> AppConfig:
    """获取全局配置单例"""
    loader = ConfigLoader()
    return loader.get_config()


def load_config(config_path: str) -> AppConfig:
    """从文件加载配置"""
    loader = ConfigLoader()
    return loader.load_from_file(config_path)

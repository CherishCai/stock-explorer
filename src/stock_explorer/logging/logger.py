"""日志模块 - 统一日志管理"""

import logging
import os
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import override
from zoneinfo import ZoneInfo

from rich.logging import RichHandler

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")

os.environ["TZ"] = "Asia/Shanghai"


def get_shanghai_time() -> datetime:
    """获取上海时区的当前时间"""
    return datetime.now(SHANGHAI_TZ)


class ShanghaiTimeFormatter(logging.Formatter):
    """使用上海时区的格式化器"""

    @override
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        """重写 formatTime 方法，使用上海时区"""
        ct = datetime.fromtimestamp(record.created, tz=UTC)
        ct_shanghai = ct.astimezone(SHANGHAI_TZ)
        if datefmt:
            return ct_shanghai.strftime(datefmt)
        return ct_shanghai.isoformat()


class Logger:
    """日志管理器"""

    _loggers: dict[str, logging.Logger] = {}
    _default_level = logging.INFO

    @classmethod
    def get_logger(
        cls,
        name: str,
        log_file: str | None = "logs/app.log",
        level: int = _default_level,
    ) -> logging.Logger:
        """获取日志记录器"""
        if name in cls._loggers:
            return cls._loggers[name]

        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.handlers.clear()
        logger.propagate = False

        shanghai_formatter = ShanghaiTimeFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        rich_handler = RichHandler(
            rich_tracebacks=True,
            markup=True,
            show_time=True,
            show_path=False,
        )
        rich_handler.setLevel(level)
        logger.addHandler(rich_handler)

        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(shanghai_formatter)
            logger.addHandler(file_handler)

        cls._loggers[name] = logger
        return logger

    @classmethod
    def set_level(cls, level: int):
        """设置全局日志级别"""
        cls._default_level = level
        for logger in cls._loggers.values():
            logger.setLevel(level)


def get_logger(name: str, log_file: str | None = None) -> logging.Logger:
    """获取日志记录器的便捷函数"""
    return Logger.get_logger(name, log_file)


def setup_logging(
    level: int = logging.INFO,
    log_file: str | None = "logs/app.log",
):
    """设置全局日志"""
    Logger.set_level(level)
    if log_file:
        Logger.get_logger("stock_explorer", log_file, level)

        for _name, logger in Logger._loggers.items():
            if "RotatingFileHandler" not in [h.__class__.__name__ for h in logger.handlers]:
                log_path = Path(log_file)
                log_path.parent.mkdir(parents=True, exist_ok=True)

                shanghai_formatter = ShanghaiTimeFormatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )

                file_handler = RotatingFileHandler(
                    log_file,
                    maxBytes=10 * 1024 * 1024,
                    backupCount=5,
                    encoding="utf-8",
                )
                file_handler.setLevel(level)
                file_handler.setFormatter(shanghai_formatter)
                logger.addHandler(file_handler)

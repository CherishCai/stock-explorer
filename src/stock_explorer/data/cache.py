"""数据缓存模块 - 支持内存缓存和 Redis 缓存"""

import time
from typing import Any

import redis

from stock_explorer.config.settings import get_config
from stock_explorer.exceptions import DataCacheError
from stock_explorer.logging.logger import get_logger
from stock_explorer.utils.cache_utils import CacheExpiryStrategy, CacheKeyGenerator

logger = get_logger(__name__)


class DataCache:
    """数据缓存器 - 支持内存缓存和 Redis 缓存"""

    def __init__(
        self, max_size: int = 100, redis_enabled: bool = True, redis_config: dict | None = None
    ):
        self.redis_enabled = redis_enabled
        self.redis_client = None
        self.max_size = max_size

        if self.redis_enabled and redis_config:
            try:
                self.redis_client = redis.Redis(
                    host=redis_config.get("host", "localhost"),
                    port=redis_config.get("port", 6379),
                    password=redis_config.get("password"),
                    db=redis_config.get("db", 0),
                )
                self.redis_client.ping()
                logger.info("Redis 连接成功")
            except Exception as e:
                logger.error(f"Redis 连接失败: {e}")
                self.redis_enabled = False

        # 内存缓存
        self.memory_cache: dict = {}
        self.cache_expiry: dict = {}
        # 缓存工具
        self.key_generator = CacheKeyGenerator()
        self.expiry_strategy = CacheExpiryStrategy(config=get_config())

    def get(self, key: str) -> Any | None:
        """获取缓存数据"""
        try:
            # 先从内存缓存获取
            if key in self.memory_cache:
                expiry = self.cache_expiry.get(key, 0)
                if time.time() < expiry:
                    logger.info(f"从内存缓存获取数据: {key}")
                    return self.memory_cache[key]
                else:
                    self._remove_from_memory(key)

            # 再从 Redis 获取
            if self.redis_enabled and self.redis_client:
                try:
                    value = self.redis_client.get(key)
                    if value and isinstance(value, bytes):
                        logger.info(f"从Redis缓存获取数据: {key}")
                        # 提供eval的全局上下文，包含datetime模块和nan值处理
                        import datetime

                        global_vars = {
                            "datetime": datetime,
                            "time": time,
                            "nan": float("nan"),
                            "inf": float("inf"),
                            "-inf": float("-inf"),
                        }
                        return eval(value.decode("utf-8"), global_vars)
                except Exception as e:
                    logger.error(f"Redis get 失败: {e}")

            logger.debug(f"缓存未命中: {key}")
            return None
        except Exception as e:
            logger.error(f"获取缓存失败: {e}")
            raise DataCacheError(f"获取缓存失败: {e}") from e

    def set(self, key: str, value: Any, ttl: int = 60) -> bool:
        """设置缓存数据"""
        try:
            # 控制内存缓存大小
            if len(self.memory_cache) >= self.max_size:
                self._cleanup_memory_cache()

            # 设置内存缓存
            self.memory_cache[key] = value
            self.cache_expiry[key] = time.time() + ttl

            # 设置 Redis 缓存
            if self.redis_enabled and self.redis_client:
                self.redis_client.setex(key, ttl, str(value))
            return True
        except Exception as e:
            logger.error(f"设置缓存失败: {e}")
            raise DataCacheError(f"设置缓存失败: {e}") from e

    def _cleanup_memory_cache(self):
        """清理内存缓存，移除过期数据"""
        now = time.time()
        expired_keys = [key for key, expiry in self.cache_expiry.items() if now >= expiry]
        for key in expired_keys:
            self._remove_from_memory(key)

        # 如果仍然超过大小限制，移除最旧的数据
        if len(self.memory_cache) >= self.max_size:
            oldest_keys = sorted(self.cache_expiry.items(), key=lambda x: x[1])[
                : len(self.memory_cache) - self.max_size + 1
            ]
            for key, _ in oldest_keys:
                self._remove_from_memory(key)

    def invalidate(self, pattern: str) -> bool:
        """清除匹配模式的缓存"""
        try:
            # 清除内存缓存
            keys_to_remove = [key for key in self.memory_cache if pattern in key]
            for key in keys_to_remove:
                self._remove_from_memory(key)

            # 清除 Redis 缓存
            if self.redis_enabled and self.redis_client:
                keys = self.redis_client.keys(f"*{pattern}*")
                if keys and isinstance(keys, list):
                    self.redis_client.delete(*[key for key in keys if isinstance(key, bytes)])
            return True
        except Exception as e:
            logger.error(f"清除缓存失败: {e}")
            raise DataCacheError(f"清除缓存失败: {e}") from e

    def _remove_from_memory(self, key: str):
        """从内存缓存中移除数据"""
        if key in self.memory_cache:
            del self.memory_cache[key]
        if key in self.cache_expiry:
            del self.cache_expiry[key]

    def get_hs300_list(self) -> list[dict] | None:
        """获取沪深300成分股列表缓存"""
        key = self.key_generator.generate_key("hs300", "list")
        return self.get(key)

    def cache_hs300_list(self, data: list[dict], ttl: int | None = None) -> bool:
        """缓存沪深300成分股列表"""
        key = self.key_generator.generate_key("hs300", "list")
        ttl = ttl or self.expiry_strategy.get_ttl("hs300")
        return self.set(key, data, ttl)

    def get_realtime_data(self, symbol: str) -> dict | None:
        """获取实时行情缓存"""
        key = self.key_generator.generate_key("realtime", symbol)
        return self.get(key)

    def cache_realtime_data(self, symbol: str, data: dict, ttl: int | None = None) -> bool:
        """缓存实时行情"""
        key = self.key_generator.generate_key("realtime", symbol)
        ttl = ttl or self.expiry_strategy.get_ttl("realtime")
        return self.set(key, data, ttl)

    def get_industry_stocks(self, industry: str) -> list[str] | None:
        """获取行业成分股缓存"""
        key = self.key_generator.generate_key("industry", industry, "stocks")
        return self.get(key)

    def get_industry_list(self) -> list[str] | None:
        """获取行业列表缓存"""
        key = self.key_generator.generate_key("industry", "list")
        return self.get(key)

    def cache_industry_list(self, data: list[str], ttl: int | None = None) -> bool:
        """缓存行业列表"""
        key = self.key_generator.generate_key("industry", "list")
        ttl = ttl or self.expiry_strategy.get_ttl("industry")
        return self.set(key, data, ttl)

    def get_industry_data(self) -> list[dict] | None:
        """获取完整行业数据缓存"""
        key = self.key_generator.generate_key("industry", "data")
        return self.get(key)

    def cache_industry_data(self, data: list[dict], ttl: int | None = None) -> bool:
        """缓存完整行业数据"""
        key = self.key_generator.generate_key("industry", "data")
        ttl = ttl or self.expiry_strategy.get_ttl("industry")
        return self.set(key, data, ttl)

    def cache_industry_stocks(
        self, industry: str, stocks: list[str], ttl: int | None = None
    ) -> bool:
        """缓存行业成分股"""
        key = self.key_generator.generate_key("industry", industry, "stocks")
        ttl = ttl or self.expiry_strategy.get_ttl("industry")
        return self.set(key, stocks, ttl)

    def get_market_stocks(self) -> list[dict] | None:
        """获取全市场股票列表缓存"""
        key = self.key_generator.generate_key("market", "stocks")
        return self.get(key)

    def cache_market_stocks(self, data: list[dict], ttl: int | None = None) -> bool:
        """缓存全市场股票列表"""
        key = self.key_generator.generate_key("market", "stocks")
        ttl = ttl or self.expiry_strategy.get_ttl("market")
        return self.set(key, data, ttl)

    def increment_signal_counter(self, name: str) -> int:
        """增加信号计数器"""
        try:
            key = self.key_generator.generate_key("signal", "counter", name)
            if self.redis_enabled and self.redis_client:
                count = self.redis_client.incr(key)
                return int(count) if isinstance(count, (int, str, bytes)) else 0
            else:
                current = self.get(key)
                current_value = int(current) if current is not None else 0
                new_value = current_value + 1
                self.set(key, new_value)
                return new_value
        except Exception as e:
            logger.error(f"增加信号计数器失败: {e}")
            raise DataCacheError(f"增加信号计数器失败: {e}") from e

    def get_signal_counter(self, name: str, date: str | None = None) -> int:
        """获取信号计数器"""
        try:
            if date:
                key = self.key_generator.generate_key("signal", "counter", name, date)
            else:
                key = self.key_generator.generate_key("signal", "counter", name)
            value = self.get(key)
            return int(value) if value else 0
        except Exception as e:
            logger.error(f"获取信号计数器失败: {e}")
            raise DataCacheError(f"获取信号计数器失败: {e}") from e

    def push_alert_queue(self, alert: dict) -> bool:
        """推送告警到队列"""
        try:
            if self.redis_enabled and self.redis_client:
                key = self.key_generator.generate_key("alert", "queue")
                self.redis_client.lpush(key, str(alert))
                return True
            return False
        except Exception as e:
            logger.error(f"推送告警队列失败: {e}")
            raise DataCacheError(f"推送告警队列失败: {e}") from e

    def pop_alert_queue(self) -> dict | None:
        """从队列中弹出告警"""
        try:
            if self.redis_enabled and self.redis_client:
                key = self.key_generator.generate_key("alert", "queue")
                value = self.redis_client.rpop(key)
                if value and isinstance(value, bytes):
                    alert_dict: dict = eval(value.decode("utf-8"))
                    return alert_dict
            return None
        except Exception as e:
            logger.error(f"弹出告警队列失败: {e}")
            raise DataCacheError(f"弹出告警队列失败: {e}") from e

    def clear(self):
        """清空所有缓存"""
        try:
            # 清空内存缓存
            self.memory_cache.clear()
            self.cache_expiry.clear()

            # 清空 Redis 缓存
            if self.redis_enabled and self.redis_client:
                self.redis_client.flushdb()
            logger.info("缓存已清空")
        except Exception as e:
            logger.error(f"清空缓存失败: {e}")
            raise DataCacheError(f"清空缓存失败: {e}") from e


# 单例模式
_cache_instance: DataCache | None = None


def get_cache() -> DataCache:
    """获取缓存器单例"""
    global _cache_instance
    if _cache_instance is None:
        config = get_config()
        redis_config = config.redis.model_dump() if config.redis.enabled else None
        _cache_instance = DataCache(redis_enabled=config.redis.enabled, redis_config=redis_config)
    return _cache_instance

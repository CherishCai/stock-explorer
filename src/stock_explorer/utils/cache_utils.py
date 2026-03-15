"""缓存管理工具模块"""

from collections.abc import Callable
from typing import Any


class CacheKeyGenerator:
    """缓存键生成器"""

    @staticmethod
    def generate_key(prefix: str, *args, **kwargs) -> str:
        """生成缓存键

        Args:
            prefix: 前缀
            *args: 可变参数
            **kwargs: 关键字参数

        Returns:
            缓存键
        """
        parts = [prefix]

        # 添加位置参数
        for arg in args:
            if arg is not None:
                parts.append(str(arg))

        # 添加关键字参数
        for key, value in sorted(kwargs.items()):
            if value is not None:
                parts.append(f"{key}:{value}")

        return ":".join(parts)


class CacheExpiryStrategy:
    """缓存过期策略"""

    def __init__(self, config=None):
        """初始化缓存过期策略

        Args:
            config: 配置对象
        """
        self.config = config

    def get_ttl(self, cache_type: str) -> int:
        """根据缓存类型获取过期时间

        Args:
            cache_type: 缓存类型

        Returns:
            过期时间（秒）
        """
        # 默认值
        ttl_map = {
            "realtime": 10,  # 实时数据10秒
            "hs300": 2592000,  # 沪深300成分股30天
            "industry": 1800,  # 行业数据30分钟
            "market": 3600,  # 全市场股票列表1小时
            "kline": 86400,  # K线数据1天
            "signal": 60,  # 信号数据1分钟
            "default": 600,  # 默认10分钟
        }

        # 从配置中读取
        if self.config:
            if cache_type == "realtime" and hasattr(self.config.redis, "realtime_ttl"):
                return int(self.config.redis.realtime_ttl)
            elif cache_type == "hs300" and hasattr(self.config.redis, "hs300_cache_ttl"):
                return int(self.config.redis.hs300_cache_ttl)
            elif cache_type == "industry" and hasattr(self.config.redis, "industry_cache_ttl"):
                return int(self.config.redis.industry_cache_ttl)
            elif cache_type == "market" and hasattr(self.config.redis, "market_cache_ttl"):
                return int(self.config.redis.market_cache_ttl)

        default_ttl: int = ttl_map.get(cache_type, ttl_map["default"])
        return default_ttl


class CacheManager:
    """缓存管理器"""

    def __init__(self, cache_client):
        """初始化缓存管理器

        Args:
            cache_client: 缓存客户端
        """
        self.cache_client = cache_client

    def get(self, key: str, default: Any = None) -> Any:
        """获取缓存

        Args:
            key: 缓存键
            default: 默认值

        Returns:
            缓存值
        """
        try:
            value = self.cache_client.get(key)
            return value if value is not None else default
        except Exception:
            return default

    def set(self, key: str, value: Any, ttl: int = 600) -> bool:
        """设置缓存

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒）

        Returns:
            是否成功
        """
        try:
            success: bool = self.cache_client.set(key, value, ttl)
            return success
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        """删除缓存

        Args:
            key: 缓存键

        Returns:
            是否成功
        """
        try:
            success: bool = self.cache_client.invalidate(key)
            return success
        except Exception:
            return False

    def get_or_set(self, key: str, func: Callable, ttl: int = 600) -> Any:
        """获取缓存，如果不存在则执行函数并缓存结果

        Args:
            key: 缓存键
            func: 获取数据的函数
            ttl: 过期时间（秒）

        Returns:
            缓存值或函数返回值
        """
        value = self.get(key)
        if value is not None:
            return value

        value = func()
        if value is not None:
            self.set(key, value, ttl)
        return value

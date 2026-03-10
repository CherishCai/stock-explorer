"""数据缓存模块测试"""

from stock_explorer.data.cache import DataCache, get_cache
from stock_explorer.utils.cache_utils import CacheExpiryStrategy, CacheKeyGenerator


class TestDataCache:
    """数据缓存测试"""

    def test_cache_init(self):
        """测试缓存初始化"""
        cache = DataCache(redis_enabled=False)
        assert cache.redis_enabled is False
        assert cache.max_size == 100
        assert isinstance(cache.key_generator, CacheKeyGenerator)
        assert isinstance(cache.expiry_strategy, CacheExpiryStrategy)

    def test_cache_set_get(self):
        """测试缓存设置和获取"""
        cache = DataCache(redis_enabled=False)
        key = "test_key"
        value = "test_value"

        # 设置缓存
        result = cache.set(key, value, ttl=10)
        assert result is True

        # 获取缓存
        retrieved = cache.get(key)
        assert retrieved == value

    def test_cache_expiry(self):
        """测试缓存过期"""
        import time

        cache = DataCache(redis_enabled=False)
        key = "test_expiry"
        value = "test_value"

        # 设置缓存，TTL为1秒
        cache.set(key, value, ttl=1)

        # 立即获取，应该存在
        assert cache.get(key) == value

        # 等待过期
        time.sleep(1.5)

        # 再次获取，应该不存在
        assert cache.get(key) is None

    def test_cache_cleanup(self):
        """测试缓存清理"""
        cache = DataCache(max_size=3, redis_enabled=False)

        # 添加超过最大容量的缓存
        for i in range(5):
            cache.set(f"key{i}", f"value{i}", ttl=100)

        # 检查缓存数量
        assert len(cache.memory_cache) <= 3

    def test_cache_invalidate(self):
        """测试缓存失效"""
        cache = DataCache(redis_enabled=False)

        # 设置多个缓存
        cache.set("test_key1", "value1", ttl=100)
        cache.set("test_key2", "value2", ttl=100)
        cache.set("other_key", "value3", ttl=100)

        # 使包含"test"的缓存失效
        cache.invalidate("test")

        # 检查缓存是否被清除
        assert cache.get("test_key1") is None
        assert cache.get("test_key2") is None
        assert cache.get("other_key") == "value3"

    def test_cache_hs300_list(self):
        """测试沪深300列表缓存"""
        cache = DataCache(redis_enabled=False)
        hs300_list = [{"代码": "000001", "名称": "平安银行"}]

        # 缓存沪深300列表
        result = cache.cache_hs300_list(hs300_list)
        assert result is True

        # 获取沪深300列表
        retrieved = cache.get_hs300_list()
        assert retrieved == hs300_list

    def test_cache_realtime_data(self):
        """测试实时数据缓存"""
        cache = DataCache(redis_enabled=False)
        symbol = "000001"
        data = {"price": 10.0, "volume": 1000000}

        # 缓存实时数据
        result = cache.cache_realtime_data(symbol, data)
        assert result is True

        # 获取实时数据
        retrieved = cache.get_realtime_data(symbol)
        assert retrieved == data

    def test_cache_industry_stocks(self):
        """测试行业成分股缓存"""
        cache = DataCache(redis_enabled=False)
        industry = "银行"
        stocks = ["000001", "600036"]

        # 缓存行业成分股
        result = cache.cache_industry_stocks(industry, stocks)
        assert result is True

        # 获取行业成分股
        retrieved = cache.get_industry_stocks(industry)
        assert retrieved == stocks

    def test_signal_counter(self):
        """测试信号计数器"""
        cache = DataCache(redis_enabled=False)
        signal_name = "golden_cross"

        # 增加计数器
        count1 = cache.increment_signal_counter(signal_name)
        assert count1 == 1

        # 再次增加
        count2 = cache.increment_signal_counter(signal_name)
        assert count2 == 2

        # 获取计数器
        count3 = cache.get_signal_counter(signal_name)
        assert count3 == 2

    def test_clear(self):
        """测试清空缓存"""
        cache = DataCache(redis_enabled=False)

        # 设置缓存
        cache.set("key1", "value1", ttl=100)
        cache.set("key2", "value2", ttl=100)

        # 清空缓存
        cache.clear()

        # 检查缓存是否为空
        assert len(cache.memory_cache) == 0
        assert len(cache.cache_expiry) == 0

    def test_get_cache_singleton(self):
        """测试缓存单例"""
        cache1 = get_cache()
        cache2 = get_cache()
        assert cache1 is cache2

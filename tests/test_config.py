"""配置与存储测试"""
import sys
from pathlib import Path as SysPath

# 设置项目路径
sys.path.insert(0, str(SysPath(__file__).parent.parent / "src"))

# 系统导入

import pytest

# 项目导入
from stock_explorer.config.settings import (
    AlertConfig,
    RedisConfig,
    ScanConfig,
    SQLiteConfig,
    get_config,
)
from stock_explorer.data.cache import DataCache


class TestSettings:
    def test_scan_config_defaults(self):
        config = ScanConfig()
        assert config.hs300.interval == 5
        assert config.market.interval == 30

    def test_redis_config_defaults(self):
        config = RedisConfig()
        assert config.host == "localhost"
        assert config.port == 6379

    def test_sqlite_config_defaults(self):
        config = SQLiteConfig()
        assert config.path == "data/stock_explorer.db"

    def test_alert_config_defaults(self):
        config = AlertConfig()
        assert config.console is True
        assert config.file is True

    def test_get_config(self):
        config = get_config()
        assert config is not None


class TestDataCache:
    @pytest.fixture
    def cache(self):
        return DataCache(max_size=100)

    def test_cache_initialization(self, cache):
        assert cache is not None
        assert cache.max_size == 100

    def test_cache_set_and_get(self, cache):
        cache.set("key1", {"data": "value"})
        result = cache.get("key1")
        assert result is not None

    def test_cache_miss(self, cache):
        result = cache.get("nonexistent")
        assert result is None

    def test_cache_clear(self, cache):
        cache.set("key1", {"data": "value"})
        cache.clear()
        result = cache.get("key1")
        assert result is None

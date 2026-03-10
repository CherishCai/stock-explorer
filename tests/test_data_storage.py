"""数据存储模块测试"""

import os
import tempfile

import pandas as pd

from stock_explorer.data.storage import DataStorage, get_database, get_storage


class TestDataStorage:
    """数据存储测试"""

    def setup_method(self):
        """设置测试环境"""
        # 创建临时数据库文件
        self.temp_db = tempfile.mktemp(suffix=".db")
        self.storage = DataStorage(db_path=self.temp_db)

    def teardown_method(self):
        """清理测试环境"""
        # 删除临时数据库文件
        if os.path.exists(self.temp_db):
            os.remove(self.temp_db)

    def test_storage_init(self):
        """测试存储初始化"""
        assert isinstance(self.storage, DataStorage)

    def test_save_kline(self):
        """测试保存K线数据"""
        # 创建测试数据
        df = pd.DataFrame(
            {
                "date": ["2024-01-01", "2024-01-02"],
                "open": [10.0, 10.5],
                "high": [11.0, 11.5],
                "low": [9.5, 10.0],
                "close": [10.5, 11.0],
                "volume": [1000000, 1200000],
                "amount": [10500000, 13200000],
            }
        )

        # 保存K线数据
        self.storage.save_kline(df, "000001", "daily")

        # 验证数据是否保存成功
        retrieved = self.storage.get_kline("000001", "2024-01-01", "2024-01-31", "daily")
        assert not retrieved.empty
        assert len(retrieved) == 2

    def test_get_kline(self):
        """测试获取K线数据"""
        # 先保存数据
        df = pd.DataFrame(
            {
                "date": ["2024-01-01", "2024-01-02"],
                "open": [10.0, 10.5],
                "high": [11.0, 11.5],
                "low": [9.5, 10.0],
                "close": [10.5, 11.0],
                "volume": [1000000, 1200000],
                "amount": [10500000, 13200000],
            }
        )
        self.storage.save_kline(df, "000001", "daily")

        # 获取数据
        result = self.storage.get_kline("000001", "2024-01-01", "2024-01-31", "daily")
        assert not result.empty
        assert "date" in result.columns
        assert "close" in result.columns

    def test_save_signals(self):
        """测试保存信号记录"""
        # 创建测试信号
        signals = [
            {
                "timestamp": "2024-01-01 10:00:00",
                "symbol": "000001",
                "name": "平安银行",
                "signal_type": "technical",
                "direction": "buy",
                "strength": "strong",
                "price": 10.5,
                "message": "金叉信号",
                "metadata": {"indicator": "MA"},
            }
        ]

        # 保存信号
        self.storage.save_signals(signals)

        # 验证信号是否保存成功
        retrieved = self.storage.get_signals("2024-01-01 00:00:00", "2024-01-01 23:59:59")
        assert not retrieved.empty
        assert len(retrieved) == 1

    def test_get_signals(self):
        """测试获取信号记录"""
        # 先保存信号
        signals = [
            {
                "timestamp": "2024-01-01 10:00:00",
                "symbol": "000001",
                "name": "平安银行",
                "signal_type": "technical",
                "direction": "buy",
                "strength": "strong",
                "price": 10.5,
                "message": "金叉信号",
                "metadata": {"indicator": "MA"},
            }
        ]
        self.storage.save_signals(signals)

        # 获取信号
        result = self.storage.get_signals("2024-01-01 00:00:00", "2024-01-01 23:59:59")
        assert not result.empty
        assert "symbol" in result.columns
        assert "signal_type" in result.columns

    def test_save_alert(self):
        """测试保存告警记录"""
        # 先保存一个信号
        signals = [
            {
                "timestamp": "2024-01-01 10:00:00",
                "symbol": "000001",
                "name": "平安银行",
                "signal_type": "technical",
                "direction": "buy",
                "strength": "strong",
                "price": 10.5,
                "message": "金叉信号",
                "metadata": {"indicator": "MA"},
            }
        ]
        self.storage.save_signals(signals)

        # 获取信号ID
        signal_id = self.storage.get_signals("2024-01-01 00:00:00", "2024-01-01 23:59:59").iloc[0][
            "id"
        ]

        # 创建测试告警
        alert = {
            "signal_id": signal_id,
            "timestamp": "2024-01-01 10:00:00",
            "channel": "console",
            "status": "sent",
            "message": "金叉信号",
            "response": "Success",
        }

        # 保存告警
        self.storage.save_alert(alert)

        # 验证告警是否保存成功
        retrieved = self.storage.get_alerts("2024-01-01 00:00:00", "2024-01-01 23:59:59")
        assert not retrieved.empty
        assert len(retrieved) == 1

    def test_get_alerts(self):
        """测试获取告警记录"""
        # 先保存一个信号和告警
        signals = [
            {
                "timestamp": "2024-01-01 10:00:00",
                "symbol": "000001",
                "name": "平安银行",
                "signal_type": "technical",
                "direction": "buy",
                "strength": "strong",
                "price": 10.5,
                "message": "金叉信号",
                "metadata": {"indicator": "MA"},
            }
        ]
        self.storage.save_signals(signals)

        signal_id = self.storage.get_signals("2024-01-01 00:00:00", "2024-01-01 23:59:59").iloc[0][
            "id"
        ]

        alert = {
            "signal_id": signal_id,
            "timestamp": "2024-01-01 10:00:00",
            "channel": "console",
            "status": "sent",
            "message": "金叉信号",
            "response": "Success",
        }
        self.storage.save_alert(alert)

        # 获取告警
        result = self.storage.get_alerts("2024-01-01 00:00:00", "2024-01-01 23:59:59")
        assert not result.empty
        assert "channel" in result.columns
        assert "status" in result.columns

    def test_save_watchlist(self):
        """测试保存监控列表"""
        # 创建测试监控列表
        symbols = [
            {"symbol": "000001", "name": "平安银行", "category": "hs300", "enabled": 1},
            {"symbol": "600036", "name": "招商银行", "category": "hs300", "enabled": 1},
        ]

        # 保存监控列表
        self.storage.save_watchlist(symbols)

        # 验证监控列表是否保存成功
        retrieved = self.storage.get_watchlist()
        assert len(retrieved) == 2

    def test_get_watchlist(self):
        """测试获取监控列表"""
        # 先保存监控列表
        symbols = [
            {"symbol": "000001", "name": "平安银行", "category": "hs300", "enabled": 1},
            {"symbol": "600036", "name": "招商银行", "category": "hs300", "enabled": 1},
        ]
        self.storage.save_watchlist(symbols)

        # 获取监控列表
        result = self.storage.get_watchlist()
        assert len(result) == 2
        assert result[0]["symbol"] == "000001"
        assert result[1]["symbol"] == "600036"

    def test_clear_table(self):
        """测试清空表数据"""
        # 先保存一些数据
        df = pd.DataFrame(
            {
                "date": ["2024-01-01", "2024-01-02"],
                "open": [10.0, 10.5],
                "high": [11.0, 11.5],
                "low": [9.5, 10.0],
                "close": [10.5, 11.0],
                "volume": [1000000, 1200000],
                "amount": [10500000, 13200000],
            }
        )
        self.storage.save_kline(df, "000001", "daily")

        # 验证数据存在
        result = self.storage.get_kline("000001", "2024-01-01", "2024-01-31", "daily")
        assert not result.empty

        # 清空表
        self.storage.clear_table("kline_data")

        # 验证数据已清空
        result = self.storage.get_kline("000001", "2024-01-01", "2024-01-31", "daily")
        assert result.empty

    def test_vacuum(self):
        """测试数据库优化"""
        # 执行优化
        self.storage.vacuum()
        # 只要不抛出异常就算成功
        assert True

    def test_get_storage_singleton(self):
        """测试存储单例"""
        storage1 = get_storage()
        storage2 = get_storage()
        assert storage1 is storage2

    def test_get_database_alias(self):
        """测试数据库别名"""
        storage = get_storage()
        database = get_database()
        assert storage is database

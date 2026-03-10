"""信号检测器测试"""

import sys
from pathlib import Path

# 设置项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# 系统导入
import numpy as np
import pandas as pd
import pytest

# 项目导入
from stock_explorer.signal.indicators import TechnicalIndicators


class TestTechnicalIndicators:
    @pytest.fixture
    def sample_data(self):
        dates = pd.date_range("2024-01-01", periods=100, freq="D")
        np.random.seed(42)
        close = 100 + np.cumsum(np.random.randn(100) * 2)
        return pd.DataFrame({"收盘": close}, index=dates)

    def test_sma(self, sample_data):
        result = TechnicalIndicators.sma(sample_data["收盘"], period=20)
        assert len(result) == len(sample_data)
        assert not result.isna().all()

    def test_ema(self, sample_data):
        result = TechnicalIndicators.ema(sample_data["收盘"], period=20)
        assert len(result) == len(sample_data)
        assert not result.isna().all()

    def test_macd(self, sample_data):
        result = TechnicalIndicators.macd(sample_data["收盘"])
        assert isinstance(result, pd.DataFrame)
        assert "macd" in result.columns
        assert "signal" in result.columns
        assert "histogram" in result.columns

    def test_rsi(self, sample_data):
        result = TechnicalIndicators.rsi(sample_data["收盘"], period=14)
        assert len(result) == len(sample_data)
        assert result.max() <= 100
        assert result.min() >= 0


class TestSignalModels:
    def test_signal_type_enum_values(self):
        from stock_explorer.signal.base import SignalType

        signal_types = [e.value for e in SignalType]
        assert isinstance(signal_types, list)
        assert len(signal_types) > 0

    def test_signal_direction_enum_values(self):
        from stock_explorer.signal.base import SignalDirection

        directions = [e.value for e in SignalDirection]
        assert isinstance(directions, list)
        assert len(directions) > 0

"""数据获取器测试"""
import sys
from pathlib import Path
from unittest.mock import patch

# 设置项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# 系统导入

import pandas as pd
import pytest

# 项目导入
from stock_explorer.data.fetcher import DataFetcher


class TestDataFetcher:
    @pytest.fixture
    def fetcher(self):
        return DataFetcher()

    def test_fetcher_initialization(self, fetcher):
        assert fetcher is not None

    @patch("akshare.stock_zh_a_spot_em")
    def test_fetch_realtime_quotes_mock(self, mock_spot):
        mock_spot.return_value = pd.DataFrame({
            "代码": ["000001"],
            "名称": ["平安银行"],
            "最新价": [12.50],
        })

        fetcher = DataFetcher()
        result = fetcher.fetch_realtime_quotes()

        assert isinstance(result, pd.DataFrame)
        assert "代码" in result.columns or len(result) > 0

    @patch("akshare.stock_zh_a_hist")
    def test_fetch_historical_kline_mock(self, mock_hist):
        mock_hist.return_value = pd.DataFrame({
            "日期": ["2024-01-01", "2024-01-02"],
            "开盘": [10.0, 10.5],
            "收盘": [10.5, 11.0],
            "最高": [11.0, 11.5],
            "最低": [9.5, 10.0],
            "成交量": [1000000, 1200000],
        })

        fetcher = DataFetcher()
        result = fetcher.fetch_historical_kline(
            symbol="000001",
            start_date="2024-01-01",
            end_date="2024-01-31",
            period="daily",
            adjust="qfq",
        )

        assert isinstance(result, pd.DataFrame)
        assert "date" in result.columns

    @patch("akshare.stock_individual_fund_flow")
    def test_fetch_individual_fund_flow_mock(self, mock_fund):
        mock_fund.return_value = pd.DataFrame({
            "日期": ["2024-01-01"],
            "主力净流入": [1000000],
            "散户净流入": [-500000],
        })

        fetcher = DataFetcher()
        result = fetcher.fetch_individual_fund_flow("000001", "主板")

        assert isinstance(result, pd.DataFrame)

    @patch("akshare.index_stock_cons_csindex")
    def test_fetch_hs300_constituents_mock(self, mock_hs300):
        mock_hs300.return_value = pd.DataFrame({
            "代码": ["000001", "000002"],
            "名称": ["平安银行", "万科A"],
        })

        fetcher = DataFetcher()
        result = fetcher.fetch_hs300_constituents()

        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0


class TestDataFetcherIntegration:
    def test_fetcher_available(self):
        fetcher = DataFetcher()
        assert fetcher is not None
        assert hasattr(fetcher, "fetch_realtime_quotes")
        assert hasattr(fetcher, "fetch_historical_kline")

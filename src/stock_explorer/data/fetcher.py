"""数据获取模块 - 集成 akshare"""

import akshare as ak
import pandas as pd

from stock_explorer.exceptions import DataFetchError
from stock_explorer.logging.logger import get_logger
from stock_explorer.utils.data_utils import format_date, normalize_kline_data, validate_stock_symbol

logger = get_logger(__name__)


class DataFetcher:
    """数据获取器 - 集成 akshare"""

    def __init__(self):
        self.ak = ak

    def _fetch_data(self, func, *args, **kwargs) -> pd.DataFrame | None:
        """通用数据获取方法

        Args:
            func: akshare函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            DataFrame或None
        """
        try:
            result = func(*args, **kwargs)
            if isinstance(result, pd.DataFrame):
                logger.info(f"获取数据成功，返回 {len(result)} 条")
                return result
            return result
        except Exception as e:
            logger.error(f"获取数据失败: {e}")
            raise DataFetchError(f"数据获取失败: {e}") from e

    def fetch_realtime_quotes(self) -> pd.DataFrame:
        """获取全部A股实时行情"""
        try:
            df = self._fetch_data(self.ak.stock_zh_a_spot_em)
            return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        except DataFetchError:
            return pd.DataFrame()

    def fetch_realtime_limit(self) -> pd.DataFrame:
        """获取涨跌停股票列表"""
        try:
            df = self._fetch_data(self.ak.stock_zh_a_limit_em)
            return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        except DataFetchError:
            return pd.DataFrame()

    def fetch_historical_kline(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        period: str = "daily",
        adjust: str = "qfq",
    ) -> pd.DataFrame | None:
        """获取历史K线数据"""
        try:
            # 标准化股票代码
            symbol = validate_stock_symbol(symbol)
            # 格式化日期
            start_date = format_date(start_date)
            end_date = format_date(end_date)

            df = self._fetch_data(
                self.ak.stock_zh_a_hist,
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )

            if isinstance(df, pd.DataFrame) and not df.empty:
                # 标准化K线数据格式
                df = normalize_kline_data(df)
            return df
        except DataFetchError:
            return None

    def fetch_minute_kline(
        self, symbol: str, start_date: str, end_date: str, period: str = "1min"
    ) -> pd.DataFrame | None:
        """获取分钟K线数据"""
        try:
            # 标准化股票代码
            symbol = validate_stock_symbol(symbol)
            # 格式化日期
            start_date = format_date(start_date)
            end_date = format_date(end_date)

            df = self._fetch_data(
                self.ak.stock_zh_a_minute,
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
            )

            if isinstance(df, pd.DataFrame) and not df.empty:
                # 标准化K线数据格式
                df = normalize_kline_data(df)
            return df
        except DataFetchError:
            return None

    def fetch_individual_fund_flow(self, symbol: str, market: str = "A股") -> pd.DataFrame:
        """获取个股资金流向"""
        try:
            # 标准化股票代码
            symbol = validate_stock_symbol(symbol)
            df = self._fetch_data(self.ak.stock_individual_fund_flow, symbol=symbol, market=market)
            return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        except DataFetchError:
            return pd.DataFrame()

    def fetch_sector_fund_flow(self) -> pd.DataFrame:
        """获取行业资金流向"""
        try:
            df = self._fetch_data(self.ak.stock_sector_fund_flow_rank)
            return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        except DataFetchError:
            return pd.DataFrame()

    def fetch_lhb_detail(self, date: str) -> pd.DataFrame:
        """获取龙虎榜详情"""
        try:
            # 格式化日期
            date = format_date(date)
            df = self._fetch_data(self.ak.stock_lhb_stock_em, date=date)
            return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        except DataFetchError:
            return pd.DataFrame()

    def fetch_lhb_summary(self, date: str) -> pd.DataFrame:
        """获取龙虎榜汇总"""
        try:
            # 格式化日期
            date = format_date(date)
            df = self._fetch_data(self.ak.stock_lhb_summary_em, date=date)
            return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        except DataFetchError:
            return pd.DataFrame()

    def fetch_lhb_institution(self, date: str) -> pd.DataFrame:
        """获取机构龙虎榜"""
        try:
            # 格式化日期
            date = format_date(date)
            df = self._fetch_data(self.ak.stock_lhb_institution_detail_em, date=date)
            return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        except DataFetchError:
            return pd.DataFrame()

    def fetch_margin_detail(self, date: str) -> pd.DataFrame:
        """获取融资融券详情"""
        try:
            # 格式化日期
            date = format_date(date)
            df = self._fetch_data(self.ak.stock_margin_detail_em, date=date)
            return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        except DataFetchError:
            return pd.DataFrame()

    def fetch_margin_stock(self, symbol: str) -> pd.DataFrame:
        """获取个股融资融券数据"""
        try:
            # 标准化股票代码
            symbol = validate_stock_symbol(symbol)
            df = self._fetch_data(self.ak.stock_margin_underlying_sec_em, symbol=symbol)
            return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        except DataFetchError:
            return pd.DataFrame()

    def fetch_holder_trade(self, symbol: str) -> pd.DataFrame:
        """获取股东增减持数据"""
        try:
            # 标准化股票代码
            symbol = validate_stock_symbol(symbol)
            df = self._fetch_data(self.ak.stock_holder_trade, symbol=symbol)
            return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        except DataFetchError:
            return pd.DataFrame()

    def fetch_bid_ask(self, symbol: str) -> pd.DataFrame:
        """获取订单簿数据"""
        try:
            # 标准化股票代码
            symbol = validate_stock_symbol(symbol)
            df = self._fetch_data(self.ak.stock_bid_ask_em, symbol=symbol)
            return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        except DataFetchError:
            return pd.DataFrame()

    def fetch_stock_info(self, symbol: str) -> dict:
        """获取个股信息"""
        try:
            # 标准化股票代码
            symbol = validate_stock_symbol(symbol)
            df = self._fetch_data(self.ak.stock_individual_info_em, symbol=symbol)
            if isinstance(df, pd.DataFrame) and not df.empty:
                stock_info: dict = df.to_dict(orient="records")[0]
                return stock_info
            logger.warning(f"未获取到 {symbol} 个股信息")
            return {}
        except DataFetchError:
            return {}

    def fetch_stock_fina_indicator(self, symbol: str) -> pd.DataFrame:
        """获取财务指标"""
        try:
            # 标准化股票代码
            symbol = validate_stock_symbol(symbol)
            df = self._fetch_data(self.ak.stock_financial_analysis_indicator, symbol=symbol)
            return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        except DataFetchError:
            return pd.DataFrame()

    def fetch_hs300_constituents(self) -> pd.DataFrame:
        """获取沪深300成分股"""
        try:
            df = self._fetch_data(self.ak.index_stock_cons_csindex, symbol="000300")
            return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        except DataFetchError:
            return pd.DataFrame()

    def fetch_industry_classification(self) -> pd.DataFrame:
        """获取行业分类"""
        try:
            df = self._fetch_data(self.ak.stock_board_industry_name_em)
            return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        except DataFetchError:
            return pd.DataFrame()

    def fetch_industry_spot(self) -> pd.DataFrame:
        """获取行业板块实时行情"""
        try:
            df = self._fetch_data(self.ak.stock_board_industry_spot_em)
            return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        except DataFetchError:
            return pd.DataFrame()

    def fetch_industry_hist(self, industry: str, start: str, end: str) -> pd.DataFrame:
        """获取行业指数历史数据"""
        try:
            # 格式化日期
            start = format_date(start)
            end = format_date(end)
            df = self._fetch_data(
                self.ak.stock_board_industry_hist_em, board=industry, start_date=start, end_date=end
            )
            if isinstance(df, pd.DataFrame) and not df.empty:
                # 标准化K线数据格式
                df = normalize_kline_data(df)
            return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        except DataFetchError:
            return pd.DataFrame()

    def fetch_concept_spot(self) -> pd.DataFrame:
        """获取概念板块实时行情"""
        try:
            df = self._fetch_data(self.ak.stock_board_concept_spot_em)
            return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        except DataFetchError:
            return pd.DataFrame()

    def fetch_index_spot(self) -> pd.DataFrame:
        """获取大盘指数实时行情"""
        try:
            df = self._fetch_data(self.ak.stock_zh_index_spot)
            return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        except DataFetchError:
            return pd.DataFrame()

    def fetch_stock_list(self) -> pd.DataFrame:
        """获取全市场股票列表"""
        try:
            df = self._fetch_data(self.ak.stock_zh_a_spot_em)
            return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        except DataFetchError:
            return pd.DataFrame()

    def fetch_stock_board_industry_cons(self, industry: str) -> pd.DataFrame:
        """获取行业成分股"""
        try:
            df = self._fetch_data(self.ak.stock_board_industry_cons_em, symbol=industry)
            return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        except DataFetchError:
            return pd.DataFrame()


# 单例模式
_fetcher_instance: DataFetcher | None = None


def get_fetcher() -> DataFetcher:
    """获取数据获取器单例"""
    global _fetcher_instance
    if _fetcher_instance is None:
        _fetcher_instance = DataFetcher()
    return _fetcher_instance

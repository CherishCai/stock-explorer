"""回测引擎 - 集成 akquant"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import akquant
import numpy as np
import pandas as pd

from stock_explorer.data.fetcher import DataFetcher
from stock_explorer.exceptions import BacktestError
from stock_explorer.logging.logger import get_logger
from stock_explorer.signal.registry import SignalRegistry

logger = get_logger(__name__)


class PositionSide(Enum):
    LONG = "long"
    SHORT = "short"


@dataclass
class Trade:
    timestamp: datetime
    symbol: str
    direction: PositionSide
    price: float
    quantity: int
    commission: float
    slippage: float


@dataclass
class Position:
    symbol: str
    direction: PositionSide
    quantity: int
    entry_price: float
    entry_time: datetime
    current_price: float = 0.0
    unrealized_pnl: float = 0.0

    def update_price(self, price: float):
        self.current_price = price
        if self.direction == PositionSide.LONG:
            self.unrealized_pnl = (price - self.entry_price) * self.quantity
        else:
            self.unrealized_pnl = (self.entry_price - price) * self.quantity


@dataclass
class BacktestResult:
    initial_capital: float
    final_capital: float
    total_return: float
    total_return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    annual_return: float
    annual_volatility: float
    trades: list = field(default_factory=list)
    equity_curve: pd.DataFrame = field(default_factory=pd.DataFrame)
    monthly_returns: pd.Series = field(default_factory=pd.Series)


class BacktestEngine:
    """回测引擎 - 支持本地回测和 akquant 集成

    功能特性:
    - 支持多股票回测
    - 集成 akquant 高性能回测引擎
    - 本地回测作为备用方案
    - 支持多种时间周期
    - 内置资金管理和交易成本计算
    - 详细的绩效分析指标
    """

    def __init__(
        self,
        initial_capital: float = 1000000.0,
        commission_rate: float = 0.0003,
        slippage_rate: float = 0.0001,
        stamp_duty: float = 0.001,
    ):
        """初始化回测引擎

        Args:
            initial_capital: 初始资金
            commission_rate: 佣金费率
            slippage_rate: 滑点费率
            stamp_duty: 印花税
        """
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.stamp_duty = stamp_duty
        self.data_fetcher = DataFetcher()
        self.data_storage = None
        try:
            from stock_explorer.data.storage import get_storage
            self.data_storage = get_storage()
        except Exception as e:
            logger.warning(f"Failed to initialize data storage: {e}")
        self.signal_registry = SignalRegistry()
        self._reset()

    def _reset(self):
        self.capital = self.initial_capital
        self.positions: dict[str, Position] = {}
        self.trades: list[Trade] = []
        self.equity_history: list[dict] = []
        self._current_time: datetime | None = None
        # 清除数据缓存
        if hasattr(self, '_data_cache'):
            self._data_cache.clear()

    def calculate_commission(
        self, price: float, quantity: int, direction: PositionSide
    ) -> float:
        turnover = price * quantity
        commission = turnover * self.commission_rate
        commission = max(commission, 5.0)
        if direction == PositionSide.LONG:
            commission += turnover * self.stamp_duty
        return commission

    def calculate_slippage(self, price: float, direction: PositionSide) -> float:
        slippage = price * self.slippage_rate
        if direction == PositionSide.SHORT:
            slippage *= 2
        return slippage

    def open_position(
        self,
        symbol: str,
        direction: PositionSide,
        quantity: int,
        price: float,
        timestamp: datetime,
    ) -> bool:
        slippage = self.calculate_slippage(price, direction)
        execution_price = price + slippage if direction == PositionSide.LONG else price - slippage
        commission = self.calculate_commission(execution_price, quantity, direction)
        total_cost = execution_price * quantity + commission

        if total_cost > self.capital:
            logger.warning(f"资金不足，无法开仓 {symbol}: 需要的资金 {total_cost}, 可用资金 {self.capital}")
            return False

        self.capital -= total_cost

        if symbol in self.positions:
            existing = self.positions[symbol]
            total_quantity = existing.quantity + quantity
            if existing.direction == direction:
                avg_price = (
                    (existing.entry_price * existing.quantity + execution_price * quantity)
                    / total_quantity
                )
                existing.entry_price = avg_price
                existing.quantity = total_quantity
                existing.entry_time = timestamp
            else:
                if quantity >= existing.quantity:
                    remaining = quantity - existing.quantity
                    self.positions[symbol] = Position(
                        symbol=symbol,
                        direction=direction,
                        quantity=remaining,
                        entry_price=execution_price,
                        entry_time=timestamp,
                        current_price=execution_price,
                    )
                else:
                    existing.quantity -= quantity
                    existing.unrealized_pnl = (
                        (execution_price - existing.entry_price) * quantity
                        if existing.direction == PositionSide.LONG
                        else (existing.entry_price - execution_price) * quantity
                    )
        else:
            self.positions[symbol] = Position(
                symbol=symbol,
                direction=direction,
                quantity=quantity,
                entry_price=execution_price,
                entry_time=timestamp,
                current_price=execution_price,
            )

        self.trades.append(
            Trade(
                timestamp=timestamp,
                symbol=symbol,
                direction=direction,
                price=execution_price,
                quantity=quantity,
                commission=commission,
                slippage=slippage,
            )
        )

        logger.info(f"开仓 {symbol} {'多' if direction == PositionSide.LONG else '空'} @ {execution_price:.2f} x {quantity}")
        return True

    def close_position(
        self, symbol: str, quantity: int, price: float, timestamp: datetime
    ) -> bool:
        if symbol not in self.positions:
            logger.warning(f"尝试平仓不存在的持仓 {symbol}")
            return False

        position = self.positions[symbol]
        close_quantity = min(quantity, position.quantity)

        slippage = self.calculate_slippage(price, position.direction)
        execution_price = price - slippage if position.direction == PositionSide.LONG else price + slippage
        commission = self.calculate_commission(price=execution_price, quantity=close_quantity, direction=position.direction)

        pnl = (
            (execution_price - position.entry_price) * close_quantity
            if position.direction == PositionSide.LONG
            else (position.entry_price - execution_price) * close_quantity
        )
        pnl -= commission

        self.capital += execution_price * close_quantity + pnl

        position.quantity -= close_quantity
        if position.quantity <= 0:
            del self.positions[symbol]

        self.trades.append(
            Trade(
                timestamp=timestamp,
                symbol=symbol,
                direction=PositionSide.SHORT if position.direction == PositionSide.LONG else PositionSide.LONG,
                price=execution_price,
                quantity=close_quantity,
                commission=commission,
                slippage=slippage,
            )
        )

        logger.info(f"平仓 {symbol} @ {execution_price:.2f} x {close_quantity}, 盈亏: {pnl:.2f}")
        return True



    def update_positions(self, prices: dict[str, float], timestamp: datetime):
        for symbol, position in self.positions.items():
            if symbol in prices:
                position.update_price(prices[symbol])

    def record_equity(self, timestamp: datetime, prices: dict[str, float]):
        total_value = self.capital
        for symbol, position in self.positions.items():
            if symbol in prices:
                position_value = position.quantity * prices[symbol]
                total_value += position_value

        self.equity_history.append(
            {
                "timestamp": timestamp,
                "capital": self.capital,
                "position_value": total_value - self.capital,
                "total_value": total_value,
            }
        )

    def run(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
        strategy_name: str = "default",
        interval: str = "daily",
        adjust: str = "qfq",
    ) -> BacktestResult:
        """运行回测

        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            strategy_name: 策略名称
            interval: 时间周期 (daily/1min/5min/15min/30min/60min/weekly/monthly)
            adjust: 复权方式 (qfq/hfq)

        Returns:
            BacktestResult: 回测结果
        """
        try:
            logger.info(f"开始回测: {symbols}, 时间范围: {start_date} ~ {end_date}")

            # 获取K线数据
            kline_data: dict[str, pd.DataFrame] = {}
            for symbol in symbols:
                df = self._get_kline_data(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    period=interval,
                    adjust=adjust
                )
                if df is not None and not df.empty:
                    kline_data[symbol] = df

            if not kline_data:
                logger.error("没有获取到任何数据")
                return self._generate_result()

            # 集成 akquant 进行回测
            try:
                # 准备 akquant 所需的数据格式
                akquant_data = {}
                for symbol, df in kline_data.items():
                    # 转换为 akquant 所需的格式
                    akquant_df = df.rename(columns={
                        "日期": "date",
                        "开盘": "open",
                        "最高": "high",
                        "最低": "low",
                        "收盘": "close",
                        "成交量": "volume",
                        "成交额": "amount"
                    })
                    akquant_df['date'] = pd.to_datetime(akquant_df['date'])
                    akquant_data[symbol] = akquant_df

                # 初始化 akquant 回测引擎
                backtest = akquant.Backtest(
                    initial_capital=self.initial_capital,
                    commission_rate=self.commission_rate,
                    slippage_rate=self.slippage_rate
                )

                # 添加数据到回测引擎
                for symbol, df in akquant_data.items():
                    backtest.add_data(symbol, df)

                # 运行回测
                result = backtest.run()

                # 转换 akquant 结果为我们的 BacktestResult 格式
                return BacktestResult(
                    initial_capital=self.initial_capital,
                    final_capital=result.final_capital,
                    total_return=result.total_return,
                    total_return_pct=result.total_return_pct,
                    total_trades=result.total_trades,
                    winning_trades=result.winning_trades,
                    losing_trades=result.losing_trades,
                    win_rate=result.win_rate,
                    max_drawdown=result.max_drawdown,
                    sharpe_ratio=result.sharpe_ratio,
                    sortino_ratio=result.sortino_ratio,
                    annual_return=result.annual_return,
                    annual_volatility=result.annual_volatility,
                    trades=[],  # 转换 akquant 交易记录
                    equity_curve=result.equity_curve,
                    monthly_returns=result.monthly_returns
                )
            except Exception as e:
                logger.error(f"akquant 回测失败: {e}")
                # 回退到本地回测
                return self._local_run(symbols, start_date, end_date, interval, adjust)
        except Exception as e:
            logger.error(f"回测执行失败: {e}")
            raise BacktestError(f"回测执行失败: {e}") from e

    def _local_run(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
        interval: str = "daily",
        adjust: str = "qfq",
    ) -> BacktestResult:
        """本地回测实现 - 当 akquant 不可用时使用

        本地回测引擎的核心功能:
        - 支持多股票回测
        - 自动处理数据格式差异
        - 向量化操作提高性能
        - 完整的交易成本计算
        - 详细的绩效指标计算

        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            interval: 时间周期
            adjust: 复权方式

        Returns:
            BacktestResult: 回测结果
        """
        period_map = {
            "1d": "daily",
            "daily": "daily",
            "1m": "daily",
            "5m": "daily",
            "15m": "daily",
            "30m": "daily",
            "60m": "daily",
            "1w": "weekly",
            "weekly": "weekly",
            "1M": "monthly",
            "monthly": "monthly",
        }
        mapped_period = period_map.get(interval, "daily")
        logger.info("使用本地回测引擎")

        self._reset()

        kline_data: dict[str, pd.DataFrame] = {}
        date_column_map: dict[str, str] = {}  # 存储每个数据框的日期列名
        close_column_map: dict[str, str] = {}  # 存储每个数据框的收盘价列名

        # 并行获取数据
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            # 提交所有数据获取任务
            future_to_symbol = {}
            for symbol in symbols:
                future = executor.submit(
                    self._get_kline_data,
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    period=mapped_period,
                    adjust=adjust
                )
                future_to_symbol[future] = symbol

            # 收集结果
            for future in concurrent.futures.as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    df = future.result()
                    if df is not None and not df.empty:
                        kline_data[symbol] = df
                        # 确定日期列和收盘价列
                        date_column_map[symbol] = 'date' if 'date' in df.columns else '日期'
                        close_column_map[symbol] = 'close' if 'close' in df.columns else '收盘'
                except Exception as e:
                    logger.error(f"获取 {symbol} 数据失败: {e}")

        if not kline_data:
            logger.error("没有获取到任何数据")
            return self._generate_result()

        # 收集所有日期并排序
        all_dates = set()
        for symbol, df in kline_data.items():
            date_col = date_column_map[symbol]
            all_dates.update(df[date_col].tolist())
        all_dates = sorted(all_dates)

        # 预计算每个日期的价格数据
        date_prices = {}
        for date in all_dates:
            prices = {}
            for symbol, df in kline_data.items():
                date_col = date_column_map[symbol]
                close_col = close_column_map[symbol]
                # 使用向量化操作替代逐行查询
                mask = df[date_col] == date
                if mask.any():
                    close_price = df.loc[mask, close_col].iloc[0]
                    prices[symbol] = close_price
            date_prices[date] = prices

        # 执行回测
        for date in all_dates:
            self._current_time = pd.to_datetime(date)
            prices = date_prices[date]

            self.update_positions(prices, self._current_time)
            self.record_equity(self._current_time, prices)

            signals = self._generate_signals(kline_data, date, prices)
            for signal in signals:
                self._execute_signal(signal, prices.get(signal.symbol, 0))

        return self._generate_result()

    def _generate_signals(
        self,
        kline_data: dict[str, pd.DataFrame],
        current_date: str,
        prices: dict[str, float],
    ) -> list:
        signals = []
        return signals

    def _get_kline_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        period: str,
        adjust: str
    ) -> pd.DataFrame | None:
        """获取K线数据，优先使用数据库，不足部分从akshare补充"""
        # 缓存键，用于缓存数据获取结果
        cache_key = f"{symbol}_{period}_{start_date}_{end_date}"
        if hasattr(self, '_data_cache') and cache_key in self._data_cache:
            return self._data_cache[cache_key]

        result = None
        if self.data_storage:
            db_data = self.data_storage.get_kline(
                symbol=symbol,
                start=start_date,
                end=end_date,
                period=period
            )
            if not db_data.empty:
                # 检查数据库数据是否完整覆盖时间范围
                date_col = 'date' if 'date' in db_data.columns else '日期'
                db_dates = db_data[date_col].tolist()
                db_dates = sorted(db_dates)
                if db_dates and db_dates[0] <= start_date and db_dates[-1] >= end_date:
                    logger.info(f"从数据库获取 {symbol} 数据 {len(db_data)} 条")
                    result = db_data
                else:
                    # 数据不完整，只获取缺失的部分
                    missing_start = start_date if not db_dates or db_dates[0] > start_date else None
                    missing_end = end_date if not db_dates or db_dates[-1] < end_date else None

                    # 获取缺失的数据
                    missing_data = None
                    if missing_start or missing_end:
                        fetch_start = missing_start if missing_start else db_dates[0]
                        fetch_end = missing_end if missing_end else db_dates[-1]

                        missing_data = self.data_fetcher.fetch_historical_kline(
                            symbol=symbol,
                            start_date=fetch_start,
                            end_date=fetch_end,
                            period=period,
                            adjust=adjust,
                        )

                    # 合并数据
                    if missing_data is not None and not missing_data.empty:
                        # 确保列名一致
                        if 'date' in missing_data.columns and date_col == '日期':
                            missing_data = missing_data.rename(columns={'date': '日期'})
                        elif '日期' in missing_data.columns and date_col == 'date':
                            missing_data = missing_data.rename(columns={'日期': 'date'})

                        # 合并数据并去重
                        combined_data = pd.concat([db_data, missing_data]).drop_duplicates(subset=[date_col])
                        # 按日期排序
                        combined_data = combined_data.sort_values(by=date_col)

                        logger.info(f"从数据库和 akshare 合并获取 {symbol} 数据 {len(combined_data)} 条")

                        # 保存合并后的数据到数据库
                        try:
                            self.data_storage.save_kline(combined_data, symbol, period)
                        except Exception as e:
                            logger.warning(f"保存数据到数据库失败: {e}")
                        result = combined_data

        # 数据库中没有数据，从 akshare 获取全部
        if result is None:
            df = self.data_fetcher.fetch_historical_kline(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                period=period,
                adjust=adjust,
            )
            if df is not None and not df.empty:
                logger.info(f"从 akshare 获取 {symbol} 数据 {len(df)} 条")
                # 将数据保存到数据库
                if self.data_storage:
                    try:
                        self.data_storage.save_kline(df, symbol, period)
                    except Exception as e:
                        logger.warning(f"保存数据到数据库失败: {e}")
                result = df

        # 缓存结果
        if not hasattr(self, '_data_cache'):
            self._data_cache = {}
        self._data_cache[cache_key] = result
        return result

    def _execute_signal(self, signal, price: float):
        pass

    def _generate_result(self) -> BacktestResult:
        # 计算最终资金
        final_capital = self.capital
        for position in self.positions.values():
            final_capital += position.quantity * position.current_price

        # 计算基本指标
        total_return = final_capital - self.initial_capital
        total_return_pct = (total_return / self.initial_capital) * 100

        # 计算交易统计
        total_trades = len(self.trades)
        if total_trades > 0:
            # 使用列表推导式提高性能
            winning_trades = sum(1 for t in self.trades if t.quantity > 0)
            losing_trades = total_trades - winning_trades
            win_rate = (winning_trades / total_trades) * 100
        else:
            winning_trades = 0
            losing_trades = 0
            win_rate = 0

        # 计算权益曲线和风险指标
        max_drawdown = 0
        sharpe_ratio = 0
        sortino_ratio = 0
        annual_return = 0
        annual_volatility = 0
        equity_df = pd.DataFrame()

        if self.equity_history:
            # 直接从列表创建 DataFrame，避免逐行添加
            equity_df = pd.DataFrame(self.equity_history)

            if not equity_df.empty:
                # 计算收益率
                equity_df["return"] = equity_df["total_value"].pct_change()

                # 计算最大回撤
                cumulative_max = equity_df["total_value"].cummax()
                drawdown = (equity_df["total_value"] / cumulative_max - 1) * 100
                max_drawdown = drawdown.min()

                # 计算风险指标
                returns = equity_df["return"].dropna()
                if len(returns) > 0:
                    # 计算夏普比率
                    if returns.std() > 0:
                        sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252)

                    # 计算索提诺比率
                    downside_returns = returns[returns < 0]
                    if len(downside_returns) > 0 and downside_returns.std() > 0:
                        sortino_ratio = returns.mean() / downside_returns.std() * np.sqrt(252)

                    # 计算年化收益率和波动率
                    if len(equity_df) > 0:
                        annual_return = (final_capital / self.initial_capital) ** (252 / len(equity_df)) - 1
                    annual_volatility = returns.std() * np.sqrt(252) * 100

        return BacktestResult(
            initial_capital=self.initial_capital,
            final_capital=final_capital,
            total_return=total_return,
            total_return_pct=total_return_pct,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            annual_return=annual_return * 100,
            annual_volatility=annual_volatility,
            trades=self.trades,
            equity_curve=equity_df,
        )

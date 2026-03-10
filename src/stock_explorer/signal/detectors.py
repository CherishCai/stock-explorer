"""技术面信号检测器"""

from stock_explorer.signal.base import (
    Signal,
    SignalDirection,
    SignalStrength,
    SignalType,
)
from stock_explorer.signal.framework import KlineBasedDetector, QuoteBasedDetector
from stock_explorer.signal.indicators import TechnicalIndicators


class GoldenCrossDetector(KlineBasedDetector):
    """金叉检测器 - MA5上穿MA20"""

    name = "golden_cross"
    signal_type = SignalType.TECHNICAL
    short_period = 5
    long_period = 20

    def __init__(self, short_period: int = 5, long_period: int = 20):
        super().__init__()
        self.short_period = short_period
        self.long_period = long_period

    def _validate_data(self, data: dict) -> bool:
        """验证数据"""
        kline = data.get("kline")
        return kline is not None and len(kline) >= self.long_period + 1

    def _perform_detection(self, data: dict) -> Signal | None:
        """执行检测"""
        df = data["df"]
        close = df["close"] if "close" in df.columns else df["收盘"]

        ma_short = TechnicalIndicators.sma(close, self.short_period)
        ma_long = TechnicalIndicators.sma(close, self.long_period)

        if ma_short.iloc[-2] <= ma_long.iloc[-2] and ma_short.iloc[-1] > ma_long.iloc[-1]:
            return Signal(
                symbol=data.get("symbol", ""),
                name=data.get("name", ""),
                signal_type=self.signal_type,
                direction=SignalDirection.BUY,
                strength=SignalStrength.MEDIUM,
                price=float(close.iloc[-1]),
                message=f"金叉信号: MA{self.short_period}上穿MA{self.long_period}",
                metadata={"ma_short": float(ma_short.iloc[-1]), "ma_long": float(ma_long.iloc[-1])},
            )
        return None


class DeathCrossDetector(KlineBasedDetector):
    """死叉检测器 - MA5下穿MA20"""

    name = "death_cross"
    signal_type = SignalType.TECHNICAL
    short_period = 5
    long_period = 20

    def __init__(self, short_period: int = 5, long_period: int = 20):
        super().__init__()
        self.short_period = short_period
        self.long_period = long_period

    def _validate_data(self, data: dict) -> bool:
        """验证数据"""
        kline = data.get("kline")
        return kline is not None and len(kline) >= self.long_period + 1

    def _perform_detection(self, data: dict) -> Signal | None:
        """执行检测"""
        df = data["df"]
        close = df["close"] if "close" in df.columns else df["收盘"]

        ma_short = TechnicalIndicators.sma(close, self.short_period)
        ma_long = TechnicalIndicators.sma(close, self.long_period)

        if ma_short.iloc[-2] >= ma_long.iloc[-2] and ma_short.iloc[-1] < ma_long.iloc[-1]:
            return Signal(
                symbol=data.get("symbol", ""),
                name=data.get("name", ""),
                signal_type=self.signal_type,
                direction=SignalDirection.SELL,
                strength=SignalStrength.MEDIUM,
                price=float(close.iloc[-1]),
                message=f"死叉信号: MA{self.short_period}下穿MA{self.long_period}",
                metadata={"ma_short": float(ma_short.iloc[-1]), "ma_long": float(ma_long.iloc[-1])},
            )
        return None


class RSIDetector(KlineBasedDetector):
    """RSI超买超卖检测器"""

    name = "rsi"
    signal_type = SignalType.TECHNICAL
    period = 14
    overbought = 70
    oversold = 30

    def __init__(self, period: int = 14, overbought: float = 70, oversold: float = 30):
        super().__init__()
        self.period = period
        self.overbought = overbought
        self.oversold = oversold

    def _validate_data(self, data: dict) -> bool:
        """验证数据"""
        kline = data.get("kline")
        return kline is not None and len(kline) >= self.period + 1

    def _perform_detection(self, data: dict) -> Signal | None:
        """执行检测"""
        df = data["df"]
        close = df["close"] if "close" in df.columns else df["收盘"]

        rsi = TechnicalIndicators.rsi(close, self.period)
        current_rsi = rsi.iloc[-1]

        if current_rsi < self.oversold:
            strength = SignalStrength.STRONG if current_rsi < 20 else SignalStrength.MEDIUM
            return Signal(
                symbol=data.get("symbol", ""),
                name=data.get("name", ""),
                signal_type=self.signal_type,
                direction=SignalDirection.BUY,
                strength=strength,
                price=float(close.iloc[-1]),
                message=f"RSI超卖信号: RSI={current_rsi:.2f}",
                metadata={"rsi": float(current_rsi)},
            )
        elif current_rsi > self.overbought:
            strength = SignalStrength.STRONG if current_rsi > 80 else SignalStrength.MEDIUM
            return Signal(
                symbol=data.get("symbol", ""),
                name=data.get("name", ""),
                signal_type=self.signal_type,
                direction=SignalDirection.SELL,
                strength=strength,
                price=float(close.iloc[-1]),
                message=f"RSI超买信号: RSI={current_rsi:.2f}",
                metadata={"rsi": float(current_rsi)},
            )
        return None


class VolumeSurgeDetector(KlineBasedDetector):
    """放量异动检测器"""

    name = "volume_surge"
    signal_type = SignalType.TECHNICAL
    surge_ratio = 2.0

    def __init__(self, surge_ratio: float = 2.0):
        super().__init__()
        self.surge_ratio = surge_ratio

    def _validate_data(self, data: dict) -> bool:
        """验证数据"""
        kline = data.get("kline")
        return kline is not None and len(kline) >= 5

    def _perform_detection(self, data: dict) -> Signal | None:
        """执行检测"""
        df = data["df"]
        volume_col = "volume" if "volume" in df.columns else "成交量"
        close_col = "close" if "close" in df.columns else "收盘"

        if volume_col not in df.columns:
            return None

        recent_volume = df[volume_col].iloc[-1]
        avg_volume = df[volume_col].iloc[-5:-1].mean()

        if avg_volume > 0 and recent_volume / avg_volume >= self.surge_ratio:
            return Signal(
                symbol=data.get("symbol", ""),
                name=data.get("name", ""),
                signal_type=self.signal_type,
                direction=SignalDirection.BUY,
                strength=SignalStrength.MEDIUM,
                price=float(df[close_col].iloc[-1]),
                message=f"放量信号: 成交量放大{recent_volume / avg_volume:.1f}倍",
                metadata={"volume_ratio": float(recent_volume / avg_volume)},
            )
        return None


class LimitUpDetector(QuoteBasedDetector):
    """涨停检测器"""

    name = "limit_up"
    signal_type = SignalType.SENTIMENT

    def _validate_data(self, data: dict) -> bool:
        """验证数据"""
        quote = data.get("quote")
        return quote is not None

    def _perform_detection(self, data: dict) -> Signal | None:
        """执行检测"""
        quote = data.get("quote", {})
        change_pct = quote.get("涨跌幅", quote.get("change_pct", 0))
        if change_pct >= 9.9:
            return Signal(
                symbol=data.get("symbol", ""),
                name=data.get("name", ""),
                signal_type=self.signal_type,
                direction=SignalDirection.BUY,
                strength=SignalStrength.STRONG,
                price=float(quote.get("最新价", quote.get("price", 0))),
                message="涨停信号",
                metadata={"change_pct": change_pct},
            )
        return None


class LimitDownDetector(QuoteBasedDetector):
    """跌停检测器"""

    name = "limit_down"
    signal_type = SignalType.SENTIMENT

    def _validate_data(self, data: dict) -> bool:
        """验证数据"""
        quote = data.get("quote")
        return quote is not None

    def _perform_detection(self, data: dict) -> Signal | None:
        """执行检测"""
        quote = data.get("quote", {})
        change_pct = quote.get("涨跌幅", quote.get("change_pct", 0))
        if change_pct <= -9.9:
            return Signal(
                symbol=data.get("symbol", ""),
                name=data.get("name", ""),
                signal_type=self.signal_type,
                direction=SignalDirection.SELL,
                strength=SignalStrength.STRONG,
                price=float(quote.get("最新价", quote.get("price", 0))),
                message="跌停信号",
                metadata={"change_pct": change_pct},
            )
        return None


class BreakoutDetector(KlineBasedDetector):
    """突破检测器 - N日新高"""

    name = "breakout"
    signal_type = SignalType.TECHNICAL
    lookback_period = 20

    def __init__(self, lookback_period: int = 20):
        super().__init__()
        self.lookback_period = lookback_period

    def _validate_data(self, data: dict) -> bool:
        """验证数据"""
        kline = data.get("kline")
        return kline is not None and len(kline) >= self.lookback_period + 1

    def _perform_detection(self, data: dict) -> Signal | None:
        """执行检测"""
        df = data["df"]
        high_col = "high" if "high" in df.columns else "最高"
        close_col = "close" if "close" in df.columns else "收盘"

        if high_col not in df.columns:
            return None

        highest = df[high_col].iloc[-self.lookback_period : -1].max()
        current_high = df[high_col].iloc[-1]

        if current_high > highest:
            return Signal(
                symbol=data.get("symbol", ""),
                name=data.get("name", ""),
                signal_type=self.signal_type,
                direction=SignalDirection.BUY,
                strength=SignalStrength.STRONG,
                price=float(df[close_col].iloc[-1]),
                message=f"突破{self.lookback_period}日新高",
                metadata={"highest": float(highest), "current": float(current_high)},
            )
        return None

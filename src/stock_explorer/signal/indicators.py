"""技术指标计算模块"""

import numpy as np
import pandas as pd


class TechnicalIndicators:
    """技术指标计算"""

    @staticmethod
    def sma(series: pd.Series, period: int) -> pd.Series:
        """简单移动平均 (SMA)"""
        return series.rolling(window=period).mean()

    @staticmethod
    def ema(series: pd.Series, period: int) -> pd.Series:
        """指数移动平均 (EMA)"""
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def macd(
        series: pd.Series,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> pd.DataFrame:
        """MACD指标"""
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        histogram = macd - signal_line
        return pd.DataFrame({"macd": macd, "signal": signal_line, "histogram": histogram})

    @staticmethod
    def rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """相对强弱指标 (RSI)"""
        delta = series.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def kdj(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.DataFrame:
        """KDJ随机指标"""
        lowest_low = low.rolling(window=9).min()
        highest_high = high.rolling(window=9).max()

        rsv = (close - lowest_low) / (highest_high - lowest_low) * 100
        k = rsv.ewm(com=2, adjust=False).mean()
        d = k.ewm(com=2, adjust=False).mean()
        j = 3 * k - 2 * d

        return pd.DataFrame({"k": k, "d": d, "j": j})

    @staticmethod
    def bollinger_bands(
        series: pd.Series,
        period: int = 20,
        std_dev: float = 2.0,
    ) -> pd.DataFrame:
        """布林带指标"""
        sma = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()

        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)

        return pd.DataFrame({"upper": upper, "middle": sma, "lower": lower})

    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """平均真实波幅 (ATR)"""
        high_low = high - low
        high_close = np.abs(high - close.shift())
        low_close = np.abs(low - close.shift())

        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()
        return pd.Series(atr)

    @staticmethod
    def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        """能量潮 (OBV)"""
        obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()
        return pd.Series(obv)

    @staticmethod
    def cci(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20) -> pd.Series:
        """商品通道指标 (CCI)"""
        tp = (high + low + close) / 3
        sma = tp.rolling(window=period).mean()
        mad = tp.rolling(window=period).apply(lambda x: np.abs(x - x.mean()).mean())
        cci = (tp - sma) / (0.015 * mad)
        return pd.Series(cci)

    @staticmethod
    def wr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """威廉指标 (WR)"""
        highest_high = high.rolling(window=period).max()
        lowest_low = low.rolling(window=period).min()
        wr = -100 * (highest_high - close) / (highest_high - lowest_low)
        return pd.Series(wr)

    @staticmethod
    def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """平均趋向指数 (ADX)"""
        plus_dm = high.diff()
        minus_dm = -low.diff()

        plus_dm = plus_dm.clip(lower=0)
        minus_dm = minus_dm.clip(lower=0)

        tr1 = high - low
        tr2 = np.abs(high - close.shift())
        tr3 = np.abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.rolling(window=period).mean()

        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)

        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()

        return pd.Series(adx)

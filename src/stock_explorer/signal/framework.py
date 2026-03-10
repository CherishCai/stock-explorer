"""信号检测框架 - 提供通用的信号检测逻辑"""

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd

from stock_explorer.exceptions import SignalDetectError
from stock_explorer.signal.base import (
    Signal,
    SignalDetector,
    SignalDirection,
    SignalStrength,
)


class BaseSignalDetector(SignalDetector, ABC):
    """基础信号检测器"""

    def __init__(self):
        super().__init__()

    def detect(self, data: dict) -> Signal | None:
        """检测信号

        Args:
            data: 包含股票数据的字典

        Returns:
            Signal对象或None
        """
        try:
            # 验证数据
            if not self._validate_data(data):
                return None

            # 提取必要数据
            processed_data = self._process_data(data)
            if not processed_data:
                return None

            # 执行检测
            signal = self._perform_detection(processed_data)
            if signal:
                # 增强信号信息
                signal = self._enhance_signal(signal, data)
            return signal
        except Exception as e:
            raise SignalDetectError(f"信号检测失败: {e}") from e

    def _validate_data(self, data: dict) -> bool:
        """验证数据

        Args:
            data: 包含股票数据的字典

        Returns:
            是否有效
        """
        return True

    def _process_data(self, data: dict) -> dict[str, Any]:
        """处理数据

        Args:
            data: 包含股票数据的字典

        Returns:
            处理后的数据
        """
        return data

    @abstractmethod
    def _perform_detection(self, data: dict[str, Any]) -> Signal | None:
        """执行检测

        Args:
            data: 处理后的数据

        Returns:
            Signal对象或None
        """
        pass

    def _enhance_signal(self, signal: Signal, data: dict) -> Signal:
        """增强信号信息

        Args:
            signal: 信号对象
            data: 原始数据

        Returns:
            增强后的信号对象
        """
        # 添加工夫信息
        if "name" in data and not signal.name:
            signal.name = data["name"]
        if "price" in data and not signal.price:
            signal.price = data["price"]
        return signal


class KlineBasedDetector(BaseSignalDetector, ABC):
    """基于K线的信号检测器"""

    def _validate_data(self, data: dict) -> bool:
        """验证数据

        Args:
            data: 包含股票数据的字典

        Returns:
            是否有效
        """
        kline = data.get("kline")
        return kline is not None and len(kline) > 0

    def _process_data(self, data: dict) -> dict[str, Any]:
        """处理数据

        Args:
            data: 包含股票数据的字典

        Returns:
            处理后的数据
        """
        kline = data.get("kline")
        df = pd.DataFrame(kline)

        # 标准化列名
        column_mapping = {
            "日期": "date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
            "成交额": "amount",
        }
        for old_col, new_col in column_mapping.items():
            if old_col in df.columns:
                df = df.rename(columns={old_col: new_col})

        # 确保日期列是datetime类型
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])

        # 排序
        if "date" in df.columns:
            df = df.sort_values("date")

        return {"df": df, "symbol": data.get("symbol", ""), "name": data.get("name", ""), **data}


class QuoteBasedDetector(BaseSignalDetector, ABC):
    """基于实时行情的信号检测器"""

    def _validate_data(self, data: dict) -> bool:
        """验证数据

        Args:
            data: 包含股票数据的字典

        Returns:
            是否有效
        """
        quote = data.get("quote")
        return quote is not None and isinstance(quote, dict)

    def _process_data(self, data: dict) -> dict[str, Any]:
        """处理数据

        Args:
            data: 包含股票数据的字典

        Returns:
            处理后的数据
        """
        quote = data.get("quote")
        return {
            "quote": quote,
            "symbol": data.get("symbol", ""),
            "name": data.get("name", ""),
            "price": quote.get("最新价", quote.get("price", 0)),
            **data,
        }


class SignalCombiner:
    """信号组合器"""

    @staticmethod
    def combine_signals(signals: list[Signal]) -> Signal | None:
        """组合多个信号

        Args:
            signals: 信号列表

        Returns:
            组合后的信号或None
        """
        if not signals:
            return None

        # 计算信号强度
        strength_score = 0
        direction_score = 0

        strength_map = {SignalStrength.WEAK: 1, SignalStrength.MEDIUM: 2, SignalStrength.STRONG: 3}

        direction_map = {
            SignalDirection.BUY: 1,
            SignalDirection.SELL: -1,
            SignalDirection.NEUTRAL: 0,
        }

        for signal in signals:
            strength_score += strength_map.get(signal.strength, 1)
            direction_score += direction_map.get(signal.direction, 0)

        # 确定最终方向
        if direction_score > 0:
            final_direction = SignalDirection.BUY
        elif direction_score < 0:
            final_direction = SignalDirection.SELL
        else:
            final_direction = SignalDirection.NEUTRAL

        # 确定最终强度
        avg_strength = strength_score / len(signals)
        if avg_strength >= 2.5:
            final_strength = SignalStrength.STRONG
        elif avg_strength >= 1.5:
            final_strength = SignalStrength.MEDIUM
        else:
            final_strength = SignalStrength.WEAK

        # 创建组合信号
        first_signal = signals[0]
        combined_signal = Signal(
            symbol=first_signal.symbol,
            name=first_signal.name,
            signal_type=first_signal.signal_type,
            direction=final_direction,
            strength=final_strength,
            price=first_signal.price,
            message=f"组合信号: {len(signals)}个信号",
            metadata={
                "signal_count": len(signals),
                "individual_signals": [signal.to_dict() for signal in signals],
            },
        )

        return combined_signal


class SignalPipeline:
    """信号检测管道"""

    def __init__(self, detectors: list[SignalDetector]):
        """初始化信号检测管道

        Args:
            detectors: 信号检测器列表
        """
        self.detectors = detectors

    def run(self, data: dict) -> list[Signal]:
        """运行信号检测管道

        Args:
            data: 包含股票数据的字典

        Returns:
            检测到的信号列表
        """
        signals = []

        for detector in self.detectors:
            try:
                signal = detector.detect(data)
                if signal:
                    signals.append(signal)
            except Exception as e:
                raise SignalDetectError(f"检测器 {detector.name} 执行失败: {e}") from e

        return signals

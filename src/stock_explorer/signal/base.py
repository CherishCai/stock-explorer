"""信号基类 - 定义信号数据结构"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SignalType(StrEnum):
    """信号类型枚举"""
    TECHNICAL = "technical"
    CAPITAL_FLOW = "capital_flow"
    MARGIN = "margin"
    HOLDER = "holder"
    SECTOR = "sECTOR"
    SENTIMENT = "sentiment"
    NEWS = "news"


class SignalDirection(StrEnum):
    """信号方向"""
    BUY = "buy"
    SELL = "sell"
    NEUTRAL = "neutral"


class SignalStrength(StrEnum):
    """信号强度"""
    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"


class Signal(BaseModel):
    """信号数据模型"""
    timestamp: datetime = Field(default_factory=datetime.now)
    symbol: str
    name: str = ""
    signal_type: SignalType
    direction: SignalDirection
    strength: SignalStrength = SignalStrength.MEDIUM
    price: float | None = None
    message: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "name": self.name,
            "signal_type": self.signal_type.value,
            "direction": self.direction.value,
            "strength": self.strength.value,
            "price": self.price,
            "message": self.message,
            "metadata": self.metadata,
        }


class SignalDetector:
    """信号检测器基类"""

    name: str = ""
    signal_type: SignalType = SignalType.TECHNICAL

    def detect(self, data: dict) -> Signal | None:
        """检测信号

        Args:
            data: 包含股票数据的字典

        Returns:
            Signal对象或None
        """
        raise NotImplementedError("Subclass must implement detect method")

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.name}>"


class SignalFilter:
    """信号过滤器"""

    def __init__(
        self,
        min_strength: SignalStrength = SignalStrength.WEAK,
        exclude_st: bool = True,
        min_market_cap: float | None = None,
    ):
        self.min_strength = min_strength
        self.exclude_st = exclude_st
        self.min_market_cap = min_market_cap

    def filter(self, signal: Signal, stock_info: dict | None = None) -> bool:
        """过滤信号"""
        strength_order = {
            SignalStrength.WEAK: 0,
            SignalStrength.MEDIUM: 1,
            SignalStrength.STRONG: 2,
        }

        if strength_order[signal.strength] < strength_order[self.min_strength]:
            return False

        if self.exclude_st and signal.name.upper().startswith("ST"):
            return False

        if self.min_market_cap and stock_info:
            market_cap = stock_info.get("流通市值") or stock_info.get("总市值", 0)
            if market_cap and market_cap < self.min_market_cap:
                return False

        return True

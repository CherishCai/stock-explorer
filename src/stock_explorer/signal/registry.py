"""信号注册表 - 管理所有信号检测器"""


from stock_explorer.signal.base import SignalDetector, SignalType
from stock_explorer.signal.detectors import (
    BreakoutDetector,
    DeathCrossDetector,
    GoldenCrossDetector,
    LimitDownDetector,
    LimitUpDetector,
    RSIDetector,
    VolumeSurgeDetector,
)


class SignalRegistry:
    """信号检测器注册表"""

    _detectors: dict[str, SignalDetector] = {}
    _initialized = False

    @classmethod
    def _initialize(cls):
        """初始化默认检测器"""
        if cls._initialized:
            return

        detectors = [
            GoldenCrossDetector(),
            DeathCrossDetector(),
            RSIDetector(),
            VolumeSurgeDetector(),
            LimitUpDetector(),
            LimitDownDetector(),
            BreakoutDetector(),
        ]

        for detector in detectors:
            cls.register(detector.name, detector)

        cls._initialized = True

    @classmethod
    def register(cls, name: str, detector: SignalDetector):
        """注册检测器"""
        detector.name = name
        cls._detectors[name] = detector

    @classmethod
    def get(cls, name: str) -> SignalDetector | None:
        """获取检测器"""
        cls._initialize()
        return cls._detectors.get(name)

    @classmethod
    def list_all(cls) -> list[str]:
        """列出所有检测器"""
        cls._initialize()
        return list(cls._detectors.keys())

    @classmethod
    def list_by_type(cls, signal_type: SignalType) -> list[str]:
        """按类型列出检测器"""
        cls._initialize()
        return [
            name
            for name, detector in cls._detectors.items()
            if detector.signal_type == signal_type
        ]

    @classmethod
    def get_detectors(cls, names: list[str]) -> list[SignalDetector]:
        """批量获取检测器"""
        cls._initialize()
        detectors = []
        for name in names:
            detector = cls._detectors.get(name)
            if detector:
                detectors.append(detector)
        return detectors

    @classmethod
    def clear(cls):
        """清空注册表"""
        cls._detectors.clear()
        cls._initialized = False

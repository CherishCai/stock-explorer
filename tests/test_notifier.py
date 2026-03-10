from datetime import datetime

from stock_explorer.config.settings import get_config
from stock_explorer.monitor.notifier import create_notifier_manager
from stock_explorer.signal.base import Signal, SignalDirection, SignalStrength, SignalType

# 创建一个测试信号
test_signal = Signal(
    symbol="600000",
    name="浦发银行",
    direction=SignalDirection.BUY,
    signal_type=SignalType.TECHNICAL,
    strength=SignalStrength.STRONG,
    price=10.0,
    timestamp=datetime.now(),
    message="测试信号",
)

# 获取配置并创建notifier
config = get_config()
notifier = create_notifier_manager(config.alert.model_dump())

# 发送测试信号
print("发送测试信号...")
notifier.notify(test_signal)
print("测试信号发送完成")

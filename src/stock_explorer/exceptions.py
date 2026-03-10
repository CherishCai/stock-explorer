"""异常处理模块 - 定义标准异常类"""


class StockExplorerError(Exception):
    """基础异常类"""

    pass


class DataError(StockExplorerError):
    """数据相关异常"""

    pass


class DataFetchError(DataError):
    """数据获取异常"""

    pass


class DataCacheError(DataError):
    """数据缓存异常"""

    pass


class DataStorageError(DataError):
    """数据存储异常"""

    pass


class SignalError(StockExplorerError):
    """信号相关异常"""

    pass


class SignalDetectError(SignalError):
    """信号检测异常"""

    pass


class BacktestError(StockExplorerError):
    """回测相关异常"""

    pass


class MonitorError(StockExplorerError):
    """监控相关异常"""

    pass


class ServiceError(StockExplorerError):
    """服务相关异常"""

    pass


class ConfigError(StockExplorerError):
    """配置相关异常"""

    pass

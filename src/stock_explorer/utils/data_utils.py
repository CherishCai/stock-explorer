"""数据处理工具模块"""


import pandas as pd


def format_date(date_str: str) -> str:
    """格式化日期字符串

    Args:
        date_str: 日期字符串

    Returns:
        格式化后的日期字符串 (YYYY-MM-DD)
    """
    try:
        # 尝试解析各种日期格式
        for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%Y%m%d']:
            try:
                return pd.to_datetime(date_str, format=fmt).strftime('%Y-%m-%d')
            except ValueError:
                continue
        # 最后尝试自动解析
        return pd.to_datetime(date_str).strftime('%Y-%m-%d')
    except Exception:
        return date_str


def normalize_kline_data(df: pd.DataFrame) -> pd.DataFrame:
    """标准化K线数据格式

    Args:
        df: K线数据DataFrame

    Returns:
        标准化后的K线数据
    """
    if df.empty:
        return df

    # 重命名列名
    column_mapping = {
        '日期': 'date',
        '开盘': 'open',
        '最高': 'high',
        '最低': 'low',
        '收盘': 'close',
        '成交量': 'volume',
        '成交额': 'amount'
    }

    # 重命名列
    for old_col, new_col in column_mapping.items():
        if old_col in df.columns:
            df = df.rename(columns={old_col: new_col})

    # 确保日期列是datetime类型
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])

    # 排序
    if 'date' in df.columns:
        df = df.sort_values('date')

    return df


def validate_stock_symbol(symbol: str) -> str:
    """验证并标准化股票代码

    Args:
        symbol: 股票代码

    Returns:
        标准化后的股票代码
    """
    # 移除空格
    symbol = symbol.strip()

    # 确保是字符串
    if not isinstance(symbol, str):
        symbol = str(symbol)

    # 移除可能的前缀或后缀
    symbol = symbol.replace('SH', '').replace('SZ', '').replace('.', '')

    # 确保6位数字
    if len(symbol) < 6:
        symbol = symbol.zfill(6)

    return symbol


def merge_dataframes(df1: pd.DataFrame, df2: pd.DataFrame, on: str = 'date') -> pd.DataFrame:
    """合并两个DataFrame

    Args:
        df1: 第一个DataFrame
        df2: 第二个DataFrame
        on: 合并键

    Returns:
        合并后的DataFrame
    """
    if df1.empty:
        return df2
    if df2.empty:
        return df1

    return pd.merge(df1, df2, on=on, how='outer').sort_values(on)


def calculate_returns(df: pd.DataFrame, price_col: str = 'close') -> pd.DataFrame:
    """计算收益率

    Args:
        df: 包含价格数据的DataFrame
        price_col: 价格列名

    Returns:
        包含收益率的DataFrame
    """
    if df.empty or price_col not in df.columns:
        return df

    df['return'] = df[price_col].pct_change()
    return df


def get_date_range(start_date: str, end_date: str) -> list[str]:
    """获取日期范围

    Args:
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        日期列表
    """
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    return pd.date_range(start, end).strftime('%Y-%m-%d').tolist()


def is_market_open(date: str) -> bool:
    """判断是否为交易日

    Args:
        date: 日期字符串

    Returns:
        是否为交易日
    """
    try:
        # 这里可以根据实际情况实现交易日判断逻辑
        # 简单实现：排除周末
        dt = pd.to_datetime(date)
        return dt.weekday() < 5  # 0-4是周一到周五
    except Exception:
        return False

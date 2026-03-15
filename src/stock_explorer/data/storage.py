"""数据存储模块 - 支持 SQLite 存储"""

import json
import os
import sqlite3
from collections.abc import Sequence

import pandas as pd

from stock_explorer.exceptions import DataStorageError
from stock_explorer.logging.logger import get_logger
from stock_explorer.utils.data_utils import normalize_kline_data

logger = get_logger(__name__)


class DataStorage:
    """数据存储 - 支持 SQLite 存储"""

    def __init__(self, db_path: str = "data/stock_explorer.db", pool_size: int = 5):
        self.db_path = db_path
        self.pool_size = pool_size
        self._init_db()
        # 连接池
        self._connection_pool: list = []
        self._pool_lock = None

    def _get_connection(self):
        """获取数据库连接"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as e:
            logger.error(f"获取数据库连接失败: {e}")
            raise DataStorageError(f"获取数据库连接失败: {e}") from e

    def _close_connection(self, conn):
        """关闭数据库连接"""
        try:
            if conn:
                conn.close()
        except Exception as e:
            logger.error(f"关闭数据库连接失败: {e}")

    def _init_db(self):
        """初始化数据库表结构"""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

            conn = self._get_connection()
            cursor = conn.cursor()

            # K线数据表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS kline_data (
                id INTEGER PRIMARY KEY,
                symbol TEXT NOT NULL,
                date TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                amount REAL,
                period TEXT,  -- daily/weekly/monthly/1min/5min/15min/30min/60min
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, date, period)
            )
            """)

            # 信号记录表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT NOT NULL,
                signal_type TEXT NOT NULL,  -- technical/fundamental/sentiment
                direction TEXT NOT NULL,    -- buy/sell
                strength TEXT,              -- strong/medium/weak
                price REAL,
                message TEXT,
                strategy TEXT,              -- 策略名称
                metadata TEXT,  -- JSON
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # 告警记录表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY,
                signal_id INTEGER,
                timestamp TIMESTAMP NOT NULL,
                channel TEXT NOT NULL,  -- console/file/email/dingtalk
                status TEXT NOT NULL,  -- sent/failed
                message TEXT,
                response TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(signal_id) REFERENCES signals(id)
            )
            """)

            # 监控配置表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY,
                symbol TEXT NOT NULL,
                name TEXT,
                category TEXT,  -- hs300/industry/custom
                enabled BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            conn.commit()
            logger.info(f"数据库初始化完成: {self.db_path}")
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise DataStorageError(f"数据库初始化失败: {e}") from e
        finally:
            if "conn" in locals():
                self._close_connection(conn)

    def save_kline(self, df: pd.DataFrame, symbol: str, period: str):
        """保存K线数据"""
        if df.empty:
            return

        # 标准化K线数据格式
        df = normalize_kline_data(df)

        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 使用事务批量插入
            cursor.execute("BEGIN TRANSACTION")

            for _, row in df.iterrows():
                # 处理时间戳类型
                date_value = row.get("date", row.get("日期"))
                if date_value and hasattr(date_value, "strftime"):
                    date_value = date_value.strftime("%Y-%m-%d")

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO kline_data
                    (symbol, date, open, high, low, close, volume, amount, period)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        symbol,
                        date_value,
                        row.get("open", row.get("开盘")),
                        row.get("high", row.get("最高")),
                        row.get("low", row.get("最低")),
                        row.get("close", row.get("收盘")),
                        row.get("volume", row.get("成交量")),
                        row.get("amount", row.get("成交额")),
                        period,
                    ),
                )

            conn.commit()
            logger.info(f"保存 {symbol} {period} K线数据 {len(df)} 条")
        except Exception as e:
            logger.error(f"保存K线数据失败: {e}")
            if conn:
                conn.rollback()
            raise DataStorageError(f"保存K线数据失败: {e}") from e
        finally:
            if conn:
                self._close_connection(conn)

    def get_kline(self, symbol: str, start: str, end: str, period: str) -> pd.DataFrame:
        """获取K线数据"""
        conn = None
        try:
            conn = self._get_connection()
            query = """
            SELECT * FROM kline_data
            WHERE symbol = ? AND period = ? AND date >= ? AND date <= ?
            ORDER BY date
            """
            df = pd.read_sql_query(query, conn, params=(symbol, period, start, end))
            logger.info(f"获取 {symbol} {period} K线数据 {len(df)} 条")
            return df
        except Exception as e:
            logger.error(f"获取K线数据失败: {e}")
            raise DataStorageError(f"获取K线数据失败: {e}") from e
        finally:
            if conn:
                self._close_connection(conn)

    def save_signals(self, signals: list[dict]):
        """保存信号记录"""
        if not signals:
            return

        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 使用事务批量插入
            cursor.execute("BEGIN TRANSACTION")

            for signal in signals:
                # 处理时间戳类型
                timestamp = signal.get("timestamp")
                if timestamp and hasattr(timestamp, "strftime"):
                    timestamp = timestamp.strftime("%Y-%m-%d %H:%M:%S")

                cursor.execute(
                    """
                    INSERT INTO signals
                    (timestamp, symbol, name, signal_type, direction, strength, price, message, strategy, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        timestamp,
                        signal.get("symbol"),
                        signal.get("name"),
                        signal.get("signal_type"),
                        signal.get("direction"),
                        signal.get("strength"),
                        signal.get("price"),
                        signal.get("message"),
                        signal.get("strategy", ""),
                        json.dumps(signal.get("metadata", {})),
                    ),
                )

            conn.commit()
            logger.info(f"保存信号记录 {len(signals)} 条")
        except Exception as e:
            logger.error(f"保存信号记录失败: {e}")
            if conn:
                conn.rollback()
            raise DataStorageError(f"保存信号记录失败: {e}") from e
        finally:
            if conn:
                self._close_connection(conn)

    def get_signals(
        self, start_date: str, end_date: str, filters: dict | None = None, limit: int | None = None
    ) -> pd.DataFrame:
        """获取信号记录"""
        conn = None
        try:
            conn = self._get_connection()
            query = """
            SELECT * FROM signals
            WHERE timestamp >= ? AND timestamp <= ?
            """
            params: Sequence = [start_date, end_date]

            if filters:
                if filters.get("symbol"):
                    query += " AND symbol = ?"
                    params = list(params) + [filters["symbol"]]
                if filters.get("signal_type"):
                    query += " AND signal_type = ?"
                    params = list(params) + [filters["signal_type"]]
                if filters.get("direction"):
                    query += " AND direction = ?"
                    params = list(params) + [filters["direction"]]

            query += " ORDER BY timestamp DESC"

            if limit:
                query += f" LIMIT {limit}"

            df = pd.read_sql_query(query, conn, params=params)
            logger.info(f"获取信号记录 {len(df)} 条")
            return df
        except Exception as e:
            logger.error(f"获取信号记录失败: {e}")
            raise DataStorageError(f"获取信号记录失败: {e}") from e
        finally:
            if conn:
                self._close_connection(conn)

    def save_alert(self, alert: dict):
        """保存告警记录"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 处理时间戳类型
            timestamp = alert.get("timestamp")
            if timestamp and hasattr(timestamp, "strftime"):
                timestamp = timestamp.strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute(
                """
                INSERT INTO alerts
                (signal_id, timestamp, channel, status, message, response)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    alert.get("signal_id"),
                    timestamp,
                    alert.get("channel"),
                    alert.get("status"),
                    alert.get("message"),
                    alert.get("response"),
                ),
            )
            conn.commit()
            logger.info("保存告警记录")
        except Exception as e:
            logger.error(f"保存告警记录失败: {e}")
            if conn:
                conn.rollback()
            raise DataStorageError(f"保存告警记录失败: {e}") from e
        finally:
            if conn:
                self._close_connection(conn)

    def get_alerts(self, start: str, end: str, channel: str | None = None) -> pd.DataFrame:
        """获取告警记录"""
        conn = None
        try:
            conn = self._get_connection()
            query = """
            SELECT * FROM alerts
            WHERE timestamp >= ? AND timestamp <= ?
            """
            params: Sequence = [start, end]

            if channel:
                query += " AND channel = ?"
                params = list(params) + [channel]

            query += " ORDER BY timestamp DESC"

            df = pd.read_sql_query(query, conn, params=params)
            logger.info(f"获取告警记录 {len(df)} 条")
            return df
        except Exception as e:
            logger.error(f"获取告警记录失败: {e}")
            raise DataStorageError(f"获取告警记录失败: {e}") from e
        finally:
            if conn:
                self._close_connection(conn)

    def save_watchlist(self, symbols: list[dict]):
        """保存监控列表"""
        if not symbols:
            return

        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 使用事务批量插入
            cursor.execute("BEGIN TRANSACTION")

            for item in symbols:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO watchlist
                    (symbol, name, category, enabled)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        item.get("symbol"),
                        item.get("name"),
                        item.get("category"),
                        item.get("enabled", 1),
                    ),
                )

            conn.commit()
            logger.info(f"保存监控列表 {len(symbols)} 条")
        except Exception as e:
            logger.error(f"保存监控列表失败: {e}")
            if conn:
                conn.rollback()
            raise DataStorageError(f"保存监控列表失败: {e}") from e
        finally:
            if conn:
                self._close_connection(conn)

    def get_watchlist(self, category: str | None = None) -> list[dict]:
        """获取监控列表"""
        conn = None
        try:
            conn = self._get_connection()
            query = "SELECT * FROM watchlist WHERE enabled = 1"
            params = []

            if category:
                query += " AND category = ?"
                params.append(category)

            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

            result = []
            for row in rows:
                result.append(
                    {
                        "id": row[0],
                        "symbol": row[1],
                        "name": row[2],
                        "category": row[3],
                        "enabled": row[4],
                        "created_at": row[5],
                    }
                )

            logger.info(f"获取监控列表 {len(result)} 条")
            return result
        except Exception as e:
            logger.error(f"获取监控列表失败: {e}")
            raise DataStorageError(f"获取监控列表失败: {e}") from e
        finally:
            if conn:
                self._close_connection(conn)

    def clear_table(self, table_name: str):
        """清空表数据"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(f"DELETE FROM {table_name}")
            conn.commit()
            logger.info(f"清空表 {table_name}")
        except Exception as e:
            logger.error(f"清空表失败: {e}")
            if conn:
                conn.rollback()
            raise DataStorageError(f"清空表失败: {e}") from e
        finally:
            if conn:
                self._close_connection(conn)

    def vacuum(self):
        """优化数据库"""
        conn = None
        try:
            conn = self._get_connection()
            conn.execute("VACUUM")
            conn.commit()
            logger.info("数据库优化完成")
        except Exception as e:
            logger.error(f"数据库优化失败: {e}")
            raise DataStorageError(f"数据库优化失败: {e}") from e
        finally:
            if conn:
                self._close_connection(conn)


# 单例模式
_storage_instance: DataStorage | None = None


def get_storage() -> DataStorage:
    """获取存储实例单例"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = DataStorage()
    return _storage_instance


def get_database() -> DataStorage:
    """获取数据库实例单例（别名）"""
    return get_storage()

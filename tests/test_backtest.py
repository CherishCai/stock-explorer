"""回测引擎测试"""
import sys
from pathlib import Path as SysPath

# 设置项目路径
sys.path.insert(0, str(SysPath(__file__).parent.parent / "src"))

# 系统导入
from datetime import datetime

import pandas as pd
import pytest

# 项目导入
from stock_explorer.backtest.analyzer import (
    PerformanceAnalyzer,
    PerformanceMetrics,
    RollingAnalyzer,
)
from stock_explorer.backtest.engine import (
    BacktestEngine,
    BacktestResult,
    Position,
    PositionSide,
)


class TestBacktestEngine:
    @pytest.fixture
    def engine(self):
        return BacktestEngine(
            initial_capital=1000000.0,
            commission_rate=0.0003,
            slippage_rate=0.0001,
        )

    def test_engine_initialization(self, engine):
        assert engine.initial_capital == 1000000.0
        assert engine.commission_rate == 0.0003
        assert engine.capital == 1000000.0

    def test_open_long_position(self, engine):
        result = engine.open_position(
            symbol="000001",
            direction=PositionSide.LONG,
            quantity=1000,
            price=10.0,
            timestamp=datetime.now(),
        )
        assert result is True
        assert "000001" in engine.positions

    def test_open_position_insufficient_capital(self, engine):
        result = engine.open_position(
            symbol="000001",
            direction=PositionSide.LONG,
            quantity=1000000,
            price=10.0,
            timestamp=datetime.now(),
        )
        assert result is False

    def test_close_position(self, engine):
        engine.open_position(
            symbol="000001",
            direction=PositionSide.LONG,
            quantity=1000,
            price=10.0,
            timestamp=datetime.now(),
        )

        result = engine.close_position(
            symbol="000001",
            quantity=1000,
            price=11.0,
            timestamp=datetime.now(),
        )
        assert result is True

    def test_close_nonexistent_position(self, engine):
        result = engine.close_position(
            symbol="999999",
            quantity=1000,
            price=11.0,
            timestamp=datetime.now(),
        )
        assert result is False

    def test_update_positions(self, engine):
        engine.positions["000001"] = Position(
            symbol="000001",
            direction=PositionSide.LONG,
            quantity=1000,
            entry_price=10.0,
            entry_time=datetime.now(),
        )

        engine.update_positions({"000001": 11.0}, datetime.now())

        assert engine.positions["000001"].current_price == 11.0
        assert engine.positions["000001"].unrealized_pnl == 1000.0

    def test_calculate_commission(self, engine):
        commission = engine.calculate_commission(price=10.0, quantity=1000, direction=PositionSide.LONG)
        assert commission > 0

    def test_generate_result(self, engine):
        result = engine._generate_result()
        assert isinstance(result, BacktestResult)
        assert result.initial_capital == 1000000.0
        assert result.total_trades == 0


class TestPosition:
    def test_position_creation(self):
        position = Position(
            symbol="000001",
            direction=PositionSide.LONG,
            quantity=1000,
            entry_price=10.0,
            entry_time=datetime.now(),
        )

        assert position.symbol == "000001"
        assert position.direction == PositionSide.LONG
        assert position.quantity == 1000
        assert position.unrealized_pnl == 0.0

    def test_position_update_price(self):
        position = Position(
            symbol="000001",
            direction=PositionSide.LONG,
            quantity=1000,
            entry_price=10.0,
            entry_time=datetime.now(),
        )

        position.update_price(11.0)
        assert position.current_price == 11.0
        assert position.unrealized_pnl == 1000.0


class TestPerformanceAnalyzer:
    @pytest.fixture
    def analyzer(self):
        return PerformanceAnalyzer(initial_capital=1000000.0)

    def test_analyzer_initialization(self, analyzer):
        assert analyzer.initial_capital == 1000000.0

    def test_analyze_empty_trades(self, analyzer):
        result = analyzer.analyze([], pd.DataFrame())
        assert isinstance(result, PerformanceMetrics)

    def test_generate_report(self, analyzer):
        metrics = PerformanceMetrics(
            total_return=10.5,
            annual_return=15.2,
            volatility=20.0,
            sharpe_ratio=0.76,
            sortino_ratio=1.0,
            max_drawdown=-8.5,
            calmar_ratio=1.79,
            win_rate=55.0,
            profit_factor=1.5,
            avg_win=5000.0,
            avg_loss=-3000.0,
            largest_win=20000.0,
            largest_loss=-10000.0,
            avg_holding_days=5.0,
            total_trades=100,
        )

        report = analyzer.generate_report(metrics)
        assert "回测绩效报告" in report
        assert "总收益率" in report


class TestRollingAnalyzer:
    @pytest.fixture
    def rolling_analyzer(self):
        return RollingAnalyzer(window=20)

    def test_rolling_analyzer_initialization(self, rolling_analyzer):
        assert rolling_analyzer.window == 20

    def test_calculate_rolling_sharpe(self, rolling_analyzer):
        returns = pd.Series([0.01, -0.005, 0.015, 0.02, -0.01] * 20)
        result = rolling_analyzer.calculate_rolling_sharpe(returns)
        assert len(result) == len(returns)

    def test_calculate_rolling_drawdown(self, rolling_analyzer):
        equity = pd.Series([1000, 1050, 1020, 1080, 1100])
        result = rolling_analyzer.calculate_rolling_drawdown(equity)
        assert len(result) == len(equity)

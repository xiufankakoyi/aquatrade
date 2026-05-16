"""
core/backtest/unified_engine.py 统一回测引擎测试

测试内容：
1. BacktestConfig 配置
2. TradeRecord 交易记录
3. BacktestResult 回测结果
4. 性能指标计算
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime
from dataclasses import asdict


class TestBacktestConfig:
    """回测配置测试"""
    
    def test_default_config(self):
        """测试默认配置"""
        from core.backtest.unified_engine import BacktestConfig
        
        config = BacktestConfig()
        
        assert config.initial_capital == 1_000_000.0
        assert config.commission_rate == 0.0003
        assert config.min_commission == 5.0
        assert config.sell_tax == 0.001
    
    def test_custom_config(self):
        """测试自定义配置"""
        from core.backtest.unified_engine import BacktestConfig
        
        config = BacktestConfig(
            initial_capital=500_000.0,
            commission_rate=0.0005,
            max_positions=10
        )
        
        assert config.initial_capital == 500_000.0
        assert config.commission_rate == 0.0005
        assert config.max_positions == 10
    
    def test_risk_control_params(self):
        """测试风控参数"""
        from core.backtest.unified_engine import BacktestConfig
        
        config = BacktestConfig(
            stop_loss=0.95,
            take_profit=1.20,
            max_holding_days=30
        )
        
        assert config.stop_loss == 0.95
        assert config.take_profit == 1.20
        assert config.max_holding_days == 30


class TestTradeRecord:
    """交易记录测试"""
    
    def test_trade_record_buy(self):
        """测试买入记录"""
        from core.backtest.unified_engine import TradeRecord
        
        record = TradeRecord(
            date="2024-01-15",
            code="000001",
            action="buy",
            shares=1000,
            price=10.5,
            amount=10500.0,
            commission=5.0
        )
        
        assert record.date == "2024-01-15"
        assert record.action == "buy"
        assert record.shares == 1000
        assert record.price == 10.5
    
    def test_trade_record_sell(self):
        """测试卖出记录"""
        from core.backtest.unified_engine import TradeRecord
        
        record = TradeRecord(
            date="2024-01-20",
            code="000001",
            action="sell",
            shares=1000,
            price=11.0,
            amount=11000.0,
            commission=5.0,
            tax=11.0,
            profit_loss=484.0,
            roi=0.046
        )
        
        assert record.action == "sell"
        assert record.tax == 11.0
        assert record.profit_loss == 484.0
    
    def test_trade_record_with_holding_info(self):
        """测试带持仓信息的记录"""
        from core.backtest.unified_engine import TradeRecord
        
        record = TradeRecord(
            date="2024-01-20",
            code="000001",
            action="sell",
            shares=1000,
            price=11.0,
            amount=11000.0,
            commission=5.0,
            entry_price=10.5,
            entry_date="2024-01-15",
            exit_price=11.0,
            exit_date="2024-01-20",
            holding_days=5
        )
        
        assert record.entry_price == 10.5
        assert record.holding_days == 5


class TestBacktestResult:
    """回测结果测试"""
    
    def test_backtest_result_basic(self):
        """测试基本回测结果"""
        from core.backtest.unified_engine import BacktestResult
        
        result = BacktestResult(
            final_equity=1_100_000.0,
            total_return=0.10,
            annualized_return=0.15,
            max_drawdown=-0.08,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            volatility=0.20,
            win_rate=0.60,
            profit_factor=1.8,
            trade_count=100,
            avg_trade_return=0.01,
            max_winning_streak=5,
            max_losing_streak=3,
            calmar_ratio=1.875
        )
        
        assert result.final_equity == 1_100_000.0
        assert result.total_return == 0.10
        assert result.sharpe_ratio == 1.5
    
    def test_backtest_result_with_trades(self):
        """测试带交易记录的结果"""
        from core.backtest.unified_engine import BacktestResult, TradeRecord
        
        trades = [
            TradeRecord(
                date="2024-01-15",
                code="000001",
                action="buy",
                shares=1000,
                price=10.5,
                amount=10500.0,
                commission=5.0
            )
        ]
        
        result = BacktestResult(
            final_equity=1_100_000.0,
            total_return=0.10,
            annualized_return=0.15,
            max_drawdown=-0.08,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            volatility=0.20,
            win_rate=0.60,
            profit_factor=1.8,
            trade_count=1,
            avg_trade_return=0.01,
            max_winning_streak=1,
            max_losing_streak=0,
            calmar_ratio=1.875,
            trades=trades
        )
        
        assert len(result.trades) == 1


class TestPerformanceMetrics:
    """性能指标计算测试"""
    
    def test_calculate_drawdown(self):
        """测试最大回撤计算"""
        from core.backtest.unified_engine import _calculate_drawdown_numba
        
        equity = np.array([100.0, 110.0, 105.0, 95.0, 100.0, 90.0, 95.0])
        
        drawdown = _calculate_drawdown_numba(equity)
        
        assert drawdown < 0
    
    def test_calculate_drawdown_empty(self):
        """测试空数组回撤"""
        from core.backtest.unified_engine import _calculate_drawdown_numba
        
        equity = np.array([])
        
        drawdown = _calculate_drawdown_numba(equity)
        
        assert drawdown == 0.0
    
    def test_calculate_sharpe(self):
        """测试夏普比率计算"""
        from core.backtest.unified_engine import _calculate_sharpe_numba
        
        returns = np.array([0.01, 0.02, -0.01, 0.03, -0.02, 0.01] * 10)
        
        sharpe = _calculate_sharpe_numba(returns)
        
        assert isinstance(sharpe, float)
    
    def test_calculate_sharpe_empty(self):
        """测试空数组夏普"""
        from core.backtest.unified_engine import _calculate_sharpe_numba
        
        returns = np.array([])
        
        sharpe = _calculate_sharpe_numba(returns)
        
        assert sharpe == 0.0
    
    def test_calculate_sortino(self):
        """测试索提诺比率计算"""
        from core.backtest.unified_engine import _calculate_sortino_numba
        
        returns = np.array([0.01, 0.02, -0.01, 0.03, -0.02, 0.01] * 10)
        
        sortino = _calculate_sortino_numba(returns)
        
        assert isinstance(sortino, float)
    
    def test_calculate_streaks(self):
        """测试连胜连亏计算"""
        from core.backtest.unified_engine import _calculate_streaks_numba
        
        profit_signs = np.array([1, 1, 1, -1, -1, 1, 1, -1, 1, 1, 1, 1])
        
        max_win, max_loss = _calculate_streaks_numba(profit_signs)
        
        assert max_win == 4
        assert max_loss == 2
    
    def test_calculate_streaks_empty(self):
        """测试空数组连胜连亏"""
        from core.backtest.unified_engine import _calculate_streaks_numba
        
        profit_signs = np.array([])
        
        max_win, max_loss = _calculate_streaks_numba(profit_signs)
        
        assert max_win == 0
        assert max_loss == 0


class TestMakeJsonSerializable:
    """JSON 序列化测试"""
    
    def test_serialize_none(self):
        """测试 None 序列化"""
        from core.backtest.unified_engine import _make_json_serializable
        
        result = _make_json_serializable(None)
        
        assert result is None
    
    def test_serialize_basic_types(self):
        """测试基本类型序列化"""
        from core.backtest.unified_engine import _make_json_serializable
        
        assert _make_json_serializable(123) == 123
        assert _make_json_serializable(3.14) == 3.14
        assert _make_json_serializable("test") == "test"
        assert _make_json_serializable(True) is True
    
    def test_serialize_list(self):
        """测试列表序列化"""
        from core.backtest.unified_engine import _make_json_serializable
        
        result = _make_json_serializable([1, 2, 3])
        
        assert result == [1, 2, 3]
    
    def test_serialize_dict(self):
        """测试字典序列化"""
        from core.backtest.unified_engine import _make_json_serializable
        
        result = _make_json_serializable({"a": 1, "b": 2})
        
        assert result == {"a": 1, "b": 2}
    
    def test_serialize_numpy_array(self):
        """测试 NumPy 数组序列化"""
        from core.backtest.unified_engine import _make_json_serializable
        
        arr = np.array([1, 2, 3])
        result = _make_json_serializable(arr)
        
        assert result == [1, 2, 3]
    
    def test_serialize_nan_inf(self):
        """测试 NaN 和 Inf 序列化"""
        from core.backtest.unified_engine import _make_json_serializable
        
        assert _make_json_serializable(float('nan')) is None
        assert _make_json_serializable(float('inf')) is None

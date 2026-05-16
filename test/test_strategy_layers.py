"""
core/strategies/strategy_layers.py 策略层测试

测试内容：
1. SignalType 枚举
2. DailyFactors 数据结构
3. Position 数据结构
4. FunctionStrategy 基本功能
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock


class TestSignalType:
    """信号类型枚举测试"""
    
    def test_signal_type_values(self):
        """测试信号类型值"""
        from core.strategies.strategy_layers import SignalType
        
        assert SignalType.HOLD.value == 0
        assert SignalType.BUY.value == 1
        assert SignalType.SELL.value == 2


class TestDailyFactors:
    """单日因子数据测试"""
    
    def test_daily_factors_creation(self):
        """测试创建单日因子"""
        from core.strategies.strategy_layers import DailyFactors
        
        factors = DailyFactors(
            date="2024-01-15",
            stock_code="000001.SZ",
            data={"ma5": 10.5, "ma10": 10.0, "volume": 1000000}
        )
        
        assert factors.date == "2024-01-15"
        assert factors.stock_code == "000001.SZ"
    
    def test_daily_factors_getitem(self):
        """测试索引访问"""
        from core.strategies.strategy_layers import DailyFactors
        
        factors = DailyFactors(
            date="2024-01-15",
            stock_code="000001.SZ",
            data={"ma5": 10.5, "ma10": 10.0}
        )
        
        assert factors["ma5"] == 10.5
        assert factors["ma10"] == 10.0
    
    def test_daily_factors_getitem_missing(self):
        """测试缺失键访问"""
        from core.strategies.strategy_layers import DailyFactors
        
        factors = DailyFactors(
            date="2024-01-15",
            stock_code="000001.SZ",
            data={"ma5": 10.5}
        )
        
        result = factors["missing"]
        
        assert np.isnan(result)
    
    def test_daily_factors_get(self):
        """测试get方法"""
        from core.strategies.strategy_layers import DailyFactors
        
        factors = DailyFactors(
            date="2024-01-15",
            stock_code="000001.SZ",
            data={"ma5": 10.5}
        )
        
        assert factors.get("ma5") == 10.5
        assert factors.get("missing", 0.0) == 0.0


class TestPosition:
    """持仓状态测试"""
    
    def test_position_default_values(self):
        """测试默认值"""
        from core.strategies.strategy_layers import Position
        
        pos = Position()
        
        assert pos.has_position is False
        assert pos.shares == 0
        assert pos.cost_price == 0.0
        assert pos.holding_days == 0
    
    def test_position_with_values(self):
        """测试带值的持仓"""
        from core.strategies.strategy_layers import Position
        
        pos = Position(
            has_position=True,
            shares=1000,
            cost_price=10.5,
            holding_days=5,
            unrealized_pnl=500.0
        )
        
        assert pos.has_position is True
        assert pos.shares == 1000
        assert pos.cost_price == 10.5
        assert pos.holding_days == 5
        assert pos.unrealized_pnl == 500.0


class TestFunctionStrategy:
    """函数策略测试"""
    
    def test_function_strategy_creation(self):
        """测试创建函数策略"""
        from core.strategies.strategy_layers import FunctionStrategy
        
        def simple_strategy(date, factors, position, history):
            return 'hold', None
        
        strategy = FunctionStrategy(simple_strategy)
        
        assert strategy.signal_func == simple_strategy
        assert strategy.required_factors == []
    
    def test_function_strategy_with_factors(self):
        """测试带因子列表的函数策略"""
        from core.strategies.strategy_layers import FunctionStrategy
        
        def ma_strategy(date, factors, position, history):
            return 'hold', None
        
        strategy = FunctionStrategy(
            ma_strategy,
            required_factors=['ma5', 'ma10'],
            name="MA策略"
        )
        
        assert strategy.required_factors == ['ma5', 'ma10']
        assert strategy.name == "MA策略"
    
    def test_function_strategy_execution_price(self):
        """测试执行价格配置"""
        from core.strategies.strategy_layers import FunctionStrategy
        
        def simple_strategy(date, factors, position, history):
            return 'hold', None
        
        strategy = FunctionStrategy(simple_strategy)
        
        assert strategy.execution_price["buy"] == "open"
        assert strategy.execution_price["sell"] == "open"
    
    def test_function_strategy_position_states(self):
        """测试持仓状态字典"""
        from core.strategies.strategy_layers import FunctionStrategy
        
        def simple_strategy(date, factors, position, history):
            return 'hold', None
        
        strategy = FunctionStrategy(simple_strategy)
        
        assert isinstance(strategy._position_states, dict)
        assert isinstance(strategy._history, list)

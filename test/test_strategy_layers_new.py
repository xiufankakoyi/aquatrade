"""
core/strategies/strategy_layers.py 三层策略系统测试

测试内容：
1. SignalType 枚举
2. DailyFactors 数据类
3. Position 数据类
4. FunctionStrategy 函数策略
"""

import pytest
import numpy as np
import pandas as pd
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
    
    def test_daily_factors_init(self):
        """测试初始化"""
        from core.strategies.strategy_layers import DailyFactors
        
        factors = DailyFactors(
            date='2024-01-15',
            stock_code='000001.SZ',
            data={'ma5': 10.0, 'ma10': 9.5}
        )
        
        assert factors.date == '2024-01-15'
        assert factors.stock_code == '000001.SZ'
        assert factors.data['ma5'] == 10.0
    
    def test_daily_factors_getitem(self):
        """测试下标访问"""
        from core.strategies.strategy_layers import DailyFactors
        
        factors = DailyFactors(
            date='2024-01-15',
            stock_code='000001.SZ',
            data={'ma5': 10.0, 'ma10': 9.5}
        )
        
        assert factors['ma5'] == 10.0
        assert factors['ma10'] == 9.5
    
    def test_daily_factors_getitem_missing(self):
        """测试缺失键返回 NaN"""
        from core.strategies.strategy_layers import DailyFactors
        
        factors = DailyFactors(
            date='2024-01-15',
            stock_code='000001.SZ',
            data={'ma5': 10.0}
        )
        
        assert np.isnan(factors['ma10'])
    
    def test_daily_factors_get(self):
        """测试 get 方法"""
        from core.strategies.strategy_layers import DailyFactors
        
        factors = DailyFactors(
            date='2024-01-15',
            stock_code='000001.SZ',
            data={'ma5': 10.0}
        )
        
        assert factors.get('ma5') == 10.0
        assert factors.get('ma10', 0.0) == 0.0


class TestPosition:
    """持仓状态测试"""
    
    def test_position_init_default(self):
        """测试默认初始化"""
        from core.strategies.strategy_layers import Position
        
        position = Position()
        
        assert position.has_position is False
        assert position.shares == 0
        assert position.cost_price == 0.0
        assert position.holding_days == 0
    
    def test_position_with_values(self):
        """测试带值初始化"""
        from core.strategies.strategy_layers import Position
        
        position = Position(
            has_position=True,
            shares=1000,
            cost_price=10.0,
            holding_days=5,
            unrealized_pnl=500.0
        )
        
        assert position.has_position is True
        assert position.shares == 1000
        assert position.cost_price == 10.0
        assert position.holding_days == 5
        assert position.unrealized_pnl == 500.0


class TestFunctionStrategy:
    """函数策略测试"""
    
    def test_function_strategy_init(self):
        """测试初始化"""
        from core.strategies.strategy_layers import FunctionStrategy
        
        def my_signal_func(date, factors, position, history):
            return 'hold', None
        
        strategy = FunctionStrategy(
            signal_func=my_signal_func,
            required_factors=['ma5', 'ma10']
        )
        
        assert strategy.name == 'my_signal_func'
        assert strategy.required_factors == ['ma5', 'ma10']
    
    def test_function_strategy_with_name(self):
        """测试带名称初始化"""
        from core.strategies.strategy_layers import FunctionStrategy
        
        def my_signal_func(date, factors, position, history):
            return 'hold', None
        
        strategy = FunctionStrategy(
            signal_func=my_signal_func,
            required_factors=['ma5'],
            name='自定义策略'
        )
        
        assert strategy.name == '自定义策略'
    
    def test_function_strategy_call(self):
        """测试策略调用"""
        from core.strategies.strategy_layers import FunctionStrategy, Position
        
        def my_signal_func(date, factors, position, history):
            if factors['ma5'] > factors['ma10']:
                return 'buy', 0.1
            return 'hold', None
        
        strategy = FunctionStrategy(
            signal_func=my_signal_func,
            required_factors=['ma5', 'ma10']
        )
        
        position = Position()
        signal, ratio = strategy.signal_func(
            '2024-01-15',
            {'ma5': 10.0, 'ma10': 9.0},
            position,
            []
        )
        
        assert signal == 'buy'
        assert ratio == 0.1

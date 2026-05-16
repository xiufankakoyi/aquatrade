"""
core/strategies/user/simpletest.py 示例策略测试

测试内容：
1. MyStrategy 初始化
2. generate_signals 方法
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock


class TestMyStrategyInit:
    """示例策略初始化测试"""
    
    def test_strategy_init_default(self):
        """测试默认初始化"""
        from core.strategies.user.simpletest import MyStrategy
        
        strategy = MyStrategy()
        
        assert strategy.strategy_name == "我的策略"
    
    def test_strategy_init_with_name(self):
        """测试带名称初始化"""
        from core.strategies.user.simpletest import MyStrategy
        
        strategy = MyStrategy(name="自定义策略")
        
        assert strategy.strategy_name == "我的策略"


class TestMyStrategyGenerateSignals:
    """示例策略信号生成测试"""
    
    def test_generate_signals_buy(self):
        """测试买入信号"""
        from core.strategies.user.simpletest import MyStrategy
        
        strategy = MyStrategy()
        
        stock_pool = pd.DataFrame({
            'stock_code': ['000001.SZ', '000002.SZ'],
            'close': [15.0, 20.0],
            'ma5': [14.0, 19.0],
            'ma20': [13.0, 18.0],
            'volume_ratio': [2.5, 3.0],
            'is_st': [False, False],
            'is_limit_up': [False, False]
        })
        
        signals = strategy.generate_signals(
            current_date='2024-01-15',
            stock_pool_today=stock_pool,
            data_query=None
        )
        
        assert signals['000001.SZ'] == 'buy'
        assert signals['000002.SZ'] == 'buy'
    
    def test_generate_signals_sell(self):
        """测试卖出信号"""
        from core.strategies.user.simpletest import MyStrategy
        
        strategy = MyStrategy()
        
        stock_pool = pd.DataFrame({
            'stock_code': ['000001.SZ', '000002.SZ'],
            'close': [13.0, 18.0],
            'ma5': [14.0, 19.0],
            'ma20': [15.0, 20.0],
            'volume_ratio': [1.0, 1.0],
            'is_st': [False, False],
            'is_limit_up': [False, False]
        })
        
        signals = strategy.generate_signals(
            current_date='2024-01-15',
            stock_pool_today=stock_pool,
            data_query=None
        )
        
        assert signals['000001.SZ'] == 'sell'
        assert signals['000002.SZ'] == 'sell'
    
    def test_generate_signals_hold(self):
        """测试持有信号"""
        from core.strategies.user.simpletest import MyStrategy
        
        strategy = MyStrategy()
        
        stock_pool = pd.DataFrame({
            'stock_code': ['000001.SZ'],
            'close': [14.5],
            'ma5': [14.0],
            'ma20': [13.0],
            'volume_ratio': [1.5],
            'is_st': [False],
            'is_limit_up': [False]
        })
        
        signals = strategy.generate_signals(
            current_date='2024-01-15',
            stock_pool_today=stock_pool,
            data_query=None
        )
        
        assert signals['000001.SZ'] == 'hold'
    
    def test_generate_signals_st_stock(self):
        """测试ST股票不买入"""
        from core.strategies.user.simpletest import MyStrategy
        
        strategy = MyStrategy()
        
        stock_pool = pd.DataFrame({
            'stock_code': ['000001.SZ'],
            'close': [15.0],
            'ma5': [14.0],
            'ma20': [13.0],
            'volume_ratio': [2.5],
            'is_st': [True],
            'is_limit_up': [False]
        })
        
        signals = strategy.generate_signals(
            current_date='2024-01-15',
            stock_pool_today=stock_pool,
            data_query=None
        )
        
        assert signals['000001.SZ'] == 'hold'
    
    def test_generate_signals_limit_up(self):
        """测试涨停股票不买入"""
        from core.strategies.user.simpletest import MyStrategy
        
        strategy = MyStrategy()
        
        stock_pool = pd.DataFrame({
            'stock_code': ['000001.SZ'],
            'close': [15.0],
            'ma5': [14.0],
            'ma20': [13.0],
            'volume_ratio': [2.5],
            'is_st': [False],
            'is_limit_up': [True]
        })
        
        signals = strategy.generate_signals(
            current_date='2024-01-15',
            stock_pool_today=stock_pool,
            data_query=None
        )
        
        assert signals['000001.SZ'] == 'hold'

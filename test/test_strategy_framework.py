"""
core/strategies/strategy_framework.py 策略框架测试

测试内容：
1. StrategyBase 初始化
2. simple_strategy 装饰器
3. 执行价格配置
4. 参数规范接口
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock


class TestStrategyBaseInit:
    """策略基类初始化测试"""
    
    def test_init_default_name(self):
        """测试默认名称初始化"""
        from core.strategies.strategy_framework import StrategyBase
        
        strategy = StrategyBase()
        
        assert strategy.name == "StrategyBase"
        assert strategy.required_days == 30
    
    def test_init_custom_name(self):
        """测试自定义名称初始化"""
        from core.strategies.strategy_framework import StrategyBase
        
        strategy = StrategyBase(name="自定义策略")
        
        assert strategy.name == "自定义策略"
    
    def test_init_cache(self):
        """测试缓存初始化"""
        from core.strategies.strategy_framework import StrategyBase
        
        strategy = StrategyBase()
        
        assert isinstance(strategy._cache, dict)
    
    def test_init_holding_state(self):
        """测试持仓状态初始化"""
        from core.strategies.strategy_framework import StrategyBase
        
        strategy = StrategyBase()
        
        assert isinstance(strategy.holding_state, dict)


class TestStrategyBaseContext:
    """运行时上下文测试"""
    
    def test_set_runtime_context(self):
        """测试设置运行时上下文"""
        from core.strategies.strategy_framework import StrategyBase
        
        strategy = StrategyBase()
        
        portfolio = {"000001.SZ": 1000}
        strategy.set_runtime_context("2024-01-15", portfolio, 100000.0)
        
        assert strategy.current_date == "2024-01-15"
        assert strategy.current_portfolio == portfolio
        assert strategy.current_cash == 100000.0
    
    def test_set_runtime_context_none(self):
        """测试设置空运行时上下文"""
        from core.strategies.strategy_framework import StrategyBase
        
        strategy = StrategyBase()
        
        strategy.set_runtime_context(None, None, None)
        
        assert strategy.current_date is None
        assert strategy.current_portfolio == {}
        assert strategy.current_cash == 0.0


class TestStrategyBaseExecutionPrice:
    """执行价格测试"""
    
    def test_get_execution_price_default(self):
        """测试默认执行价格"""
        from core.strategies.strategy_framework import StrategyBase
        
        strategy = StrategyBase()
        
        assert strategy.get_execution_price("buy") == "close"
        assert strategy.get_execution_price("sell") == "close"
    
    def test_get_execution_price_dict(self):
        """测试字典配置执行价格"""
        from core.strategies.strategy_framework import StrategyBase
        
        strategy = StrategyBase()
        strategy.execution_price = {
            "buy": "open",
            "sell": "close",
            "default": "close"
        }
        
        assert strategy.get_execution_price("buy") == "open"
        assert strategy.get_execution_price("sell") == "close"
    
    def test_get_execution_price_string(self):
        """测试字符串配置执行价格"""
        from core.strategies.strategy_framework import StrategyBase
        
        strategy = StrategyBase()
        strategy.execution_price = "open"
        
        assert strategy.get_execution_price("buy") == "open"


class TestStrategyBaseParamSpec:
    """参数规范测试"""
    
    def test_get_param_spec_default(self):
        """测试默认参数规范"""
        from core.strategies.strategy_framework import StrategyBase
        
        spec = StrategyBase.get_param_spec()
        
        assert spec == []
    
    def test_default_optimization_config(self):
        """测试默认优化配置"""
        from core.strategies.strategy_framework import StrategyBase
        
        config = StrategyBase.default_optimization_config()
        
        assert config == {}


class TestStrategyBaseIndicators:
    """指标配置测试"""
    
    def test_get_required_indicators_default(self):
        """测试默认指标配置"""
        from core.strategies.strategy_framework import StrategyBase
        
        strategy = StrategyBase()
        
        indicators = strategy.get_required_indicators()
        
        assert indicators == []


class TestSimpleStrategyDecorator:
    """simple_strategy 装饰器测试"""
    
    def test_decorator_wraps_function(self):
        """测试装饰器包装函数"""
        from core.strategies.strategy_framework import simple_strategy, StrategyBase
        
        class TestStrategy(StrategyBase):
            @simple_strategy(required_days=30)
            def generate_signals(self, stock_code, data, history):
                return 'buy'
        
        strategy = TestStrategy()
        
        assert hasattr(strategy, 'generate_signals')
    
    def test_decorator_preserves_function_name(self):
        """测试装饰器保留函数名"""
        from core.strategies.strategy_framework import simple_strategy, StrategyBase
        
        class TestStrategy(StrategyBase):
            @simple_strategy(required_days=30)
            def generate_signals(self, stock_code, data, history):
                return 'buy'
        
        strategy = TestStrategy()
        
        assert strategy.generate_signals.__name__ == 'generate_signals'

"""
core/strategies/vectorized_strategy_base.py 向量化策略基类测试

测试内容：
1. VectorizedStrategyBase 初始化
2. is_vectorized 标记
3. generate_signals 方法
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock


class TestVectorizedStrategyBaseInit:
    """向量化策略基类初始化测试"""
    
    def test_init_default_name(self):
        """测试默认名称初始化"""
        from core.strategies.vectorized_strategy_base import VectorizedStrategyBase
        
        strategy = VectorizedStrategyBase()
        
        assert strategy.is_vectorized is True
    
    def test_init_custom_name(self):
        """测试自定义名称初始化"""
        from core.strategies.vectorized_strategy_base import VectorizedStrategyBase
        
        strategy = VectorizedStrategyBase(name="测试策略")
        
        assert strategy.is_vectorized is True
        assert strategy.name == "测试策略"


class TestVectorizedStrategyBaseGenerateSignals:
    """向量化策略信号生成测试"""
    
    def test_generate_signals_empty_pool(self):
        """测试空股票池"""
        from core.strategies.vectorized_strategy_base import VectorizedStrategyBase
        
        strategy = VectorizedStrategyBase()
        
        result = strategy.generate_signals("2024-01-15", None, Mock())
        
        assert result == {}
    
    def test_generate_signals_empty_dataframe(self):
        """测试空 DataFrame"""
        from core.strategies.vectorized_strategy_base import VectorizedStrategyBase
        
        strategy = VectorizedStrategyBase()
        
        empty_df = pd.DataFrame()
        result = strategy.generate_signals("2024-01-15", empty_df, Mock())
        
        assert result == {}


class TestVectorizedStrategyBaseMethods:
    """向量化策略方法测试"""
    
    def test_has_generate_signals_vectorized(self):
        """测试是否有向量化信号生成方法"""
        from core.strategies.vectorized_strategy_base import VectorizedStrategyBase
        
        strategy = VectorizedStrategyBase()
        
        assert hasattr(strategy, 'generate_signals_vectorized')
    
    def test_has_pre_screen_stocks(self):
        """测试是否有预筛选方法"""
        from core.strategies.vectorized_strategy_base import VectorizedStrategyBase
        
        strategy = VectorizedStrategyBase()
        
        assert hasattr(strategy, '_pre_screen_stocks')
    
    def test_has_prepare_market_matrix(self):
        """测试是否有准备市场矩阵方法"""
        from core.strategies.vectorized_strategy_base import VectorizedStrategyBase
        
        strategy = VectorizedStrategyBase()
        
        assert hasattr(strategy, '_prepare_market_matrix')

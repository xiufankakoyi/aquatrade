"""
core/strategies/vectorized_base.py 向量化策略基类测试

测试内容：
1. VectorizedStrategyBase 初始化
2. 矩阵缓存功能
3. safe_matrix_fill 装饰器
4. prepare_data 方法
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock


class TestMatrixCacheFunctions:
    """矩阵缓存函数测试"""
    
    def test_get_cache_key(self):
        """测试缓存键生成"""
        from core.strategies.vectorized_base import _get_cache_key
        
        data = {"test": "data"}
        dates = ["2024-01-01", "2024-01-02"]
        codes = ["000001.SZ", "000002.SZ"]
        
        key = _get_cache_key(data, dates, codes)
        
        assert isinstance(key, tuple)
        assert len(key) == 3
        assert key[1] == ("2024-01-01", "2024-01-02")
        assert key[2] == ("000001.SZ", "000002.SZ")
    
    def test_clear_matrix_cache(self):
        """测试清除矩阵缓存"""
        from core.strategies.vectorized_base import (
            clear_matrix_cache, _global_matrix_cache,
            _global_matrix_cache_hits, _global_matrix_cache_misses
        )
        
        _global_matrix_cache["test_key"] = {"data": "test"}
        
        clear_matrix_cache()
        
        assert len(_global_matrix_cache) == 0
    
    def test_get_matrix_cache_stats(self):
        """测试获取缓存统计"""
        from core.strategies.vectorized_base import (
            get_matrix_cache_stats, clear_matrix_cache
        )
        
        clear_matrix_cache()
        
        stats = get_matrix_cache_stats()
        
        assert isinstance(stats, dict)
        assert 'hits' in stats
        assert 'misses' in stats
        assert 'hit_rate' in stats
        assert 'size' in stats


class TestSafeMatrixFill:
    """安全矩阵填充装饰器测试"""
    
    def test_safe_matrix_fill_valid(self):
        """测试有效数据填充"""
        from core.strategies.vectorized_base import safe_matrix_fill
        
        class TestClass:
            @safe_matrix_fill
            def fill_matrix(self, matrix, row_codes, col_codes, values, name="matrix",
                           trading_dates=None, stock_codes=None):
                matrix[row_codes, col_codes] = values
                return matrix
        
        obj = TestClass()
        
        matrix = np.zeros((3, 3))
        row_codes = np.array([0, 1, 2])
        col_codes = np.array([0, 1, 2])
        values = np.array([1.0, 2.0, 3.0])
        
        result = obj.fill_matrix(
            matrix, row_codes, col_codes, values,
            trading_dates=["2024-01-01", "2024-01-02", "2024-01-03"],
            stock_codes=["000001.SZ", "000002.SZ", "000003.SZ"]
        )
        
        assert result[0, 0] == 1.0
        assert result[1, 1] == 2.0
        assert result[2, 2] == 3.0
    
    def test_safe_matrix_fill_with_invalid_codes(self):
        """测试带无效代码的安全填充"""
        from core.strategies.vectorized_base import safe_matrix_fill
        
        class TestClass:
            @safe_matrix_fill
            def fill_matrix(self, matrix, row_codes, col_codes, values, name="matrix",
                           trading_dates=None, stock_codes=None):
                matrix[row_codes, col_codes] = values
                return matrix
        
        obj = TestClass()
        
        matrix = np.zeros((3, 3))
        row_codes = np.array([0, -1, 2])
        col_codes = np.array([0, 1, -1])
        values = np.array([1.0, 2.0, 3.0])
        
        result = obj.fill_matrix(
            matrix, row_codes, col_codes, values,
            trading_dates=["2024-01-01", "2024-01-02", "2024-01-03"],
            stock_codes=["000001.SZ", "000002.SZ", "000003.SZ"]
        )
        
        assert result[0, 0] == 1.0


class TestVectorizedStrategyBaseInit:
    """向量化策略基类初始化测试"""
    
    def test_init_default_name(self):
        """测试默认名称初始化"""
        from core.strategies.vectorized_base import VectorizedStrategyBase
        
        strategy = VectorizedStrategyBase()
        
        assert strategy.name == "VectorizedStrategyBase"
    
    def test_init_custom_name(self):
        """测试自定义名称初始化"""
        from core.strategies.vectorized_base import VectorizedStrategyBase
        
        strategy = VectorizedStrategyBase(name="自定义策略")
        
        assert strategy.name == "自定义策略"
    
    def test_init_matrix_none(self):
        """测试矩阵初始化为 None"""
        from core.strategies.vectorized_base import VectorizedStrategyBase
        
        strategy = VectorizedStrategyBase()
        
        assert strategy.close is None
        assert strategy.open is None
        assert strategy.high is None
        assert strategy.low is None
        assert strategy.volume is None
    
    def test_init_factors_dict(self):
        """测试因子字典初始化"""
        from core.strategies.vectorized_base import VectorizedStrategyBase
        
        strategy = VectorizedStrategyBase()
        
        assert isinstance(strategy.factors, dict)
    
    def test_init_required_factors(self):
        """测试必需因子列表"""
        from core.strategies.vectorized_base import VectorizedStrategyBase
        
        class MyStrategy(VectorizedStrategyBase):
            required_factors = ['rsi_14', 'macd_dif']
        
        strategy = MyStrategy()
        
        assert strategy.required_factors == ['rsi_14', 'macd_dif']


class TestVectorizedStrategyBasePrepareData:
    """向量化策略基类数据准备测试"""
    
    def test_prepare_data_empty(self):
        """测试空数据准备"""
        from core.strategies.vectorized_base import VectorizedStrategyBase
        
        strategy = VectorizedStrategyBase()
        
        strategy.prepare_data({}, [], [])
        
        assert strategy.T == 0
        assert strategy.N == 0
    
    def test_prepare_data_with_dates(self):
        """测试带日期的数据准备"""
        from core.strategies.vectorized_base import VectorizedStrategyBase
        
        strategy = VectorizedStrategyBase()
        
        trading_dates = ["2024-01-01", "2024-01-02", "2024-01-03"]
        stock_codes = ["000001.SZ", "000002.SZ"]
        
        strategy.prepare_data({}, trading_dates, stock_codes)
        
        assert strategy.T == 3
        assert strategy.N == 2
        assert strategy.close.shape == (3, 2)
    
    def test_prepare_data_with_price_matrix(self):
        """测试带价格矩阵的数据准备"""
        from core.strategies.vectorized_base import VectorizedStrategyBase
        
        strategy = VectorizedStrategyBase()
        
        trading_dates = ["2024-01-01", "2024-01-02"]
        stock_codes = ["000001.SZ", "000002.SZ"]
        price_matrix = np.random.randn(2, 2, 4).astype(np.float32)
        
        strategy.prepare_data({}, trading_dates, stock_codes, price_matrix)
        
        assert strategy.open.shape == (2, 2)
        assert strategy.high.shape == (2, 2)
        assert strategy.low.shape == (2, 2)
        assert strategy.close.shape == (2, 2)

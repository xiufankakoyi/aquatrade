"""
core/strategies/vectorized_base.py 向量化策略基类测试

测试内容：
1. 矩阵缓存功能
2. 缓存统计
3. 安全填充装饰器
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock


class TestMatrixCache:
    """矩阵缓存测试"""
    
    def test_get_cache_key(self):
        """测试缓存键生成"""
        from core.strategies.vectorized_base import _get_cache_key
        
        data = {"test": "data"}
        dates = ["2024-01-01", "2024-01-02"]
        codes = ["000001.SZ", "000002.SZ"]
        
        key = _get_cache_key(data, dates, codes)
        
        assert isinstance(key, tuple)
        assert len(key) == 3
    
    def test_clear_matrix_cache(self):
        """测试清除缓存"""
        from core.strategies.vectorized_base import (
            _global_matrix_cache,
            clear_matrix_cache
        )
        
        _global_matrix_cache["test_key"] = {"test": "data"}
        
        clear_matrix_cache()
        
        assert len(_global_matrix_cache) == 0
    
    def test_get_matrix_cache_stats(self):
        """测试缓存统计"""
        from core.strategies.vectorized_base import (
            clear_matrix_cache,
            get_matrix_cache_stats
        )
        
        clear_matrix_cache()
        
        stats = get_matrix_cache_stats()
        
        assert 'hits' in stats
        assert 'misses' in stats
        assert 'hit_rate' in stats
        assert 'size' in stats


class TestSafeMatrixFill:
    """安全填充装饰器测试"""
    
    def test_safe_matrix_fill_decorator(self):
        """测试安全填充装饰器"""
        from core.strategies.vectorized_base import safe_matrix_fill
        
        class TestClass:
            @safe_matrix_fill
            def fill_matrix(self, matrix, row_codes, col_codes, values, name="matrix",
                           trading_dates=None, stock_codes=None):
                return matrix
        
        obj = TestClass()
        
        matrix = np.zeros((3, 3))
        row_codes = np.array([0, 1, 2])
        col_codes = np.array([0, 1, 2])
        values = np.array([1.0, 2.0, 3.0])
        
        result = obj.fill_matrix(matrix, row_codes, col_codes, values)
        
        assert result is not None
    
    def test_safe_matrix_fill_with_invalid_codes(self):
        """测试带无效代码的安全填充"""
        from core.strategies.vectorized_base import safe_matrix_fill
        
        class TestClass:
            @safe_matrix_fill
            def fill_matrix(self, matrix, row_codes, col_codes, values, name="matrix",
                           trading_dates=None, stock_codes=None):
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
        
        assert result is not None


class TestVectorizedStrategyBase:
    """向量化策略基类测试"""
    
    def test_strategy_base_import(self):
        """测试策略基类导入"""
        from core.strategies.vectorized_base import VectorizedStrategyBase
        
        assert VectorizedStrategyBase is not None
    
    def test_strategy_base_inheritance(self):
        """测试策略基类继承"""
        from core.strategies.vectorized_base import VectorizedStrategyBase
        from core.strategies.strategy_framework import StrategyBase
        
        assert issubclass(VectorizedStrategyBase, StrategyBase)

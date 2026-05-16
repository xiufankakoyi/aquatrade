"""
core/strategies/vectorized_base.py 向量化基类补充测试

测试内容：
1. 矩阵缓存功能
2. 向量化基类方法
"""

import pytest
import numpy as np
import pandas as pd
import polars as pl
from unittest.mock import Mock, patch, MagicMock


class TestVectorizedStrategyBaseMatrixCache:
    """向量化基类矩阵缓存测试"""
    
    def test_clear_matrix_cache(self):
        """测试清除矩阵缓存"""
        from core.strategies.vectorized_base import clear_matrix_cache
        
        clear_matrix_cache()
        
        from core.strategies.vectorized_base import _global_matrix_cache
        assert len(_global_matrix_cache) == 0
    
    def test_get_matrix_cache_stats(self):
        """测试获取缓存统计"""
        from core.strategies.vectorized_base import get_matrix_cache_stats, clear_matrix_cache
        
        clear_matrix_cache()
        stats = get_matrix_cache_stats()
        
        assert 'hits' in stats
        assert 'misses' in stats
        assert 'hit_rate' in stats
    
    def test_get_cache_key(self):
        """测试缓存键生成"""
        from core.strategies.vectorized_base import _get_cache_key
        
        data = {"test": "data"}
        dates = ["2024-01-01", "2024-01-02"]
        codes = ["000001.SZ", "000002.SZ"]
        
        key = _get_cache_key(data, dates, codes)
        
        assert isinstance(key, tuple)
        assert len(key) == 3


class TestVectorizedStrategyBaseMethods:
    """向量化基类方法测试"""
    
    def test_has_generate_signals_vectorized(self):
        """测试是否有向量化信号生成方法"""
        from core.strategies.vectorized_base import VectorizedStrategyBase
        
        assert hasattr(VectorizedStrategyBase, 'generate_signals_vectorized')
    
    def test_has_prepare_data(self):
        """测试是否有数据准备方法"""
        from core.strategies.vectorized_base import VectorizedStrategyBase
        
        assert hasattr(VectorizedStrategyBase, 'prepare_data')


class TestSafeMatrixFill:
    """安全矩阵填充测试"""
    
    def test_safe_matrix_fill_decorator(self):
        """测试安全矩阵填充装饰器"""
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

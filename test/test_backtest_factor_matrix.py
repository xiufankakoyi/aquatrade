"""
core/backtest/factor_matrix.py 因子矩阵测试

测试内容：
1. FactorMatrix 数据结构
2. 因子数据访问
3. 股票代码转换
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os


class TestStockCodeConversion:
    """股票代码转换测试"""
    
    def test_stock_code_to_int_sz(self):
        """测试深市代码转换"""
        from core.backtest.factor_matrix import stock_code_to_int
        
        result = stock_code_to_int("000001.SZ")
        
        assert result == 1000001
    
    def test_stock_code_to_int_sh(self):
        """测试沪市代码转换"""
        from core.backtest.factor_matrix import stock_code_to_int
        
        result = stock_code_to_int("600001.SH")
        
        assert result == 6600001
    
    def test_stock_code_to_int_numeric(self):
        """测试纯数字代码"""
        from core.backtest.factor_matrix import stock_code_to_int
        
        result = stock_code_to_int("123456")
        
        assert result == 123456
    
    def test_stock_code_to_int_with_spaces(self):
        """测试带空格的代码"""
        from core.backtest.factor_matrix import stock_code_to_int
        
        result = stock_code_to_int(" 000001.SZ ")
        
        assert result == 1000001


class TestFactorMatrixDataStructure:
    """FactorMatrix 数据结构测试"""
    
    @pytest.fixture
    def sample_factor_matrix(self):
        """创建示例因子矩阵"""
        from core.backtest.factor_matrix import FactorMatrix
        
        T, N, F = 5, 3, 2
        values = np.random.randn(T, N, F).astype(np.float32)
        dates = ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
        codes_int = np.array([1000001, 1000002, 6000001], dtype=np.int32)
        codes_str = ["000001.SZ", "000002.SZ", "600001.SH"]
        factor_names = ["factor_a", "factor_b"]
        date_to_idx = {d: i for i, d in enumerate(dates)}
        code_to_idx = {str(c): i for i, c in enumerate(codes_int)}
        
        return FactorMatrix(
            values=values,
            dates=dates,
            codes_int=codes_int,
            codes_str=codes_str,
            factor_names=factor_names,
            date_to_idx=date_to_idx,
            code_to_idx=code_to_idx
        )
    
    def test_get_day_data(self, sample_factor_matrix):
        """测试获取某天数据"""
        result = sample_factor_matrix.get_day_data("2024-01-03")
        
        assert result is not None
        assert result.shape == (3, 2)
    
    def test_get_day_data_not_found(self, sample_factor_matrix):
        """测试获取不存在的日期"""
        result = sample_factor_matrix.get_day_data("2024-12-31")
        
        assert result is None
    
    def test_get_day_index(self, sample_factor_matrix):
        """测试获取日期索引"""
        result = sample_factor_matrix.get_day_index("2024-01-03")
        
        assert result == 2
    
    def test_get_day_index_not_found(self, sample_factor_matrix):
        """测试获取不存在日期的索引"""
        result = sample_factor_matrix.get_day_index("2024-12-31")
        
        assert result == -1
    
    def test_get_factor(self, sample_factor_matrix):
        """测试获取因子数据"""
        result = sample_factor_matrix.get_factor("factor_a")
        
        assert result is not None
        assert result.shape == (5, 3)
    
    def test_get_factor_not_found(self, sample_factor_matrix):
        """测试获取不存在的因子"""
        result = sample_factor_matrix.get_factor("nonexistent")
        
        assert result is None


class TestFactorMatrixSaveLoad:
    """FactorMatrix 保存加载测试"""
    
    def test_to_parquet_creates_files(self):
        """测试保存创建文件"""
        from core.backtest.factor_matrix import FactorMatrix
        
        import tempfile
        tmpdir = tempfile.mkdtemp()
        
        try:
            path = Path(tmpdir) / "test_factor_matrix.parquet"
            
            T, N, F = 3, 2, 1
            values = np.array([
                [[1.0], [2.0]],
                [[3.0], [4.0]],
                [[5.0], [6.0]],
            ], dtype=np.float32)
            dates = ["2024-01-01", "2024-01-02", "2024-01-03"]
            codes_int = np.array([1000001, 6600001], dtype=np.int32)
            codes_str = ["000001.SZ", "600001.SH"]
            factor_names = ["test_factor"]
            date_to_idx = {d: i for i, d in enumerate(dates)}
            code_to_idx = {str(c): i for i, c in enumerate(codes_int)}
            
            fm = FactorMatrix(
                values=values,
                dates=dates,
                codes_int=codes_int,
                codes_str=codes_str,
                factor_names=factor_names,
                date_to_idx=date_to_idx,
                code_to_idx=code_to_idx
            )
            
            fm.to_parquet(path)
            
            assert path.exists()
            assert path.with_suffix('.json').exists()
            assert path.with_suffix('.npy').exists()
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestFactorMatrixShape:
    """FactorMatrix 形状测试"""
    
    def test_values_shape(self):
        """测试值数组形状"""
        from core.backtest.factor_matrix import FactorMatrix
        
        T, N, F = 10, 5, 3
        values = np.zeros((T, N, F), dtype=np.float32)
        
        fm = FactorMatrix(
            values=values,
            dates=["d"] * T,
            codes_int=np.zeros(N, dtype=np.int32),
            codes_str=["c"] * N,
            factor_names=["f"] * F,
            date_to_idx={},
            code_to_idx={}
        )
        
        assert fm.values.shape == (T, N, F)
    
    def test_empty_factor_matrix(self):
        """测试空因子矩阵"""
        from core.backtest.factor_matrix import FactorMatrix
        
        fm = FactorMatrix(
            values=np.array([], dtype=np.float32).reshape(0, 0, 0),
            dates=[],
            codes_int=np.array([], dtype=np.int32),
            codes_str=[],
            factor_names=[],
            date_to_idx={},
            code_to_idx={}
        )
        
        assert fm.values.shape == (0, 0, 0)
        assert len(fm.dates) == 0

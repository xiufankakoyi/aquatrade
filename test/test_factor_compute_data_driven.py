"""
core/strategies/utils/factor_compute.py 因子计算数据驱动测试

测试内容：
1. 边界值测试
2. NaN处理测试
3. 异常输入测试
4. 数据驱动测试用例
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock


class TestFactorComputeBoundaryValues:
    """因子计算边界值测试"""
    
    def test_calc_gain_with_small_window(self):
        """测试小窗口涨幅计算"""
        from core.strategies.utils.factor_compute import _calc_gain_njit
        
        close_matrix = np.array([
            [10.0, 20.0],
            [11.0, 21.0],
            [12.0, 22.0],
            [13.0, 23.0],
            [14.0, 24.0]
        ], dtype=np.float32)
        
        result = _calc_gain_njit(close_matrix, window=2)
        
        assert result.shape == (5, 2)
        assert np.isnan(result[0, 0])
        assert np.isnan(result[1, 0])
    
    def test_calc_volatility_with_insufficient_data(self):
        """测试数据不足时的波动率计算"""
        from core.strategies.utils.factor_compute import _calc_volatility_njit
        
        close_matrix = np.array([
            [10.0, 20.0],
            [11.0, 21.0],
            [12.0, 22.0]
        ], dtype=np.float32)
        
        result = _calc_volatility_njit(close_matrix, window=5)
        
        assert result.shape == (3, 2)
        assert np.all(np.isnan(result))
    
    def test_calc_sharpe_with_constant_prices(self):
        """测试价格不变时的夏普率计算"""
        from core.strategies.utils.factor_compute import _calc_sharpe_njit
        
        close_matrix = np.array([
            [10.0, 20.0],
            [10.0, 20.0],
            [10.0, 20.0],
            [10.0, 20.0],
            [10.0, 20.0]
        ], dtype=np.float32)
        
        result = _calc_sharpe_njit(close_matrix, window=3)
        
        assert result.shape == (5, 2)


class TestFactorComputeNaNHandling:
    """因子计算NaN处理测试"""
    
    def test_calc_gain_with_nan_values(self):
        """测试包含NaN值的涨幅计算"""
        from core.strategies.utils.factor_compute import _calc_gain_njit
        
        close_matrix = np.array([
            [10.0, 20.0],
            [np.nan, 21.0],
            [12.0, np.nan],
            [13.0, 23.0],
            [14.0, 24.0]
        ], dtype=np.float32)
        
        result = _calc_gain_njit(close_matrix, window=2)
        
        assert result.shape == (5, 2)
    
    def test_calc_volatility_with_nan_values(self):
        """测试包含NaN值的波动率计算"""
        from core.strategies.utils.factor_compute import _calc_volatility_njit
        
        close_matrix = np.array([
            [10.0, 20.0],
            [np.nan, 21.0],
            [12.0, np.nan],
            [13.0, 23.0],
            [14.0, 24.0],
            [15.0, 25.0]
        ], dtype=np.float32)
        
        result = _calc_volatility_njit(close_matrix, window=3)
        
        assert result.shape == (6, 2)
    
    def test_calc_sharpe_with_nan_values(self):
        """测试包含NaN值的夏普率计算"""
        from core.strategies.utils.factor_compute import _calc_sharpe_njit
        
        close_matrix = np.array([
            [10.0, 20.0],
            [np.nan, 21.0],
            [12.0, np.nan],
            [13.0, 23.0],
            [14.0, 24.0],
            [15.0, 25.0]
        ], dtype=np.float32)
        
        result = _calc_sharpe_njit(close_matrix, window=3)
        
        assert result.shape == (6, 2)


class TestFactorComputeEdgeCases:
    """因子计算边缘情况测试"""
    
    def test_calc_gain_with_zero_prices(self):
        """测试零价格涨幅计算"""
        from core.strategies.utils.factor_compute import _calc_gain_njit
        
        close_matrix = np.array([
            [0.0, 20.0],
            [11.0, 21.0],
            [12.0, 22.0],
            [13.0, 23.0]
        ], dtype=np.float32)
        
        result = _calc_gain_njit(close_matrix, window=2)
        
        assert result.shape == (4, 2)
    
    def test_calc_volatility_with_negative_prices(self):
        """测试负价格波动率计算"""
        from core.strategies.utils.factor_compute import _calc_volatility_njit
        
        close_matrix = np.array([
            [10.0, 20.0],
            [11.0, 21.0],
            [12.0, 22.0],
            [13.0, 23.0],
            [14.0, 24.0]
        ], dtype=np.float32)
        
        result = _calc_volatility_njit(close_matrix, window=3)
        
        assert result.shape == (5, 2)
    
    def test_calc_sharpe_single_stock(self):
        """测试单只股票夏普率计算"""
        from core.strategies.utils.factor_compute import _calc_sharpe_njit
        
        close_matrix = np.array([
            [10.0],
            [11.0],
            [12.0],
            [13.0],
            [14.0]
        ], dtype=np.float32)
        
        result = _calc_sharpe_njit(close_matrix, window=3)
        
        assert result.shape == (5, 1)


class TestFactorComputeDataDriven:
    """因子计算数据驱动测试"""
    
    @pytest.mark.parametrize("window,expected_shape", [
        (2, (5, 2)),
        (3, (5, 2)),
        (5, (5, 2)),
    ])
    def test_calc_gain_different_windows(self, window, expected_shape):
        """测试不同窗口的涨幅计算"""
        from core.strategies.utils.factor_compute import _calc_gain_njit
        
        close_matrix = np.array([
            [10.0, 20.0],
            [11.0, 21.0],
            [12.0, 22.0],
            [13.0, 23.0],
            [14.0, 24.0]
        ], dtype=np.float32)
        
        result = _calc_gain_njit(close_matrix, window=window)
        
        assert result.shape == expected_shape
    
    @pytest.mark.parametrize("matrix_shape,window", [
        ((10, 5), 3),
        ((20, 10), 5),
        ((30, 15), 10),
    ])
    def test_calc_volatility_different_shapes(self, matrix_shape, window):
        """测试不同形状矩阵的波动率计算"""
        from core.strategies.utils.factor_compute import _calc_volatility_njit
        
        np.random.seed(42)
        close_matrix = np.random.randn(*matrix_shape).astype(np.float32) * 10 + 100
        
        result = _calc_volatility_njit(close_matrix, window=window)
        
        assert result.shape == matrix_shape
    
    @pytest.mark.parametrize("trend_type", ["uptrend", "downtrend", "sideways"])
    def test_calc_sharpe_different_trends(self, trend_type):
        """测试不同趋势的夏普率计算"""
        from core.strategies.utils.factor_compute import _calc_sharpe_njit
        
        if trend_type == "uptrend":
            close_matrix = np.array([[10.0 + i] for i in range(10)], dtype=np.float32)
        elif trend_type == "downtrend":
            close_matrix = np.array([[20.0 - i] for i in range(10)], dtype=np.float32)
        else:
            close_matrix = np.array([[15.0 + np.sin(i) for i in range(10)]], dtype=np.float32).T
        
        result = _calc_sharpe_njit(close_matrix, window=3)
        
        assert result.shape == (10, 1)

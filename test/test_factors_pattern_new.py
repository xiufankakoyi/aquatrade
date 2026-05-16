"""
core/factors/pattern_factors.py 形态因子测试

测试内容：
1. 局部极值点检测
2. 收敛三角形计算
3. 因子矩阵计算
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch


class TestFindLocalExtrema:
    """局部极值点检测测试"""
    
    def test_find_local_extrema_basic(self):
        """测试基本极值点检测"""
        from core.factors.pattern_factors import _find_local_extrema_numba
        
        prices = np.array([10.0, 12.0, 11.0, 13.0, 10.0, 14.0, 9.0])
        
        highs, lows = _find_local_extrema_numba(prices, window=1)
        
        assert len(highs) > 0
        assert len(lows) > 0
    
    def test_find_local_extrema_short_prices(self):
        """测试短价格序列"""
        from core.factors.pattern_factors import _find_local_extrema_numba
        
        prices = np.array([10.0])
        
        highs, lows = _find_local_extrema_numba(prices, window=2)
        
        assert len(highs) == 1
        assert len(lows) == 1
        assert highs[0] == -1
        assert lows[0] == -1
    
    def test_find_local_extrema_flat(self):
        """测试平坦价格序列"""
        from core.factors.pattern_factors import _find_local_extrema_numba
        
        prices = np.array([10.0] * 10)
        
        highs, lows = _find_local_extrema_numba(prices, window=2)
        
        assert len(highs) > 0
        assert len(lows) > 0
    
    def test_find_local_extrema_with_trend(self):
        """测试趋势序列"""
        from core.factors.pattern_factors import _find_local_extrema_numba
        
        prices = np.array([10.0, 11.0, 12.0, 13.0, 14.0, 13.0, 12.0, 11.0, 10.0])
        
        highs, lows = _find_local_extrema_numba(prices, window=2)
        
        assert len(highs) > 0
        assert len(lows) > 0


class TestCalculateApexConvergence:
    """收敛三角形计算测试"""
    
    def test_calculate_apex_convergence_no_pattern(self):
        """测试无形态"""
        from core.factors.pattern_factors import _calculate_apex_convergence
        
        prices = np.array([10.0] * 30)
        highs = np.array([5, 10, 15, 20, 25])
        lows = np.array([3, 8, 13, 18, 23])
        
        signal, days, confidence = _calculate_apex_convergence(prices, highs, lows)
        
        assert signal == 0.0
        assert days == 999.0
        assert confidence == 0.0
    
    def test_calculate_apex_convergence_insufficient_points(self):
        """测试极值点不足"""
        from core.factors.pattern_factors import _calculate_apex_convergence
        
        prices = np.array([10.0] * 30)
        highs = np.array([5])
        lows = np.array([3])
        
        signal, days, confidence = _calculate_apex_convergence(prices, highs, lows)
        
        assert signal == 0.0
    
    def test_calculate_apex_convergence_invalid_indices(self):
        """测试无效索引"""
        from core.factors.pattern_factors import _calculate_apex_convergence
        
        prices = np.array([10.0] * 30)
        highs = np.array([-1, -1])
        lows = np.array([-1, -1])
        
        signal, days, confidence = _calculate_apex_convergence(prices, highs, lows)
        
        assert signal == 0.0


class TestComputeApexFactorMatrix:
    """因子矩阵计算测试"""
    
    def test_compute_apex_factor_matrix_shape(self):
        """测试输出形状"""
        from core.factors.pattern_factors import _compute_apex_factor_matrix
        
        T, N = 30, 5
        close_matrix = np.random.randn(T, N) * 10 + 100
        
        result = _compute_apex_factor_matrix(close_matrix, window=2)
        
        assert result.shape == (T, N)
    
    def test_compute_apex_factor_matrix_zeros_start(self):
        """测试开头为零"""
        from core.factors.pattern_factors import _compute_apex_factor_matrix
        
        T, N = 30, 3
        close_matrix = np.random.randn(T, N) * 10 + 100
        
        result = _compute_apex_factor_matrix(close_matrix, window=2)
        
        assert np.all(result[:20, :] == 0)
    
    def test_compute_apex_factor_matrix_single_stock(self):
        """测试单只股票"""
        from core.factors.pattern_factors import _compute_apex_factor_matrix
        
        T, N = 30, 1
        close_matrix = np.random.randn(T, N) * 10 + 100
        
        result = _compute_apex_factor_matrix(close_matrix, window=2)
        
        assert result.shape == (T, 1)


class TestPatternFactorsIntegration:
    """形态因子集成测试"""
    
    def test_full_pipeline(self):
        """测试完整流程"""
        from core.factors.pattern_factors import _find_local_extrema_numba, _calculate_apex_convergence
        
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.randn(50) * 0.5)
        
        highs, lows = _find_local_extrema_numba(prices, window=2)
        
        if len(highs) > 0 and highs[0] >= 0:
            signal, days, confidence = _calculate_apex_convergence(prices, highs, lows)
            
            assert signal >= 0.0
            assert days >= 0.0
            assert confidence >= 0.0

"""
core/calc/vectorized_ops.py 向量化计算测试

测试内容：
1. MA 移动平均计算
2. 金叉检测
3. 死叉检测
4. 边界条件处理
"""

import pytest
import numpy as np


class TestCalcMAVectorized:
    """向量化 MA 计算测试"""
    
    def test_calc_ma_basic(self):
        """测试基本 MA 计算"""
        from core.calc.vectorized_ops import calc_ma_vectorized
        
        matrix = np.array([
            [10.0, 20.0],
            [11.0, 21.0],
            [12.0, 22.0],
            [13.0, 23.0],
            [14.0, 24.0],
        ])
        
        result = calc_ma_vectorized(matrix, window=3)
        
        assert result.shape == matrix.shape
        assert np.isnan(result[0, 0])
        assert np.isnan(result[1, 0])
        assert result[2, 0] == 11.0
        assert result[3, 0] == 12.0
        assert result[4, 0] == 13.0
    
    def test_calc_ma_window_2(self):
        """测试窗口为 2 的 MA"""
        from core.calc.vectorized_ops import calc_ma_vectorized
        
        matrix = np.array([
            [10.0, 20.0],
            [12.0, 24.0],
            [14.0, 28.0],
        ])
        
        result = calc_ma_vectorized(matrix, window=2)
        
        assert np.isnan(result[0, 0])
        assert result[1, 0] == 11.0
        assert result[2, 0] == 13.0
    
    def test_calc_ma_with_nan(self):
        """测试包含 NaN 的 MA 计算"""
        from core.calc.vectorized_ops import calc_ma_vectorized
        
        matrix = np.array([
            [10.0, 20.0],
            [np.nan, 21.0],
            [12.0, 22.0],
            [13.0, 23.0],
            [14.0, 24.0],
        ])
        
        result = calc_ma_vectorized(matrix, window=3)
        
        assert result.shape == matrix.shape
    
    def test_calc_ma_window_too_large(self):
        """测试窗口过大"""
        from core.calc.vectorized_ops import calc_ma_vectorized
        
        matrix = np.array([
            [10.0, 20.0],
            [11.0, 21.0],
        ])
        
        result = calc_ma_vectorized(matrix, window=10)
        
        assert np.all(np.isnan(result))
    
    def test_calc_ma_window_zero(self):
        """测试窗口为 0"""
        from core.calc.vectorized_ops import calc_ma_vectorized
        
        matrix = np.array([
            [10.0, 20.0],
            [11.0, 21.0],
        ])
        
        result = calc_ma_vectorized(matrix, window=0)
        
        assert np.all(np.isnan(result))
    
    def test_calc_ma_single_column(self):
        """测试单列数据"""
        from core.calc.vectorized_ops import calc_ma_vectorized
        
        matrix = np.array([[10.0], [11.0], [12.0], [13.0], [14.0]])
        
        result = calc_ma_vectorized(matrix, window=3)
        
        assert result.shape == (5, 1)
        assert result[2, 0] == 11.0
    
    def test_calc_ma_all_nan(self):
        """测试全 NaN 数据"""
        from core.calc.vectorized_ops import calc_ma_vectorized
        
        matrix = np.full((5, 2), np.nan)
        
        result = calc_ma_vectorized(matrix, window=3)
        
        assert np.all(np.isnan(result))


class TestCalcCrossOver:
    """金叉检测测试"""
    
    def test_calc_cross_over_basic(self):
        """测试基本金叉检测"""
        from core.calc.vectorized_ops import calc_cross_over
        
        fast_line = np.array([
            [10.0, 20.0],
            [11.0, 19.0],
            [12.0, 21.0],
        ])
        
        slow_line = np.array([
            [11.0, 21.0],
            [11.0, 20.0],
            [11.0, 20.0],
        ])
        
        result = calc_cross_over(fast_line, slow_line)
        
        assert result.shape == fast_line.shape
        assert result[0, 0] == False
        assert result[1, 0] == False
        assert result[2, 0] == True
    
    def test_calc_cross_over_no_cross(self):
        """测试无交叉"""
        from core.calc.vectorized_ops import calc_cross_over
        
        fast_line = np.array([
            [12.0, 22.0],
            [13.0, 23.0],
            [14.0, 24.0],
        ])
        
        slow_line = np.array([
            [10.0, 20.0],
            [10.0, 20.0],
            [10.0, 20.0],
        ])
        
        result = calc_cross_over(fast_line, slow_line)
        
        assert np.all(result == False)
    
    def test_calc_cross_over_with_nan(self):
        """测试包含 NaN 的金叉检测"""
        from core.calc.vectorized_ops import calc_cross_over
        
        fast_line = np.array([
            [10.0, 20.0],
            [np.nan, 19.0],
            [12.0, 21.0],
        ])
        
        slow_line = np.array([
            [11.0, 21.0],
            [11.0, 20.0],
            [11.0, 20.0],
        ])
        
        result = calc_cross_over(fast_line, slow_line)
        
        assert result.shape == fast_line.shape
        assert result[1, 0] == False
    
    def test_calc_cross_over_first_row(self):
        """测试第一行（无法判断）"""
        from core.calc.vectorized_ops import calc_cross_over
        
        fast_line = np.array([[10.0], [12.0]])
        slow_line = np.array([[11.0], [11.0]])
        
        result = calc_cross_over(fast_line, slow_line)
        
        assert result[0, 0] == False


class TestCalcCrossUnder:
    """死叉检测测试"""
    
    def test_calc_cross_under_basic(self):
        """测试基本死叉检测"""
        from core.calc.vectorized_ops import calc_cross_under
        
        fast_line = np.array([
            [12.0, 22.0],
            [11.0, 21.0],
            [10.0, 19.0],
        ])
        
        slow_line = np.array([
            [11.0, 21.0],
            [11.0, 20.0],
            [11.0, 20.0],
        ])
        
        result = calc_cross_under(fast_line, slow_line)
        
        assert result.shape == fast_line.shape
        assert result[0, 0] == False
        assert result[1, 0] == False
        assert result[2, 0] == True
    
    def test_calc_cross_under_no_cross(self):
        """测试无交叉"""
        from core.calc.vectorized_ops import calc_cross_under
        
        fast_line = np.array([
            [8.0, 18.0],
            [9.0, 19.0],
            [10.0, 20.0],
        ])
        
        slow_line = np.array([
            [12.0, 22.0],
            [12.0, 22.0],
            [12.0, 22.0],
        ])
        
        result = calc_cross_under(fast_line, slow_line)
        
        assert np.all(result == False)
    
    def test_calc_cross_under_first_row(self):
        """测试第一行（无法判断）"""
        from core.calc.vectorized_ops import calc_cross_under
        
        fast_line = np.array([[10.0], [8.0]])
        slow_line = np.array([[9.0], [9.0]])
        
        result = calc_cross_under(fast_line, slow_line)
        
        assert result[0, 0] == False


class TestVectorizedOpsIntegration:
    """向量化操作集成测试"""
    
    def test_ma_and_cross_over(self):
        """测试 MA 与金叉结合"""
        from core.calc.vectorized_ops import calc_ma_vectorized, calc_cross_over
        
        prices = np.array([
            [10.0],
            [11.0],
            [12.0],
            [11.0],
            [10.0],
            [11.0],
            [12.0],
            [13.0],
            [14.0],
            [15.0],
        ])
        
        ma5 = calc_ma_vectorized(prices, window=5)
        ma10 = calc_ma_vectorized(prices, window=10)
        
        cross = calc_cross_over(ma5, ma10)
        
        assert cross.shape == prices.shape
    
    def test_cross_over_and_cross_under(self):
        """测试金叉与死叉交替"""
        from core.calc.vectorized_ops import calc_cross_over, calc_cross_under
        
        fast_line = np.array([
            [10.0],
            [12.0],
            [11.0],
            [9.0],
            [10.0],
            [12.0],
        ])
        
        slow_line = np.array([
            [11.0],
            [11.0],
            [11.0],
            [11.0],
            [11.0],
            [11.0],
        ])
        
        cross_over = calc_cross_over(fast_line, slow_line)
        cross_under = calc_cross_under(fast_line, slow_line)
        
        assert not np.any(cross_over & cross_under)

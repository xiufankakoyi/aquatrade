"""
calc/vectorized_ops.py 向量化计算函数测试

测试内容：
1. 移动平均计算精度
2. 金叉死叉检测
3. NaN 处理
4. 边界条件
"""

import pytest
import numpy as np


class TestCalcMAVectorized:
    """移动平均计算测试"""
    
    def test_ma_basic_calculation(self):
        """测试基本移动平均计算"""
        from core.calc.vectorized_ops import calc_ma_vectorized
        
        data = np.array([
            [10.0, 20.0],
            [11.0, 21.0],
            [12.0, 22.0],
            [13.0, 23.0],
            [14.0, 24.0],
        ])
        
        ma = calc_ma_vectorized(data, window=3)
        
        assert ma.shape == data.shape
        assert np.isnan(ma[0, 0])
        assert np.isnan(ma[1, 0])
        assert abs(ma[2, 0] - 11.0) < 0.01
        assert abs(ma[3, 0] - 12.0) < 0.01
        assert abs(ma[4, 0] - 13.0) < 0.01
    
    def test_ma_window_larger_than_data(self):
        """测试窗口大于数据长度"""
        from core.calc.vectorized_ops import calc_ma_vectorized
        
        data = np.array([[10.0, 20.0], [11.0, 21.0]])
        
        ma = calc_ma_vectorized(data, window=5)
        
        assert np.all(np.isnan(ma))
    
    def test_ma_window_one(self):
        """测试窗口为 1"""
        from core.calc.vectorized_ops import calc_ma_vectorized
        
        data = np.array([[10.0, 20.0], [11.0, 21.0]])
        
        ma = calc_ma_vectorized(data, window=1)
        
        assert abs(ma[0, 0] - 10.0) < 0.01
        assert abs(ma[1, 0] - 11.0) < 0.01
    
    def test_ma_with_nan_values(self):
        """测试包含 NaN 的数据"""
        from core.calc.vectorized_ops import calc_ma_vectorized
        
        data = np.array([
            [10.0, 20.0],
            [11.0, 21.0],
            [12.0, 22.0],
            [13.0, 23.0],
            [14.0, 24.0],
        ])
        
        ma = calc_ma_vectorized(data, window=3)
        
        assert ma.shape == data.shape
        assert np.sum(~np.isnan(ma)) > 0
    
    def test_ma_all_nan(self):
        """测试全 NaN 数据"""
        from core.calc.vectorized_ops import calc_ma_vectorized
        
        data = np.full((5, 2), np.nan)
        
        ma = calc_ma_vectorized(data, window=3)
        
        assert np.all(np.isnan(ma))
    
    def test_ma_window_zero(self):
        """测试窗口为 0"""
        from core.calc.vectorized_ops import calc_ma_vectorized
        
        data = np.array([[10.0, 20.0], [11.0, 21.0]])
        
        ma = calc_ma_vectorized(data, window=0)
        
        assert np.all(np.isnan(ma))
    
    def test_ma_negative_window(self):
        """测试负窗口"""
        from core.calc.vectorized_ops import calc_ma_vectorized
        
        data = np.array([[10.0, 20.0], [11.0, 21.0]])
        
        ma = calc_ma_vectorized(data, window=-1)
        
        assert np.all(np.isnan(ma))
    
    def test_ma_single_column(self):
        """测试单列数据"""
        from core.calc.vectorized_ops import calc_ma_vectorized
        
        data = np.array([[10.0], [11.0], [12.0], [13.0], [14.0]])
        
        ma = calc_ma_vectorized(data, window=3)
        
        assert ma.shape == (5, 1)
        assert abs(ma[2, 0] - 11.0) < 0.01
    
    def test_ma_large_window(self):
        """测试大窗口"""
        from core.calc.vectorized_ops import calc_ma_vectorized
        
        data = np.arange(100).reshape(100, 1).astype(np.float64)
        
        ma = calc_ma_vectorized(data, window=50)
        
        assert ma.shape == (100, 1)
        assert np.sum(~np.isnan(ma)) == 51


class TestCalcCrossOver:
    """金叉检测测试"""
    
    def test_cross_over_basic(self):
        """测试基本金叉检测"""
        from core.calc.vectorized_ops import calc_cross_over
        
        fast = np.array([
            [10.0, 20.0],
            [9.0, 21.0],
            [11.0, 19.0],
        ])
        
        slow = np.array([
            [9.5, 21.0],
            [10.0, 20.0],
            [10.5, 18.0],
        ])
        
        cross = calc_cross_over(fast, slow)
        
        assert cross.shape == fast.shape
        assert cross[0, 0] == False
        assert cross[1, 0] == False
        assert cross[2, 0] == True
    
    def test_cross_over_no_cross(self):
        """测试无交叉情况"""
        from core.calc.vectorized_ops import calc_cross_over
        
        fast = np.array([[10.0], [11.0], [12.0]])
        slow = np.array([[9.0], [9.5], [10.0]])
        
        cross = calc_cross_over(fast, slow)
        
        assert not np.any(cross)
    
    def test_cross_over_with_nan(self):
        """测试包含 NaN 的金叉检测"""
        from core.calc.vectorized_ops import calc_cross_over
        
        fast = np.array([
            [10.0],
            [np.nan],
            [12.0],
        ])
        
        slow = np.array([
            [11.0],
            [10.0],
            [11.0],
        ])
        
        cross = calc_cross_over(fast, slow)
        
        assert cross[1, 0] == False
    
    def test_cross_over_multiple_stocks(self):
        """测试多股票金叉检测"""
        from core.calc.vectorized_ops import calc_cross_over
        
        fast = np.array([
            [10.0, 20.0, 30.0],
            [9.0, 22.0, 28.0],
            [11.0, 21.0, 32.0],
        ])
        
        slow = np.array([
            [9.5, 21.0, 31.0],
            [10.0, 21.0, 30.0],
            [10.5, 22.0, 31.0],
        ])
        
        cross = calc_cross_over(fast, slow)
        
        assert cross[2, 0] == True
        assert cross[2, 1] == False
        assert cross[2, 2] == True


class TestCalcCrossUnder:
    """死叉检测测试"""
    
    def test_cross_under_basic(self):
        """测试基本死叉检测"""
        from core.calc.vectorized_ops import calc_cross_under
        
        fast = np.array([
            [11.0, 19.0],
            [10.0, 21.0],
            [9.0, 20.0],
            [8.0, 19.0],
        ])
        
        slow = np.array([
            [10.0, 20.0],
            [10.5, 20.0],
            [11.0, 21.0],
            [11.5, 22.0],
        ])
        
        cross = calc_cross_under(fast, slow)
        
        assert cross.shape == fast.shape
    
    def test_cross_under_no_cross(self):
        """测试无交叉情况"""
        from core.calc.vectorized_ops import calc_cross_under
        
        fast = np.array([[9.0], [8.0], [7.0]])
        slow = np.array([[10.0], [11.0], [12.0]])
        
        cross = calc_cross_under(fast, slow)
        
        assert not np.any(cross)
    
    def test_cross_under_with_nan(self):
        """测试包含 NaN 的死叉检测"""
        from core.calc.vectorized_ops import calc_cross_under
        
        fast = np.array([
            [12.0],
            [11.0],
            [10.0],
        ])
        
        slow = np.array([
            [11.0],
            [11.0],
            [11.0],
        ])
        
        cross = calc_cross_under(fast, slow)
        
        assert cross[1, 0] == False


class TestVectorizedOpsPrecision:
    """数值精度测试"""
    
    def test_ma_precision_large_numbers(self):
        """测试大数值精度"""
        from core.calc.vectorized_ops import calc_ma_vectorized
        
        data = np.array([[1e10], [1e10 + 1], [1e10 + 2]])
        
        ma = calc_ma_vectorized(data, window=3)
        
        assert abs(ma[2, 0] - (1e10 + 1)) < 1
    
    def test_ma_precision_small_numbers(self):
        """测试小数值精度"""
        from core.calc.vectorized_ops import calc_ma_vectorized
        
        data = np.array([[1e-10], [2e-10], [3e-10]])
        
        ma = calc_ma_vectorized(data, window=3)
        
        assert abs(ma[2, 0] - 2e-10) < 1e-12
    
    def test_cross_over_precision(self):
        """测试交叉检测精度"""
        from core.calc.vectorized_ops import calc_cross_over
        
        fast = np.array([[10.0000001], [10.0000002]])
        slow = np.array([[10.0000002], [10.0000001]])
        
        cross = calc_cross_over(fast, slow)
        
        assert cross[1, 0] == True

"""
core/strategies/utils/signal_utils.py 信号工具测试

测试内容：
1. crossover 金叉检测
2. crossunder 死叉检测
3. above/below 阈值检测
4. rising/falling 趋势检测
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock


class TestCrossover:
    """金叉检测测试"""
    
    def test_crossover_1d_basic(self):
        """测试一维数组金叉"""
        from core.strategies.utils.signal_utils import crossover
        
        fast = np.array([10.0, 11.0, 12.0, 13.0, 14.0])
        slow = np.array([12.0, 12.0, 11.0, 11.0, 11.0])
        
        result = crossover(fast, slow)
        
        assert isinstance(result, np.ndarray)
        assert len(result) == 4
    
    def test_crossover_1d_golden_cross(self):
        """测试真实金叉场景"""
        from core.strategies.utils.signal_utils import crossover
        
        fast = np.array([9.0, 10.0, 11.0, 12.0])
        slow = np.array([10.0, 10.0, 10.0, 10.0])
        
        result = crossover(fast, slow)
        
        assert result[1] == True
    
    def test_crossover_2d(self):
        """测试二维数组金叉"""
        from core.strategies.utils.signal_utils import crossover
        
        fast = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
        slow = np.array([[2.0, 3.0], [3.0, 4.0], [4.0, 5.0]])
        
        result = crossover(fast, slow)
        
        assert isinstance(result, np.ndarray)
        assert result.shape == (2, 2)


class TestCrossunder:
    """死叉检测测试"""
    
    def test_crossunder_1d_basic(self):
        """测试一维数组死叉"""
        from core.strategies.utils.signal_utils import crossunder
        
        fast = np.array([14.0, 13.0, 12.0, 11.0, 10.0])
        slow = np.array([11.0, 11.0, 12.0, 12.0, 12.0])
        
        result = crossunder(fast, slow)
        
        assert isinstance(result, np.ndarray)
        assert len(result) == 4
    
    def test_crossunder_1d_death_cross(self):
        """测试真实死叉场景"""
        from core.strategies.utils.signal_utils import crossunder
        
        fast = np.array([11.0, 10.0, 9.0, 8.0])
        slow = np.array([10.0, 10.0, 10.0, 10.0])
        
        result = crossunder(fast, slow)
        
        assert result[1] == True


class TestAbove:
    """上穿阈值测试"""
    
    def test_above_scalar_threshold(self):
        """测试标量阈值"""
        from core.strategies.utils.signal_utils import above
        
        series = np.array([25.0, 30.0, 35.0, 40.0])
        
        result = above(series, 30)
        
        assert isinstance(result, np.ndarray)
        assert result[0] == False
        assert result[1] == False
        assert result[2] == True
        assert result[3] == True
    
    def test_above_array_threshold(self):
        """测试数组阈值"""
        from core.strategies.utils.signal_utils import above
        
        series = np.array([10.0, 20.0, 30.0, 40.0])
        threshold = np.array([15.0, 25.0, 35.0, 45.0])
        
        result = above(series, threshold)
        
        assert result[0] == False
        assert result[1] == False
        assert result[2] == False
        assert result[3] == False


class TestBelow:
    """下穿阈值测试"""
    
    def test_below_scalar_threshold(self):
        """测试标量阈值"""
        from core.strategies.utils.signal_utils import below
        
        series = np.array([75.0, 70.0, 65.0, 60.0])
        
        result = below(series, 70)
        
        assert isinstance(result, np.ndarray)
        assert result[0] == False
        assert result[1] == False
        assert result[2] == True
        assert result[3] == True
    
    def test_below_array_threshold(self):
        """测试数组阈值"""
        from core.strategies.utils.signal_utils import below
        
        series = np.array([10.0, 20.0, 30.0, 40.0])
        threshold = np.array([15.0, 25.0, 35.0, 45.0])
        
        result = below(series, threshold)
        
        assert result[0] == True
        assert result[1] == True
        assert result[2] == True
        assert result[3] == True


class TestRising:
    """上涨趋势测试"""
    
    def test_rising_basic(self):
        """测试基本上涨"""
        from core.strategies.utils.signal_utils import rising
        
        series = np.array([10.0, 11.0, 12.0, 13.0, 14.0])
        
        result = rising(series, window=1)
        
        assert isinstance(result, np.ndarray)


class TestFalling:
    """下跌趋势测试"""
    
    def test_falling_basic(self):
        """测试基本下跌"""
        from core.strategies.utils.signal_utils import falling
        
        series = np.array([14.0, 13.0, 12.0, 11.0, 10.0])
        
        result = falling(series, window=1)
        
        assert isinstance(result, np.ndarray)

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


class TestCrossover:
    """金叉检测测试"""
    
    def test_crossover_basic(self):
        """测试基本金叉检测"""
        from core.strategies.utils.signal_utils import crossover
        
        fast = np.array([10.0, 11.0, 12.0, 13.0, 14.0])
        slow = np.array([12.0, 12.0, 12.0, 12.0, 12.0])
        
        result = crossover(fast, slow)
        
        assert len(result) == 4
        assert result[0] == False
        assert result[1] == False
        assert result[2] == True
    
    def test_crossover_no_cross(self):
        """测试无交叉"""
        from core.strategies.utils.signal_utils import crossover
        
        fast = np.array([10.0, 11.0, 12.0, 13.0, 14.0])
        slow = np.array([15.0, 16.0, 17.0, 18.0, 19.0])
        
        result = crossover(fast, slow)
        
        assert not np.any(result)
    
    def test_crossover_2d(self):
        """测试二维数组金叉"""
        from core.strategies.utils.signal_utils import crossover
        
        fast = np.array([
            [10.0, 20.0],
            [11.0, 19.0],
            [12.0, 18.0],
        ])
        slow = np.array([
            [11.0, 19.0],
            [11.0, 18.0],
            [11.0, 17.0],
        ])
        
        result = crossover(fast, slow)
        
        assert result.shape == (2, 2)


class TestCrossunder:
    """死叉检测测试"""
    
    def test_crossunder_basic(self):
        """测试基本死叉检测"""
        from core.strategies.utils.signal_utils import crossunder
        
        fast = np.array([14.0, 13.0, 12.0, 11.0, 10.0])
        slow = np.array([12.0, 12.0, 12.0, 12.0, 12.0])
        
        result = crossunder(fast, slow)
        
        assert len(result) == 4
        assert result[0] == False
        assert result[1] == False
        assert result[2] == True
    
    def test_crossunder_no_cross(self):
        """测试无交叉"""
        from core.strategies.utils.signal_utils import crossunder
        
        fast = np.array([10.0, 11.0, 12.0, 13.0, 14.0])
        slow = np.array([5.0, 6.0, 7.0, 8.0, 9.0])
        
        result = crossunder(fast, slow)
        
        assert not np.any(result)


class TestAbove:
    """上穿阈值测试"""
    
    def test_above_scalar(self):
        """测试标量阈值"""
        from core.strategies.utils.signal_utils import above
        
        series = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        
        result = above(series, 25.0)
        
        assert result[0] == False
        assert result[1] == False
        assert result[2] == True
        assert result[3] == True
    
    def test_above_array(self):
        """测试数组阈值"""
        from core.strategies.utils.signal_utils import above
        
        series = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        threshold = np.array([15.0, 25.0, 35.0, 45.0, 55.0])
        
        result = above(series, threshold)
        
        assert result[0] == False
        assert result[1] == False
        assert result[2] == False


class TestBelow:
    """下穿阈值测试"""
    
    def test_below_scalar(self):
        """测试标量阈值"""
        from core.strategies.utils.signal_utils import below
        
        series = np.array([50.0, 40.0, 30.0, 20.0, 10.0])
        
        result = below(series, 25.0)
        
        assert result[0] == False
        assert result[1] == False
        assert result[2] == False
        assert result[3] == True
        assert result[4] == True


class TestRising:
    """连续上涨测试"""
    
    def test_rising_basic(self):
        """测试基本连续上涨"""
        from core.strategies.utils.signal_utils import rising
        
        series = np.array([10.0, 11.0, 12.0, 13.0, 14.0])
        
        result = rising(series, window=1)
        
        assert result[0] == True
        assert result[1] == True
    
    def test_rising_window(self):
        """测试多窗口连续上涨"""
        from core.strategies.utils.signal_utils import rising
        
        series = np.array([10.0, 11.0, 12.0, 11.0, 10.0])
        
        result = rising(series, window=2)
        
        assert result[0] == True
        assert result[3] == False
    
    def test_rising_2d(self):
        """测试二维数组连续上涨"""
        from core.strategies.utils.signal_utils import rising
        
        series = np.array([
            [10.0, 20.0],
            [11.0, 19.0],
            [12.0, 18.0],
        ])
        
        result = rising(series, window=1)
        
        assert result.shape == (3, 2)

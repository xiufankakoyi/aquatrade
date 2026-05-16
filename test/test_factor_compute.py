"""
core/strategies/utils/factor_compute.py 因子计算测试

测试内容：
1. FactorCompute 静态方法
2. Numba 加速函数
3. 错误处理
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock


class TestFactorComputeGain:
    """涨幅计算测试"""
    
    def test_calc_gain_3d_missing_close(self):
        """测试缺少 close 属性"""
        from core.strategies.utils.factor_compute import FactorCompute
        
        strategy = Mock()
        del strategy.close
        
        with pytest.raises(ValueError, match="缺少 'close' 属性"):
            FactorCompute.calc_gain_3d(strategy)
    
    def test_calc_gain_3d_none_close(self):
        """测试 close 为 None"""
        from core.strategies.utils.factor_compute import FactorCompute
        
        strategy = Mock()
        strategy.close = None
        
        with pytest.raises(ValueError, match="缺少 'close' 属性"):
            FactorCompute.calc_gain_3d(strategy)
    
    def test_calc_gain_3d_basic(self):
        """测试基本涨幅计算"""
        from core.strategies.utils.factor_compute import FactorCompute, _calc_gain_njit
        
        strategy = Mock()
        strategy.close = np.array([
            [10.0, 20.0],
            [11.0, 21.0],
            [12.0, 22.0],
            [13.0, 23.0],
            [14.0, 24.0],
        ], dtype=np.float32)
        
        result = FactorCompute.calc_gain_3d(strategy, window=3)
        
        assert result.shape == (5, 2)
    
    def test_calc_gain_5d(self):
        """测试5日涨幅"""
        from core.strategies.utils.factor_compute import FactorCompute
        
        strategy = Mock()
        strategy.close = np.array([
            [10.0, 20.0],
            [11.0, 21.0],
            [12.0, 22.0],
            [13.0, 23.0],
            [14.0, 24.0],
            [15.0, 25.0],
        ], dtype=np.float32)
        
        result = FactorCompute.calc_gain_5d(strategy, window=5)
        
        assert result.shape == (6, 2)
    
    def test_calc_gain_10d(self):
        """测试10日涨幅"""
        from core.strategies.utils.factor_compute import FactorCompute
        
        strategy = Mock()
        strategy.close = np.random.randn(15, 3).astype(np.float32) * 10 + 100
        
        result = FactorCompute.calc_gain_10d(strategy, window=10)
        
        assert result.shape == (15, 3)


class TestFactorComputeVolatility:
    """波动率计算测试"""
    
    def test_calc_volatility_missing_close(self):
        """测试缺少 close 属性"""
        from core.strategies.utils.factor_compute import FactorCompute
        
        strategy = Mock()
        del strategy.close
        
        with pytest.raises(ValueError, match="缺少 'close' 属性"):
            FactorCompute.calc_volatility(strategy)
    
    def test_calc_volatility_basic(self):
        """测试基本波动率计算"""
        from core.strategies.utils.factor_compute import FactorCompute
        
        strategy = Mock()
        strategy.close = np.random.randn(30, 3).astype(np.float32) * 10 + 100
        
        result = FactorCompute.calc_volatility(strategy, window=20)
        
        assert result.shape == (30, 3)


class TestFactorComputeSharpe:
    """夏普率计算测试"""
    
    def test_calc_sharpe_missing_close(self):
        """测试缺少 close 属性"""
        from core.strategies.utils.factor_compute import FactorCompute
        
        strategy = Mock()
        del strategy.close
        
        with pytest.raises(ValueError, match="缺少 'close' 属性"):
            FactorCompute.calc_sharpe(strategy)
    
    def test_calc_sharpe_basic(self):
        """测试基本夏普率计算"""
        from core.strategies.utils.factor_compute import FactorCompute
        
        strategy = Mock()
        strategy.close = np.random.randn(30, 3).astype(np.float32) * 10 + 100
        
        result = FactorCompute.calc_sharpe(strategy, window=20)
        
        assert result.shape == (30, 3)


class TestFactorComputeTurnover:
    """换手率计算测试"""
    
    def test_calc_turnover_ma_missing(self):
        """测试缺少换手率属性"""
        from core.strategies.utils.factor_compute import FactorCompute
        
        strategy = Mock()
        del strategy.turnover_rate
        
        with pytest.raises(ValueError, match="缺少 'turnover_rate' 属性"):
            FactorCompute.calc_turnover_ma(strategy)
    
    def test_calc_turnover_ma_basic(self):
        """测试基本换手率均值计算"""
        from core.strategies.utils.factor_compute import FactorCompute
        
        strategy = Mock()
        strategy.turnover_rate = np.random.randn(20, 3).astype(np.float32) * 0.05 + 0.03
        
        result = FactorCompute.calc_turnover_ma(strategy, window=5)
        
        assert result.shape == (20, 3)


class TestFactorComputeAmount:
    """成交额计算测试"""
    
    def test_calc_amount_ratio_missing(self):
        """测试缺少成交额属性"""
        from core.strategies.utils.factor_compute import FactorCompute
        
        strategy = Mock()
        del strategy.amount
        
        with pytest.raises(ValueError, match="缺少 'amount' 属性"):
            FactorCompute.calc_amount_ratio(strategy)
    
    def test_calc_amount_ratio_basic(self):
        """测试基本成交额比率计算"""
        from core.strategies.utils.factor_compute import FactorCompute
        
        strategy = Mock()
        strategy.amount = np.random.randn(20, 3).astype(np.float32) * 1e8 + 1e7
        
        result = FactorCompute.calc_amount_ratio(strategy, window=5)
        
        assert result.shape == (20, 3)


class TestFactorComputeRank:
    """排名计算测试"""
    
    def test_calc_rank_pct_basic(self):
        """测试基本排名计算"""
        from core.strategies.utils.factor_compute import _calc_rank_pct_njit
        
        factor_matrix = np.array([
            [1.0, 2.0, 3.0, 4.0, 5.0],
            [5.0, 4.0, 3.0, 2.0, 1.0],
        ], dtype=np.float32)
        
        result = _calc_rank_pct_njit(factor_matrix, 1)
        
        assert result.shape == (2, 5)


class TestFactorComputeBias:
    """乖离率计算测试"""
    
    def test_calc_bias_1d(self):
        """测试一维数组乖离率"""
        from core.strategies.utils.factor_compute import FactorCompute
        
        close_array = np.array([10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0,
                               20.0, 21.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0, 29.0,
                               30.0], dtype=np.float32)
        
        result = FactorCompute.calc_bias(close_array, ma_period=5)
        
        assert len(result) == len(close_array)
    
    def test_calc_bias_2d(self):
        """测试二维数组乖离率"""
        from core.strategies.utils.factor_compute import FactorCompute
        
        close_array = np.random.randn(30, 3).astype(np.float32) * 10 + 100
        
        result = FactorCompute.calc_bias(close_array, ma_period=20)
        
        assert result.shape == close_array.shape


class TestFactorComputeMACD:
    """MACD 计算测试"""
    
    def test_calc_macd_config(self):
        """测试 MACD 配置"""
        from core.strategies.utils.factor_compute import FactorCompute
        
        close_array = np.random.randn(100).astype(np.float32) * 10 + 100
        
        assert hasattr(FactorCompute, 'calc_macd')


class TestFactorComputeRSI:
    """RSI 计算测试"""
    
    def test_calc_rsi_1d(self):
        """测试一维数组 RSI"""
        from core.strategies.utils.factor_compute import FactorCompute
        
        close_array = np.random.randn(50).astype(np.float32) * 10 + 100
        
        result = FactorCompute.calc_rsi(close_array, period=14)
        
        assert len(result) == len(close_array)
    
    def test_calc_rsi_2d(self):
        """测试二维数组 RSI"""
        from core.strategies.utils.factor_compute import FactorCompute
        
        close_array = np.random.randn(50, 3).astype(np.float32) * 10 + 100
        
        result = FactorCompute.calc_rsi(close_array, period=14)
        
        assert result.shape == close_array.shape


class TestFactorComputeMABreakout:
    """均线突破计算测试"""
    
    def test_calc_ma_breakout_1d(self):
        """测试一维数组均线突破"""
        from core.strategies.utils.factor_compute import FactorCompute
        
        close_array = np.array([10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0,
                               20.0, 21.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0, 29.0,
                               30.0], dtype=np.float32)
        
        result = FactorCompute.calc_ma_breakout(close_array, ma_period=10)
        
        assert len(result) == len(close_array)


class TestFactorComputeValuation:
    """估值分位计算测试"""
    
    def test_calc_valuation_percentile_1d(self):
        """测试一维数组估值分位"""
        from core.strategies.utils.factor_compute import FactorCompute
        
        value_array = np.random.randn(300).astype(np.float32) * 10 + 20
        
        result = FactorCompute.calc_valuation_percentile(value_array, window=252)
        
        assert len(result) == len(value_array)


class TestNumbaFunctions:
    """Numba 加速函数测试"""
    
    def test_calc_gain_njit(self):
        """测试 Numba 涨幅计算"""
        from core.strategies.utils.factor_compute import _calc_gain_njit
        
        close_matrix = np.array([
            [10.0, 20.0],
            [11.0, 21.0],
            [12.0, 22.0],
            [13.0, 23.0],
            [14.0, 24.0],
        ], dtype=np.float32)
        
        result = _calc_gain_njit(close_matrix, 3)
        
        assert result.shape == (5, 2)
    
    def test_calc_volatility_njit(self):
        """测试 Numba 波动率计算"""
        from core.strategies.utils.factor_compute import _calc_volatility_njit
        
        close_matrix = np.random.randn(30, 3).astype(np.float32) * 10 + 100
        
        result = _calc_volatility_njit(close_matrix, 20)
        
        assert result.shape == (30, 3)
    
    def test_calc_ma_njit(self):
        """测试 Numba 移动平均计算"""
        from core.strategies.utils.factor_compute import _calc_ma_njit
        
        data_matrix = np.random.randn(20, 3).astype(np.float32) * 10 + 100
        
        result = _calc_ma_njit(data_matrix, 5)
        
        assert result.shape == (20, 3)

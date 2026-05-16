"""
core/utils/indicator_calculator.py 指标计算器测试

测试内容：
1. MA 移动平均线计算
2. EMA 指数移动平均线计算
3. RSI 相对强弱指标计算
4. MACD 指标计算
5. 布林带计算
6. ATR 平均真实波幅计算
7. 批量指标计算
"""

import pytest
import pandas as pd
import numpy as np


class TestIndicatorCalculatorInit:
    """指标计算器初始化测试"""
    
    def test_init_default(self):
        """测试默认初始化"""
        from core.utils.indicator_calculator import IndicatorCalculator
        
        calculator = IndicatorCalculator()
        
        assert calculator.enable_cache is True
        assert calculator._cache == {}
    
    def test_init_no_cache(self):
        """测试禁用缓存"""
        from core.utils.indicator_calculator import IndicatorCalculator
        
        calculator = IndicatorCalculator(enable_cache=False)
        
        assert calculator.enable_cache is False
    
    def test_clear_cache(self):
        """测试清空缓存"""
        from core.utils.indicator_calculator import IndicatorCalculator
        
        calculator = IndicatorCalculator()
        calculator._cache["test"] = "value"
        
        calculator.clear_cache()
        
        assert calculator._cache == {}


class TestMACalculation:
    """MA 移动平均线计算测试"""
    
    @pytest.fixture
    def calculator(self):
        """创建计算器实例"""
        from core.utils.indicator_calculator import IndicatorCalculator
        
        return IndicatorCalculator()
    
    @pytest.fixture
    def sample_df(self):
        """创建示例数据"""
        return pd.DataFrame({
            'close': [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0],
        })
    
    def test_calculate_ma_basic(self, calculator, sample_df):
        """测试基本 MA 计算"""
        result = calculator.calculate_ma(sample_df, column='close', window=3)
        
        assert len(result) == len(sample_df)
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])
        assert result.iloc[2] == 11.0
    
    def test_calculate_ma_window_5(self, calculator, sample_df):
        """测试 5 日 MA"""
        result = calculator.calculate_ma(sample_df, column='close', window=5)
        
        assert len(result) == len(sample_df)
        assert result.iloc[4] == 12.0
    
    def test_calculate_ma_with_min_periods(self, calculator, sample_df):
        """测试带最小周期的 MA"""
        result = calculator.calculate_ma(
            sample_df, column='close', window=5, min_periods=1
        )
        
        assert len(result) == len(sample_df)
        assert not pd.isna(result.iloc[0])
    
    def test_calculate_ma_with_groupby(self, calculator):
        """测试分组 MA 计算"""
        df = pd.DataFrame({
            'stock_code': ['A', 'A', 'A', 'B', 'B', 'B'],
            'close': [10.0, 11.0, 12.0, 20.0, 21.0, 22.0],
        })
        
        result = calculator.calculate_ma(
            df, column='close', window=2, group_by='stock_code'
        )
        
        assert len(result) == len(df)
        assert result.iloc[1] == 10.5
        assert result.iloc[4] == 20.5


class TestEMACalculation:
    """EMA 指数移动平均线计算测试"""
    
    @pytest.fixture
    def calculator(self):
        from core.utils.indicator_calculator import IndicatorCalculator
        
        return IndicatorCalculator()
    
    @pytest.fixture
    def sample_df(self):
        return pd.DataFrame({
            'close': [10.0, 11.0, 12.0, 13.0, 14.0],
        })
    
    def test_calculate_ema_basic(self, calculator, sample_df):
        """测试基本 EMA 计算"""
        result = calculator.calculate_ema(sample_df, column='close', window=3)
        
        assert len(result) == len(sample_df)
        assert result.iloc[0] == 10.0
    
    def test_calculate_ema_with_groupby(self, calculator):
        """测试分组 EMA 计算"""
        df = pd.DataFrame({
            'stock_code': ['A', 'A', 'B', 'B'],
            'close': [10.0, 11.0, 20.0, 21.0],
        })
        
        result = calculator.calculate_ema(
            df, column='close', window=2, group_by='stock_code'
        )
        
        assert len(result) == len(df)


class TestRSICalculation:
    """RSI 相对强弱指标计算测试"""
    
    @pytest.fixture
    def calculator(self):
        from core.utils.indicator_calculator import IndicatorCalculator
        
        return IndicatorCalculator()
    
    @pytest.fixture
    def sample_df(self):
        np.random.seed(42)
        return pd.DataFrame({
            'close': 100 + np.cumsum(np.random.randn(30)),
        })
    
    def test_calculate_rsi_basic(self, calculator, sample_df):
        """测试基本 RSI 计算"""
        result = calculator.calculate_rsi(sample_df, column='close', window=14)
        
        assert len(result) == len(sample_df)
        assert all(0 <= r <= 100 for r in result.dropna())
    
    def test_calculate_rsi_range(self, calculator):
        """测试 RSI 值范围"""
        df = pd.DataFrame({
            'close': [10.0] * 20,
        })
        
        result = calculator.calculate_rsi(df, column='close', window=14)
        
        assert all(0 <= r <= 100 for r in result.dropna())
    
    def test_calculate_rsi_with_groupby(self, calculator):
        """测试分组 RSI 计算"""
        df = pd.DataFrame({
            'stock_code': ['A'] * 20 + ['B'] * 20,
            'close': list(range(10, 30)) + list(range(20, 40)),
        })
        
        result = calculator.calculate_rsi(
            df, column='close', window=14, group_by='stock_code'
        )
        
        assert len(result) == len(df)


class TestMACDCalculation:
    """MACD 指标计算测试"""
    
    @pytest.fixture
    def calculator(self):
        from core.utils.indicator_calculator import IndicatorCalculator
        
        return IndicatorCalculator()
    
    @pytest.fixture
    def sample_df(self):
        np.random.seed(42)
        return pd.DataFrame({
            'close': 100 + np.cumsum(np.random.randn(50)),
        })
    
    def test_calculate_macd_basic(self, calculator, sample_df):
        """测试基本 MACD 计算"""
        result = calculator.calculate_macd(sample_df, column='close')
        
        assert 'macd' in result.columns
        assert 'signal' in result.columns
        assert 'histogram' in result.columns
        assert len(result) == len(sample_df)
    
    def test_calculate_macd_custom_params(self, calculator, sample_df):
        """测试自定义参数 MACD"""
        result = calculator.calculate_macd(
            sample_df, column='close', fast=5, slow=10, signal=3
        )
        
        assert 'macd' in result.columns
        assert 'signal' in result.columns
    
    def test_calculate_macd_with_groupby(self, calculator):
        """测试分组 MACD 计算"""
        df = pd.DataFrame({
            'stock_code': ['A'] * 30 + ['B'] * 30,
            'close': list(range(10, 40)) + list(range(20, 50)),
        })
        
        result = calculator.calculate_macd(
            df, column='close', group_by='stock_code'
        )
        
        assert len(result) == len(df)


class TestBollingerBandsCalculation:
    """布林带计算测试"""
    
    @pytest.fixture
    def calculator(self):
        from core.utils.indicator_calculator import IndicatorCalculator
        
        return IndicatorCalculator()
    
    @pytest.fixture
    def sample_df(self):
        np.random.seed(42)
        return pd.DataFrame({
            'close': 100 + np.cumsum(np.random.randn(30)),
        })
    
    def test_calculate_bollinger_basic(self, calculator, sample_df):
        """测试基本布林带计算"""
        result = calculator.calculate_bollinger_bands(
            sample_df, column='close', window=20
        )
        
        assert 'upper' in result.columns
        assert 'middle' in result.columns
        assert 'lower' in result.columns
        assert len(result) == len(sample_df)
    
    def test_calculate_bollinger_relationship(self, calculator, sample_df):
        """测试布林带上下轨关系"""
        result = calculator.calculate_bollinger_bands(
            sample_df, column='close', window=20
        )
        
        valid_mask = ~(result['upper'].isna() | result['lower'].isna())
        assert all(result.loc[valid_mask, 'upper'] >= result.loc[valid_mask, 'lower'])


class TestATRCalculation:
    """ATR 平均真实波幅计算测试"""
    
    @pytest.fixture
    def calculator(self):
        from core.utils.indicator_calculator import IndicatorCalculator
        
        return IndicatorCalculator()
    
    @pytest.fixture
    def sample_df(self):
        return pd.DataFrame({
            'high': [11.0, 12.0, 13.0, 14.0, 15.0],
            'low': [9.0, 10.0, 11.0, 12.0, 13.0],
            'close': [10.0, 11.0, 12.0, 13.0, 14.0],
        })
    
    def test_calculate_atr_basic(self, calculator, sample_df):
        """测试基本 ATR 计算"""
        result = calculator.calculate_atr(sample_df, window=3)
        
        assert len(result) == len(sample_df)
    
    def test_calculate_atr_positive(self, calculator, sample_df):
        """测试 ATR 为正值"""
        result = calculator.calculate_atr(sample_df, window=3)
        
        valid_values = result.dropna()
        assert all(v >= 0 for v in valid_values)


class TestBatchCalculation:
    """批量指标计算测试"""
    
    @pytest.fixture
    def calculator(self):
        from core.utils.indicator_calculator import IndicatorCalculator
        
        return IndicatorCalculator()
    
    @pytest.fixture
    def sample_df(self):
        np.random.seed(42)
        return pd.DataFrame({
            'close': 100 + np.cumsum(np.random.randn(50)),
        })
    
    def test_calculate_batch_ma(self, calculator, sample_df):
        """测试批量计算 MA"""
        indicators = [
            {'type': 'ma', 'column': 'close', 'window': 5, 'name': 'ma5'},
            {'type': 'ma', 'column': 'close', 'window': 20, 'name': 'ma20'},
        ]
        
        result = calculator.calculate_batch(sample_df, indicators)
        
        assert 'ma5' in result.columns
        assert 'ma20' in result.columns
    
    def test_calculate_batch_multiple_types(self, calculator, sample_df):
        """测试批量计算多种指标"""
        indicators = [
            {'type': 'ma', 'column': 'close', 'window': 5, 'name': 'ma5'},
            {'type': 'ema', 'column': 'close', 'window': 12, 'name': 'ema12'},
            {'type': 'rsi', 'column': 'close', 'window': 14, 'name': 'rsi14'},
        ]
        
        result = calculator.calculate_batch(sample_df, indicators)
        
        assert 'ma5' in result.columns
        assert 'ema12' in result.columns
        assert 'rsi14' in result.columns
    
    def test_calculate_batch_macd(self, calculator, sample_df):
        """测试批量计算 MACD"""
        indicators = [
            {'type': 'macd', 'column': 'close', 'name': 'macd'},
        ]
        
        result = calculator.calculate_batch(sample_df, indicators)
        
        assert 'macd_macd' in result.columns
        assert 'macd_signal' in result.columns
        assert 'macd_histogram' in result.columns
    
    def test_calculate_batch_bollinger(self, calculator, sample_df):
        """测试批量计算布林带"""
        indicators = [
            {'type': 'bollinger', 'column': 'close', 'name': 'bb'},
        ]
        
        result = calculator.calculate_batch(sample_df, indicators)
        
        assert 'bb_upper' in result.columns
        assert 'bb_middle' in result.columns
        assert 'bb_lower' in result.columns
    
    def test_calculate_batch_unknown_type(self, calculator, sample_df):
        """测试未知指标类型"""
        indicators = [
            {'type': 'unknown', 'column': 'close', 'name': 'unknown'},
        ]
        
        result = calculator.calculate_batch(sample_df, indicators)
        
        assert 'unknown' not in result.columns
